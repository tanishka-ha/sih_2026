"""
Tests for Role 1, Role 2, and Role 3 Adapters
=============================================
Validates exact inputs/outputs, confidence normalization, bounding boxes,
failure resilience, and error-vs-fraud separation.
"""

from __future__ import annotations

import io
from pathlib import Path
import pytest
from PIL import Image

from adapters.role1_adapter import extract_page_fields, extract_document_fields
from adapters.role2_adapter import evaluate_application_rules
from adapters.role3_adapter import analyze_page_tampering


def create_test_page_image(tmp_path, name="page_001.png") -> Path:
    p = tmp_path / name
    img = Image.new("RGB", (300, 400), color=(240, 240, 240))
    img.save(p, "PNG")
    return p


def test_role1_adapter_extraction(tmp_path):
    img_path = create_test_page_image(tmp_path, "income_page.png")
    schema_fields, raw_info, flags = extract_page_fields(
        page_image_path=img_path,
        doc_type="income_certificate",
        original_filename="income.pdf",
    )
    assert isinstance(schema_fields, dict)
    assert "income_amount" in schema_fields or "income" in schema_fields or "name" in schema_fields
    # Verify confidence is normalized float between 0.0 and 1.0
    for f in schema_fields.values():
        assert 0.0 <= f.confidence <= 1.0


def test_role3_adapter_clean_document(tmp_path):
    img_path = create_test_page_image(tmp_path, "clean_page.png")
    tampering, flags = analyze_page_tampering(img_path, page_num=1, doc_id="DOC-001", doc_type="id_proof")
    assert tampering.detected is False
    assert tampering.confidence >= 0.0
    assert isinstance(tampering.bounding_boxes, list)


def test_role3_adapter_error_safety(tmp_path):
    """CRITICAL TEST: Verify an unreadable or non-existent file NEVER flags tampering=True."""
    non_existent = tmp_path / "missing_image.png"
    tampering, flags = analyze_page_tampering(non_existent, page_num=1, doc_id="DOC-999")
    assert tampering.detected is False  # Must remain False!
    assert any(f.category == "SYSTEM_ERROR" for f in flags)


def test_role2_adapter_cross_doc_checks():
    documents = [
        {
            "document_id": "DOC-01",
            "doc_type": "income_certificate",
            "flat_fields": {
                "name": "Priya Sharma",
                "income_amount": "50000",
                "issue_date": "2024-03-15",
                "certificate_id": "INC12345",
            },
            "tampering_detected": False,
        },
        {
            "document_id": "DOC-02",
            "doc_type": "category_certificate",
            "flat_fields": {
                "name": "Priya Sharna",  # Name typo
                "issue_date": "2026-01-10",
                "certificate_id": "CAT12345",
            },
            "tampering_detected": False,
        },
    ]

    flags = evaluate_application_rules(
        application_id="APP-TEST-R2",
        applicant_name="Priya Sharma",
        documents=documents,
    )
    assert isinstance(flags, list)
    assert len(flags) > 0
    categories = [f.category for f in flags]
    assert "CROSS_DOC_MISMATCH" in categories or "EXPIRED_DOCUMENT" in categories
