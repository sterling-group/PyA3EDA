#!/usr/bin/env python
"""Render every SLURM characterization case to ``tests/data/golden/``.

Run before and after the runner refactor and ``git diff tests/data/golden`` —
an empty diff is the byte-for-byte guarantee that the generated SLURM/bash
script is unchanged.

    PYTHONPATH=src python scripts/dump_slurm.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from slurm_cases import CASES, render

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "tests" / "data" / "golden"


def main() -> None:
    """Write one ``<case>.slurm`` golden per matrix case."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name in CASES:
        (GOLDEN_DIR / f"{name}.slurm").write_text(render(name), encoding="utf-8")
        print(f"wrote {name}.slurm")


if __name__ == "__main__":
    main()
