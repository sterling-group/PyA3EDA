"""Byte-for-byte gate: the SLURM generator must reproduce the committed goldens.

The goldens were captured from the original ``qqchem.slurm.generate_slurm_script``
and live inline in :mod:`tests.golden_slurm`; ``slurm_cases.render`` is repointed
at the absorbed generator and this test proves the output is unchanged down to the
byte.
"""

from __future__ import annotations

import pytest

from tests.golden_slurm import GOLDENS
from tests.slurm_cases import CASES, render


@pytest.mark.parametrize("name", sorted(CASES))
def test_generated_script_matches_golden(name: str) -> None:
    """Each matrix case renders byte-identical to its committed golden."""
    assert render(name) == GOLDENS[name]


def test_every_case_has_a_golden() -> None:
    """No matrix case is missing its golden (and vice versa)."""
    assert set(CASES) == set(GOLDENS)
