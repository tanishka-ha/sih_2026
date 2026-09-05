"""
End-to-End Verification Test
============================
Simulates the complete 5-document scholarship application bundle:
1. income_certificate.pdf
2. category_certificate.pdf
3. marksheet.pdf
4. id_proof.jpg
5. bank_proof.jpg

Validates full orchestration across normalisation, Role 1, Role 3, Role 2,
SQLite persistence, SHA-256 audit hashing, and Master JSON generation.
"""

from __future__ import annotations

import io
from fastapi.testclient import TestClient
from PIL import Image

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from main import app

client = TestClient(app)


def make_pdf(title: str, pages: int = 1) -> bytes:
    doc = fitz.open()
    for i in range(pages):
        p = doc.new_page(width=500, height=700)
        p.insert_text((50, 60), f"{title} - Page {i+1}")
        p.insert_text((50, 100), "Name: Priya Sharma")
        p.insert_text((50, 140), "Father: Raj Sharma")
        p.insert_text((50, 180), "Date: 2024-03-15")
    b = doc.tobytes()
    doc.close()
    return b


def make_image(title: str) -> bytes:
    img = Image.new("RGB", (350, 450), color=(245, 245, 245))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_complete_5_document_scholarship_bundle():
    # Prepare 5 documents
    income_pdf = make_pdf("Income Certificate", pages=1)
    category_pdf = make_pdf("Category Certificate", pages=1)
    marksheet_pdf = make_pdf("Academic Marksheet", pages=2)  # Multi-page test
    id_jpg = make_image("Aadhaar Card")
    bank_jpg = make_image("Bank Passbook")

    files = [
        ("files", ("income_certificate.pdf", income_pdf, "application/pdf")),
        ("files", ("category_certificate.pdf", category_pdf, "application/pdf")),
        ("files", ("marksheet.pdf", marksheet_pdf, "application/pdf")),
        ("files", ("id_proof.jpg", id_jpg, "image/jpeg")),
        ("files", ("bank_proof.jpg", bank_jpg, "image/jpeg")),
    ]
    data = {
        "application_id": "APP-2026-FINAL-BUNDLE",
        "applicant_name": "Priya Sharma",
    }

    # Execute full pipeline through POST /verify-bundle
    response = client.post("/verify-bundle", files=files, data=data)
    assert response.status_code == 200

    result = response.json()

    # 1. Assert Application-Level Contract
    assert result["application_id"] == "APP-2026-FINAL-BUNDLE"
    assert result["applicant_name"] == "Priya Sharma"
    assert result["status"] in ("COMPLETED", "COMPLETED_WITH_FLAGS")
    assert len(result["documents"]) == 5

    # 2. Assert Document-Level Traceability & Page Results
    doc_types = [d["doc_type"] for d in result["documents"]]
    assert "income_certificate" in doc_types
    assert "category_certificate" in doc_types
    assert "marksheet" in doc_types
    assert "id_proof" in doc_types
    assert "bank_proof" in doc_types

    marksheet_doc = next(d for d in result["documents"] if d["doc_type"] == "marksheet")
    assert len(marksheet_doc["pages"]) == 2  # Confirms multi-page PDF was handled correctly

    # 3. Assert Forensics & OCR on Pages
    for doc in result["documents"]:
        for page in doc["pages"]:
            assert "fields" in page
            assert "tampering" in page
            assert isinstance(page["tampering"]["detected"], bool)

    # 4. Assert Flags and Summary
    assert "flags" in result
    assert "summary" in result
    assert result["summary"]["total"] == len(result["flags"])
    assert result["summary"]["total"] >= 0

    # 5. Assert SQLite Persistence via GET /applications/{id}
    app_query = client.get("/applications/APP-2026-FINAL-BUNDLE")
    assert app_query.status_code == 200
    app_data = app_query.json()
    assert app_data["document_count"] == 5

    # 6. Assert Cryptographic Audit Trail
    audit_verify = client.get("/applications/APP-2026-FINAL-BUNDLE/verify-audit")
    assert audit_verify.status_code == 200
    assert audit_verify.json()["chain_valid"] is True
