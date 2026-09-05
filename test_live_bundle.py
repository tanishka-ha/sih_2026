"""
Live Verification Script
========================
Tests POST /submit-bundle using the real 'Sample.pdf' file present in the directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

def main():
    sample_pdf = Path("Sample.pdf")
    if not sample_pdf.exists():
        print("Sample.pdf not found.")
        return

    print("Submitting real 'Sample.pdf' to POST /verify-bundle...")
    with open(sample_pdf, "rb") as f:
        files = [
            ("files", ("Sample.pdf", f, "application/pdf")),
        ]
        data = {
            "application_id": "APP-HACKATHON-DEMO-2026",
            "applicant_name": "Priya Sharma",
        }
        response = client.post("/verify-bundle", files=files, data=data)

    print(f"\nResponse HTTP Status: {response.status_code}")
    result = response.json()
    print("\nMaster JSON Response:")
    print(json.dumps(result, indent=2))

    assert response.status_code == 200
    assert result["status"] in ["COMPLETED", "COMPLETED_WITH_FLAGS"]
    assert result["application_id"] == "APP-HACKATHON-DEMO-2026"
    assert len(result["documents"]) == 1
    doc = result["documents"][0]
    assert doc["original_filename"] == "Sample.pdf"
    assert len(doc["pages"]) >= 1
    assert "summary" in result
    print("\nSUCCESS: Real document pipeline executed perfectly end-to-end!")

if __name__ == "__main__":
    main()
