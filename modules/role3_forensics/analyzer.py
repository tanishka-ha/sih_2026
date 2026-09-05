"""
Document Forensics Analyzer — Main Orchestrator
==================================================
Combines EXIF header analysis and Error Level Analysis (ELA) into a
unified forensics pipeline. Exposes the ``analyze_document_forensics()``
function that Role 4 (Backend Orchestrator) calls.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Union
import cv2
import numpy as np

try:
    from .models import (
        BoundingBox,
        ELARegion,
        EXIFFlag,
        ForensicsResult,
        SeverityLevel,
    )
    from .exif_analysis import analyze_exif
    from .ela_analysis import (
        compute_ela_map,
        detect_ela_regions,
        save_ela_visualization,
    )
except ImportError:
    from models import (
        BoundingBox,
        ELARegion,
        EXIFFlag,
        ForensicsResult,
        SeverityLevel,
    )
    from exif_analysis import analyze_exif
    from ela_analysis import (
        compute_ela_map,
        detect_ela_regions,
        save_ela_visualization,
    )

logger = logging.getLogger(__name__)


class DocumentForensicsAnalyzer:
    """High-level analyzer combining EXIF and ELA forensics."""

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
        """Run the full forensics pipeline on a single document image."""
        start_time = time.time()
        image_path = Path(image_path)
        result = ForensicsResult()

        logger.info("═" * 60)
        logger.info("Starting forensics analysis: %s", image_path.name)
        logger.info("═" * 60)

        # Step 1: EXIF Header Analysis
        exif_flags = analyze_exif(image_path)
        result.exif_flags = exif_flags
        if exif_flags:
            logger.warning("  Found %d suspicious EXIF entries", len(exif_flags))

        # Step 2: Error Level Analysis (ELA)
        try:
            original, ela_map = compute_ela_map(
                image_path,
                quality=self.ela_quality,
                scale=self.ela_scale,
            )
        except (ValueError, RuntimeError) as exc:
            logger.error("  ELA computation failed: %s", exc)
            result.analysis_details["ela_error"] = str(exc)
            return self._finalize_result(result, start_time, image_path)

        # Step 3: Contour Detection & Bounding Boxes
        ela_regions = detect_ela_regions(
            ela_map,
            threshold=self.ela_threshold,
            min_area=self.min_area,
            dilation_kernel=self.dilation_kernel,
            dilation_iters=self.dilation_iters,
        )
        result.ela_regions = ela_regions
        result.bounding_boxes = [r.bounding_box.to_list() for r in ela_regions]

        # Step 4: Confidence Scoring
        h, w = original.shape[:2]
        result.document_dimensions = [w, h]
        total_pixels = w * h
        tampered_pixels = sum(r.area for r in ela_regions)
        result.tamper_pixel_ratio = round(tampered_pixels / total_pixels, 6) if total_pixels > 0 else 0.0

        result.confidence = self._compute_confidence(
            exif_flags, ela_regions, result.tamper_pixel_ratio, total_pixels
        )

        # Step 5: Severity Classification
        result.severity = self._classify_severity(
            exif_flags, ela_regions, result.confidence
        )
        result.tampering_detected = result.severity != SeverityLevel.NONE

        # Optional Visualization
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
        confidence = 0.0
        if exif_flags:
            exif_weight = min(len(exif_flags) * 0.15, 0.30)
            confidence += exif_weight

        if ela_regions:
            max_mean_error = max(r.mean_error for r in ela_regions)
            error_score = min(max_mean_error / 255.0, 1.0) * 0.40
            confidence += error_score

        if tamper_ratio > 0:
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
        return result

    def analyze_batch(
        self,
        image_paths: List[str | Path],
        visualization_dir: Optional[str | Path] = None,
    ) -> Dict[str, ForensicsResult]:
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
    """Analyze a document image for tampering — Role 4 API entry point."""
    analyzer = DocumentForensicsAnalyzer(
        ela_quality=ela_quality,
        ela_scale=ela_scale,
        ela_threshold=ela_threshold,
        min_area=min_area,
        save_visualizations=save_visualization,
    )
    result = analyzer.analyze(image_path, visualization_dir)
    return result.to_dict()
