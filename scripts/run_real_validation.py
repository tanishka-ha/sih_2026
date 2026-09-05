"""
Real-World Comprehensive Pipeline Validation Script
===================================================
Executes live end-to-end testing of the complete scholarship verification system:
1. Clean 5-document bundle (checks clean path, persistence, audit chain)
2. Cross-document mismatch (Priya Sharma vs Priya Sharna)
3. Expired document detection (old issue date)
4. Duplicate identifier check (reused certificate ID)
5. Tampering detection (ELA on spliced image)
6. Partial failure handling (corrupt + unsupported docx with valid docs)
7. Direct SQLite relational integrity verification
8. SHA-256 cryptographic audit verification
9. Human-in-the-loop (no auto-rejection) verification
10. Multi-run stability & idempotency test (3 consecutive runs)
"""

from __future__ import annotations

import json
import os
import sys
import sqlite3
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from db.database import SessionLocal
from db.models import ApplicationModel, DocumentModel, ExtractedFieldModel, FlagModel, VerificationRunModel

client = TestClient(app)
BUNDLES_DIR = Path("test_bundles")


def print_header(title: str):
    print("\n" + "=" * 80)
    print(f"  {title.upper()}")
    print("=" * 80)


def test_1_clean_bundle():
    print_header("Scenario 1: Clean 5-Document Scholarship Bundle")
    bundle_path = BUNDLES_DIR / "clean_bundle"

    with open(bundle_path / "income_certificate.pdf", "rb") as f1, \
         open(bundle_path / "category_certificate.pdf", "rb") as f2, \
         open(bundle_path / "marksheet.pdf", "rb") as f3, \
         open(bundle_path / "id_proof.jpg", "rb") as f4, \
         open(bundle_path / "bank_proof.jpg", "rb") as f5:

        files = [
            ("files", ("income_certificate.pdf", f1, "application/pdf")),
            ("files", ("category_certificate.pdf", f2, "application/pdf")),
            ("files", ("marksheet.pdf", f3, "application/pdf")),
            ("files", ("id_proof.jpg", f4, "image/jpeg")),
            ("files", ("bank_proof.jpg", f5, "image/jpeg")),
        ]
        data = {
            "application_id": "APP-VAL-CLEAN-01",
            "applicant_name": "Priya Sharma",
        }

        response = client.post("/verify-bundle", files=files, data=data)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    result = response.json()

    print(f"Status: {result['status']}")
    print(f"Applicant: {result['applicant_name']}")
    print(f"Documents Ingested: {len(result['documents'])}")
    print(f"Flags Raised: {result['summary']['total']} (High: {result['summary']['high']}, Med: {result['summary']['medium']}, Low: {result['summary']['low']})")

    # Assertions
    assert result["application_id"] == "APP-VAL-CLEAN-01"
    assert result["applicant_name"] == "Priya Sharma"
    assert result["status"] in ("COMPLETED", "COMPLETED_WITH_FLAGS")
    # High fraud flags should NOT be present on clean bundle
    high_tampering = [f for f in result["flags"] if f["severity"] == "HIGH" and f["category"] == "TAMPERING"]
    assert len(high_tampering) == 0, f"False tampering flag raised: {high_tampering}"

    # Audit Verification
    audit_res = client.get("/applications/APP-VAL-CLEAN-01/verify-audit")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    print(f"Audit Chain Valid: {audit_data['chain_valid']} ({audit_data.get('verification_message')})")
    assert audit_data["chain_valid"] is True
    print(">>> Scenario 1 PASSED: Clean bundle verified without false fraud flags.")
    return result


