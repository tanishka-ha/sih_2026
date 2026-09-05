# Scholarship AI Document Verification System
## Role 4: Main Backend Orchestrator & Input Normalisation Pipeline

---

## 1. Role & Architecture Overview

In this 6-person hackathon project, **Role 4 (Backend Orchestrator)** is the central backbone that receives user uploads, coordinates all AI analysis modules, and delivers unified verification results to the Clerk Dashboard (Role 5):

```
                       USER / ROLE 5 DASHBOARD
                                  │
                                  ▼ [POST /submit-bundle]
┌────────────────────────────────────────────────────────────────────────┐
│               ROLE 4: FASTAPI BACKEND ORCHESTRATOR                      │
│                                                                        │
│  1. Storage Service: Safe storage & path-traversal prevention          │
│  2. Input Normalisation: Calls existing file_converter.py               │
│     (Converts PDF, JPG, JPEG, PNG into standard RGB page_001.png ...)   │
│                                                                        │
│  3. Concurrent Stage Dispatch:                                         │
│        ┌─────────────────────────────┬─────────────────────────────┐   │
│        ▼                             ▼                             │   │
│   ROLE 1 (OCR Adapter)         ROLE 3 (Forensics Adapter)          │   │
│   OCR & Field Extraction       Tampering / ELA / Anomaly Detection │   │
│        │                             │                             │   │
│        └─────────────────────────────┴─────────────────────────────┘   │
│                                  │                                     │
│  4. Aggregation & Rules:         ▼                                     │
│     ROLE 2 (Rules Adapter): Cross-document validation & checks         │
│                                                                        │
│  5. Master JSON Builder: Traceable contract for Dashboard              │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                         MASTER JSON RESPONSE
```

---

## 2. Project Directory Structure

```
document_normalisation_pipeline/
│
├── main.py                     # FastAPI application & HTTP endpoints
├── file_converter.py           # Core file normaliser (already verified: 14/14 tests)
├── config.py                   # Central settings, paths, and size limits
├── requirements.txt            # Dependency specification
├── README.md                   # Full documentation & team integration guide
│
├── models/
│   ├── __init__.py
│   └── schemas.py              # Pydantic models & Master JSON contracts
│
├── integrations/               # Modular adapters with realistic mocks
│   ├── __init__.py
│   ├── ocr_adapter.py          # Adapter for Role 1 (OCR)
│   ├── forensics_adapter.py    # Adapter for Role 3 (Forensics)
│   └── rules_adapter.py        # Adapter for Role 2 (Cross-Check Rules)
│
├── services/
│   ├── __init__.py
│   ├── pipeline_service.py     # Main workflow orchestrator
│   └── storage_service.py      # Secure file storage & path sanitization
│
├── tests/
│   ├── __init__.py
│   ├── test_pipeline.py        # Service & adapter unit tests
│   └── test_api.py             # FastAPI HTTP endpoint tests
│
├── storage/                    # Application uploads and converted PNGs
│   └── .gitkeep
│
└── test_file_converter.py      # Standalone test suite for file_converter.py
```

---

## 3. Installation

Ensure Python 3.10+ is installed, then run:

```powershell
pip install -r requirements.txt
```

---

## 4. Running the Server

Start the FastAPI development server with automatic reload:

```powershell
uvicorn main:app --reload
```

The server starts at `http://127.0.0.1:8000`.

* **Root Status**: `http://127.0.0.1:8000/`
* **Health Check**: `http://127.0.0.1:8000/health`
* **Interactive Swagger UI**: `http://127.0.0.1:8000/docs`
* **ReDoc**: `http://127.0.0.1:8000/redoc`

---

## 5. Testing via Swagger UI (`/docs`)

1. Start the server (`uvicorn main:app --reload`).
2. Open your browser and navigate to `http://127.0.0.1:8000/docs`.
3. Expand **`POST /submit-bundle`**.
4. Click **Try it out**.
5. *(Optional)* Enter an `application_id` (e.g. `APP-2026-8891`). If left blank, the backend auto-generates one.
6. Under `files`, click **Choose Files** and select one or more documents (`PDF`, `JPG`, `PNG`).
7. Click **Execute**.
8. View the complete Master JSON response showing page conversion, extracted OCR entities, forensics status, and cross-check flags.

---

## 6. Automated Testing

Run the automated test suites from the command line:

```powershell
# Run the 19 FastAPI & Pipeline tests
python -m pytest tests -v

# Run the 14 File Normaliser tests
python test_file_converter.py

# Run live bundle verification with real Sample.pdf
python test_live_bundle.py
```

**Total Automated Tests**: 33 passing tests with 0 failures.

---

## 7. How the Existing `file_converter.py` is Connected

