#!/usr/bin/env python3
"""Convert MusicXML files to SVG for static score display.

Uses verovio to render each page then stacks them into one tall SVG so the
entire score is visible in a single <img> element.

Usage:
    python3 scripts/07_generate_svg.py <input.musicxml> [<output.svg>]
    python3 scripts/07_generate_svg.py --dir <scores_dir>   # convert all *.musicxml in dir

When --dir is given, each <name>.musicxml produces <name>.svg beside it.
If output.svg is omitted in single-file mode, writes <input>.svg beside the input.

Requires: pip install verovio
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Matches the opening <svg ...> tag (including multi-line attribute spans)
_SVG_OPEN_RE = re.compile(r"<svg\b[^>]*>", re.DOTALL)
# Extracts width and height from the opening <svg> tag
_DIM_RE = re.compile(r'\b(width|height)="(\d+(?:\.\d+)?)px"')


def _get_attr(tag: str, name: str) -> str | None:
    m = re.search(rf'\b{re.escape(name)}="([^"]*)"', tag)
    return m.group(1) if m else None


def _parse_dim(tag: str, attr: str) -> float:
    for m in _DIM_RE.finditer(tag):
        if m.group(1) == attr:
            return float(m.group(2))
    return 0.0


def convert(xml_path: Path, svg_path: Path) -> None:
    import verovio  # type: ignore[import]

    tk = verovio.toolkit()
    tk.setOptions({
        "pageWidth": 2100,
        "adjustPageHeight": True,
        "scale": 35,
        "spacingSystem": 12,
        "spacingStaff": 8,
        "breaks": "auto",
    })
    if not tk.loadFile(str(xml_path)):
        raise RuntimeError(f"verovio failed to load {xml_path}")

    n_pages = tk.getPageCount()
    pages = [tk.renderToSVG(i) for i in range(1, n_pages + 1)]

    if n_pages == 1:
        svg_path.write_text(pages[0], encoding="utf-8")
    else:
        svg_path.write_text(_stack_pages(pages), encoding="utf-8")

    print(f"[svg] {xml_path.name} → {svg_path.name} ({n_pages} page(s))")


def _stack_pages(pages: list[str]) -> str:
    """Combine per-page SVGs into one tall SVG by stacking vertically."""
    widths: list[float] = []
    heights: list[float] = []
    inner_svgs: list[str] = []

    for svg in pages:
        m = _SVG_OPEN_RE.search(svg)
        if not m:
            continue
        tag = m.group(0)
        widths.append(_parse_dim(tag, "width"))
        heights.append(_parse_dim(tag, "height"))
        # Extract content between opening and closing <svg> tags
        inner = svg[m.end():]
        inner = inner.rsplit("</svg>", 1)[0]
        inner_svgs.append(inner)

    total_width = max(widths, default=735)
    total_height = sum(heights)
    gap = 8  # pixels between pages
    total_height += gap * (len(heights) - 1)

    # Inherit id and color from the first page so CSS selectors like
    # `#<id> path { stroke:currentColor }` that verovio emits continue to match.
    first_match = _SVG_OPEN_RE.search(pages[0])
    first_tag = first_match.group(0) if first_match else ""
    root_id = _get_attr(first_tag, "id")
    root_color = _get_attr(first_tag, "color")
    id_attr = f' id="{root_id}"' if root_id else ""
    color_attr = f' color="{root_color}"' if root_color else ""
    lines: list[str] = [
        f'<svg width="{total_width:.0f}px" height="{total_height:.0f}px"'
        ' version="1.1"'
        ' xmlns="http://www.w3.org/2000/svg"'
        ' xmlns:xlink="http://www.w3.org/1999/xlink"'
        f' overflow="visible"{id_attr}{color_attr}>',
    ]

    y_offset = 0.0
    for i, (inner, h) in enumerate(zip(inner_svgs, heights)):
        lines.append(f'  <g transform="translate(0,{y_offset:.0f})">')
        lines.append(inner)
        lines.append("  </g>")
        y_offset += h + gap

    lines.append("</svg>")
    return "\n".join(lines)


def convert_dir(scores_dir: Path) -> int:
    xmls = list(scores_dir.glob("*.musicxml"))
    if not xmls:
        print(f"[svg] No .musicxml files found in {scores_dir}")
        return 0
    for xml in sorted(xmls):
        convert(xml, xml.with_suffix(".svg"))
    return len(xmls)


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert MusicXML to SVG via verovio")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("input", nargs="?", metavar="INPUT.musicxml",
                       help="Single MusicXML file to convert")
    group.add_argument("--dir", metavar="DIR",
                       help="Directory: convert all *.musicxml files inside")
    ap.add_argument("output", nargs="?", metavar="OUTPUT.svg",
                    help="Output SVG path (single-file mode only; default: same dir as input)")
    args = ap.parse_args()

    try:
        import verovio  # noqa: F401
    except ImportError:
        print("ERROR: verovio is not installed. Run: pip install verovio", file=sys.stderr)
        sys.exit(1)

    if args.dir:
        d = Path(args.dir)
        if not d.is_dir():
            print(f"ERROR: not a directory: {d}", file=sys.stderr)
            sys.exit(1)
        n = convert_dir(d)
        print(f"[svg] Converted {n} file(s) in {d}")
    else:
        xml = Path(args.input)
        if not xml.exists():
            print(f"ERROR: file not found: {xml}", file=sys.stderr)
            sys.exit(1)
        svg = Path(args.output) if args.output else xml.with_suffix(".svg")
        convert(xml, svg)


if __name__ == "__main__":
    main()
