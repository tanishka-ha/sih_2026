"""
Role 1 Integration: OCR Adapter
===============================
Provides a stable interface for OCR extraction.
Currently implements a realistic MOCK.

TEAM INTEGRATION NOTE:
When Role 1 delivers their OCR & field extraction module, replace the contents
of `_execute_role_1_ocr()` with calls to their actual model or library.
Do NOT change the signature of `run_ocr_on_document()`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from models.schemas import DocumentContext, OcrResult, StageStatus

logger = logging.getLogger("ocr_adapter")


# =====================================================================
# ROLE 1 MOCK IMPLEMENTATION (REPLACE WHEN ROLE 1 CODE IS DELIVERED)
# =====================================================================

def _execute_role_1_ocr(document: DocumentContext) -> Dict[str, Any]:
    """Internal implementation of Role 1 OCR extraction.

    Currently returns realistic simulated OCR fields based on document filename heuristics.
    """
    filename_lower = document.original_filename.lower()

    # Heuristic detection for realistic mock data
    if "income" in filename_lower:
        return {
            "status": StageStatus.SUCCESS,
            "doc_type": "income_certificate",
            "fields": {
                "name": "Priya Sharma",
                "income_amount": "50000",
                "issue_date": "2024-03-15",
                "certificate_number": "INC-2024-8891",
                "father_name": "Rajesh Sharma",
            },
            "confidence": 0.94,
        }

    if "marksheet" in filename_lower or "grade" in filename_lower or "score" in filename_lower:
        return {
            "status": StageStatus.SUCCESS,
            "doc_type": "academic_marksheet",
            "fields": {
                "name": "Priya Sharma",
                "roll_number": "2024-MS-4412",
                "percentage": "88.5",
                "institution": "National Institute of Technology",
                "graduation_year": "2024",
            },
            "confidence": 0.96,
        }

    if "category" in filename_lower or "caste" in filename_lower or "community" in filename_lower:
        return {
            "status": StageStatus.SUCCESS,
            "doc_type": "category_certificate",
            "fields": {
                "name": "Priya Sharma",
                "category": "OBC-NCL",
                "issuing_authority": "District Magistrate Office",
                "valid_until": "2026-12-31",
            },
            "confidence": 0.92,
        }

    # Default general document mock
    return {
        "status": StageStatus.SUCCESS,
        "doc_type": "identity_or_supporting_doc",
        "fields": {
            "name": "Priya Sharma",
            "document_title": document.original_filename,
            "page_count_extracted": len(document.image_paths),
        },
        "confidence": 0.89,
    }


# =====================================================================
# PUBLIC STABLE INTERFACE
# =====================================================================

def run_ocr_on_document(document: DocumentContext) -> OcrResult:
    """Execute OCR and information extraction on a standardized document.

    Args:
        document: DocumentContext containing document ID, metadata, and normalized PNG image paths.

    Returns:
        OcrResult with status, detected document type, extracted fields, and confidence.
    """
    logger.info(f"Running OCR on document: {document.document_id} ({document.original_filename})")

    # Testing hook: allow simulating OCR failure via filename convention
    if "ocr_fail" in document.original_filename.lower():
        logger.warning(f"Simulating OCR failure for document {document.document_id}")
        return OcrResult(
            status=StageStatus.FAILED,
            doc_type=None,
            fields={},
            confidence=0.0,
            error="OCR text extraction model timed out or failed to parse characters.",
        )

    try:
        raw_result = _execute_role_1_ocr(document)
        return OcrResult(
            status=raw_result["status"],
            doc_type=raw_result.get("doc_type"),
            fields=raw_result.get("fields", {}),
            confidence=raw_result.get("confidence", 0.0),
            error=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in OCR extraction for {document.document_id}: {e}")
        return OcrResult(
            status=StageStatus.FAILED,
            doc_type=None,
            fields={},
            confidence=0.0,
            error=f"OCR execution error: {str(e)}",
        )
