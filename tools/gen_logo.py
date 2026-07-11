#!/usr/bin/env python3
"""PyA3EDA brand kit generator.

Draws the logo from a small declarative anchor table and writes every asset
the project needs into docs/assets/.

Design
------
Three reaction profiles over the "PyA3EDA" wordmark:
  black = uncatalyzed (tallest), red = intermediate surface,
  blue  = fully relaxed (lowest barrier).
Geometry was digitized from the original raster draft: red stays above blue
through blue's whole first bump; the single blue/red crossing sits at
half-width where blue rises out of its dip as red settles into its tail;
blue's second bump is the higher one; both tails descend monotonically and
settle flat at their endpoints (each tail's low point), blue ending just
below the black tail — a hair of clearance between the strokes, no overlap
(only the stroke-boosted favicon merges them, black on top).

Every curve is built by `spath()` from anchors of the form
    (x, y, tx, ty, len_in, len_out)
one point + ONE tangent direction per anchor, so tangent (G1) continuity is
guaranteed by construction and the node count is minimal.

One drawing, two optical sizes
------------------------------
All assets are built from the same anchor tables and profiles(). logo.svg and
the lockups share identical stroke proportions (logo.svg IS the lockup minus
the wordmark). favicon.svg (and every raster derived from it) thickens the
strokes for 16-48 px legibility only — never use it at display sizes.

Outputs (docs/assets/)
----------------------
  logo.svg                   square curves-only mark, true proportions
  logo-dark.svg              same, ink recolored for dark backgrounds
  favicon.svg                stroke-boosted micro-size mark (tabs, favicons)
  logo-header.svg            white mono boosted mark (docs header bar)
  logo-wordmark.svg          full lockup, wordmark converted to paths
  logo-wordmark-dark.svg     dark-background lockup
  logo-wordmark-src.svg      editable source (live <text>, needs Arial Black)
  favicon-16.png ... icon-512.png, apple-touch-icon.png, favicon.ico

Requires: inkscape (text->path + PNG export), Pillow (favicon.ico),
and the Arial Black font (msttcorefonts) for the wordmark.

Regenerating
------------
    python3 tools/check_logo.py   # after editing anchors: design + math audit
    python3 tools/gen_logo.py     # rebuild every asset (runs from anywhere)

This script lives in tools/ on purpose: mkdocs publishes everything under
docs/, so a script inside docs/assets/ would ship to the website. The
docs/assets path is resolved relative to this file, not the CWD.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from itertools import pairwise
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "docs" / "assets"

INK, INK_DARK = "#1c1c1c", "#f5f5f5"
RED = "#e8503b"
BLUE, BLUE_DARK = "#2b6cb8", "#4a8fd6"
WHITE = "#ffffff"  # mono header mark: white-on-primary header bars
FONT = "Arial Black"  # its own family; regular style IS the 900 weight
FONT_WEIGHT = "normal"  # converted to paths for distribution

# ---------------------------------------------------------------- curves ----
# (x, y, tx, ty, len_in, len_out): point, unit-ish tangent, handle lengths.
# Hand-aligned anchor columns:
# fmt: off
BLACK = [
    (12, 268,   1, -0.08, 0, 58),  # start: soft reactant plateau
    (148, 20,   1,   0, 58, 52),   # first peak (tallest)
    (305, 206,  1,   0, 70, 35),   # valley
    (383, 117,  1,   0, 38, 42),   # second peak
    (500, 240, 60,  15, 58,  9),   # descending tail, easing out
    (532, 244,  1,   0, 10,  0),   # end: settles flat at the tail's low point
]
RED_C = [
    (22, 294,  28,  -3,  0, 45),   # start: soft plateau
    (169, 150,  1,   0, 60, 42),   # peak (one cubic from the start: no joint)
    (313, 303, 83,  56, 75, 25),   # crossing point with blue (half-width)
    (375, 320,  1,  -0.03, 25, 35),  # tail sag
    (452, 310,  1,  -0.04, 22, 0),   # tail tip (~74% width)
]
BLUE_C = [
    (91, 342,  44,  -6,  0, 48),   # start (indented, lowest)
    (207, 247,  1,   0, 48, 34),   # first bump (stays below red)
    (291, 318,  1,   0, 36, 42),   # dip (locally below red)
    (385, 212,  1,   0, 44, 30),   # second bump (the higher one)
    (478, 251, 60,  14, 34, 12),   # descending tail, easing out
    (529, 257,  1,   0, 11,  0),   # end: settles flat at the tail's low point
]
# fmt: on


def spath(anchors) -> str:
    """Cubic-bezier path through anchors with G1-continuous joints."""

    def unit(tx, ty):
        n = math.hypot(tx, ty) or 1.0
        return tx / n, ty / n

    x0, y0 = anchors[0][:2]
    d = [f"M {x0:g},{y0:g}"]
    for (ax, ay, atx, aty, _, aout), (bx, by, btx, bty, bin_, _) in pairwise(anchors):
        aux, auy = unit(atx, aty)
        bux, buy = unit(btx, bty)
        c1 = (ax + aux * aout, ay + auy * aout)
        c2 = (bx - bux * bin_, by - buy * bin_)
        d.append(f"C {c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {bx:g},{by:g}")
    return " ".join(d)


def profiles(ink=INK, blue=BLUE, red=RED, sw_black=12.5, sw_other=10.5) -> str:
    # black is drawn LAST: at true strokes the tails no longer touch, but
    # the stroke-boosted favicon merges them and black must sit on top
    stroke = 'fill="none" stroke-linecap="round"'
    return "\n".join(
        f'<path d="{spath(a)}" {stroke} stroke="{c}" stroke-width="{w}"/>'
        for a, c, w in (
            (RED_C, red, sw_other),
            (BLUE_C, blue, sw_other),
            (BLACK, ink, sw_black),
        )
    )


# -------------------------------------------------------------- documents ---
# The wordmark must share the curves' exact ink extents (same left and right
# edge). Font metrics vary, so fit_wordmark() measures a probe render with
# inkscape and solves for the font size, x offset and baseline. Letter
# spacing is given in em so the fit scales linearly with font size.
CURVE_LEFT, CURVE_RIGHT = 5.75, 538.25  # profile ink extents incl. stroke
CAP_TOP = 376  # top of capitals (sets curve gap)
LS = "-0.016em"


def _wordmark_text(x, y, size, ink, blue) -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-family="{FONT}" '
        f'font-weight="{FONT_WEIGHT}" '
        f'font-size="{size:.2f}" letter-spacing="{LS}">'
        f'<tspan fill="{ink}">Py</tspan><tspan fill="{blue}">A3EDA</tspan></text>'
    )


def fit_wordmark(wd: Path):
    """Measure 'PyA3EDA' at size 100 and fit it to the curves' extents.

    Returns (x, baseline_y, font_size, canvas_height)."""
    probe = wd / "probe.svg"
    probe.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2000 600">'
        + _wordmark_text(0, 300, 100, INK, BLUE)
        + "</svg>"
    )
    out = subprocess.run(
        ["inkscape", str(probe), "--query-all"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    # first text/tspan bbox line that covers the whole string: use the union
    # of all reported boxes to be safe
    boxes = []
    for line in out.strip().splitlines():
        parts = line.split(",")
        if len(parts) == 5:
            _, x, y, w, h = parts
            boxes.append((float(x), float(y), float(w), float(h)))
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    target_w = CURVE_RIGHT - CURVE_LEFT
    size = 100 * target_w / (x1 - x0)
    scale = size / 100
    x = CURVE_LEFT - x0 * scale
    baseline = CAP_TOP - (y0 - 300) * scale  # bbox top -> CAP_TOP
    height = baseline + (y1 - 300) * scale + 8  # room for the y descender
    return x, baseline, size, math.ceil(height)


def lockup_svg(fit, ink=INK, blue=BLUE) -> str:
    x, baseline, size, height = fit
    width = math.ceil(CURVE_RIGHT + CURVE_LEFT)  # symmetric side margins
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">\n'
        f"{profiles(ink, blue)}\n"
        f"{_wordmark_text(x, baseline, size, ink, blue)}\n</svg>"
    )


def icon_svg(ink=INK, blue=BLUE, red=RED, boost=False) -> str:
    """Square curves-only mark.

    boost=False: exactly the lockup drawing without the wordmark (true stroke
    proportions). boost=True: thicker strokes for micro sizes (favicons,
    browser tabs) — an optical-size adaptation; at 16-48 px the thin true
    strokes vanish, and the blue/black tail convergence that the thick
    strokes merge is not resolvable anyway. Never use the boosted variant
    at display sizes."""
    sw = (22, 19) if boost else (12.5, 10.5)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        'width="512" height="512">\n<g transform="translate(10,98) scale(0.9)">\n'
        f"{profiles(ink, blue, red, sw_black=sw[0], sw_other=sw[1])}\n</g>\n</svg>"
    )


def text_to_path(src: Path, dst: Path) -> None:
    subprocess.run(
        ["inkscape", str(src), "--export-text-to-path", "--export-plain-svg", "-o", str(dst)],
        check=True,
        capture_output=True,
    )
    if not dst.exists():
        raise RuntimeError(f"inkscape produced no output: {dst}")


def export_png(svg: Path, png: Path, size: int) -> None:
    subprocess.run(
        ["inkscape", str(svg), "-w", str(size), "-h", str(size), "-o", str(png)],
        check=True,
        capture_output=True,
    )
    if not png.exists():
        raise RuntimeError(f"inkscape produced no output: {png}")


def main() -> int:
    if shutil.which("inkscape") is None:
        print("error: inkscape is required (text->path, PNG export)")
        return 1
    ASSETS.mkdir(parents=True, exist_ok=True)

    # Snap-packaged inkscape cannot read/write some paths (notably ~/bin and
    # hidden dirs), and it exits 0 even when an export fails - so do all
    # inkscape I/O in a plain top-level home workdir and copy results over.
    wd = Path.home() / "pya3eda_logo_build"
    wd.mkdir(exist_ok=True)
    try:
        # icons (curves only, square): logo.svg = the lockup drawing minus
        # the wordmark; favicon.svg = stroke-boosted micro-size variant;
        # logo-header.svg = white mono boosted mark for the docs header bar
        # (on the indigo header the colored strokes drop to ~1.3-2.5:1
        # contrast, so the header gets the standard white-on-primary mark)
        (ASSETS / "logo.svg").write_text(icon_svg())
        (ASSETS / "logo-dark.svg").write_text(icon_svg(INK_DARK, BLUE_DARK))
        (ASSETS / "favicon.svg").write_text(icon_svg(boost=True))
        (ASSETS / "logo-header.svg").write_text(icon_svg(WHITE, WHITE, WHITE, boost=True))
        (wd / "favicon.svg").write_text(icon_svg(boost=True))

        # full lockups: fit the wordmark to the curves' width, author with
        # live text, then flatten to paths
        fit = fit_wordmark(wd)
        (ASSETS / "logo-wordmark-src.svg").write_text(lockup_svg(fit))
        (wd / "light.svg").write_text(lockup_svg(fit))
        (wd / "dark.svg").write_text(lockup_svg(fit, INK_DARK, BLUE_DARK))
        text_to_path(wd / "light.svg", wd / "logo-wordmark.svg")
        text_to_path(wd / "dark.svg", wd / "logo-wordmark-dark.svg")
        shutil.copy2(wd / "logo-wordmark.svg", ASSETS / "logo-wordmark.svg")
        shutil.copy2(wd / "logo-wordmark-dark.svg", ASSETS / "logo-wordmark-dark.svg")

        # favicon / app icon rasters from the boosted micro-size mark
        sizes = {
            "favicon-16.png": 16,
            "favicon-32.png": 32,
            "favicon-48.png": 48,
            "apple-touch-icon.png": 180,
            "icon-192.png": 192,
            "icon-512.png": 512,
        }
        for name, px in sizes.items():
            export_png(wd / "favicon.svg", wd / name, px)
            shutil.copy2(wd / name, ASSETS / name)

        try:
            from PIL import Image

            img = Image.open(ASSETS / "favicon-48.png")
            img.save(ASSETS / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
            print("wrote favicon.ico (16/32/48)")
        except ImportError:
            print("Pillow not found - skipped favicon.ico")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    print(f"brand kit written to {ASSETS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
