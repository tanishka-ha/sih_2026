"""
generate_dataset.py
--------------------
Role 6 deliverable for the SIH Scholarship Verification project.

Generates a synthetic corpus of scholarship application bundles with
KNOWN, deliberately-injected defects, so the rest of the team can test
their modules against ground truth (and you can report real
precision/recall numbers in the pitch).

No external dependencies beyond Pillow (PIL) and reportlab, both of
which are extremely common and easy to install. No Faker needed --
this script has its own small built-in name/data generator so it
works even with zero internet access on hackathon wifi.

USAGE:
    python generate_dataset.py

OUTPUT (created in ./dataset/):
    dataset/
        APP-2026-0001/
            income_certificate.jpg
            category_certificate.jpg
            marksheet.jpg
            id_proof_front.jpg     <- realistic card-style ID (front)
            id_proof_back.jpg      <- ID back: address + sample QR block
            bank_proof.jpg
            bundle.pdf              <- all 6 docs as one multi-page PDF
        APP-2026-0002/
            ...
        ground_truth.json          <- full ground truth for every application
        ground_truth_summary.csv   <- quick human-readable overview

Note on the ID card: it's styled like a real front/back national ID card
(photo box, formatted ID number, address + QR-style block on the back) so
OCR/layout testing is realistic. It carries a visible "SPECIMEN - SYNTHETIC
TEST DATA" watermark and a footer disclaimer so it can never be mistaken
for, or reused as, a real identity document.
"""

import os
import json
import random
import csv
from datetime import date, timedelta
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

random.seed(42)  # reproducible dataset -- re-run gives identical output

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
IMG_W, IMG_H = 1240, 900  # ~ A4-ish at low-medium scan resolution

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")

# ---------------------------------------------------------------------------
# Tiny built-in "fake data" generator (no internet / no Faker required)
# ---------------------------------------------------------------------------

FIRST_NAMES = ["Priya", "Rahul", "Anjali", "Vikram", "Sneha", "Arjun", "Kavya",
               "Rohan", "Neha", "Aditya", "Pooja", "Karan", "Divya", "Manish",
               "Ritu", "Suresh", "Meera", "Ajay", "Shreya", "Nikhil"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Singh", "Patel", "Reddy", "Kumar",
              "Nair", "Iyer", "Das", "Chauhan", "Mishra", "Joshi", "Yadav",
              "Menon", "Rao", "Kapoor", "Bhatt", "Pillai", "Agarwal"]
CATEGORIES = ["General", "OBC", "SC", "ST", "EWS"]
BANKS = ["State Bank of India", "Punjab National Bank", "Bank of Baroda",
         "Canara Bank", "Union Bank of India"]
DISTRICTS = ["Lucknow", "Patna", "Jaipur", "Nagpur", "Indore", "Bhopal",
             "Ranchi", "Raipur", "Guwahati", "Kanpur"]

used_cert_numbers = []  # pool we can deliberately re-use for duplicate defect


def random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_father_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_dob():
    start = date(2003, 1, 1)
    end = date(2007, 12, 31)
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def random_issue_date(years_ago_min=0, years_ago_max=1):
    days_min = int(years_ago_min * 365)
    days_max = int(years_ago_max * 365)
    d = random.randint(days_min, days_max)
    return date.today() - timedelta(days=d)


def random_cert_number(prefix, remember=True):
    num = f"{prefix}-{random.randint(100000, 999999)}"
    if remember:
        used_cert_numbers.append(num)
    return num


def random_address(district):
    house = random.randint(1, 400)
    streets = ["Gandhi Nagar", "MG Road", "Station Road", "Nehru Colony",
               "Shastri Nagar", "Civil Lines", "Model Town", "Ashok Vihar"]
    return f"H.No {house}, {random.choice(streets)}, {district}"


def random_aadhaar_like():
    return " ".join(f"{random.randint(0, 9999):04d}" for _ in range(3))


