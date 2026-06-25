"""Characterization snapshot of the full registry enumeration (parity oracle).

Guards the registry refactor — and any future change — against accidental drift.
Regenerate ``registry_snapshot.txt`` only for an *intentional* enumeration change
and review the diff:

    python -c "from pathlib import Path; from tests.registry_dump import \
        dump_registry, snapshot_config; from pya3eda.registry import CalcRegistry; \
        Path('tests/registry_snapshot.txt').write_text(\
        dump_registry(CalcRegistry(snapshot_config(), Path('/B'))))"
"""

from __future__ import annotations

from pathlib import Path

from pya3eda.registry import CalcRegistry

from .registry_dump import dump_registry, snapshot_config

_SNAPSHOT = Path(__file__).parent / "registry_snapshot.txt"


def test_registry_enumeration_matches_snapshot() -> None:
    """The full enumeration (calcs + profiles) is byte-identical to the snapshot."""
    reg = CalcRegistry(snapshot_config(), Path("/B"))
    assert dump_registry(reg) == _SNAPSHOT.read_text()
