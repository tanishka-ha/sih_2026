"""
Pipeline Service and Adapter Unit Tests
=======================================
Validates core Role 4 orchestration, storage management, and integration adapter contracts:
- OCR mock success and failure
- Forensics mock success and failure (critical: failure != tampering)
- Rules mock success and failure
- Application ID generation (automatic vs user-provided)
- Full and partial pipeline bundle orchestration
"""

from __future__ import annotations

import io
import tempfile
import pytest
from pathlib import Path
from fastapi import UploadFile

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from PIL import Image

from integrations.ocr_adapter import run_ocr_on_document
from integrations.forensics_adapter import run_forensics_on_document
from integrations.rules_adapter import run_rules_engine
from models.schemas import (
    ConversionResult,
    DocumentContext,
    DocumentResult,
    FlagSeverity,
    ForensicsResult,
    OcrResult,
    PipelineStatus,
    StageStatus,
)
from services.pipeline_service import PipelineService
from services.storage_service import StorageService


# =====================================================================
# FIXTURE HELPERS
# =====================================================================

def create_in_memory_pdf(pages: int = 1, text: str = "Test Doc") -> bytes:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 100), f"{text} - Page {i+1}")
    data = doc.tobytes()
    doc.close()
    return data


def create_in_memory_jpg() -> bytes:
    img = Image.new("RGB", (200, 200), color=(100, 150, 200))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


# =====================================================================
# ADAPTER TESTS
# =====================================================================

def test_ocr_adapter_success():
    doc = DocumentContext(
        application_id="APP-TEST",
        document_id="DOC-001",
        original_filename="income_certificate.pdf",
        original_type="pdf",
        image_paths=["/path/to/page_001.png"],
    )
    result = run_ocr_on_document(doc)
    assert result.status == StageStatus.SUCCESS
    assert result.doc_type == "income_certificate"
    assert "income_amount" in result.fields
    assert result.confidence > 0.8
    assert result.error is None


def test_ocr_adapter_failure():
    doc = DocumentContext(
        application_id="APP-TEST",
        document_id="DOC-002",
        original_filename="document_ocr_fail.pdf",
        original_type="pdf",
        image_paths=["/path/to/page_001.png"],
    )
    result = run_ocr_on_document(doc)
    assert result.status == StageStatus.FAILED
    assert result.confidence == 0.0
    assert result.error is not None


def test_forensics_adapter_success():
    doc = DocumentContext(
        application_id="APP-TEST",
        document_id="DOC-003",
        original_filename="marksheet.jpg",
        original_type="jpg",
        image_paths=["/path/to/page_001.png"],
    )
    result = run_forensics_on_document(doc)
    assert result.status == StageStatus.SUCCESS
    assert result.tampering_detected is False
    assert result.confidence > 0.9
    assert result.error is None


def test_forensics_adapter_failure_is_not_tampering():
    """CRITICAL TEST: Ensure forensics analysis failure NEVER marks tampering_detected=True."""
    doc = DocumentContext(
        application_id="APP-TEST",
        document_id="DOC-004",
        original_filename="marksheet_forensics_fail.jpg",
        original_type="jpg",
        image_paths=["/path/to/page_001.png"],
    )
    result = run_forensics_on_document(doc)
    assert result.status == StageStatus.FAILED
    assert result.tampering_detected is False  # Failure is analysis unavailable, NOT fraud!
    assert result.error is not None


def test_rules_adapter_success():
    doc = DocumentResult(
        document_id="DOC-001",
        original_filename="income_certificate.pdf",
        original_type="pdf",
        conversion=ConversionResult(success=True, status=StageStatus.SUCCESS, page_count=1, image_paths=["p.png"]),
        ocr=OcrResult(
            status=StageStatus.SUCCESS,
            doc_type="income_certificate",
            fields={"name": "Priya Sharma", "income_amount": "50000"},
            confidence=0.95,
        ),
        forensics=ForensicsResult(status=StageStatus.SUCCESS, tampering_detected=False, confidence=0.98),
    )
    result = run_rules_engine("APP-1234", [doc])
    assert result.status == StageStatus.SUCCESS
    assert isinstance(result.flags, list)
    assert result.error is None


def test_rules_adapter_failure():
    doc = DocumentResult(
        document_id="DOC-001",
        original_filename="income_certificate.pdf",
        original_type="pdf",
        conversion=ConversionResult(success=True, status=StageStatus.SUCCESS, page_count=1, image_paths=["p.png"]),
        ocr=OcrResult(status=StageStatus.SUCCESS, fields={}, confidence=0.95),
        forensics=ForensicsResult(status=StageStatus.SUCCESS, tampering_detected=False, confidence=0.98),
    )
    result = run_rules_engine("APP-rules_fail-999", [doc])
    assert result.status == StageStatus.FAILED
    assert result.error is not None


# =====================================================================
# STORAGE SERVICE TESTS
# =====================================================================

def test_application_id_generation():
    storage = StorageService()

    # User provided ID
    custom_id = storage.generate_application_id("MY-CUSTOM-APP-101")
    assert custom_id == "MY-CUSTOM-APP-101"

    # User provided ID with unsafe characters stripped
    unsafe_id = storage.generate_application_id("APP/../evil$ID;--")
    assert "/" not in unsafe_id
    assert ";" not in unsafe_id

    # Auto generated ID
    auto_id = storage.generate_application_id(None)
    assert auto_id.startswith("APP-2026-")


