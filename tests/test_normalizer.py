"""
Tests for FileNormalizerService
===============================
Covers PNG, JPG, PDF, multi-page PDF, unsupported files, and corrupted files.
"""

from __future__ import annotations

import io
from pathlib import Path
import pytest
from fastapi import UploadFile
from PIL import Image

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from services.file_normalizer import FileNormalizerService


def make_test_pdf(num_pages: int = 1) -> bytes:
    doc = fitz.open()
    for i in range(num_pages):
        p = doc.new_page(width=400, height=600)
        p.insert_text((50, 50), f"Page {i+1} Text")
    b = doc.tobytes()
    doc.close()
    return b


def make_test_image(fmt: str = "JPEG") -> bytes:
    img = Image.new("RGB", (200, 200), color=(120, 180, 240))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_normalize_single_png(tmp_path):
    normalizer = FileNormalizerService(base_dir=tmp_path)
    png_bytes = make_test_image("PNG")
    upload = UploadFile(filename="student_id.png", file=io.BytesIO(png_bytes))

    res = await normalizer.save_and_normalize("APP-001", upload)
    assert res["success"] is True
    assert res["page_count"] == 1
    assert len(res["page_image_paths"]) == 1
    assert Path(res["page_image_paths"][0]).exists()


@pytest.mark.asyncio
async def test_normalize_single_jpg(tmp_path):
    normalizer = FileNormalizerService(base_dir=tmp_path)
    jpg_bytes = make_test_image("JPEG")
    upload = UploadFile(filename="photo.jpg", file=io.BytesIO(jpg_bytes))

    res = await normalizer.save_and_normalize("APP-002", upload)
    assert res["success"] is True
    assert res["page_count"] == 1


@pytest.mark.asyncio
async def test_normalize_single_pdf(tmp_path):
    normalizer = FileNormalizerService(base_dir=tmp_path)
    pdf_bytes = make_test_pdf(num_pages=1)
    upload = UploadFile(filename="certificate.pdf", file=io.BytesIO(pdf_bytes))

    res = await normalizer.save_and_normalize("APP-003", upload)
    assert res["success"] is True
    assert res["page_count"] == 1


@pytest.mark.asyncio
async def test_normalize_multipage_pdf(tmp_path):
    normalizer = FileNormalizerService(base_dir=tmp_path)
    pdf_bytes = make_test_pdf(num_pages=3)
    upload = UploadFile(filename="marksheet_full.pdf", file=io.BytesIO(pdf_bytes))

    res = await normalizer.save_and_normalize("APP-004", upload)
    assert res["success"] is True
    assert res["page_count"] == 3
    assert len(res["page_image_paths"]) == 3


@pytest.mark.asyncio
async def test_normalize_corrupted_file(tmp_path):
    normalizer = FileNormalizerService(base_dir=tmp_path)
    bad_bytes = b"%PDF-corrupted-stream"
    upload = UploadFile(filename="corrupt.pdf", file=io.BytesIO(bad_bytes))

    res = await normalizer.save_and_normalize("APP-005", upload)
    assert res["success"] is False
    assert res["error"] is not None


@pytest.mark.asyncio
async def test_normalize_unsupported_file(tmp_path):
    normalizer = FileNormalizerService(base_dir=tmp_path)
    docx_bytes = b"PK\x03\x04fakeworddoc"
    upload = UploadFile(filename="notes.docx", file=io.BytesIO(docx_bytes))

    res = await normalizer.save_and_normalize("APP-006", upload)
    assert res["success"] is False
    assert res["error"]["type"] == "UnsupportedFileTypeError"
