#!/usr/bin/env python3
"""
generate.py — CLI entry point for the golf-plaque Claude Code skill.

Generates a Bambu Studio .3mf plaque with three lines of engraved text,
using the sibling `plate_text.py` library and the packaged
`Frames/Mike Kallbrier.3mf` template.

Usage:
    python generate.py "Line 1" "Line 2" "Line 3" --out /path/to/plaque.3mf
"""

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a custom-text golf plaque as a Bambu Studio .3mf file.",
    )
    parser.add_argument("line1", help="First (top) line of text.")
    parser.add_argument("line2", help="Second (middle) line of text.")
    parser.add_argument("line3", help="Third (bottom) line of text.")
    parser.add_argument(
        "--out",
        required=True,
        metavar="PATH",
        help="Output path for the generated .3mf file.",
    )
    parser.add_argument(
        "--font",
        default="Helvetica",
        metavar="FONT_NAME",
        help=argparse.SUPPRESS,  # Hidden: Thomas wants Helvetica hardcoded.
    )
    args = parser.parse_args()

    # Import here so --help works even if deps aren't installed yet.
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)

    try:
        from plate_text import generate_plate_3mf
    except ImportError as exc:
        print(f"error: could not import plate_text ({exc}). "
              f"Install requirements: pip install -r requirements.txt",
              file=sys.stderr)
        return 1

    try:
        out_path = generate_plate_3mf(
            args.line1,
            args.line2,
            args.line3,
            output_path=args.out,
            font_family=args.font,
        )
    except Exception as exc:
        print(f"error: plaque generation failed: {exc}", file=sys.stderr)
        return 1

    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