def make_typo(name):
    """Introduce a small, OCR-plausible edit so fuzzy match lands ~80-95%."""
    name = list(name)
    idx = random.randrange(len(name))
    while name[idx] == " ":
        idx = random.randrange(len(name))
    swaps = {"m": "n", "n": "m", "a": "o", "o": "a", "i": "l", "l": "i",
             "e": "c", "s": "5", "r": "n", "u": "v", "v": "u"}
    name[idx] = swaps.get(name[idx].lower(), "x")
    return "".join(name)


# ---------------------------------------------------------------------------
# Document rendering
# ---------------------------------------------------------------------------

def font(size, bold=False):
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(path, size)


def draw_header(draw, title):
    draw.rectangle([0, 0, IMG_W, 110], fill=(235, 235, 235))
    draw.rectangle([0, 0, IMG_W, 110], outline=(0, 0, 0), width=2)
    draw.text((IMG_W / 2, 35), "GOVERNMENT OF INDIA", font=font(28, bold=True),
               fill=(0, 0, 0), anchor="mm")
    draw.text((IMG_W / 2, 75), title, font=font(22, bold=True),
               fill=(30, 30, 30), anchor="mm")


def draw_field(draw, y, label, value, x=90):
    draw.text((x, y), f"{label}:", font=font(24, bold=True), fill=(0, 0, 0))
    draw.text((x + 340, y), str(value), font=font(24), fill=(20, 20, 20))
    return y + 55


def draw_footer_seal(draw):
    cx, cy, r = IMG_W - 180, IMG_H - 140, 70
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(150, 0, 0), width=3)
    draw.text((cx, cy), "OFFICIAL\nSEAL", font=font(16, bold=True),
               fill=(150, 0, 0), anchor="mm", align="center")
    draw.line([90, IMG_H - 90, 400, IMG_H - 90], fill=(0, 0, 0), width=2)
    draw.text((90, IMG_H - 80), "Signature of Issuing Authority",
               font=font(16), fill=(0, 0, 0))


