"""
Comprehensive Test Suite for File Normalisation Module
======================================================
Tests all 14 required pipeline scenarios:
1.  Valid single-page PDF
2.  Valid multi-page PDF
3.  Valid JPG
4.  Valid JPEG
5.  Valid PNG (including transparency flattening check)
6.  Missing file (FileNotFoundError)
7.  Unsupported file type (UnsupportedFileTypeError)
8.  Corrupted image (InvalidImageError)
9.  Corrupted PDF (InvalidPDFError)
10. Empty PDF (EmptyPDFError / FileValidationError)
11. Password-protected PDF (PasswordProtectedPDFError)
12. File exceeding size limit (FileTooLargeError)
13. PDF exceeding page limit (TooManyPagesError)
14. Output directory error (OutputDirectoryError)
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from PIL import Image, ImageDraw

from file_converter import (
    convert_to_images,
    MAX_FILE_SIZE_MB,
    MAX_PDF_PAGES,
    PDF_RENDER_SCALE,
)


class TestRunner:
    def __init__(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_converter_"))
        self.fixtures_dir = self.temp_dir / "fixtures"
        self.output_dir = self.temp_dir / "outputs"
        self.fixtures_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = []

    def cleanup(self):
        """Remove all temporary fixture and output files."""
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup temp dir {self.temp_dir}: {e}")

    def record_result(self, name: str, passed: bool, details: str = ""):
        self.results.append({"name": name, "passed": passed, "details": details})
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status:8} | {name:<45} | {details}")

    # =================================================================
    # FIXTURE GENERATORS
    # =================================================================

    def make_single_page_pdf(self) -> Path:
        p = self.fixtures_dir / "single_page.pdf"
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)  # A4
        page.insert_text((72, 100), "Scholarship Verification Document - Single Page", fontsize=14)
        doc.save(str(p))
        doc.close()
        return p

    def make_multi_page_pdf(self, page_count: int = 3) -> Path:
        p = self.fixtures_dir / f"multi_page_{page_count}.pdf"
        doc = fitz.open()
        for i in range(page_count):
            page = doc.new_page(width=595, height=842)
            page.insert_text((72, 100), f"Document Page {i + 1} of {page_count}", fontsize=14)
        doc.save(str(p))
        doc.close()
        return p

    def make_valid_jpg(self) -> Path:
        p = self.fixtures_dir / "test_certificate.jpg"
        img = Image.new("RGB", (400, 300), color=(180, 220, 240))
        draw = ImageDraw.Draw(img)
        draw.text((30, 50), "Income Certificate - Valid JPG", fill=(0, 0, 0))
        img.save(p, format="JPEG")
        return p

    def make_valid_jpeg(self) -> Path:
        p = self.fixtures_dir / "marksheet.jpeg"
        img = Image.new("RGB", (400, 300), color=(240, 220, 180))
        draw = ImageDraw.Draw(img)
        draw.text((30, 50), "Marksheet - Valid JPEG", fill=(0, 0, 0))
        img.save(p, format="JPEG")
        return p

    def make_valid_png_with_transparency(self) -> Path:
        p = self.fixtures_dir / "transparent_stamp.png"
        # RGBA with transparent canvas and a solid colored shape
        img = Image.new("RGBA", (300, 300), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((50, 50, 250, 250), fill=(220, 20, 60, 255))
        draw.text((100, 140), "OFFICIAL STAMP", fill=(255, 255, 255, 255))
        img.save(p, format="PNG")
        return p

    def make_corrupted_image(self) -> Path:
        p = self.fixtures_dir / "corrupted_photo.jpg"
        # Starts with valid JPEG header but immediately cut off with garbage
        p.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01--CORRUPTED_STREAM--")
        return p

    def make_corrupted_pdf(self) -> Path:
        p = self.fixtures_dir / "corrupted_form.pdf"
        # Has %PDF header but garbage payload
        p.write_bytes(b"%PDF-1.4\n%--GARBAGE_PAYLOAD_NOT_VALID_PDF_STRUCTURE--\n%%EOF")
        return p

    def make_empty_pdf(self) -> Path:
        p = self.fixtures_dir / "empty_doc.pdf"
        # 0-byte file
        p.write_bytes(b"")
        return p

    def make_encrypted_pdf(self) -> Path:
        p = self.fixtures_dir / "password_protected.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Confidential Bank Passbook")
        doc.save(
            str(p),
            encryption=fitz.PDF_ENCRYPT_AES_256,
            user_pw="secure_pass123",
            owner_pw="admin_pass123",
        )
        doc.close()
        return p

    def make_unsupported_file(self) -> Path:
        p = self.fixtures_dir / "document.docx"
        p.write_bytes(b"PK\x03\x04\x14\x00\x06\x00FakeDocxContents")
        return p

    # =================================================================
    # TESTS
    # =================================================================

    def test_01_valid_single_page_pdf(self):
        pdf_path = self.make_single_page_pdf()
        res = convert_to_images(pdf_path, output_directory=self.output_dir)

        passed = (
            res["success"] is True
            and res["page_count"] == 1
            and len(res["image_paths"]) == 1
            and res["original_type"] == "pdf"
            and res["error"] is None
            and Path(res["image_paths"][0]).exists()
            and Path(res["image_paths"][0]).name == "page_001.png"
        )
        self.record_result("1. Valid single-page PDF", passed, f"Generated {res['page_count']} page(s)")

    def test_02_valid_multi_page_pdf(self):
        pdf_path = self.make_multi_page_pdf(page_count=3)
        res = convert_to_images(pdf_path, output_directory=self.output_dir)

        paths = [Path(p) for p in res["image_paths"]]
        all_exist = all(p.exists() for p in paths)
        correct_names = [p.name for p in paths] == ["page_001.png", "page_002.png", "page_003.png"]

        passed = (
            res["success"] is True
            and res["page_count"] == 3
            and all_exist
            and correct_names
            and res["error"] is None
        )
        self.record_result("2. Valid multi-page PDF", passed, f"Generated {res['page_count']} ordered pages")

    def test_03_valid_jpg(self):
        jpg_path = self.make_valid_jpg()
        res = convert_to_images(jpg_path, output_directory=self.output_dir)

        passed = (
            res["success"] is True
            and res["page_count"] == 1
            and res["original_type"] == "jpg"
            and res["error"] is None
            and Path(res["image_paths"][0]).name == "page_001.png"
        )
        self.record_result("3. Valid JPG", passed, f"Converted to standard {Path(res['image_paths'][0]).name}")

    def test_04_valid_jpeg(self):
        jpeg_path = self.make_valid_jpeg()
        res = convert_to_images(jpeg_path, output_directory=self.output_dir)

        passed = (
            res["success"] is True
            and res["page_count"] == 1
            and res["original_type"] == "jpeg"
            and res["error"] is None
            and Path(res["image_paths"][0]).name == "page_001.png"
        )
        self.record_result("4. Valid JPEG", passed, f"Converted to standard {Path(res['image_paths'][0]).name}")

    def test_05_valid_png_transparency(self):
        png_path = self.make_valid_png_with_transparency()
        res = convert_to_images(png_path, output_directory=self.output_dir)

        out_path = Path(res["image_paths"][0])
        # Verify that output image is RGB and corners (previously transparent) are pure white (255, 255, 255)
        with Image.open(out_path) as img:
            mode_is_rgb = img.mode == "RGB"
            corner_pixel = img.getpixel((10, 10))  # Should be pure white (255, 255, 255)
            not_black = corner_pixel == (255, 255, 255)

        passed = (
            res["success"] is True
            and res["original_type"] == "png"
            and mode_is_rgb
            and not_black
        )
        details = f"Mode: {img.mode}, Background Pixel: {corner_pixel} (White composited)"
        self.record_result("5. Valid PNG (Transparency Flatten)", passed, details)

    def test_06_missing_file(self):
        non_existent = self.fixtures_dir / "does_not_exist_999.pdf"
        res = convert_to_images(non_existent, output_directory=self.output_dir)

        passed = (
            res["success"] is False
            and res["page_count"] == 0
            and res["error"]["type"] == "FileNotFoundError"
        )
        self.record_result("6. Missing File", passed, f"Caught {res['error']['type']}")

    def test_07_unsupported_file_type(self):
        docx_path = self.make_unsupported_file()
        res = convert_to_images(docx_path, output_directory=self.output_dir)

        passed = (
            res["success"] is False
            and res["page_count"] == 0
            and res["error"]["type"] == "UnsupportedFileTypeError"
        )
        self.record_result("7. Unsupported File Type (.docx)", passed, f"Caught {res['error']['type']}")

    def test_08_corrupted_image(self):
        corrupt_img = self.make_corrupted_image()
        res = convert_to_images(corrupt_img, output_directory=self.output_dir)

        passed = (
            res["success"] is False
            and res["page_count"] == 0
            and res["error"]["type"] in ("InvalidImageError", "UnexpectedConversionError")
        )
        self.record_result("8. Corrupted Image", passed, f"Caught {res['error']['type']}")

    def test_09_corrupted_pdf(self):
        corrupt_pdf = self.make_corrupted_pdf()
        res = convert_to_images(corrupt_pdf, output_directory=self.output_dir)

        passed = (
            res["success"] is False
            and res["page_count"] == 0
            and res["error"]["type"] in ("InvalidPDFError", "UnexpectedConversionError")
        )
        self.record_result("9. Corrupted PDF", passed, f"Caught {res['error']['type']}")

    def test_10_empty_pdf(self):
        empty_pdf = self.make_empty_pdf()
        res = convert_to_images(empty_pdf, output_directory=self.output_dir)

        passed = (
            res["success"] is False
            and res["page_count"] == 0
            and res["error"]["type"] in ("FileValidationError", "EmptyPDFError", "InvalidPDFError")
        )
        self.record_result("10. Empty PDF (0 bytes)", passed, f"Caught {res['error']['type']}")

    def test_11_password_protected_pdf(self):
        enc_pdf = self.make_encrypted_pdf()
        res = convert_to_images(enc_pdf, output_directory=self.output_dir)

        passed = (
            res["success"] is False
            and res["page_count"] == 0
            and res["error"]["type"] == "PasswordProtectedPDFError"
        )
        self.record_result("11. Password-Protected PDF", passed, f"Caught {res['error']['type']}")

    def test_12_file_exceeding_size_limit(self):
        valid_pdf = self.make_single_page_pdf()
        # Set max limit to tiny 0.0001 MB (~100 bytes) so our ~1KB PDF exceeds it
        res = convert_to_images(valid_pdf, output_directory=self.output_dir, max_file_size_mb=0.0001)

        passed = (
            res["success"] is False
            and res["page_count"] == 0
            and res["error"]["type"] == "FileTooLargeError"
        )
        self.record_result("12. File Exceeding Size Limit", passed, f"Caught {res['error']['type']}")

    def test_13_pdf_exceeding_page_limit(self):
        multi_pdf = self.make_multi_page_pdf(page_count=5)
        # Set max pages limit to 3
        res = convert_to_images(multi_pdf, output_directory=self.output_dir, max_pdf_pages=3)

        passed = (
            res["success"] is False
            and res["page_count"] == 0
            and res["error"]["type"] == "TooManyPagesError"
        )
        self.record_result("13. PDF Exceeding Page Limit", passed, f"Caught {res['error']['type']}")

    def test_14_output_directory_error(self):
        valid_pdf = self.make_single_page_pdf()
        # Pass a regular file as base output directory; mkdir will fail with NotADirectoryError / OutputDirectoryError
        invalid_out_dir = self.fixtures_dir / "regular_file.txt"
        invalid_out_dir.write_text("I am a file, not a directory")

        res = convert_to_images(valid_pdf, output_directory=invalid_out_dir)

        passed = (
            res["success"] is False
            and res["page_count"] == 0
            and res["error"]["type"] == "OutputDirectoryError"
        )
        self.record_result("14. Output Directory Error", passed, f"Caught {res['error']['type']}")

    def run_all(self) -> bool:
        print("\n" + "=" * 80)
        print("RUNNING DOCUMENT NORMALISATION TEST SUITE (14 SCENARIOS)")
        print("=" * 80)

        self.test_01_valid_single_page_pdf()
        self.test_02_valid_multi_page_pdf()
        self.test_03_valid_jpg()
        self.test_04_valid_jpeg()
        self.test_05_valid_png_transparency()
        self.test_06_missing_file()
        self.test_07_unsupported_file_type()
        self.test_08_corrupted_image()
        self.test_09_corrupted_pdf()
        self.test_10_empty_pdf()
        self.test_11_password_protected_pdf()
        self.test_12_file_exceeding_size_limit()
        self.test_13_pdf_exceeding_page_limit()
        self.test_14_output_directory_error()

        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed

        print("=" * 80)
        print(f"TEST SUMMARY: Total: {total} | Passed: {passed} | Failed: {failed}")
        print("=" * 80 + "\n")

        self.cleanup()
        return failed == 0


if __name__ == "__main__":
    runner = TestRunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)
