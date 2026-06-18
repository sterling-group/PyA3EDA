"""Byte-for-byte gate: the SLURM generator must reproduce the committed goldens.

The goldens were captured from the original ``qqchem.slurm.generate_slurm_script``
(``scripts/dump_slurm.py``). After the runner refactor, ``slurm_cases.render``
is repointed at the absorbed generator; this test then proves the output is
unchanged down to the byte.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.slurm_cases import CASES, render

GOLDEN_DIR = Path(__file__).parent / "data" / "golden"


@pytest.mark.parametrize("name", sorted(CASES))
def test_generated_script_matches_golden(name: str) -> None:
    """Each matrix case renders byte-identical to its committed golden."""
    golden = (GOLDEN_DIR / f"{name}.slurm").read_text(encoding="utf-8")
    assert render(name) == golden


def test_every_case_has_a_golden() -> None:
    """No matrix case is missing its golden (and vice versa)."""
    cases = set(CASES)
    goldens = {p.stem for p in GOLDEN_DIR.glob("*.slurm")}
    assert cases == goldens
