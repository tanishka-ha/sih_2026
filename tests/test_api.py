"""
FastAPI HTTP Endpoint Integration Tests
========================================
Tests GET /health, POST /verify-bundle, application query, and audit trail verification.
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


def make_in_memory_pdf(text: str = "Test Certificate") -> bytes:
    doc = fitz.open()
    p = doc.new_page(width=400, height=600)
    p.insert_text((50, 50), text)
    b = doc.tobytes()
    doc.close()
    return b


def make_in_memory_jpg() -> bytes:
    img = Image.new("RGB", (200, 200), color=(180, 220, 240))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_root_endpoint():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "RUNNING"


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["database"] == "connected"


def test_verify_bundle_endpoint():
    pdf_bytes = make_in_memory_pdf("Income Certificate")
    jpg_bytes = make_in_memory_jpg()

    files = [
        ("files", ("income_certificate.pdf", pdf_bytes, "application/pdf")),
        ("files", ("marksheet.jpg", jpg_bytes, "image/jpeg")),
    ]
    data = {
        "application_id": "APP-HTTP-TEST-01",
        "applicant_name": "Priya Sharma",
    }

    res = client.post("/verify-bundle", files=files, data=data)
    assert res.status_code == 200
    payload = res.json()

    assert payload["application_id"] == "APP-HTTP-TEST-01"
    assert payload["applicant_name"] == "Priya Sharma"
    assert payload["status"] in ("COMPLETED", "COMPLETED_WITH_FLAGS")
    assert len(payload["documents"]) == 2
    assert "summary" in payload
    assert "flags" in payload

    # Test GET /applications/{id}
    app_res = client.get("/applications/APP-HTTP-TEST-01")
    assert app_res.status_code == 200
    assert app_res.json()["document_count"] == 2

    # Test GET /applications/{id}/audit-trail
    audit_res = client.get("/applications/APP-HTTP-TEST-01/audit-trail")
    assert audit_res.status_code == 200
    assert audit_res.json()["events_count"] >= 5

    # Test GET /applications/{id}/verify-audit
    verify_res = client.get("/applications/APP-HTTP-TEST-01/verify-audit")
    assert verify_res.status_code == 200
    assert verify_res.json()["chain_valid"] is True
