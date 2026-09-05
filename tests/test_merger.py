"""
Tests for Result Merger Service
===============================
Validates flag deduplication, severity ranking, summary metrics, and status assignment.
"""

from schemas import CanonicalFlag, DocumentBundleResult, PageResult
from services.result_merger import merge_and_rank_results


def test_result_merger_with_flags():
    doc = DocumentBundleResult(
        document_id="DOC-01",
        doc_type="income_certificate",
        original_filename="income.pdf",
        pages=[PageResult(page_number=1, fields={}, tampering={"detected": False, "confidence": 0.0, "bounding_boxes": []})],
    )
    flags = [
        CanonicalFlag(flag_id="TEMP-1", severity="LOW", category="OCR_QUALITY", message="Low conf", source="ROLE_1"),
        CanonicalFlag(flag_id="TEMP-2", severity="HIGH", category="EXPIRED_DOCUMENT", message="Expired", source="ROLE_2"),
        CanonicalFlag(flag_id="TEMP-3", severity="MEDIUM", category="CROSS_DOC_MISMATCH", message="Diff name", source="ROLE_2"),
    ]

    res = merge_and_rank_results(
        application_id="APP-MERGE-01",
        applicant_name="Priya Sharma",
        documents=[doc],
        all_flags=flags,
    )

    assert res.status == "COMPLETED_WITH_FLAGS"
    assert res.summary.total == 3
    assert res.summary.high == 1
    assert res.summary.medium == 1
    assert res.summary.low == 1

    # Check ranking: HIGH should come first
    assert res.flags[0].severity == "HIGH"
    assert res.flags[0].flag_id == "FLAG-001"


def test_result_merger_clean_completed():
    doc = DocumentBundleResult(
        document_id="DOC-01",
        doc_type="id_proof",
        original_filename="id.png",
        pages=[PageResult(page_number=1, fields={}, tampering={"detected": False, "confidence": 0.0, "bounding_boxes": []})],
    )
    res = merge_and_rank_results(
        application_id="APP-CLEAN",
        applicant_name="Priya Sharma",
        documents=[doc],
        all_flags=[],
    )
    assert res.status == "COMPLETED"
    assert res.summary.total == 0