# =====================================================================
# PIPELINE SERVICE BUNDLE TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_pipeline_single_valid_pdf(tmp_path):
    storage = StorageService(base_storage_dir=tmp_path)
    pipeline = PipelineService(storage_service=storage)

    pdf_bytes = create_in_memory_pdf(pages=1, text="Single Page Application")
    upload = UploadFile(filename="scholarship_form.pdf", file=io.BytesIO(pdf_bytes))

    response = await pipeline.process_document_bundle([upload], application_id="APP-TEST-SINGLE")

    assert response.status == PipelineStatus.SUCCESS
    assert response.application_id == "APP-TEST-SINGLE"
    assert len(response.documents) == 1
    doc = response.documents[0]
    assert doc.conversion.success is True
    assert doc.conversion.page_count == 1
    assert len(doc.conversion.image_paths) == 1
    assert doc.ocr.status == StageStatus.SUCCESS
    assert doc.forensics.status == StageStatus.SUCCESS


@pytest.mark.asyncio
async def test_pipeline_multi_page_pdf(tmp_path):
    storage = StorageService(base_storage_dir=tmp_path)
    pipeline = PipelineService(storage_service=storage)

    pdf_bytes = create_in_memory_pdf(pages=3, text="Multi Page Grade Sheet")
    upload = UploadFile(filename="marksheet_pages.pdf", file=io.BytesIO(pdf_bytes))

    response = await pipeline.process_document_bundle([upload])

    assert response.status == PipelineStatus.SUCCESS
    assert len(response.documents) == 1
    doc = response.documents[0]
    assert doc.conversion.page_count == 3
    assert len(doc.conversion.image_paths) == 3


@pytest.mark.asyncio
async def test_pipeline_valid_jpg(tmp_path):
    storage = StorageService(base_storage_dir=tmp_path)
    pipeline = PipelineService(storage_service=storage)

    jpg_bytes = create_in_memory_jpg()
    upload = UploadFile(filename="id_card.jpg", file=io.BytesIO(jpg_bytes))

    response = await pipeline.process_document_bundle([upload])

    assert response.status == PipelineStatus.SUCCESS
    assert len(response.documents) == 1
    doc = response.documents[0]
    assert doc.conversion.success is True
    assert doc.conversion.page_count == 1


@pytest.mark.asyncio
async def test_pipeline_multiple_uploaded_documents(tmp_path):
    storage = StorageService(base_storage_dir=tmp_path)
    pipeline = PipelineService(storage_service=storage)

    pdf_bytes = create_in_memory_pdf(pages=1, text="Income Certificate")
    jpg_bytes = create_in_memory_jpg()

    upload_pdf = UploadFile(filename="income_certificate.pdf", file=io.BytesIO(pdf_bytes))
    upload_jpg = UploadFile(filename="marksheet.jpg", file=io.BytesIO(jpg_bytes))

    response = await pipeline.process_document_bundle([upload_pdf, upload_jpg])

    assert response.status == PipelineStatus.SUCCESS
    assert len(response.documents) == 2
    assert response.documents[0].conversion.success is True
    assert response.documents[1].conversion.success is True


@pytest.mark.asyncio
async def test_pipeline_conversion_failure_handling(tmp_path):
    storage = StorageService(base_storage_dir=tmp_path)
    pipeline = PipelineService(storage_service=storage)

    corrupted_bytes = b"%PDF-corrupted-data-header-truncated"
    upload = UploadFile(filename="corrupt.pdf", file=io.BytesIO(corrupted_bytes))

    response = await pipeline.process_document_bundle([upload])

    assert response.status == PipelineStatus.FAILED
    assert len(response.documents) == 1
    doc = response.documents[0]
    assert doc.conversion.success is False
    assert doc.conversion.status == StageStatus.FAILED
    assert doc.ocr.status == StageStatus.SKIPPED
    assert doc.forensics.status == StageStatus.SKIPPED


@pytest.mark.asyncio
async def test_pipeline_partial_success(tmp_path):
    """Test mixed bundle: one valid PDF and one corrupted file."""
    storage = StorageService(base_storage_dir=tmp_path)
    pipeline = PipelineService(storage_service=storage)

    valid_pdf = create_in_memory_pdf(pages=1, text="Valid Doc")
    corrupt_pdf = b"%PDF-truncated-bytes"

    upload1 = UploadFile(filename="good_doc.pdf", file=io.BytesIO(valid_pdf))
    upload2 = UploadFile(filename="bad_doc.pdf", file=io.BytesIO(corrupt_pdf))

    response = await pipeline.process_document_bundle([upload1, upload2])

    assert response.status == PipelineStatus.PARTIAL_SUCCESS
    assert len(response.documents) == 2
    # Document 1 succeeded
    assert response.documents[0].conversion.success is True
    assert response.documents[0].ocr.status == StageStatus.SUCCESS
    # Document 2 failed safely
    assert response.documents[1].conversion.success is False
    assert response.documents[1].ocr.status == StageStatus.SKIPPED
