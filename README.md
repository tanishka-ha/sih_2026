# Document Forensics Analyzer

Detects visual pixel tampering and digital header manipulation in scanned document images. Built as **Role 3 (Tampering & Image Forensics)** for a Scholarship Document Verification System.

## What It Does

1. **EXIF Analysis** — Flags if the document was edited in Photoshop, GIMP, Canva, etc.
2. **Error Level Analysis (ELA)** — Detects pixel-level tampering by comparing JPEG compression artifacts
3. **Bounding Box Detection** — Draws precise `[x, y, w, h]` rectangles around tampered regions
4. **Confidence Scoring** — Assigns a 0.0–1.0 confidence score based on evidence strength
5. **Severity Classification** — Rates tampering from NONE → LOW → MEDIUM → HIGH → CRITICAL

## Installation

```bash
pip install opencv-python numpy piexif Pillow
```

## Quick Start

### Run the Demo
```bash
python demo.py
```
Generates a synthetic tampered document and runs the full analysis pipeline.

### Analyze Your Own Document
```bash
python main.py your_document.jpg --save-viz
```

### Use as a Library (for Role 4 Backend)
```python
from forensics import analyze_document_forensics

result = analyze_document_forensics("scanned_certificate.jpg")

if result["tampering_detected"]:
    print(f"Severity: {result['severity']}")
    print(f"Confidence: {result['confidence']}")
    for box in result["bounding_boxes"]:
        print(f"Tampered region at {box}")  # [x, y, w, h]
```

## Output JSON Format

```json
{
  "tampering_detected": true,
  "bounding_boxes": [[93, 56, 444, 52], [572, 404, 35, 39]],
  "severity": "high",
  "confidence": 0.27,
  "exif_flags": [],
  "ela_regions": [{"bounding_box": {"x": 93, "y": 56, "w": 444, "h": 52}, "mean_error": 18.39, "area": 18497}],
  "tamper_pixel_ratio": 0.05,
  "document_dimensions": [1200, 1600]
}
```

## Project Structure

| File | Purpose |
|------|---------|
| `forensics/exif_analysis.py` | EXIF header inspection (Photoshop, GIMP, Canva detection) |
| `forensics/ela_analysis.py` | Error Level Analysis + contour detection |
| `forensics/analyzer.py` | Main orchestrator combining all modules |
| `forensics/models.py` | Data models for the JSON output |
| `main.py` | CLI entry point |
| `demo.py` | Generates test documents and runs demo |

## Tech Stack

- **OpenCV** — Image processing, `cv2.absdiff`, contour detection
- **NumPy** — Array operations for ELA computation
- **Pillow** — JPEG re-compression and metadata extraction
- **piexif** — EXIF header parsing

## Team Integration

| Role | How They Use This |
|------|------------------|
| Role 4 (Backend) | Calls `analyze_document_forensics()` → gets JSON dict |
| Role 5 (Frontend) | Uses `bounding_boxes` `[x,y,w,h]` to draw red overlays |
| Role 6 (Test Data) | Provides sample JPEG documents for testing |
