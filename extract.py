import json
import os
import re
import cv2
import numpy as np
import pytesseract
from PIL import Image
from rapidfuzz import fuzz

os.chdir(os.path.dirname(os.path.abspath(__file__)))

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# Each field says HOW to find it, not just what it is called.
#   ("right",   "Label")  value sits to the right of the label
#   ("above",   "Label")  value sits on the line above (unlabelled fields)
#   ("pattern", regex)    no label at all - match the value's own shape
DOC_FIELDS = {
    "income_certificate": {
        "certificate_number": ("right", "Certificate No"),
        "name":               ("right", "Name"),
        "father_name":        ("right", "Father's Name"),
        "dob":                ("right", "Date of Birth"),
        "district":           ("right", "District"),
        "issue_date":         ("right", "Issue Date"),
        "income_amount":      ("right", "Annual Income"),
    },
    "category_certificate": {
        "certificate_number": ("right", "Certificate No"),
        "name":               ("right", "Name"),
        "father_name":        ("right", "Father's Name"),
        "dob":                ("right", "Date of Birth"),
        "category":           ("right", "Category"),
        "issue_date":         ("right", "Issue Date"),
    },
    "marksheet": {
        "roll_number":        ("right", "Roll Number"),
        "name":               ("right", "Name"),
        "father_name":        ("right", "Father's Name"),
        "dob":                ("right", "Date of Birth"),
        "exam_year":          ("right", "Exam Year"),
        "percentage":         ("right", "Percentage"),
    },
    "bank_proof": {
        "name":               ("right", "Account Holder"),
        "bank_name":          ("right", "Bank Name"),
        "account_number":     ("right", "Account Number"),
        "ifsc":               ("right", "IFSC Code"),
    },
    "id_proof_front": {
        "dob":                ("right", "DOB"),
        "gender":             ("right", "Gender"),
        "name":               ("above", "DOB"),
    },
    "id_proof_back": {
        "id_number":          ("right", "ID No"),
        "address":            ("above", "ID No"),
    },
    "default": {
        "name":               ("right", "Name"),
        "date":               ("right", "Date"),
        "number":             ("right", "Number"),
    },
}


