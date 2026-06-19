"""Utility functions: file I/O, unit conversion, thermodynamic corrections."""

from __future__ import annotations

import math
from pathlib import Path

from pya3eda import constants as C

# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def read_text(path: str | Path) -> str | None:
    """Read a text file and return its contents, or ``None`` if missing."""
    p = Path(path)
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8")


def write_text(path: str | Path, content: str) -> None:
    """Write *content* to *path*, creating parent directories as needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------

# Lookup: (from_unit, to_unit) → factor  (value * factor)
_CONVERSIONS: dict[tuple[str, str], float] = {
    ("hartree", "kcal/mol"): C.HARTREE_TO_KCALMOL,
    ("kcal/mol", "hartree"): 1.0 / C.HARTREE_TO_KCALMOL,
    ("hartree", "kj/mol"): C.HARTREE_TO_KJMOL,
    ("kj/mol", "hartree"): C.KJMOL_TO_HARTREE,
    ("kj/mol", "kcal/mol"): C.KJMOL_TO_HARTREE * C.HARTREE_TO_KCALMOL,
    ("kcal/mol", "kj/mol"): 1.0 / C.KJMOL_TO_KCALMOL,
    ("cal/mol.k", "kcal/mol.k"): 1e-3,
    ("j/mol", "kcal/mol"): 1e-3 * C.KJMOL_TO_KCALMOL,
    ("atm", "pa"): C.ATM_TO_PA,
    ("pa", "atm"): 1.0 / C.ATM_TO_PA,
}

_ALIASES: dict[str, str] = {
    "ha": "hartree",
    "a.u.": "hartree",
    "pascal": "pa",
}


def convert_unit(value: float, from_unit: str, to_unit: str) -> float:
    """Convert *value* between units.  Raises ``ValueError`` on unknown pair."""
    src = _ALIASES.get(from_unit.lower(), from_unit.lower())
    dst = _ALIASES.get(to_unit.lower(), to_unit.lower())
    if src == dst:
        return value
    factor = _CONVERSIONS.get((src, dst))
    if factor is None:
        raise ValueError(f"Unknown unit conversion: {from_unit!r} → {to_unit!r}")
    return value * factor


# ---------------------------------------------------------------------------
# Thermodynamic corrections
# ---------------------------------------------------------------------------


def standard_state_correction(temperature: float, pressure: float = 1.0) -> float:
    """ΔG correction from gas-phase (1 atm) to solution-phase (1 M) in kcal/mol.

    dG = RT·ln(RT·C_1M / P)   where C_1M = 1000 L / m³.
    At 298.15 K / 1 atm → ≈ 1.89 kcal/mol.
    """
    pressure_pa = convert_unit(pressure, "atm", "Pa")
    ratio = (C.MOLAR_GAS_CONSTANT * temperature * C.M3_TO_L) / pressure_pa
    correction_j = C.MOLAR_GAS_CONSTANT * temperature * math.log(ratio)
    return convert_unit(correction_j, "J/mol", "kcal/mol")
