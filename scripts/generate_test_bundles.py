"""
Synthetic Scholarship Document Bundle Generator
================================================
Generates realistic, readable printed-English documents for pipeline validation:
- Clean bundle (all match, valid dates, no tampering)
- Mismatch bundle (Priya Sharma vs Priya Sharna)
- Expired bundle (old certificate issue date)
- Duplicate bundle (reused certificate ID)
- Tampered bundle (digitally modified income field for ELA detection)
- Partial failure bundle (valid docs + corrupt/unsupported file)
"""

from __future__ import annotations

import os
from pathlib import Path
from PIL import Image, ImageDraw
import cv2
import numpy as np

try:
    import pymupdf as fitz
except ImportError:
    import fitz

BASE_OUTPUT_DIR = Path("test_bundles")


def create_certificate_image(
    title: str,
    fields: dict[str, str],
    footer: str = "Government of National Capital Territory",
    watermark: str = "OFFICIAL RECORD",
    width: int = 1200,
    height: int = 1600,
) -> Image.Image:
    """Create a high-resolution printed English certificate image."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Decorative Border
    draw.rectangle([(30, 30), (width - 30, height - 30)], outline=(30, 60, 120), width=4)
    draw.rectangle([(40, 40), (width - 40, height - 40)], outline=(180, 190, 210), width=2)

    # Header
    draw.text((width // 2 - 250, 80), title, fill=(20, 40, 90))
    draw.line([(100, 130), (width - 100, 130)], fill=(30, 60, 120), width=2)

    # Body Fields
    y = 200
    for key, val in fields.items():
        draw.text((120, y), f"{key}:", fill=(40, 40, 40))
        draw.text((380, y), str(val), fill=(10, 10, 10))
        draw.line([(370, y + 25), (width - 150, y + 25)], fill=(220, 220, 220), width=1)
        y += 80

    # Verification Seal / Stamp Placeholder
    draw.ellipse([(width - 300, height - 350), (width - 100, height - 150)], outline=(180, 40, 40), width=4)
    draw.text((width - 270, height - 260), "OFFICIAL SEAL", fill=(180, 40, 40))

    # Footer
    draw.line([(100, height - 100), (width - 100, height - 100)], fill=(180, 180, 180), width=1)
    draw.text((120, height - 80), footer, fill=(100, 100, 100))

    return img


def save_image_as_pdf(img: Image.Image, output_path: Path, fields: dict = None, second_page: bool = False):
    """Save PIL image as PDF with embedded text layer, optionally appending a second page."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()

    # Page 1
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    page1 = doc.new_page(width=img.width, height=img.height)
    page1.insert_image(fitz.Rect(0, 0, img.width, img.height), stream=buf.getvalue())

    # Embed digital text layer matching coordinates
    if fields:
        y = 200
        for key, val in fields.items():
            page1.insert_text((120, y), f"{key}: {val}", fontsize=18)
            y += 80

    # Optional Page 2 (for multi-page marksheet)
    if second_page:
        p2_img = Image.new("RGB", (img.width, img.height), color=(255, 255, 255))
        p2_draw = ImageDraw.Draw(p2_img)
        p2_draw.text((150, 100), "GRADING SYSTEM & REGULATORY CODES", fill=(20, 40, 90))
        p2_draw.text((150, 180), "Grade A+: 90% and above", fill=(50, 50, 50))
        p2_draw.text((150, 230), "Grade A:  80% - 89%", fill=(50, 50, 50))
        p2_draw.text((150, 280), "Grade B:  70% - 79%", fill=(50, 50, 50))
        p2_draw.text((150, 380), "Issued under Controller of Examinations Authority", fill=(80, 80, 80))
        buf2 = io.BytesIO()
        p2_img.save(buf2, format="PNG")
        buf2.seek(0)
        page2 = doc.new_page(width=img.width, height=img.height)
        page2.insert_image(fitz.Rect(0, 0, img.width, img.height), stream=buf2.getvalue())
        page2.insert_text((150, 100), "GRADING SYSTEM & REGULATORY CODES", fontsize=18)

    doc.save(str(output_path))
    doc.close()


