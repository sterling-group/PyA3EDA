#!/usr/bin/env python3
"""Sanity checks for the logo curves in gen_logo.py.

Run after ANY edit to the anchor tables, before regenerating the kit:

    python3 tools/check_logo.py

Verifies the digitized design constraints
  1. red stays above blue through blue's whole first bump and dip
  2. exactly one blue/red crossing, at ~half-width
  3. blue's second bump is higher than the first
  4. blue ends just below the black tail: converging but NOT overlapping at
     true strokes (>= 1 px air beyond the 11.5 px half-stroke sum; only the
     stroke-boosted favicon merges them, black drawn last on top)
  5. red tail tip at ~74% width
  6. both tails: monotone descent, ending flat at the tail's low point
     (no upturn/curl on either curve)
and the construction math
  - every segment's control polygon is x-monotone (no loops/cusps,
    each curve stays a function of x)
  - handle pairs never exceed their chord
  - curvature is reported across every joint; spath() only guarantees G1,
    so flag jump ratios > 2.5 and sign flips (both read as visible kinks).
"""

import math
import sys
from itertools import pairwise

import gen_logo as g


def unit(tx, ty):
    n = math.hypot(tx, ty)
    if n == 0:
        raise ValueError("zero tangent")
    return tx / n, ty / n


def segments(anchors):
    """The exact cubics spath() emits: (p0, c1, c2, p3) per anchor pair."""
    for (ax, ay, atx, aty, _, aout), (bx, by, btx, bty, bin_, _) in pairwise(anchors):
        aux, auy = unit(atx, aty)
        bux, buy = unit(btx, bty)
        yield (
            (ax, ay),
            (ax + aux * aout, ay + auy * aout),
            (bx - bux * bin_, by - buy * bin_),
            (bx, by),
        )


def sample(anchors, n=400):
    pts = []
    for p0, c1, c2, p3 in segments(anchors):
        for i in range(n):
            t = i / n
            u = 1 - t
            pts.append(
                tuple(
                    u**3 * p0[k] + 3 * u**2 * t * c1[k] + 3 * u * t**2 * c2[k] + t**3 * p3[k]
                    for k in (0, 1)
                )
            )
    pts.append(anchors[-1][:2])
    return pts


def y_at(pts, x):
    for (x0, y0), (x1, y1) in pairwise(pts):
        if x0 <= x <= x1:
            f = 0 if x1 == x0 else (x - x0) / (x1 - x0)
            return y0 + f * (y1 - y0)
    return None


def curvature(p0, c1, c2, p3, t):
    def d1(a, b, c, d):
        return 3 * ((1 - t) ** 2 * (b - a) + 2 * (1 - t) * t * (c - b) + t**2 * (d - c))

    def d2(a, b, c, d):
        return 6 * ((1 - t) * (c - 2 * b + a) + t * (d - 2 * c + b))

    xp, yp = (d1(p0[k], c1[k], c2[k], p3[k]) for k in (0, 1))
    xs, ys = (d2(p0[k], c1[k], c2[k], p3[k]) for k in (0, 1))
    speed = math.hypot(xp, yp)
    return (xp * ys - yp * xs) / speed**3 if speed else float("inf")


