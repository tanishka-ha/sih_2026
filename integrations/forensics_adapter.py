"""
Role 3 Integration: Document Forensics & Tampering Adapter
==========================================================
Provides a stable interface for image tampering and forensics analysis.
Currently implements a realistic MOCK.

CRITICAL ARCHITECTURAL RULE:
If forensics analysis fails, NEVER interpret that as "tampering detected".
A processing failure is strictly "analysis unavailable", NOT evidence of fraud.

TEAM INTEGRATION NOTE:
When Role 3 delivers their forensics analysis module (ELA, noise analysis, copy-move detection),
replace the contents of `_execute_role_3_forensics()` with calls to their actual model.
Do NOT change the signature of `run_forensics_on_document()`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from models.schemas import DocumentContext, ForensicsResult, StageStatus

logger = logging.getLogger("forensics_adapter")


# =====================================================================
# ROLE 3 MOCK IMPLEMENTATION (REPLACE WHEN ROLE 3 CODE IS DELIVERED)
# =====================================================================

def _execute_role_3_forensics(document: DocumentContext) -> Dict[str, Any]:
    """Internal implementation of Role 3 forensics analysis.

    Currently returns clean tampering analysis results.
    """
    filename_lower = document.original_filename.lower()

    # Testing hook: allow simulating a genuinely tampered document for demonstration
    if "tampered" in filename_lower:
        return {
            "status": StageStatus.SUCCESS,
            "tampering_detected": True,
            "confidence": 0.95,
            "bounding_boxes": [
                {"page": 1, "box": [120, 340, 280, 390], "label": "Digit modification in income field"}
            ],
            "metadata_flags": ["Inconsistent JPEG quantization tables detected", "Photoshop signature in EXIF"],
        }

    # Standard clean document mock
    return {
        "status": StageStatus.SUCCESS,
        "tampering_detected": False,
        "confidence": 0.98,
        "bounding_boxes": [],
        "metadata_flags": [],
    }


# =====================================================================
# PUBLIC STABLE INTERFACE
# =====================================================================

def run_forensics_on_document(document: DocumentContext) -> ForensicsResult:
    """Execute tampering and forensics analysis on a standardized document.

    Args:
        document: DocumentContext containing document ID, metadata, and normalized PNG image paths.

    Returns:
        ForensicsResult with status, tampering flag, confidence, and detected anomaly regions.
    """
    logger.info(f"Running Forensics on document: {document.document_id} ({document.original_filename})")

    # Testing hook: allow simulating forensics failure
    if "forensics_fail" in document.original_filename.lower():
        logger.warning(
            f"Simulating forensics failure for {document.document_id}. "
            "Marking analysis unavailable without flagging tampering."
        )
        return ForensicsResult(
            status=StageStatus.FAILED,
            tampering_detected=False,  # CRITICAL: Analysis failure is NOT evidence of fraud
            confidence=0.0,
            bounding_boxes=[],
            metadata_flags=[],
            error="Forensics engine analysis unavailable.",
        )

    try:
        raw_result = _execute_role_3_forensics(document)
        return ForensicsResult(
            status=raw_result["status"],
            tampering_detected=raw_result.get("tampering_detected", False),
            confidence=raw_result.get("confidence", 0.0),
            bounding_boxes=raw_result.get("bounding_boxes", []),
            metadata_flags=raw_result.get("metadata_flags", []),
            error=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in Forensics for {document.document_id}: {e}")
        # Safeguard: Even on uncaught exception, tampering_detected must remain FALSE
        return ForensicsResult(
            status=StageStatus.FAILED,
            tampering_detected=False,
            confidence=0.0,
            bounding_boxes=[],
            metadata_flags=[],
            error=f"Forensics execution error: {str(e)}",
        )
