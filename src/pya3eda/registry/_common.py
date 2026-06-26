"""Theory-derived helpers and shared constants for the registry enumeration."""

from __future__ import annotations

from pya3eda.config import TheoryConfig
from pya3eda.sanitize import sanitize
from pya3eda.vocab import CalcType

_FULL_CAT = CalcType.FULL_CAT
_CALC_TYPES = (CalcType.FULL_CAT, CalcType.POL_CAT, CalcType.FRZ_CAT)
_TS_SPECIES = "tscomplex"


def build_method_key(theory: TheoryConfig) -> str:
    """Build a filesystem-safe method folder name from a theory config.

    Format: ``{method}[_{dispersion}]_{basis}[_{solvent}]``
    Components that are ``None`` are omitted.
    """
    parts = [sanitize(theory.method)]
    if theory.dispersion is not None:
        parts.append(sanitize(theory.dispersion))
    parts.append(sanitize(theory.basis))
    if theory.solvent is not None:
        parts.append(sanitize(theory.solvent))
    return "_".join(parts)


def _sp_subfolder(sp_theory: TheoryConfig) -> str:
    """Build the SP sub-folder name (method_key + ``_sp`` suffix)."""
    return build_method_key(sp_theory) + "_sp"


def _has_solvent(theory: TheoryConfig) -> bool:
    """Whether the theory uses an implicit solvent (→ SSC applies)."""
    return theory.solvent is not None and theory.solvent.lower() not in ("false", "gas")