The existing converter is treated as completed and frozen. It is imported cleanly in `services/pipeline_service.py`:

```python
from file_converter import convert_to_images
```

Inside `process_document_bundle()`, conversion runs in FastAPI's threadpool to prevent CPU-bound image transcoding from blocking async operations:

```python
raw_conv_result = await run_in_threadpool(
    convert_to_images,
    input_path=saved_path,
    output_directory=converted_dir,
)
```

Each page is transformed into a standard 3-channel RGB PNG (`page_001.png`, `page_002.png`, ...). These image paths are packaged into a `DocumentContext` and forwarded to Role 1 and Role 3.

---

## 8. Team Integration Guide: Connecting Real Teammate Modules

To integrate your teammates' actual modules, **you only need to update the internal logic in the three adapter files**. No changes to `main.py` or `pipeline_service.py` are required!

### Connecting Role 1 (OCR & Field Extraction)
* **File**: `integrations/ocr_adapter.py`
* **Function**: `_execute_role_1_ocr(document: DocumentContext)`
* **Input Available**: `document.image_paths` (list of standard PNG page images), `document.original_filename`.
* **Required Output**: Dictionary with `status`, `doc_type`, `fields` (extracted key-values), and `confidence`.

### Connecting Role 3 (Document Forensics / Tampering)
* **File**: `integrations/forensics_adapter.py`
* **Function**: `_execute_role_3_forensics(document: DocumentContext)`
* **Input Available**: `document.image_paths`, `document.document_id`.
* **Required Output**: Dictionary with `status`, `tampering_detected` (`True`/`False`), `confidence`, `bounding_boxes`, `metadata_flags`.
* **Crucial Rule**: If analysis fails or model crashes, `status` must be `FAILED` and `tampering_detected` must be `False`. Processing errors are NOT fraud.

### Connecting Role 2 (Cross-Check Validation Rules)
* **File**: `integrations/rules_adapter.py`
* **Function**: `_execute_role_2_rules(documents: List[DocumentResult])`
* **Input Available**: Full list of `DocumentResult` objects containing OCR fields and forensic findings across all bundle documents.
* **Required Output**: List of `RuleFlag(severity, category, message, confidence)`.

---

## 9. Example Request & Response

### Request (cURL)
```bash
curl -X POST "http://127.0.0.1:8000/submit-bundle" \
  -F "application_id=APP-2026-8891" \
  -F "files=@income_certificate.pdf" \
  -F "files=@marksheet.jpg"
```

### Response (Master JSON)
```json
{
  "application_id": "APP-2026-8891",
  "status": "SUCCESS",
  "documents": [
    {
      "document_id": "DOC-A1B2C3D4",
      "original_filename": "income_certificate.pdf",
      "original_type": "pdf",
      "conversion": {
        "success": true,
        "status": "SUCCESS",
        "page_count": 1,
        "image_paths": [
          "C:\\storage\\APP-2026-8891\\converted\\a1b2c3d4_income_certificate\\page_001.png"
        ],
        "output_directory": "C:\\storage\\APP-2026-8891\\converted\\a1b2c3d4_income_certificate",
        "error": null
      },
      "ocr": {
        "status": "SUCCESS",
        "doc_type": "income_certificate",
        "fields": {
          "name": "Priya Sharma",
          "income_amount": "50000",
          "issue_date": "2024-03-15",
          "certificate_number": "INC-2024-8891"
        },
        "confidence": 0.94,
        "error": null
      },
      "forensics": {
        "status": "SUCCESS",
        "tampering_detected": false,
        "confidence": 0.98,
        "bounding_boxes": [],
        "metadata_flags": [],
        "error": null
      }
    }
  ],
  "flags": [],
  "pipeline_errors": [],
  "created_at": "2026-09-05T10:45:39.720973+00:00"
}
```

---

## 10. Error Handling & The "Error vs. Fraud" Distinction

| Scenario | Behavior | Status Returned |
|---|---|---|
| **Document corrupted / unreadable** | Document conversion fails; OCR and forensics are `SKIPPED`. Other valid documents continue. | Global: `PARTIAL_SUCCESS` |
| **OCR model timeout / failure** | `ocr.status = "FAILED"`. Forensics still executes. | Document: `ocr_status = "FAILED"` |
| **Forensics model crash** | `forensics.status = "FAILED"`, `tampering_detected = false`. **Never** marks document as tampered. | Safe fallback: Analysis Unavailable |
| **Rules engine error** | Document results preserved; error appended to `pipeline_errors`. | Global: Flags empty, error reported |
| **Tampered document detected** | `forensics.tampering_detected = true`, Rule 2 generates `TAMPERING_SUSPECTED` flag with bounding boxes. | Master JSON contains critical flag |
