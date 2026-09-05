#!/usr/bin/env python3
"""
Document Forensics CLI
========================
Command-line interface for analyzing document images for tampering.

Usage:
    python main.py <image_path> [options]
    python main.py --batch <dir_path> [options]

Examples:
    python main.py document.jpg
    python main.py document.jpg --save-viz --output results.json
    python main.py --batch ./documents/ --min-area 200 --threshold 50
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from forensics.analyzer import DocumentForensicsAnalyzer, analyze_document_forensics


def setup_logging(verbose: bool = False) -> None:
    """Configure logging output."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Document Forensics Analyzer — Detect pixel tampering and header manipulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s scan.jpg                          Analyze a single document
  %(prog)s scan.jpg --save-viz               Analyze and save ELA visualization
  %(prog)s --batch ./docs/ --output out.json Batch analyze a directory
  %(prog)s scan.jpg -v --threshold 30        Verbose mode with custom threshold
        """,
    )

    # Input
    parser.add_argument(
        "image",
        nargs="?",
        help="Path to a single document image to analyze",
    )
    parser.add_argument(
        "--batch",
        metavar="DIR",
        help="Directory of images to batch-analyze",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generate synthetic demo files and run complete demo test pipeline",
    )

    # ELA parameters
    params = parser.add_argument_group("ELA Parameters")
    params.add_argument(
        "--quality",
        type=int,
        default=90,
        help="JPEG re-compression quality (default: 90)",
    )
    params.add_argument(
        "--scale",
        type=int,
        default=15,
        help="Error amplification scale factor (default: 15)",
    )
    params.add_argument(
        "--threshold",
        type=int,
        default=40,
        help="Binary threshold for anomaly detection (default: 40)",
    )
    params.add_argument(
        "--min-area",
        type=int,
        default=150,
        help="Minimum contour area for noise suppression (default: 150)",
    )

    # Output
    output = parser.add_argument_group("Output Options")
    output.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Write JSON results to file (default: stdout)",
    )
    output.add_argument(
        "--save-viz",
        action="store_true",
        help="Save ELA visualization images",
    )
    output.add_argument(
        "--viz-dir",
        metavar="DIR",
        help="Directory for visualization output (default: same as input)",
    )

    # Misc
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose/debug logging",
    )

    return parser.parse_args()


def analyze_single(args: argparse.Namespace) -> dict:
    """Analyze a single document image."""
    return analyze_document_forensics(
        args.image,
        ela_quality=args.quality,
        ela_scale=args.scale,
        ela_threshold=args.threshold,
        min_area=args.min_area,
        save_visualization=args.save_viz,
        visualization_dir=args.viz_dir,
    )


def analyze_directory(args: argparse.Namespace) -> dict:
    """Batch-analyze all images in a directory."""
    batch_dir = Path(args.batch)
    if not batch_dir.is_dir():
        print(f"Error: {batch_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    extensions = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}
    image_paths = sorted(
        p for p in batch_dir.iterdir()
        if p.suffix.lower() in extensions and p.is_file()
    )

    if not image_paths:
        print(f"No image files found in {batch_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(image_paths)} images in {batch_dir}")

    analyzer = DocumentForensicsAnalyzer(
        ela_quality=args.quality,
        ela_scale=args.scale,
        ela_threshold=args.threshold,
        min_area=args.min_area,
        save_visualizations=args.save_viz,
    )

    results_map = analyzer.analyze_batch(image_paths, args.viz_dir)

    # Convert to serializable dict
    return {
        name: result.to_dict() for name, result in results_map.items()
    }


def main():
    args = parse_args()
    setup_logging(args.verbose)

    if args.demo:
        from demo import run_demo
        run_demo()
        return

    if not args.image and not args.batch:
        print("Error: Provide an image path, --batch directory, or --demo flag", file=sys.stderr)
        sys.exit(1)

    # Run analysis
    if args.batch:
        results = analyze_directory(args)
    else:
        if not Path(args.image).exists():
            print(f"Error: File not found: {args.image}", file=sys.stderr)
            sys.exit(1)
        results = analyze_single(args)

    # Output
    json_output = json.dumps(results, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json_output)
        print(f"\nResults written to {output_path}")
    else:
        print("\n" + "=" * 60)
        print("FORENSICS ANALYSIS RESULTS")
        print("=" * 60)
        print(json_output)


if __name__ == "__main__":
    main()