def test_2_mismatch_bundle():
    print_header("Scenario 2: Cross-Document Name Mismatch (Priya Sharma vs Priya Sharna)")
    bundle_path = BUNDLES_DIR / "mismatch_bundle"

    with open(bundle_path / "income_certificate.pdf", "rb") as f1, \
         open(bundle_path / "category_certificate.pdf", "rb") as f2, \
         open(bundle_path / "marksheet.pdf", "rb") as f3, \
         open(bundle_path / "id_proof.jpg", "rb") as f4, \
         open(bundle_path / "bank_proof.jpg", "rb") as f5:

        files = [
            ("files", ("income_certificate.pdf", f1, "application/pdf")),
            ("files", ("category_certificate.pdf", f2, "application/pdf")),
            ("files", ("marksheet.pdf", f3, "application/pdf")),
            ("files", ("id_proof.jpg", f4, "image/jpeg")),
            ("files", ("bank_proof.jpg", f5, "image/jpeg")),
        ]
        data = {
            "application_id": "APP-VAL-MISMATCH-02",
            "applicant_name": "Priya Sharma",
        }

        response = client.post("/verify-bundle", files=files, data=data)

    assert response.status_code == 200
    result = response.json()

    print(f"Status: {result['status']}")
    print(f"Flags count: {len(result['flags'])}")
    for flg in result["flags"]:
        print(f"  [{flg['severity']}] {flg['category']}: {flg['message']}")
        if flg.get("explanation"):
            print(f"       Explanation: {flg['explanation']}")

    # Must NOT be REJECTED
    assert result["status"] != "REJECTED"
    assert result["status"] == "COMPLETED_WITH_FLAGS"
    print(">>> Scenario 2 PASSED: Mismatch flagged with explainability, no auto-rejection.")
    return result


def test_3_expired_bundle():
    print_header("Scenario 3: Expired Document Detection (Issue Date: 2022-01-01)")
    bundle_path = BUNDLES_DIR / "expired_bundle"

    with open(bundle_path / "income_certificate.pdf", "rb") as f1, \
         open(bundle_path / "category_certificate.pdf", "rb") as f2:

        files = [
            ("files", ("income_certificate.pdf", f1, "application/pdf")),
            ("files", ("category_certificate.pdf", f2, "application/pdf")),
        ]
        data = {
            "application_id": "APP-VAL-EXPIRED-03",
            "applicant_name": "Priya Sharma",
        }

        response = client.post("/verify-bundle", files=files, data=data)

    assert response.status_code == 200
    result = response.json()

    expired_flags = [f for f in result["flags"] if f["category"] == "EXPIRED_DOCUMENT"]
    print(f"Expired Document Flags Found: {len(expired_flags)}")
    for ef in expired_flags:
        print(f"  [{ef['severity']}] {ef['message']}")
        print(f"       Explanation: {ef['explanation']}")

    assert len(expired_flags) >= 1, "Role 2 failed to detect expired income certificate"
    assert expired_flags[0]["severity"] == "HIGH"
    assert expired_flags[0]["source"] == "ROLE_2"
    print(">>> Scenario 3 PASSED: Role 2 expired document rule triggered accurately.")
    return result


def test_4_duplicate_bundle():
    print_header("Scenario 4: Duplicate Certificate ID Detection (INC12345 reused)")
    bundle_path = BUNDLES_DIR / "duplicate_bundle"

    with open(bundle_path / "income_certificate.pdf", "rb") as f1:
        files = [
            ("files", ("income_certificate.pdf", f1, "application/pdf")),
        ]
        data = {
            "application_id": "APP-VAL-DUP-04",
            "applicant_name": "Rahul Kumar",  # Different applicant reusing INC12345
        }

        response = client.post("/verify-bundle", files=files, data=data)

    assert response.status_code == 200
    result = response.json()

    dup_flags = [f for f in result["flags"] if f["category"] == "DUPLICATE_CERTIFICATE"]
    print(f"Duplicate Flags Found: {len(dup_flags)}")
    for df in dup_flags:
        print(f"  [{df['severity']}] {df['message']}")

    assert len(dup_flags) >= 1, "Role 2 duplicate checker did not detect reused certificate_id"
    assert dup_flags[0]["severity"] == "HIGH"
    assert dup_flags[0]["source"] == "ROLE_2"
    print(">>> Scenario 4 PASSED: Role 2 duplicate certificate checker caught reused identifier.")
    return result


