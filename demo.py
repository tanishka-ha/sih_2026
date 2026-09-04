#!/usr/bin/env python3
"""
Demo & Test Script for Document Forensics Analyzer
=====================================================
Generates a synthetic document with deliberate tampered regions,
then runs the forensics pipeline to demonstrate detection capabilities.

Usage:
    python demo.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# Project imports
from forensics.analyzer import DocumentForensicsAnalyzer, analyze_document_forensics


DEMO_DIR = Path(__file__).parent / "demo_output"


def create_synthetic_document() -> Path:
    """Create a synthetic document image with deliberate tampered regions.

    This simulates a scanned document where specific text regions have been
    digitally altered — the altered regions will have different JPEG
    compression characteristics than the original.

    Returns:
        Path to the generated test document.
    """
    DEMO_DIR.mkdir(exist_ok=True)

    width, height = 1200, 1600
    # Light paper background with subtle texture
    np.random.seed(42)
    paper = np.full((height, width, 3), 245, dtype=np.uint8)
    noise = np.random.normal(0, 3, paper.shape).astype(np.int16)
    paper = np.clip(paper.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # -- Draw "original" text lines (dark gray, simulating printed text) --
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_color = (40, 40, 40)

    # Header
    cv2.putText(paper, "OFFICIAL DOCUMENT", (100, 100), font, 1.5, text_color, 3)
    cv2.putText(paper, "Certificate No: DOC-2025-04821", (100, 180), font, 0.8, text_color, 2)

    # Body text
    lines = [
        "This document certifies that the holder has completed",
        "all required assessments and evaluations for the year",
        "ending December 31, 2025. The total score achieved was",
        "78 out of 100 points, corresponding to a Grade B rating.",
        "",
        "Issued by: Central Verification Authority",
        "Date: January 15, 2026",
        "Authorized Signatory: Dr. A. Kumar",
    ]
    for i, line in enumerate(lines):
        y = 300 + i * 50
        cv2.putText(paper, line, (100, y), font, 0.6, text_color, 1)

    # First: save as high-quality JPEG to establish baseline compression
    baseline_path = DEMO_DIR / "baseline.jpg"
    cv2.imwrite(str(baseline_path), paper, [cv2.IMWRITE_JPEG_QUALITY, 95])

    # Reload the baseline (this now has JPEG artifacts)
    document = cv2.imread(str(baseline_path))

    # -- TAMPER REGION 1: Alter the score (78 → 98) --
    # Draw a white rectangle over "78" and write "98"
    tamper1_roi = (570, 430, 90, 40)  # x, y, w, h
    x, y, w, h = tamper1_roi
    cv2.rectangle(document, (x, y - h), (x + w, y), (245, 245, 245), -1)
    cv2.putText(document, "98", (x + 5, y - 5), font, 0.6, text_color, 1)

    # -- TAMPER REGION 2: Alter the grade (B → A) --
    tamper2_roi = (890, 430, 50, 40)
    x, y, w, h = tamper2_roi
    cv2.rectangle(document, (x, y - h), (x + w, y), (245, 245, 245), -1)
    cv2.putText(document, "A", (x + 10, y - 5), font, 0.6, text_color, 1)

    # -- TAMPER REGION 3: Alter the date --
    tamper3_roi = (280, 530, 200, 40)
    x, y, w, h = tamper3_roi
    cv2.rectangle(document, (x, y - h), (x + w, y), (245, 245, 245), -1)
    cv2.putText(document, "March 20, 2026", (x + 5, y - 5), font, 0.6, text_color, 1)

    # Save the tampered document with slightly different quality
    # (simulating re-save after editing)
    tampered_path = DEMO_DIR / "tampered_document.jpg"
    cv2.imwrite(str(tampered_path), document, [cv2.IMWRITE_JPEG_QUALITY, 92])

    print(f"✓ Synthetic tampered document created: {tampered_path}")
    print(f"  Tampered regions:")
    print(f"    1. Score changed (78→98): {tamper1_roi}")
    print(f"    2. Grade changed (B→A):   {tamper2_roi}")
    print(f"    3. Date changed:          {tamper3_roi}")

    return tampered_path


def create_clean_document() -> Path:
    """Create a clean (unaltered) document for comparison."""
    DEMO_DIR.mkdir(exist_ok=True)

    width, height = 1200, 1600
    paper = np.full((height, width, 3), 245, dtype=np.uint8)
    np.random.seed(99)
    noise = np.random.normal(0, 2, paper.shape).astype(np.int16)
    paper = np.clip(paper.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    font = cv2.FONT_HERSHEY_SIMPLEX
    text_color = (40, 40, 40)

    cv2.putText(paper, "CLEAN REFERENCE DOCUMENT", (100, 100), font, 1.2, text_color, 3)
    cv2.putText(paper, "This document has not been altered.", (100, 200), font, 0.7, text_color, 1)
    cv2.putText(paper, "It should produce no tampering flags.", (100, 250), font, 0.7, text_color, 1)

    clean_path = DEMO_DIR / "clean_document.jpg"
    cv2.imwrite(str(clean_path), paper, [cv2.IMWRITE_JPEG_QUALITY, 95])

    print(f"✓ Clean reference document created: {clean_path}")
    return clean_path


def run_demo():
    """Run the full demo pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(levelname)-7s │ %(message)s",
        datefmt="%H:%M:%S",
    )

    print("=" * 70)
    print("  DOCUMENT FORENSICS ANALYZER — DEMO")
    print("=" * 70)
    print()

    # Step 1: Generate test documents
    print("─" * 70)
    print("STEP 1: Generating synthetic test documents")
    print("─" * 70)
    tampered_path = create_synthetic_document()
    clean_path = create_clean_document()
    print()

    # Step 2: Analyze tampered document
    print("─" * 70)
    print("STEP 2: Analyzing TAMPERED document")
    print("─" * 70)
    analyzer = DocumentForensicsAnalyzer(
        ela_quality=90,
        ela_scale=15,
        ela_threshold=40,
        min_area=150,
        save_visualizations=True,
    )
    tampered_result = analyzer.analyze(tampered_path, DEMO_DIR)
    print()

    # Step 3: Analyze clean document
    print("─" * 70)
    print("STEP 3: Analyzing CLEAN document")
    print("─" * 70)
    clean_result = analyzer.analyze(clean_path, DEMO_DIR)
    print()

    # Step 4: Show comparative results
    print("=" * 70)
    print("  COMPARATIVE RESULTS")
    print("=" * 70)
    print()

    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│ TAMPERED DOCUMENT                                              │")
    print("├─────────────────────────────────────────────────────────────────┤")
    print(f"│ Tampering Detected : {tampered_result.tampering_detected!s:<43}│")
    print(f"│ Severity           : {tampered_result.severity.value.upper():<43}│")
    print(f"│ Confidence         : {tampered_result.confidence:<43}│")
    print(f"│ Bounding Boxes     : {len(tampered_result.bounding_boxes):<43}│")
    print(f"│ Tamper Pixel Ratio : {tampered_result.tamper_pixel_ratio:<43}│")
    print("└─────────────────────────────────────────────────────────────────┘")

    for i, bb in enumerate(tampered_result.bounding_boxes):
        print(f"  Box {i+1}: [x={bb[0]}, y={bb[1]}, w={bb[2]}, h={bb[3]}]")

    print()
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│ CLEAN DOCUMENT                                                 │")
    print("├─────────────────────────────────────────────────────────────────┤")
    print(f"│ Tampering Detected : {clean_result.tampering_detected!s:<43}│")
    print(f"│ Severity           : {clean_result.severity.value.upper():<43}│")
    print(f"│ Confidence         : {clean_result.confidence:<43}│")
    print(f"│ Bounding Boxes     : {len(clean_result.bounding_boxes):<43}│")
    print("└─────────────────────────────────────────────────────────────────┘")

    # Step 5: Output standardized JSON (as Role 4 would receive it)
    print()
    print("─" * 70)
    print("STANDARDIZED JSON OUTPUT (for Role 4 / Backend Orchestrator)")
    print("─" * 70)
    json_output = tampered_result.to_json(indent=2)
    print(json_output)

    # Save JSON to file
    json_path = DEMO_DIR / "forensics_result.json"
    json_path.write_text(json_output)
    print(f"\n✓ Full JSON result saved to: {json_path}")

    # Step 6: Using the convenience function (Role 4 API)
    print()
    print("─" * 70)
    print("API USAGE EXAMPLE (analyze_document_forensics)")
    print("─" * 70)
    print()
    print("  from forensics import analyze_document_forensics")
    print()
    print("  result = analyze_document_forensics('document.jpg')")
    print("  if result['tampering_detected']:")
    print("      for box in result['bounding_boxes']:")
    print("          print(f'Tampered region at {box}')")
    print()

    return tampered_result, clean_result


if __name__ == "__main__":
    run_demo()
