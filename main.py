"""
FastAPI Main Application & Integration Entrypoint
=================================================
Role 4: Main Backend Orchestrator for Scholarship AI Document Verification.
Exposes /health, /verify-bundle, application queries, and audit log verification.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from audit.audit_log import AuditLogger
from config import BASE_DIR, LOG_LEVEL
from db.database import get_db, init_db
from db.models import ApplicationModel, DocumentModel, FlagModel
from schemas import MasterBundleResponse
from services.orchestrator import VerificationOrchestrator

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

# Initialize database schema
init_db()

# Initialize FastAPI application
app = FastAPI(
    title="Scholarship AI Document Verification Pipeline",
    description=(
        "Role 4 Backend Orchestrator connecting input normalisation, "
        "Role 1 (OCR), Role 3 (Forensics), and Role 2 (Validation Rules) "
        "into a single, unified verification pipeline for the Role 5 Clerk Dashboard."
    ),
    version="2.0.0",
)

# Enable CORS for Role 5 Clerk Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = VerificationOrchestrator()


# =====================================================================
# SYSTEM ENDPOINTS
# =====================================================================

@app.get("/", tags=["System"])
async def root():
    return {
        "service": "Scholarship AI Document Verification Backend",
        "role": "Role 4 - Backend Orchestrator",
        "status": "RUNNING",
        "docs_url": "/docs",
    }


@app.get("/health", tags=["System"])
async def health(db: Session = Depends(get_db)):
    """System health check verifying database and storage readiness."""
    uploads_dir = BASE_DIR / "uploads"
    storage_ok = uploads_dir.exists()
    db_ok = False
    try:
        db.execute(ApplicationModel.__table__.select().limit(1))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if (storage_ok and db_ok) else "degraded",
        "database": "connected" if db_ok else "unavailable",
        "storage_ready": storage_ok,
        "version": "2.0.0",
    }


# =====================================================================
# CORE PIPELINE ENDPOINT
# =====================================================================

@app.post(
    "/verify-bundle",
    response_model=MasterBundleResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify Scholarship Document Bundle",
    description=(
        "Ingests multiple scholarship documents (PDF, JPG, JPEG, PNG). "
        "Normalises each page into standard PNGs, executes OCR (Role 1), "
        "runs Forensics (Role 3), performs cross-document validation (Role 2), "
        "stores findings in SQLite, seals the execution in the SHA-256 audit log, "
        "and returns a unified Master JSON response for the Clerk Dashboard."
    ),
    tags=["Verification Pipeline"],
)
async def verify_bundle(
    files: List[UploadFile] = File(
        ...,
        description="List of document files belonging to the applicant bundle.",
    ),
    application_id: Optional[str] = Form(
        None,
        description="Optional custom application ID (e.g. 'APP-2026-00001'). If omitted, auto-generated.",
        examples=["APP-2026-00001"],
    ),
    applicant_name: Optional[str] = Form(
        None,
        description="Optional applicant name for cross-document consistency verification.",
        examples=["Priya Sharma"],
    ),
    db: Session = Depends(get_db),
):
    logger.info(f"POST /verify-bundle received: {len(files)} files (Application: {application_id})")

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files were uploaded in this submission bundle.",
        )

    response = await orchestrator.verify_bundle(
        files=files,
        application_id=application_id,
        applicant_name=applicant_name,
        db=db,
    )
    return response


# =====================================================================
# DASHBOARD QUERY & AUDIT ENDPOINTS
# =====================================================================

@app.get(
    "/applications/{application_id}",
    summary="Get Application Summary",
    tags=["Dashboard"],
)
async def get_application(application_id: str, db: Session = Depends(get_db)):
    """Retrieve application status, documents, and recorded flags from SQLite."""
    app_record = (
        db.query(ApplicationModel)
        .filter(ApplicationModel.application_id == application_id)
        .first()
    )
    if not app_record:
        raise HTTPException(status_code=404, detail=f"Application '{application_id}' not found.")

    docs = (
        db.query(DocumentModel)
        .filter(DocumentModel.application_id == application_id)
        .all()
    )
    flags = (
        db.query(FlagModel)
        .filter(FlagModel.application_id == application_id)
        .all()
    )

    return {
        "application_id": app_record.application_id,
        "applicant_name": app_record.applicant_name,
        "status": app_record.status,
        "created_at": app_record.created_at,
        "document_count": len(docs),
        "flag_count": len(flags),
        "flags": [
            {
                "flag_id": f.flag_id,
                "severity": f.severity,
                "category": f.category,
                "message": f.message,
                "confidence": f.confidence,
                "document_id": f.document_id,
                "source": f.source,
            }
            for f in flags
        ],
    }


@app.get(
    "/applications/{application_id}/audit-trail",
    summary="Get Audit Trail",
    tags=["Audit & Governance"],
)
async def get_audit_trail(application_id: str, db: Session = Depends(get_db)):
    """Retrieve chronological SHA-256 hash-chain audit log records for an application."""
    audit_logger = AuditLogger(db)
    trail = audit_logger.get_audit_trail(application_id)
    if not trail:
        raise HTTPException(status_code=404, detail=f"No audit trail for '{application_id}'.")
    return {
        "application_id": application_id,
        "events_count": len(trail),
        "audit_trail": trail,
    }


@app.get(
    "/applications/{application_id}/verify-audit",
    summary="Verify Audit Hash Chain",
    tags=["Audit & Governance"],
)
async def verify_audit(application_id: str, db: Session = Depends(get_db)):
    """Cryptographically verify the integrity of the audit chain."""
    audit_logger = AuditLogger(db)
    is_valid, reason = audit_logger.verify_chain(application_id)
    return {
        "application_id": application_id,
        "chain_valid": is_valid,
        "verification_message": reason,
    }


@app.get(
    "/applications/{application_id}/documents/{document_id}/pages/{page_number}",
    summary="Serve Normalized Page Image",
    tags=["Dashboard"],
)
async def get_page_image(
    application_id: str,
    document_id: str,
    page_number: int,
    db: Session = Depends(get_db),
):
    """Safely retrieve a normalized page PNG image for the Clerk Dashboard."""
    clean_app_id = "".join(c for c in application_id if c.isalnum() or c in ("-", "_"))
    clean_doc_id = "".join(c for c in document_id if c.isalnum() or c in ("-", "_"))

    normalized_dir = BASE_DIR / "uploads" / clean_app_id / "normalized"
    if not normalized_dir.exists():
        raise HTTPException(status_code=404, detail="Application normalized directory not found.")

    target_page_name = f"page_{page_number:03d}.png"
    target_page_name_alt = f"page_{page_number}.png"

    # Search safely within the application's normalized subfolders
    for subfolder in normalized_dir.iterdir():
        if subfolder.is_dir():
            cand1 = subfolder / target_page_name
            cand2 = subfolder / target_page_name_alt
            if cand1.exists():
                return FileResponse(cand1, media_type="image/png")
            if cand2.exists():
                return FileResponse(cand2, media_type="image/png")

    raise HTTPException(status_code=404, detail=f"Page image '{page_number}' not found.")


if __name__ == "__main__":
    import uvicorn
    print("Starting Scholarship Document Verification Backend (Role 4 Orchestrator)...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
