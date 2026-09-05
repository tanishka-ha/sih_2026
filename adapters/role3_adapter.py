"""
Role 3 Adapter: Forensics & Tampering Analysis Integration
==========================================================
Integrates Role 3 Error Level Analysis (ELA) and EXIF metadata inspection.
Detects digital manipulations, extracts bounding boxes, and strictly enforces
that analysis errors NEVER produce false-positive tampering verdicts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from modules.role3_forensics.analyzer import analyze_document_forensics
from schemas import CanonicalFlag, TamperingInfo

logger = logging.getLogger("role3_adapter")


def analyze_page_tampering(
    page_image_path: str | Path,
    page_num: int = 1,
    doc_id: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> Tuple[TamperingInfo, List[CanonicalFlag]]:
    """Analyze a single normalized page image for pixel and metadata tampering using Role 3.

    Args:
        page_image_path: Path to the normalized PNG image.
        page_num: Page index (1-based).
        doc_id: Canonical document ID.
        doc_type: Canonical document type.

    Returns:
        Tuple of:
        - TamperingInfo object (for frontend document page model)
        - List of CanonicalFlag items
    """
    flags: List[CanonicalFlag] = []
    page_path = Path(page_image_path)

    if not page_path.exists():
        logger.warning(f"Forensics target image does not exist: {page_path}")
        return (
            TamperingInfo(detected=False, confidence=0.0, bounding_boxes=[]),
            [
                CanonicalFlag(
                    flag_id=f"FLAG-FOR-MISSING-P{page_num}",
                    severity="MEDIUM",
                    category="SYSTEM_ERROR",
                    message="Forensics analysis skipped: page image file was not found.",
                    confidence=1.0,
                    document_id=doc_id,
                    document_type=doc_type,
                    page=page_num,
                    source="ROLE_3",
                    explanation="Underlying page rendering file could not be accessed.",
                )
            ],
        )

    try:
        logger.info(f"Calling real Role 3 Forensics on page {page_num}: {page_path.name}")
        raw_result = analyze_document_forensics(
            str(page_path),
            ela_quality=90,
            ela_scale=15,
            ela_threshold=40,
            min_area=150,
            save_visualization=False,
        )

        tampering_detected = bool(raw_result.get("tampering_detected", False))
        confidence = float(raw_result.get("confidence", 0.0))
        bounding_boxes = raw_result.get("bounding_boxes", [])
        severity_str = str(raw_result.get("severity", "none")).upper()
        exif_flags = raw_result.get("exif_flags", [])

        # Construct page-level model
        tampering_info = TamperingInfo(
            detected=tampering_detected,
            confidence=round(confidence, 2),
            bounding_boxes=bounding_boxes,
        )

        # Flag 1: Visual pixel alterations (ELA)
        if tampering_detected and bounding_boxes:
            if severity_str in ("HIGH", "CRITICAL") and confidence >= 0.50:
                sev = "HIGH"
            elif severity_str in ("HIGH", "CRITICAL", "MEDIUM") and confidence >= 0.20:
                sev = "MEDIUM"
            else:
                sev = "LOW"
            flags.append(
                CanonicalFlag(
                    flag_id=f"FLAG-TAMPER-{doc_id or 'DOC'}-P{page_num}",
                    severity=sev,
                    category="TAMPERING",
                    message=(
                        f"Possible image alteration detected in {doc_type or 'document'} "
                        f"(page {page_num}). {len(bounding_boxes)} anomalous region(s) identified."
                    ),
                    confidence=round(confidence, 2),
                    document_id=doc_id,
                    document_type=doc_type,
                    page=page_num,
                    bounding_box=bounding_boxes[0] if bounding_boxes else None,
                    source="ROLE_3",
                    rule="Error Level Analysis (ELA) Contour Discrepancy",
                    explanation=(
                        f"Compression variance indicates digital modifications in "
                        f"pixel regions: {bounding_boxes[:3]}."
                    ),
                )
            )

        # Flag 2: EXIF Digital editing software detection
        if exif_flags:
            for i, ef in enumerate(exif_flags, start=1):
                flags.append(
                    CanonicalFlag(
                        flag_id=f"FLAG-EXIF-{doc_id or 'DOC'}-P{page_num}-{i}",
                        severity="MEDIUM",
                        category="TAMPERING",
                        message=f"Suspicious editing software signature detected: {ef.get('reason', 'Edited image')}.",
                        confidence=0.85,
                        document_id=doc_id,
                        document_type=doc_type,
                        page=page_num,
                        source="ROLE_3",
                        rule="EXIF Header Signature Match",
                        explanation=f"Tag '{ef.get('tag')}' contains value '{ef.get('value')}'.",
                    )
                )

        return tampering_info, flags

    except Exception as e:
        # CRITICAL SAFETY RULE: A processing error is NEVER fraud
        logger.exception(f"Unexpected error in Role 3 forensics for {page_path}: {e}")
        return (
            TamperingInfo(detected=False, confidence=0.0, bounding_boxes=[]),
            [
                CanonicalFlag(
                    flag_id=f"FLAG-FOR-ERR-{doc_id or 'DOC'}-P{page_num}",
                    severity="LOW",
                    category="SYSTEM_ERROR",
                    message=f"Forensics analysis unavailable for page {page_num}: {str(e)}",
                    confidence=1.0,
                    document_id=doc_id,
                    document_type=doc_type,
                    page=page_num,
                    source="ROLE_3",
                    explanation="The forensics module encountered an internal error during ELA processing.",
                )
            ],
        )