def generate_all_bundles():
    BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------
    # 1. Clean Bundle
    # -------------------------------------------------------------
    clean_dir = BASE_OUTPUT_DIR / "clean_bundle"
    clean_dir.mkdir(parents=True, exist_ok=True)

    inc_fields = {
        "Certificate ID": "INC12345",
        "Applicant Name": "Priya Sharma",
        "Father Name": "Raj Sharma",
        "Annual Income": "120000",
        "Issue Date": "2026-01-15",
        "Issuing Office": "Tehsildar Revenue Office",
    }
    inc_img = create_certificate_image("ANNUAL INCOME CERTIFICATE", inc_fields)
    save_image_as_pdf(inc_img, clean_dir / "income_certificate.pdf", fields=inc_fields)

    cat_fields = {
        "Certificate ID": "CAT12345",
        "Applicant Name": "Priya Sharma",
        "Father Name": "Raj Sharma",
        "Caste / Category": "OBC",
        "Issue Date": "2026-01-20",
    }
    cat_img = create_certificate_image("COMMUNITY / CASTE CERTIFICATE", cat_fields)
    save_image_as_pdf(cat_img, clean_dir / "category_certificate.pdf", fields=cat_fields)

    mark_fields = {
        "Candidate Name": "Priya Sharma",
        "Father Name": "Raj Sharma",
        "Roll Number": "2024MS89",
        "Date of Birth": "12-05-2006",
        "Examination Year": "2024",
        "Total Marks": "465 / 500",
    }
    mark_img = create_certificate_image("SENIOR SECONDARY EXAMINATION MARKSHEET", mark_fields)
    save_image_as_pdf(mark_img, clean_dir / "marksheet.pdf", fields=mark_fields, second_page=True)

    id_fields = {
        "Name": "Priya Sharma",
        "Father Name": "Raj Sharma",
        "DOB": "12-05-2006",
        "ID Number": "9999 1111 2222",
        "Address": "123 North Avenue, Sector 4, New Delhi",
    }
    id_img = create_certificate_image("NATIONAL IDENTITY VERIFICATION (AADHAAR)", id_fields)
    id_img.save(clean_dir / "id_proof.jpg", "JPEG", quality=95)

    bank_fields = {
        "Account Holder": "Priya Sharma",
        "Account Number": "123456789012",
        "IFSC Code": "NBIN0001234",
        "Branch": "Central University Road",
        "Date": "2026-02-01",
    }
    bank_img = create_certificate_image("SAVINGS BANK ACCOUNT PASSBOOK", bank_fields)
    bank_img.save(clean_dir / "bank_proof.jpg", "JPEG", quality=95)

    # -------------------------------------------------------------
    # 2. Mismatch Bundle (Priya Sharma vs Priya Sharna)
    # -------------------------------------------------------------
    mismatch_dir = BASE_OUTPUT_DIR / "mismatch_bundle"
    mismatch_dir.mkdir(parents=True, exist_ok=True)

    cat_typo_fields = {
        "Certificate ID": "CAT12345",
        "Applicant Name": "Priya Sharna",  # Typo mismatch
        "Father Name": "Raj Sharma",
        "Caste / Category": "OBC",
        "Issue Date": "2026-01-20",
    }
    cat_typo_img = create_certificate_image("COMMUNITY / CASTE CERTIFICATE", cat_typo_fields)
    save_image_as_pdf(inc_img, mismatch_dir / "income_certificate.pdf", fields=inc_fields)
    save_image_as_pdf(cat_typo_img, mismatch_dir / "category_certificate.pdf", fields=cat_typo_fields)
    save_image_as_pdf(mark_img, mismatch_dir / "marksheet.pdf", fields=mark_fields, second_page=True)
    id_img.save(mismatch_dir / "id_proof.jpg", "JPEG", quality=95)
    bank_img.save(mismatch_dir / "bank_proof.jpg", "JPEG", quality=95)

    # -------------------------------------------------------------
    # 3. Expired Bundle (Issue Date: 2022-01-01 > 365 days ago)
    # -------------------------------------------------------------
    expired_dir = BASE_OUTPUT_DIR / "expired_bundle"
    expired_dir.mkdir(parents=True, exist_ok=True)

    inc_expired_fields = {
        "Certificate ID": "INC12345",
        "Applicant Name": "Priya Sharma",
        "Father Name": "Raj Sharma",
        "Annual Income": "120000",
        "Issue Date": "2022-01-01",  # Intentionally expired!
        "Issuing Office": "Tehsildar Revenue Office",
    }
    inc_expired_img = create_certificate_image("ANNUAL INCOME CERTIFICATE", inc_expired_fields)
    save_image_as_pdf(inc_expired_img, expired_dir / "income_certificate.pdf", fields=inc_expired_fields)
    save_image_as_pdf(cat_img, expired_dir / "category_certificate.pdf", fields=cat_fields)
    save_image_as_pdf(mark_img, expired_dir / "marksheet.pdf", fields=mark_fields)
    id_img.save(expired_dir / "id_proof.jpg", "JPEG", quality=95)
    bank_img.save(expired_dir / "bank_proof.jpg", "JPEG", quality=95)

    # -------------------------------------------------------------
    # 4. Duplicate Bundle (Reuses INC12345 across another applicant)
    # -------------------------------------------------------------
    dup_dir = BASE_OUTPUT_DIR / "duplicate_bundle"
    dup_dir.mkdir(parents=True, exist_ok=True)

    dup_inc_fields = {
        "Certificate ID": "INC12345",  # Duplicate identifier
        "Applicant Name": "Rahul Kumar",  # Different applicant
        "Father Name": "Sunil Kumar",
        "Annual Income": "95000",
        "Issue Date": "2026-02-10",
    }
    dup_inc_img = create_certificate_image("ANNUAL INCOME CERTIFICATE", dup_inc_fields)
    save_image_as_pdf(dup_inc_img, dup_dir / "income_certificate.pdf", fields=dup_inc_fields)

    # -------------------------------------------------------------
    # 5. Tampered Bundle (Digitally spliced amount creating ELA discrepancy)
    # -------------------------------------------------------------
    tampered_dir = BASE_OUTPUT_DIR / "tampered_bundle"
    tampered_dir.mkdir(parents=True, exist_ok=True)

    base_img = create_certificate_image(
        "ANNUAL INCOME CERTIFICATE",
        {
            "Certificate ID": "INC99887",
            "Applicant Name": "Priya Sharma",
            "Father Name": "Raj Sharma",
            "Annual Income": "120000",
            "Issue Date": "2026-01-15",
        },
    )
    temp_orig = tampered_dir / "temp_orig.jpg"
    base_img.save(temp_orig, "JPEG", quality=60)

    # Now open, paste an uncompressed patch with altered amount: "10000"
    cv_img = cv2.imread(str(temp_orig))
    # Draw a distinct sharp rectangle over the income amount region
    cv2.rectangle(cv_img, (370, 430), (580, 475), (255, 255, 255), -1)
    cv2.putText(cv_img, "10000", (380, 465), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)

    tampered_path = tampered_dir / "income_certificate.jpg"
    cv2.imwrite(str(tampered_path), cv_img, [int(cv2.IMWRITE_JPEG_QUALITY), 98])
    if temp_orig.exists():
        temp_orig.unlink()

    try:
        import piexif
        exif_dict = {"0th": {piexif.ImageIFD.Software: "Adobe Photoshop 2024"}}
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, str(tampered_path))
    except Exception as e:
        pass

    # -------------------------------------------------------------
    # 6. Partial Failure Bundle (Valid docs + Corrupt/Unsupported file)
    # -------------------------------------------------------------
    partial_dir = BASE_OUTPUT_DIR / "partial_failure_bundle"
    partial_dir.mkdir(parents=True, exist_ok=True)

    save_image_as_pdf(inc_img, partial_dir / "income_certificate.pdf")
    save_image_as_pdf(cat_img, partial_dir / "category_certificate.pdf")
    # Corrupted PDF
    with open(partial_dir / "corrupted_document.pdf", "wb") as f:
        f.write(b"NOT A VALID PDF HEADER %PDF-CORRUPT GARBAGE")
    # Unsupported file extension
    with open(partial_dir / "word_resume.docx", "wb") as f:
        f.write(b"PK\x03\x04 fake word docx payload")

    print("All synthetic test bundles generated successfully in 'test_bundles/' directory.")


if __name__ == "__main__":
    generate_all_bundles()