def deskew(img):
    """Straighten a tilted scan before OCR.

    Tilt breaks the same-line test: a label and its value end up at
    different heights, so the value is never found.
    """
    arr = np.array(img.convert("L"))
    inverted = cv2.bitwise_not(arr)
    mask = cv2.threshold(inverted, 0, 255,
                         cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

    coords = np.column_stack(np.where(mask > 0))
    if len(coords) < 50:
        return img

    angle = cv2.minAreaRect(coords)[-1]
    if angle > 45:
        angle -= 90

    if abs(angle) < 0.3 or abs(angle) > 15:
        return img

    h, w = arr.shape
    matrix = cv2.getRotationMatrix2D((w // 2, h // 2), -angle, 1.0)
    rotated = cv2.warpAffine(np.array(img), matrix, (w, h),
                             flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(rotated)


def load_pages(path):
    if path.lower().endswith(".pdf"):
        from pdf2image import convert_from_path
        return convert_from_path(path, dpi=300)
    return [Image.open(path)]


def get_words(img, preprocess=False, straighten=True):
    if straighten:
        img = deskew(img)

    if preprocess:
        arr = np.array(img.convert("L"))
        thresh = cv2.adaptiveThreshold(
            arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
        img = Image.fromarray(thresh)

    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    words = []
    for i in range(len(data["text"])):
        word = data["text"][i].strip()
        conf = int(data["conf"][i])
        if word != "" and conf > 0:
            words.append({
                "text": word,
                "x": data["left"][i],
                "y": data["top"][i],
                "w": data["width"][i],
                "h": data["height"][i],
                "cy": data["top"][i] + data["height"][i] / 2,
                "conf": conf,
            })
    return words


def looks_wrong(text):
    stripped = text.replace(" ", "").replace("|", "")
    if stripped == "":
        return True
    letters = sum(1 for c in stripped if c.isalpha())
    digits = sum(1 for c in stripped if c.isdigit())
    return letters > 0 and digits > 0 and letters >= digits


def pack(group):
    group = list(group)
    while group and group[0]["text"].strip() in {":", "-"}:
        group.pop(0)
    if not group:
        return None

    text = " ".join(w["text"] for w in group).strip(": ")
    lowest = min(w["conf"] for w in group)

    left = min(w["x"] for w in group)
    top = min(w["y"] for w in group)
    right = max(w["x"] + w["w"] for w in group)
    bottom = max(w["y"] + w["h"] for w in group)

    return {
        "value": text,
        "conf": lowest,
        "bbox": [left, top, right - left, bottom - top],
        "needs_review": lowest < 60 or looks_wrong(text),
    }


def find_anchor(label, words, top_skip=0):
    """Match a label across 1-3 consecutive words on the same line.

    Single-word matching cannot tell 'Account Holder' from 'Account
    Number', or 'Name' from "Father's Name". Matching the phrase can.
    """
    expected = len(label.split())
    best_score, best_span = 0, None

    for i in range(len(words)):
        if words[i]["y"] < top_skip:
            continue
        for span in range(1, 4):
            group = words[i:i + span]
            if len(group) < span:
                break
            if any(abs(g["cy"] - group[0]["cy"]) > group[0]["h"] * 0.6 for g in group):
                break

            phrase = " ".join(g["text"] for g in group).strip(":")
            score = fuzz.ratio(label.lower(), phrase.lower())
            if span == expected:
                score += 5
            if score > 82 and score > best_score:
                best_score, best_span = score, group

    return best_span


def find_right(label, words, top_skip=0):
    group = find_anchor(label, words, top_skip)
    if not group:
        return None
    first, last = group[0], group[-1]
    label_right = last["x"] + last["w"]

    found = [w for w in words
             if abs(w["cy"] - first["cy"]) < first["h"] * 0.85
             and w["x"] > label_right
             and w["x"] - label_right < 400]

    if not found:
        found = [w for w in words
                 if first["y"] < w["y"] < first["y"] + 60
                 and abs(w["x"] - first["x"]) < 200]

    if not found:
        return None
    found.sort(key=lambda w: w["x"])
    return pack(found)


def find_above(label, words, top_skip=0):
    """For unlabelled fields: take the line directly above a known label."""
    group = find_anchor(label, words, top_skip)
    if not group:
        return None
    anchor = group[0]

    above = [w for w in words if w["cy"] < anchor["cy"] - anchor["h"] * 0.6]
    if not above:
        return None

    nearest = max(w["cy"] for w in above)
    line = [w for w in above if abs(w["cy"] - nearest) < anchor["h"] * 0.9]
    line.sort(key=lambda w: w["x"])
    return pack(line) if line else None


def find_pattern(pattern, words):
    """No label at all: match the value's own shape, e.g. 1234 5678 9012."""
    for i in range(len(words)):
        for span in (1, 2, 3, 4):
            group = words[i:i + span]
            if len(group) < span:
                break
            if any(abs(g["cy"] - group[0]["cy"]) > group[0]["h"] * 0.6 for g in group):
                break
            if re.fullmatch(pattern, " ".join(g["text"] for g in group)):
                return pack(group)
    return None


def extract(file_path, doc_type="default", preprocess=False, straighten=True):
    plan = DOC_FIELDS.get(doc_type, DOC_FIELDS["default"])
    pages = load_pages(file_path)

    all_pages = []
    total_words = 0

    for page_num, img in enumerate(pages, start=1):
        words = get_words(img, preprocess, straighten)
        total_words += len(words)

        page_height = max((w["y"] for w in words), default=1000)
        top_skip = int(page_height * 0.12)

        fields = {}
        for name, (how, what) in plan.items():
            if how == "right":
                field = find_right(what, words, top_skip)
            elif how == "above":
                field = find_above(what, words, top_skip)
            elif how == "pattern":
                field = find_pattern(what, words)
            else:
                field = None
            if field:
                fields[name] = field

        all_pages.append({
            "page": page_num,
            "word_count": len(words),
            "fields": fields,
        })

    return {
        "source_file": file_path,
        "doc_type": doc_type,
        "page_count": len(pages),
        "total_words": total_words,
        "pages": all_pages,
    }


if __name__ == "__main__":
    out = extract("dataset/APP-2026-0003/id_proof_front.jpg", "id_proof_front")
    print(json.dumps(out, indent=2))