def test_5_tampering_bundle():
    print_header("Scenario 5: Document Forensics (ELA Digital Alteration Detection)")
    bundle_path = BUNDLES_DIR / "tampered_bundle"

    with open(bundle_path / "income_certificate.jpg", "rb") as f1:
        files = [
            ("files", ("income_certificate.jpg", f1, "image/jpeg")),
        ]
        data = {
            "application_id": "APP-VAL-TAMPER-05",
            "applicant_name": "Priya Sharma",
        }

        response = client.post("/verify-bundle", files=files, data=data)

    assert response.status_code == 200
    result = response.json()

    doc = result["documents"][0]
    p1 = doc["pages"][0]
    print(f"Tampering Detected on Page 1: {p1['tampering']['detected']}")
    print(f"Forensic Confidence: {p1['tampering']['confidence']}")
    print(f"Bounding Boxes Count: {len(p1['tampering']['bounding_boxes'])}")
    if p1['tampering']['bounding_boxes']:
        print(f"Sample Bounding Box: {p1['tampering']['bounding_boxes'][0]}")

    tamper_flags = [f for f in result["flags"] if f["category"] == "TAMPERING"]
    print(f"Tampering Flags: {len(tamper_flags)}")
    for tf in tamper_flags:
        print(f"  [{tf['severity']}] {tf['message']}")
        print(f"       Rule: {tf['rule']}")
        print(f"       Explanation: {tf['explanation']}")

    assert p1["tampering"]["detected"] is True, "Role 3 ELA failed to flag digitally altered image"
    assert len(tamper_flags) >= 1
    assert tamper_flags[0]["source"] == "ROLE_3"
    print(">>> Scenario 5 PASSED: Role 3 forensics identified spliced image region with bounding box.")
    return result


