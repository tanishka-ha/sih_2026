"""
Document Forensics Analyzer — Main Orchestrator
==================================================
Combines EXIF header analysis and Error Level Analysis (ELA) into a
unified forensics pipeline. Exposes the ``analyze_document_forensics()``
function that Role 4 (Backend Orchestrator) calls, returning structured
results consumed by both the backend and Role 5 (Frontend Dashboard).
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Union

import cv2
import numpy as np

from forensics.models import (
    BoundingBox,
    ELARegion,
    EXIFFlag,
    ForensicsResult,
    SeverityLevel,
)
from forensics.exif_analysis import analyze_exif
from forensics.ela_analysis import (
    compute_ela_map,
    detect_ela_regions,
    save_ela_visualization,
)

logger = logging.getLogger(__name__)


class DocumentForensicsAnalyzer:
    """High-level analyzer combining EXIF and ELA forensics.

    This class is the primary integration point for the forensics pipeline.
    It is designed to be instantiated once and reused across multiple
    document analyses.

    Args:
        ela_quality: JPEG re-compression quality for ELA (0-100).
        ela_scale: Error amplification scale factor.
        ela_threshold: Binary threshold for ELA anomaly detection.
        min_area: Minimum contour area to suppress ambient scan noise.
        dilation_kernel: Morphological dilation kernel size.
        dilation_iters: Number of dilation iterations.
        save_visualizations: If True, save annotated ELA visualization
                             images alongside the analysis results.
    """

    def __init__(
        self,
        ela_quality: int = 90,
        ela_scale: int = 15,
        ela_threshold: int = 40,
        min_area: int = 150,
        dilation_kernel: int = 5,
        dilation_iters: int = 2,
        save_visualizations: bool = False,
    ):
        self.ela_quality = ela_quality
        self.ela_scale = ela_scale
        self.ela_threshold = ela_threshold
        self.min_area = min_area
        self.dilation_kernel = dilation_kernel
        self.dilation_iters = dilation_iters
        self.save_visualizations = save_visualizations

    def analyze(
        self,
        image_path: str | Path,
        visualization_dir: Optional[str | Path] = None,
    ) -> ForensicsResult:
        """Run the full forensics pipeline on a single document image.

        Pipeline Steps:
            1. EXIF analysis — flag suspicious editing software in headers.
            2. ELA analysis — detect pixel-level compression anomalies.
            3. Contour detection — generate bounding boxes over tampered zones.
            4. Confidence scoring — compute tamper pixel density ratio.
            5. Severity classification — assign severity based on evidence.

        Args:
            image_path: Path to the document image to analyze.
            visualization_dir: Optional directory to save ELA visualizations.
                               If None, uses the image's parent directory.

        Returns:
            A ForensicsResult with all detected anomalies, bounding boxes,
            severity flags, and confidence metrics.
        """
        start_time = time.time()
        image_path = Path(image_path)
        result = ForensicsResult()

        logger.info("═" * 60)
        logger.info("Starting forensics analysis: %s", image_path.name)
        logger.info("═" * 60)

        # ------------------------------------------------------------------
        # Step 1: EXIF / Digital Header Analysis
        # ------------------------------------------------------------------
        logger.info("▶ Step 1: EXIF Header Analysis")
        exif_flags = analyze_exif(image_path)
        result.exif_flags = exif_flags

        if exif_flags:
            logger.warning(
                "  ⚠ Found %d suspicious EXIF entries", len(exif_flags)
            )
            for flag in exif_flags:
                logger.warning("    • [%s] %s → %s", flag.tag, flag.value, flag.reason)

        # ------------------------------------------------------------------
        # Step 2: Error Level Analysis (ELA)
        # ------------------------------------------------------------------
        logger.info("▶ Step 2: Error Level Analysis (ELA)")
        try:
            original, ela_map = compute_ela_map(
                image_path,
                quality=self.ela_quality,
                scale=self.ela_scale,
            )
        except (ValueError, RuntimeError) as exc:
            logger.error("  ✗ ELA computation failed: %s", exc)
            result.analysis_details["ela_error"] = str(exc)
            return self._finalize_result(result, start_time, image_path)

        # ------------------------------------------------------------------
        # Step 3: Contour Detection & Bounding Box Generation
        # ------------------------------------------------------------------
        logger.info("▶ Step 3: Contour Detection & Bounding Boxes")
        ela_regions = detect_ela_regions(
            ela_map,
            threshold=self.ela_threshold,
            min_area=self.min_area,
            dilation_kernel=self.dilation_kernel,
            dilation_iters=self.dilation_iters,
        )
        result.ela_regions = ela_regions
        result.bounding_boxes = [r.bounding_box.to_list() for r in ela_regions]

        if ela_regions:
            logger.info("  Found %d anomalous regions:", len(ela_regions))
            for i, region in enumerate(ela_regions):
                bb = region.bounding_box
                logger.info(
                    "    Region %d: [x=%d, y=%d, w=%d, h=%d] "
                    "mean_error=%.1f area=%d",
                    i + 1, bb.x, bb.y, bb.w, bb.h,
                    region.mean_error, region.area,
                )

        # ------------------------------------------------------------------
        # Step 4: Confidence Scoring (Tamper Pixel Density)
        # ------------------------------------------------------------------
        logger.info("▶ Step 4: Confidence & Tamper Density Scoring")
        h, w = original.shape[:2]
        result.document_dimensions = [w, h]
        total_pixels = w * h

        tampered_pixels = sum(r.area for r in ela_regions)
        result.tamper_pixel_ratio = round(tampered_pixels / total_pixels, 6) if total_pixels > 0 else 0.0

        # Confidence: blend EXIF evidence + ELA coverage
        result.confidence = self._compute_confidence(
            exif_flags, ela_regions, result.tamper_pixel_ratio, total_pixels
        )

        logger.info(
            "  Tampered pixels: %d / %d (ratio=%.6f)",
            tampered_pixels, total_pixels, result.tamper_pixel_ratio,
        )
        logger.info("  Confidence: %.4f", result.confidence)

        # ------------------------------------------------------------------
        # Step 5: Severity Classification
        # ------------------------------------------------------------------
        logger.info("▶ Step 5: Severity Classification")
        result.severity = self._classify_severity(
            exif_flags, ela_regions, result.confidence
        )
        result.tampering_detected = result.severity != SeverityLevel.NONE

        logger.info("  Severity: %s", result.severity.value.upper())
        logger.info("  Tampering Detected: %s", result.tampering_detected)

        # ------------------------------------------------------------------
        # Optional: Save Visualization
        # ------------------------------------------------------------------
        if self.save_visualizations and ela_regions:
            vis_dir = Path(visualization_dir) if visualization_dir else image_path.parent
            vis_dir.mkdir(parents=True, exist_ok=True)
            vis_path = vis_dir / f"{image_path.stem}_ela_visualization.png"
            save_ela_visualization(original, ela_map, ela_regions, vis_path)
            result.analysis_details["visualization_path"] = str(vis_path)

        return self._finalize_result(result, start_time, image_path)

    def _compute_confidence(
        self,
        exif_flags: List[EXIFFlag],
        ela_regions: List[ELARegion],
        tamper_ratio: float,
        total_pixels: int,
    ) -> float:
        """Compute a dynamic confidence metric (0.0 - 1.0).

        The confidence score blends three signals:
            1. EXIF evidence weight (0.0 - 0.3)
            2. ELA region error intensity (0.0 - 0.4)
            3. Tamper pixel density ratio (0.0 - 0.3)

        This produces a balanced score: a document with only EXIF flags
        but no pixel anomalies scores lower than one with both signals.
        """
        confidence = 0.0

        # Signal 1: EXIF flags (max 0.30)
        if exif_flags:
            exif_weight = min(len(exif_flags) * 0.15, 0.30)
            confidence += exif_weight

        # Signal 2: ELA region error intensity (max 0.40)
        if ela_regions:
            max_mean_error = max(r.mean_error for r in ela_regions)
            # Normalize: 255 → 1.0
            error_score = min(max_mean_error / 255.0, 1.0) * 0.40
            confidence += error_score

        # Signal 3: Tamper pixel density (max 0.30)
        if tamper_ratio > 0:
            # Log-scale density to handle wide range of ratios
            import math
            density_score = min(math.log1p(tamper_ratio * 1000) / 5.0, 1.0) * 0.30
            confidence += density_score

        return round(min(confidence, 1.0), 4)

    def _classify_severity(
        self,
        exif_flags: List[EXIFFlag],
        ela_regions: List[ELARegion],
        confidence: float,
    ) -> SeverityLevel:
        """Classify overall tampering severity.

        Classification Rules:
            CRITICAL : confidence >= 0.80 and multiple ELA regions
            HIGH     : confidence >= 0.60 or 3+ ELA regions
            MEDIUM   : confidence >= 0.35 or EXIF flags + ELA regions
            LOW      : any EXIF flags only (no pixel anomalies)
            NONE     : no evidence of tampering
        """
        has_exif = len(exif_flags) > 0
        num_regions = len(ela_regions)

        if confidence >= 0.80 and num_regions >= 2:
            return SeverityLevel.CRITICAL
        elif confidence >= 0.60 or num_regions >= 3:
            return SeverityLevel.HIGH
        elif confidence >= 0.35 or (has_exif and num_regions > 0):
            return SeverityLevel.MEDIUM
        elif has_exif or num_regions > 0:
            return SeverityLevel.LOW
        else:
            return SeverityLevel.NONE

    def _finalize_result(
        self,
        result: ForensicsResult,
        start_time: float,
        image_path: Path,
    ) -> ForensicsResult:
        """Add final metadata and log summary."""
        elapsed = round(time.time() - start_time, 3)
        result.analysis_details.update({
            "source_file": str(image_path),
            "analysis_time_seconds": elapsed,
            "parameters": {
                "ela_quality": self.ela_quality,
                "ela_scale": self.ela_scale,
                "ela_threshold": self.ela_threshold,
                "min_area": self.min_area,
                "dilation_kernel": self.dilation_kernel,
                "dilation_iters": self.dilation_iters,
            },
        })

        logger.info("═" * 60)
        logger.info(
            "Analysis complete in %.3fs — tampering=%s severity=%s confidence=%.4f regions=%d",
            elapsed,
            result.tampering_detected,
            result.severity.value,
            result.confidence,
            len(result.ela_regions),
        )
        logger.info("═" * 60)

        return result

    def analyze_batch(
        self,
        image_paths: List[str | Path],
        visualization_dir: Optional[str | Path] = None,
    ) -> Dict[str, ForensicsResult]:
        """Analyze a batch of document images.

        Args:
            image_paths: List of paths to document images.
            visualization_dir: Optional directory for ELA visualizations.

        Returns:
            A dictionary mapping filename → ForensicsResult.
        """
        results = {}
        for path in image_paths:
            path = Path(path)
            try:
                result = self.analyze(path, visualization_dir)
                results[path.name] = result
            except Exception as exc:
                logger.error("Failed to analyze %s: %s", path.name, exc)
                error_result = ForensicsResult()
                error_result.analysis_details["error"] = str(exc)
                results[path.name] = error_result
        return results


# ---------------------------------------------------------------------------
# Convenience Function (API Entry Point for Role 4)
# ---------------------------------------------------------------------------

def analyze_document_forensics(
    image_path: str | Path,
    *,
    ela_quality: int = 90,
    ela_scale: int = 15,
    ela_threshold: int = 40,
    min_area: int = 150,
    save_visualization: bool = False,
    visualization_dir: Optional[str | Path] = None,
) -> dict:
    """Analyze a document image for tampering — Role 4 API entry point.

    This is the primary function exposed to the Backend Orchestrator (Role 4).
    It returns a standardized JSON-serializable dictionary.

    Args:
        image_path: Path to the high-resolution document image.
        ela_quality: JPEG re-compression quality for ELA.
        ela_scale: Error amplification scale factor.
        ela_threshold: Binary threshold for anomaly detection.
        min_area: Minimum contour area for noise suppression.
        save_visualization: Whether to save annotated ELA images.
        visualization_dir: Directory for visualization output.

    Returns:
        A dictionary with the following schema::

            {
                "tampering_detected": bool,
                "bounding_boxes": [[x, y, w, h], ...],
                "severity": "none" | "low" | "medium" | "high" | "critical",
                "confidence": float,  # 0.0 - 1.0
                "exif_flags": [...],
                "ela_regions": [...],
                "tamper_pixel_ratio": float,
                "document_dimensions": [width, height],
                "analysis_details": {...}
            }
    """
    analyzer = DocumentForensicsAnalyzer(
        ela_quality=ela_quality,
        ela_scale=ela_scale,
        ela_threshold=ela_threshold,
        min_area=min_area,
        save_visualizations=save_visualization,
    )
    result = analyzer.analyze(image_path, visualization_dir)
    return result.to_dict()