def render_income_certificate(fields, path, degrade=None):
    img = Image.new("RGB", (IMG_W, IMG_H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    draw_header(d, "INCOME CERTIFICATE")
    y = 160
    y = draw_field(d, y, "Certificate No", fields["certificate_number"])
    y = draw_field(d, y, "Name", fields["name"])
    y = draw_field(d, y, "Father's Name", fields["father_name"])
    y = draw_field(d, y, "Date of Birth", fields["dob"])
    y = draw_field(d, y, "District", fields["district"])
    y = draw_field(d, y, "Issue Date", fields["issue_date"])
    amount_y = y
    y = draw_field(d, y, "Annual Income (Rs.)", fields["income_amount"])
    d.text((90, y + 10), "This is to certify that the annual family income",
           font=font(18), fill=(60, 60, 60))
    d.text((90, y + 40), "stated above has been verified by this office.",
           font=font(18), fill=(60, 60, 60))
    draw_footer_seal(d)
    finalize_and_save(img, path, degrade=degrade)
    # bounding box of the income amount text region, for tampering ground truth
    amount_bbox = [90 + 340, amount_y - 5, 90 + 340 + 260, amount_y + 40]
    return amount_bbox


def render_category_certificate(fields, path, degrade=None):
    img = Image.new("RGB", (IMG_W, IMG_H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    draw_header(d, "CASTE / CATEGORY CERTIFICATE")
    y = 160
    y = draw_field(d, y, "Certificate No", fields["certificate_number"])
    y = draw_field(d, y, "Name", fields["name"])
    y = draw_field(d, y, "Father's Name", fields["father_name"])
    y = draw_field(d, y, "Date of Birth", fields["dob"])
    y = draw_field(d, y, "Category", fields["category"])
    y = draw_field(d, y, "Issue Date", fields["issue_date"])
    draw_footer_seal(d)
    finalize_and_save(img, path, degrade=degrade)


def render_marksheet(fields, path, degrade=None):
    img = Image.new("RGB", (IMG_W, IMG_H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    draw_header(d, "SENIOR SECONDARY MARKSHEET")
    y = 160
    y = draw_field(d, y, "Roll Number", fields["roll_number"])
    y = draw_field(d, y, "Name", fields["name"])
    y = draw_field(d, y, "Father's Name", fields["father_name"])
    y = draw_field(d, y, "Date of Birth", fields["dob"])
    y = draw_field(d, y, "Exam Year", fields["exam_year"])
    y = draw_field(d, y, "Percentage", fields["percentage"])
    draw_footer_seal(d)
    finalize_and_save(img, path, degrade=degrade)


CARD_W, CARD_H = 1050, 660  # roughly a physical ID-card aspect ratio


def draw_specimen_watermark(img):
    """Tiled diagonal 'SPECIMEN' watermark. Keeps the card visually
    realistic for layout/OCR testing while making unmistakably clear it is
    synthetic test data, not a real government-issued document."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    text = "SPECIMEN - SYNTHETIC TEST DATA"
    step_x, step_y = 420, 140
    for ty in range(-100, img.size[1] + 100, step_y):
        for tx in range(-100, img.size[0] + 100, step_x):
            od.text((tx, ty), text, font=font(20, bold=True), fill=(180, 30, 30, 70))
    overlay = overlay.rotate(28, expand=False)
    overlay = overlay.resize(img.size)
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"), (0, 0))


def draw_photo_placeholder(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], outline=(120, 120, 120), width=2, fill=(230, 230, 230))
    # simple silhouette icon: head + shoulders
    cx = x + w / 2
    d.ellipse([cx - w * 0.22, y + h * 0.15, cx + w * 0.22, y + h * 0.55],
              fill=(180, 180, 180))
    d.pieslice([x + w * 0.1, y + h * 0.45, x + w * 0.9, y + h * 1.25],
               start=180, end=360, fill=(180, 180, 180))


def render_id_proof_front(fields, path, degrade=None):
    img = Image.new("RGB", (CARD_W, CARD_H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, CARD_W - 1, CARD_H - 1], outline=(0, 60, 120), width=4)
    d.rectangle([0, 0, CARD_W - 1, 90], fill=(0, 60, 120))
    d.text((30, 22), "GOVERNMENT OF INDIA", font=font(26, bold=True), fill=(255, 255, 255))
    d.text((30, 58), "National Identity Card (Specimen)", font=font(16), fill=(220, 230, 240))

    draw_photo_placeholder(d, 40, 130, 190, 230)

    tx = 260
    ty = 140
    d.text((tx, ty), fields["name"], font=font(30, bold=True), fill=(0, 0, 0))
    ty += 50
    d.text((tx, ty), f"DOB: {fields['dob']}", font=font(22), fill=(30, 30, 30))
    ty += 38
    d.text((tx, ty), f"Gender: {fields['gender']}", font=font(22), fill=(30, 30, 30))

    id_str = fields["id_number"]
    d.text((tx, ty + 90), id_str, font=font(38, bold=True), fill=(10, 10, 10))

    d.text((30, CARD_H - 40), "This is a synthetically generated specimen card for software testing only.",
           font=font(13), fill=(140, 30, 30))

    draw_specimen_watermark(img)
    finalize_and_save(img, path, degrade=degrade)


def render_id_proof_back(fields, path, degrade=None):
    img = Image.new("RGB", (CARD_W, CARD_H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, CARD_W - 1, CARD_H - 1], outline=(0, 60, 120), width=4)
    d.rectangle([0, 0, CARD_W - 1, 60], fill=(0, 60, 120))
    d.text((30, 15), "Address", font=font(20, bold=True), fill=(255, 255, 255))

    d.text((40, 90), fields["address"], font=font(22), fill=(20, 20, 20))
    d.text((40, 130), f"ID No: {fields['id_number']}", font=font(20), fill=(20, 20, 20))

    # abstract QR-style placeholder block -- a random pixel grid, NOT a real
    # scannable code, just visual texture so the layout looks authentic
    qr_size, cell = 220, 11
    qx, qy = CARD_W - qr_size - 60, CARD_H - qr_size - 80
    rng = random.Random(fields["id_number"])  # deterministic per-card pattern
    for row in range(qr_size // cell):
        for col in range(qr_size // cell):
            if rng.random() < 0.5:
                d.rectangle([qx + col * cell, qy + row * cell,
                             qx + col * cell + cell - 1, qy + row * cell + cell - 1],
                            fill=(0, 0, 0))
    d.rectangle([qx - 4, qy - 4, qx + qr_size + 4, qy + qr_size + 4], outline=(0, 0, 0), width=2)
    d.text((qx, qy + qr_size + 8), "(sample code - non-functional)", font=font(13), fill=(100, 100, 100))

    d.text((30, CARD_H - 40), "This is a synthetically generated specimen card for software testing only.",
           font=font(13), fill=(140, 30, 30))

    draw_specimen_watermark(img)
    finalize_and_save(img, path, degrade=degrade)


def render_bank_proof(fields, path, degrade=None):
    img = Image.new("RGB", (IMG_W, IMG_H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    draw_header(d, "BANK ACCOUNT PROOF")
    y = 160
    y = draw_field(d, y, "Account Holder", fields["name"])
    y = draw_field(d, y, "Bank Name", fields["bank_name"])
    y = draw_field(d, y, "Account Number", fields["account_number"])
    y = draw_field(d, y, "IFSC Code", fields["ifsc"])
    draw_footer_seal(d)
    finalize_and_save(img, path, degrade=degrade)


def finalize_and_save(img, path, degrade=None):
    """Add light scan-realism noise to every document (so tampered patches
    actually stand out under ELA, and OCR is tested on non-perfect input),
    then optionally apply one extra degradation to stress-test the pipeline:
        'rotate'  -> angled scan (1-4 degrees)
        'blur'    -> out-of-focus / low-quality scan
        'lowres'  -> low-resolution phone photo (downscale + upscale)
    """
    arr = np.array(img).astype(np.int16)
    noise = np.random.normal(0, 4, arr.shape).astype(np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    quality = 90
    if degrade == "rotate":
        angle = random.uniform(1.5, 4.0) * random.choice([-1, 1])
        img = img.rotate(angle, expand=False, fillcolor=(255, 255, 255))
    elif degrade == "blur":
        img = img.filter(ImageFilter.GaussianBlur(radius=1.6))
        quality = 70
    elif degrade == "lowres":
        w, h = img.size
        img = img.resize((w // 3, h // 3), Image.BILINEAR).resize((w, h), Image.BILINEAR)
        quality = 60

    img.save(path, "JPEG", quality=quality)


def apply_amount_tampering(path, bbox, new_amount):
    """Simulate someone editing the scanned image in an editor and
    re-saving it. This creates a genuine double-JPEG-compression
    inconsistency in the edited region, which is exactly what
    Error Level Analysis (Role 3) is meant to catch."""
    img = Image.open(path).convert("RGB")
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = bbox
    d.rectangle([x0 - 5, y0 - 5, x1 + 5, y1 + 5], fill=(255, 255, 255))
    d.text((x0, y0), str(new_amount), font=font(24), fill=(10, 10, 10))
    img.save(path, "JPEG", quality=90)


def make_bundle_pdf(app_dir, doc_paths_in_order):
    pdf_path = os.path.join(app_dir, "bundle.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    pw, ph = A4
    for p in doc_paths_in_order:
        img = ImageReader(p)
        iw, ih = Image.open(p).size
        scale = min(pw / iw, ph / ih)
        c.drawImage(img, 0, ph - ih * scale, width=iw * scale, height=ih * scale)
        c.showPage()
    c.save()
    return pdf_path


# ---------------------------------------------------------------------------
# Application (bundle) generation
# ---------------------------------------------------------------------------

def build_application(app_index, defect_type=None, borrow_cert_from=None):
    app_id = f"APP-2026-{app_index:04d}"
    app_dir = os.path.join(OUT_DIR, app_id)
    os.makedirs(app_dir, exist_ok=True)

    name = random_name()
    father_name = random_father_name()
    dob = random_dob().isoformat()
    district = random.choice(DISTRICTS)
    category = random.choice(CATEGORIES)

    income_issue_date = random_issue_date(0, 1)  # normally within last year
    if defect_type == "expired":
        income_issue_date = date.today() - timedelta(days=365 * 2 + 30)  # 2+ yrs old

    income_amount = random.randint(20000, 150000)
    tampered_amount = None
    if defect_type == "tampered_amount":
        tampered_amount = max(5000, income_amount - random.randint(20000, 60000))

    cert_no_income = random_cert_number("INC")
    cert_no_category = random_cert_number("CAT")

    duplicated_field = None
    if defect_type == "duplicate_cert" and borrow_cert_from:
        # reuse an existing certificate number from an earlier, different applicant
        cert_no_income = borrow_cert_from
        duplicated_field = "income_certificate.certificate_number"

    # name used on the "odd one out" document if this is a typo case
    name_on_category_doc = name
    if defect_type == "name_typo":
        name_on_category_doc = make_typo(name)

    fields = {
        "income_certificate": {
            "certificate_number": cert_no_income,
            "name": name,
            "father_name": father_name,
            "dob": dob,
            "district": district,
            "issue_date": income_issue_date.isoformat(),
            "income_amount": income_amount,
        },
        "category_certificate": {
            "certificate_number": cert_no_category,
            "name": name_on_category_doc,
            "father_name": father_name,
            "dob": dob,
            "category": category,
            "issue_date": random_issue_date(0, 2).isoformat(),
        },
        "marksheet": {
            "roll_number": f"RN{random.randint(100000, 999999)}",
            "name": name,
            "father_name": father_name,
            "dob": dob,
            "exam_year": str(random.randint(2022, 2024)),
            "percentage": f"{random.randint(55, 95)}.{random.randint(0, 9)}%",
        },
        "id_proof": {
            "id_number": random_aadhaar_like(),
            "name": name,
            "dob": dob,
            "gender": random.choice(["Male", "Female"]),
            "address": random_address(district),
        },
        "bank_proof": {
            "name": name,
            "bank_name": random.choice(BANKS),
            "account_number": str(random.randint(10**10, 10**11 - 1)),
            "ifsc": f"{random.choice(BANKS)[:4].upper().replace(' ', 'X')[:4]}0{random.randint(100000, 999999)}",
        },
    }

    paths = {
        "income_certificate": os.path.join(app_dir, "income_certificate.jpg"),
        "category_certificate": os.path.join(app_dir, "category_certificate.jpg"),
        "marksheet": os.path.join(app_dir, "marksheet.jpg"),
        "id_proof_front": os.path.join(app_dir, "id_proof_front.jpg"),
        "id_proof_back": os.path.join(app_dir, "id_proof_back.jpg"),
        "bank_proof": os.path.join(app_dir, "bank_proof.jpg"),
    }

    # ~20% of documents get an extra "hard mode" scan degradation, so Role 1
    # (OCR) and Role 3 (forensics) have realistic messy inputs to test against
    # this week, not just clean renders. Never applied to the tampered doc
    # itself, so the tampering signal stays clean and demo-able.
    scan_quality = {}
    for doc_type in ["income_certificate", "category_certificate", "marksheet", "id_proof", "bank_proof"]:
        if doc_type == "income_certificate" and defect_type == "tampered_amount":
            scan_quality[doc_type] = "normal"
            continue
        scan_quality[doc_type] = random.choices(
            ["normal", "rotate", "blur", "lowres"], weights=[80, 7, 7, 6])[0]

    amount_bbox = render_income_certificate(
        fields["income_certificate"], paths["income_certificate"],
        degrade=None if scan_quality["income_certificate"] == "normal" else scan_quality["income_certificate"])
    render_category_certificate(
        fields["category_certificate"], paths["category_certificate"],
        degrade=None if scan_quality["category_certificate"] == "normal" else scan_quality["category_certificate"])
    render_marksheet(
        fields["marksheet"], paths["marksheet"],
        degrade=None if scan_quality["marksheet"] == "normal" else scan_quality["marksheet"])
    id_degrade = None if scan_quality["id_proof"] == "normal" else scan_quality["id_proof"]
    render_id_proof_front(fields["id_proof"], paths["id_proof_front"], degrade=id_degrade)
    render_id_proof_back(fields["id_proof"], paths["id_proof_back"], degrade=id_degrade)
    render_bank_proof(
        fields["bank_proof"], paths["bank_proof"],
        degrade=None if scan_quality["bank_proof"] == "normal" else scan_quality["bank_proof"])

    tampering_bbox = None
    if defect_type == "tampered_amount":
        apply_amount_tampering(paths["income_certificate"], amount_bbox, tampered_amount)
        tampering_bbox = amount_bbox
        fields["income_certificate"]["income_amount_displayed"] = tampered_amount

    make_bundle_pdf(app_dir, [paths["income_certificate"], paths["category_certificate"],
                              paths["marksheet"], paths["id_proof_front"], paths["id_proof_back"],
                              paths["bank_proof"]])

    # ---------------- Ground truth flags for this application ----------------
    expected_flags = []
    if defect_type == "expired":
        expected_flags.append({
            "severity": "HIGH", "category": "EXPIRED_DOCUMENT",
            "doc_type": "income_certificate",
            "message": f"Income certificate issue date {income_issue_date.isoformat()} is older than 1 year",
        })
    if defect_type == "name_typo":
        expected_flags.append({
            "severity": "MEDIUM", "category": "CROSS_DOC_MISMATCH",
            "doc_type": "category_certificate",
            "message": f"Name on Category Certificate ('{name_on_category_doc}') vs canonical name "
                       f"('{name}') -- likely OCR error, not fraud",
        })
    if defect_type == "tampered_amount":
        expected_flags.append({
            "severity": "HIGH", "category": "TAMPERING",
            "doc_type": "income_certificate",
            "message": "Income amount field shows signs of digital alteration",
            "bounding_box": tampering_bbox,
        })
    if defect_type == "duplicate_cert":
        expected_flags.append({
            "severity": "HIGH", "category": "DUPLICATE_CERTIFICATE",
            "doc_type": "income_certificate",
            "message": f"Certificate number {cert_no_income} already used in another application",
        })

    return {
        "application_id": app_id,
        "applicant_name": name,
        "is_defective": defect_type is not None,
        "defect_type": defect_type,
        "fields": fields,
        "scan_quality": scan_quality,
        "tampering_bounding_box": tampering_bbox,
        "duplicated_certificate_number": cert_no_income if defect_type == "duplicate_cert" else None,
        "expected_flags": expected_flags,
        "files": {
            "bundle_pdf": os.path.relpath(os.path.join(app_dir, "bundle.pdf"), OUT_DIR),
            **{k: os.path.relpath(v, OUT_DIR) for k, v in paths.items()},
        },
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # Exact mix required by the plan: 10 clean, 10 defective
    # (1 expired, 2 name typos, 2 modified amounts, 5 duplicate IDs)
    defect_plan = (
        ["expired"] * 1 +
        ["name_typo"] * 2 +
        ["tampered_amount"] * 2 +
        ["duplicate_cert"] * 5 +
        [None] * 10
    )
    random.shuffle(defect_plan)

    ground_truth = []
    generated_income_certs = []  # for picking a "donor" cert number for duplicates

    app_index = 1
    for defect_type in defect_plan:
        borrow_cert_from = None
        if defect_type == "duplicate_cert" and generated_income_certs:
            borrow_cert_from = random.choice(generated_income_certs)

        record = build_application(app_index, defect_type=defect_type,
                                    borrow_cert_from=borrow_cert_from)
        ground_truth.append(record)
        generated_income_certs.append(record["fields"]["income_certificate"]["certificate_number"])
        app_index += 1

    with open(os.path.join(OUT_DIR, "ground_truth.json"), "w") as f:
        json.dump(ground_truth, f, indent=2)

    # human-readable summary CSV
    with open(os.path.join(OUT_DIR, "ground_truth_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["application_id", "applicant_name", "is_defective", "defect_type", "expected_flag_count"])
        for r in ground_truth:
            w.writerow([r["application_id"], r["applicant_name"], r["is_defective"],
                        r["defect_type"], len(r["expected_flags"])])

    n_defective = sum(1 for r in ground_truth if r["is_defective"])
    print(f"Done. Generated {len(ground_truth)} applications in: {OUT_DIR}")
    print(f"  Clean: {len(ground_truth) - n_defective}   Defective: {n_defective}")
    print("  Ground truth: dataset/ground_truth.json")
    print("  Summary:      dataset/ground_truth_summary.csv")


if __name__ == "__main__":
    main()