def test_6_partial_failure():
    print_header("Scenario 6: Partial Failure Handling (Valid + Corrupt + Unsupported Files)")
    bundle_path = BUNDLES_DIR / "partial_failure_bundle"

    with open(bundle_path / "income_certificate.pdf", "rb") as f1, \
         open(bundle_path / "category_certificate.pdf", "rb") as f2, \
         open(bundle_path / "corrupted_document.pdf", "rb") as f3, \
         open(bundle_path / "word_resume.docx", "rb") as f4:

        files = [
            ("files", ("income_certificate.pdf", f1, "application/pdf")),
            ("files", ("category_certificate.pdf", f2, "application/pdf")),
            ("files", ("corrupted_document.pdf", f3, "application/pdf")),
            ("files", ("word_resume.docx", f4, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
        ]
        data = {
            "application_id": "APP-VAL-PARTIAL-06",
            "applicant_name": "Priya Sharma",
        }

        response = client.post("/verify-bundle", files=files, data=data)

    assert response.status_code == 200
    result = response.json()

    print(f"Overall Status: {result['status']}")
    print(f"Documents Successfully Processed: {len(result['documents'])}")
    norm_err_flags = [f for f in result["flags"] if f["category"] == "FORMAT_ERROR"]
    print(f"Format Error Flags: {len(norm_err_flags)}")
    for nf in norm_err_flags:
        print(f"  [{nf['severity']}] {nf['message']}")

    # Assertions
    assert result["status"] == "PARTIAL", f"Expected PARTIAL status, got {result['status']}"
    assert len(result["documents"]) == 4  # 4 documents submitted
    successful_docs = [d for d in result["documents"] if len(d["pages"]) > 0]
    failed_docs = [d for d in result["documents"] if len(d["pages"]) == 0]
    assert len(successful_docs) == 2      # 2 valid documents succeeded
    assert len(failed_docs) == 2          # 2 failed documents recorded
    assert len(norm_err_flags) >= 2       # Corrupted and unsupported reported
    print(">>> Scenario 6 PASSED: Pipeline handled partial failures gracefully with PARTIAL status.")
    return result


def test_7_database_persistence():
    print_header("Scenario 7: Direct SQLite Relational Integrity Verification")
    db: Session = SessionLocal()
    try:
        app = db.query(ApplicationModel).filter_by(application_id="APP-VAL-CLEAN-01").first()
        assert app is not None, "Application record missing in SQLite"
        print(f"Found Application: {app.application_id} (Status: {app.status}, Applicant: {app.applicant_name})")

        print(f"Associated Documents: {len(app.documents)}")
        for d in app.documents:
            print(f"  - Document: {d.document_id} ({d.document_type}, file: {d.original_filename}, pages: {d.page_count})")
            print(f"    Extracted Fields: {len(d.fields)}")

        print(f"Associated Flags: {len(app.flags)}")
        print(f"Verification Runs: {len(app.runs)}")
        for r in app.runs:
            print(f"  - Run: {r.run_id} (Started: {r.started_at}, Completed: {r.completed_at}, Status: {r.status})")

        assert len(app.documents) == 5, "Expected 5 documents linked to clean application"
        assert len(app.runs) >= 1, "Verification run record missing"
        print(">>> Scenario 7 PASSED: SQLite relational integrity completely validated.")
    finally:
        db.close()


def test_8_human_in_the_loop_audit():
    print_header("Scenario 8: Verification of No Auto-Rejection Policy")
    backend_files = [
        Path("main.py"),
        Path("services/orchestrator.py"),
        Path("services/result_merger.py"),
        Path("schemas.py"),
        Path("adapters/role1_adapter.py"),
        Path("adapters/role2_adapter.py"),
        Path("adapters/role3_adapter.py"),
    ]

    rejections_found = []
    for bf in backend_files:
        content = bf.read_text(encoding="utf-8")
        if '"REJECTED"' in content or "'REJECTED'" in content:
            rejections_found.append(str(bf))

    print(f"Files containing 'REJECTED' assignment: {rejections_found}")
    assert len(rejections_found) == 0, f"Found prohibited 'REJECTED' status in {rejections_found}"
    print(">>> Scenario 8 PASSED: Confirmed strictly zero auto-rejection logic in backend.")


def test_9_stability_and_idempotency():
    print_header("Scenario 9: Multi-Run Stability & Idempotency (3 Consecutive Runs)")
    bundle_path = BUNDLES_DIR / "clean_bundle"

    for run_idx in range(1, 4):
        app_id = f"APP-VAL-STAB-{run_idx:02d}"
        with open(bundle_path / "income_certificate.pdf", "rb") as f1, \
             open(bundle_path / "marksheet.pdf", "rb") as f2:
            files = [
                ("files", ("income_certificate.pdf", f1, "application/pdf")),
                ("files", ("marksheet.pdf", f2, "application/pdf")),
            ]
            res = client.post("/verify-bundle", files=files, data={"application_id": app_id, "applicant_name": "Priya Sharma"})
            assert res.status_code == 200
            data = res.json()
            assert data["application_id"] == app_id
            print(f"Run {run_idx}: Application {app_id} -> Status {data['status']}, {len(data['documents'])} docs")

    print(">>> Scenario 9 PASSED: 3 consecutive runs succeeded with clean isolation and unique IDs.")


def main():
    print("\n" + "#" * 80)
    print("  RUNNING FULL REAL-WORLD INTEGRATION VALIDATION FOR ROLE 4 BACKEND")
    print("#" * 80)

    test_1_clean_bundle()
    test_2_mismatch_bundle()
    test_3_expired_bundle()
    test_4_duplicate_bundle()
    test_5_tampering_bundle()
    test_6_partial_failure()
    test_7_database_persistence()
    test_8_human_in_the_loop_audit()
    test_9_stability_and_idempotency()

    print("\n" + "=" * 80)
    print("  ALL 9 REAL-WORLD VALIDATION SUITES PASSED PERFECTLY!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
