"""Domain vocabulary — the closed sets of stage / mode / calc-type / surface
strings, as :class:`~enum.StrEnum`\\s so a typo is a type error rather than a
silent mismatch.

Each member compares equal to (and renders as) its plain string value, so every
path, label, dict key, and serialised value is byte-identical to the bare strings
these replace — the enums add type-checking without changing behaviour.
"""

from __future__ import annotations

from enum import StrEnum


class Mode(StrEnum):
    """Calculation mode: geometry optimisation or single point."""

    OPT = "opt"
    SP = "sp"


class Stage(StrEnum):
    """Reaction/calculation stage (the ``CalcID.stage`` vocabulary)."""

    REACTANTS = "reactants"
    PRODUCTS = "products"
    TS = "ts"
    PRETS = "preTS"
    POSTTS = "postTS"
    CAT = "cat"
    DIMER = "dimer"


class CalcType(StrEnum):
    """EDA calc type, plus the profile-trace pseudo-types (``nocat``, ``ni``)."""

    FULL_CAT = "full_cat"
    POL_CAT = "pol_cat"
    FRZ_CAT = "frz_cat"
    NOCAT = "nocat"
    NI = "ni"


class Surface(StrEnum):
    """Energy surface for barriers / plots."""

    E = "E"
    G = "G"
    G_NI = "G_ni"