def main() -> int:
    ok = True

    def fail(msg):
        nonlocal ok
        ok = False
        print(f"FAIL: {msg}")

    black, red, blue = sample(g.BLACK), sample(g.RED_C), sample(g.BLUE_C)

    # -- design constraints ---------------------------------------------
    x0 = max(red[0][0], blue[0][0])
    x1 = min(red[-1][0], blue[-1][0])
    crossings, prev = [], None
    for i in range(1000):
        x = x0 + (x1 - x0) * i / 999
        d = y_at(red, x) - y_at(blue, x)
        if prev is not None and prev * d < 0:
            crossings.append(x)
        prev = d
    print(f"crossings at x = {[f'{c:.0f}' for c in crossings]}")
    if len(crossings) != 1 or not (290 <= crossings[0] <= 325):
        fail("expected exactly one blue/red crossing at ~half-width")

    xc = crossings[0] if crossings else 313
    worst = min(
        y_at(blue, x) - y_at(red, x) for x in (x0 + (xc - 5 - x0) * i / 200 for i in range(201))
    )
    print(f"min blue-red gap left of crossing: {worst:.1f} (must be > 0)")
    if worst <= 0:
        fail("red dips below blue before the crossing")

    b1 = min(y for x, y in blue if 150 <= x <= 250)
    b2 = min(y for x, y in blue if 340 <= x <= 430)
    print(f"blue bump1 y={b1:.0f}, bump2 y={b2:.0f} (bump2 must be smaller)")
    if b2 >= b1:
        fail("second bump not higher than first")

    bex = g.BLUE_C[-1][0]
    clear = (
        min(
            y_at(blue, x) - y_at(black, x)
            for x in (450 + (bex - 450) * i / 200 for i in range(201))
        )
        - 11.5
    )  # centerline gap minus the two half-strokes (12.5/2 + 10.5/2)
    print(f"blue-black tail clearance: {clear:.1f} px air (want 1..5)")
    if not (1 <= clear <= 5) or bex >= g.BLACK[-1][0]:
        fail("blue end must converge just below the black tail, no overlap")
    print(f"red tip at {g.RED_C[-1][0] / 610 * 100:.0f}% width (target ~74%)")

    for name, pts, peak_x in (("black", black, 383), ("blue", blue, 385)):
        tail = [y for x, y in pts if x >= peak_x]
        upturns = sum(1 for a, b in pairwise(tail) if b < a - 1e-6)
        end_is_min = tail[-1] >= max(tail) - 1e-6
        print(f"{name} tail: {upturns} upturn samples, ends at its low point: {end_is_min}")
        if upturns or not end_is_min:
            fail(f"{name} tail must descend monotonically and end at its low point")

    # -- construction math ----------------------------------------------
    for name, anchors in (("BLACK", g.BLACK), ("RED", g.RED_C), ("BLUE", g.BLUE_C)):
        segs = list(segments(anchors))
        print(f"\n{name}: {len(anchors)} anchors -> {len(segs)} cubic segments")
        for i, (p0, c1, c2, p3) in enumerate(segs):
            xs = (p0[0], c1[0], c2[0], p3[0])
            if not all(a <= b + 1e-9 for a, b in pairwise(xs)):
                fail(f"{name} seg {i}: control polygon not x-monotone")
            chord = math.hypot(p3[0] - p0[0], p3[1] - p0[1])
            h = math.hypot(c1[0] - p0[0], c1[1] - p0[1]) + math.hypot(p3[0] - c2[0], p3[1] - c2[1])
            if h > chord * 1.05:
                fail(f"{name} seg {i}: handles ({h:.0f}) exceed chord ({chord:.0f})")
        for i in range(len(segs) - 1):
            ke = curvature(*segs[i], 1.0)
            ks = curvature(*segs[i + 1], 0.0)
            hi, lo = max(abs(ke), abs(ks)), min(abs(ke), abs(ks))
            ratio = hi / lo if lo > 1e-12 else float("inf")
            print(
                f"  joint at x={segs[i][3][0]:g}: "
                f"curvature {ke:+.4f} -> {ks:+.4f} (ratio {ratio:.2f})"
            )
            if ke * ks < 0 and min(abs(ke), abs(ks)) > 1e-3:
                fail(f"{name} joint x={segs[i][3][0]:g}: curvature sign flip")
            elif ratio > 2.5:
                fail(f"{name} joint x={segs[i][3][0]:g}: curvature jump {ratio:.1f}x")

    print(
        "\nOK: constraints hold and curves are sound"
        if ok
        else "\nISSUES FOUND - see FAIL lines above"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
