"""
Role 1: OCR and Document Field Extraction Engine
================================================
Extracts text, identifies key-value anchors using fuzzy matching,
and computes bounding boxes and confidence metrics.
"""

import json
import cv2
import numpy as np
import pytesseract
from PIL import Image
from rapidfuzz import fuzz

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


DOC_LABELS = {
    "aadhaar":            ["NAME", "DOB", "AADHAAR", "FATHER"],
    "pan":                ["NAME", "FATHER", "DATE"],
    "voter_id":           ["NAME", "FATHER", "AGE", "ADDRESS"],
    "driving_licence":    ["NAME", "DOB", "ADDRESS", "VALID"],
    "birth_certificate":  ["NAME", "BIRTH", "FATHER", "MOTHER", "PLACE"],
    "marksheet":          ["NAME", "ROLL", "FATHER", "SCHOOL", "YEAR"],
    "ration_card":        ["NAME", "ADDRESS", "MEMBERS"],
    "income_certificate": ["NAME", "INCOME", "FATHER", "DATE"],
    "caste_certificate":  ["NAME", "CASTE", "FATHER", "DATE"],
    "domicile":           ["NAME", "ADDRESS", "FATHER", "DATE"],
    "default":            ["NAME", "DATE", "NUMBER"]
}


def load_pages(path):
    if str(path).lower().endswith(".pdf"):
        from pdf2image import convert_from_path
        return convert_from_path(str(path), dpi=300)
    else:
        return [Image.open(str(path))]


def get_words(img, preprocess=False):
    if preprocess:
        arr = np.array(img.convert("L"))
        thresh = cv2.adaptiveThreshold(arr, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
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
                "conf": conf
            })
    return words


def looks_wrong(text):
    stripped = text.replace(" ", "").replace("|", "")
    if stripped == "":
        return True
    letters = sum(1 for c in stripped if c.isalpha())
    digits = sum(1 for c in stripped if c.isdigit())
    if letters > 0 and digits > 0 and letters >= digits:
        return True
    return False


def find_field(label, words):
    anchor = None
    best_score = 0
    for w in words:
        candidate = w["text"].lower().strip(":")
        score = fuzz.ratio(label.lower(), candidate)
        if score > 80 and score > best_score:
            best_score = score
            anchor = w

    if anchor is None:
        return None

    right = []
    for w in words:
        same_line = abs(w["y"] - anchor["y"]) < anchor["h"]
        to_right = w["x"] > anchor["x"] + anchor["w"]
        close_enough = w["x"] - (anchor["x"] + anchor["w"]) < 300
        if same_line and to_right and close_enough:
            right.append(w)

    found = right
    if not found:
        below = []
        for w in words:
            is_below = anchor["y"] < w["y"] < anchor["y"] + 60
            aligned = abs(w["x"] - anchor["x"]) < 200
            if is_below and aligned:
                below.append(w)
        found = below

    if not found:
        return None

    found.sort(key=lambda w: w["x"])

    text = " ".join(m["text"] for m in found).strip(": ")
    lowest = min(m["conf"] for m in found)

    left = min(m["x"] for m in found)
    top = min(m["y"] for m in found)
    right_edge = max(m["x"] + m["w"] for m in found)
    bottom = max(m["y"] + m["h"] for m in found)

    return {
        "value": text,
        "conf": lowest,
        "bbox": [left, top, right_edge - left, bottom - top],
        "needs_review": lowest < 60 or looks_wrong(text)
    }


def extract(file_path, doc_type="default", preprocess=False):
    labels = DOC_LABELS.get(doc_type, DOC_LABELS["default"])
    pages = load_pages(file_path)

    all_pages = []
    total_words = 0

    for page_num, img in enumerate(pages, start=1):
        words = get_words(img, preprocess)
        total_words += len(words)

        fields = {}
        for label in labels:
            field = find_field(label, words)
            if field:
                fields[label.lower()] = field

        all_pages.append({
            "page": page_num,
            "word_count": len(words),
            "fields": fields
        })

    return {
        "source_file": str(file_path),
        "doc_type": doc_type,
        "page_count": len(pages),
        "total_words": total_words,
        "pages": all_pages
    }
