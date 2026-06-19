"""Typed identifiers and specifications for calculations and profiles.

Every calculation and energy profile in the system is identified by a frozen,
hashable model that can be used as a dictionary key.  ``CalcSpec`` and
``ProfileSpec`` carry the full derived metadata needed by downstream modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, NamedTuple

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Calculation identity
# ---------------------------------------------------------------------------


class CalcID(BaseModel, frozen=True):
    """Unique, hashable identifier for a single calculation."""

    method_key: str  # OPT-level folder, e.g. "wB97X-V_def2-SVP_smd"
    catalyst: str | None = None  # None → uncatalyzed, else catalyst name
    stage: str  # reactants | products | ts | preTS | postTS | cat
    species: str  # e.g. "prop2enal", "lip-prop2enal", "ts_lip-tscomplex"
    calc_type: str | None = None  # full_cat | pol_cat | frz_cat | None
    mode: str = "opt"  # opt | sp
    sp_subfolder: str | None = None  # e.g. "wB97M-V_def2-TZVPPD_smd_sp"

    def to_opt(self) -> CalcID:
        """The OPT calculation this id derives from (``mode='opt'``, no SP subfolder)."""
        return self.model_copy(update={"mode": "opt", "sp_subfolder": None})


class CalcSpec(BaseModel, frozen=True):
    """Full specification of a calculation, including path and metadata."""

    id: CalcID
    input_path: Path  # relative to base_dir
    output_path: Path  # .in → .out

    # Original (unsanitized) values for Q-Chem input content
    method_name: str
    basis_set: str
    dispersion: str  # "false" when no dispersion
    solvent: str  # "false" when gas phase
    eda2: int | None = None  # Only for SP

    # SP path info
    sp_subfolder: str | None = None  # e.g. "wB97M-V_def2-TZVPPD_smd_sp"

    # Molecule structure
    is_fragmented: bool = False  # True for catalytic complexes

    # Reaction context (for profile assembly)
    present_reactants: tuple[str, ...] = ()
    present_products: tuple[str, ...] = ()
    present_catalysts: tuple[str, ...] = ()
    all_reactants: tuple[str, ...] = ()
    all_products: tuple[str, ...] = ()
    all_catalysts: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Profile identity
# ---------------------------------------------------------------------------


class ProfileID(BaseModel, frozen=True):
    """Unique, hashable identifier for an energy profile."""

    method_key: str
    catalyst: str | None = None  # None → uncatalyzed
    calc_type: str | None = None  # None → uncatalyzed
    mode: str = "opt"
    sp_subfolder: str | None = None  # distinguishes SP profiles under same OPT

    # Ordered EDA calc_type cascade with display labels
    TRACE_ORDER: ClassVar[tuple[tuple[str | None, str], ...]] = (
        (None, "uncat"),
        ("ni", "NI"),
        ("frz_cat", "FRZ"),
        ("pol_cat", "POL"),
        ("full_cat", "FULL"),
    )

    # Canonical stage order for the reaction coordinate
    STAGE_ORDER: ClassVar[tuple[str, ...]] = (
        "reactants",
        "preTS",
        "ts",
        "postTS",
        "products",
    )

    @staticmethod
    def method_label(method_key: str, sp_subfolder: str | None) -> str:
        """Build the method portion of an export/plot filename."""
        if sp_subfolder:
            return f"{sp_subfolder}_{method_key}_opt"
        return method_key


class NiStageRef(NamedTuple):
    """Non-interacting reference for one profile stage.

    *ref_cids*          — species that supply H and non-translational S.
    *trans_cids*        — species that supply translational S only.
    *apply_ssc_to_g_ni* — whether to add the standard-state correction to G_ni
                          (True when an implicit solvent is used).
    """

    ref_cids: tuple[CalcID, ...]
    trans_cids: tuple[CalcID, ...]
    apply_ssc_to_g_ni: bool = False


class StageAlt(BaseModel, frozen=True):
    """Alternative composition for one profile stage (complex subset)."""

    calc_ids: tuple[CalcID, ...]
    label: str
    ni_ref: NiStageRef | None = None


class StageSpec(BaseModel, frozen=True):
    """One stage of a reaction profile, with pre-resolved CalcIDs to sum."""

    name: str  # reactants | preTS | ts | postTS | products
    calc_ids: tuple[CalcID, ...]  # calculations to sum for this stage
    label: str  # display label, e.g. "prop2enal + buta13diene + lip"
    ni_ref: NiStageRef | None = None  # non-interacting reference (full_cat only)
    alternatives: tuple[StageAlt, ...] = ()  # candidate complex subsets


class ProfileSpec(BaseModel, frozen=True):
    """Full specification of an energy profile — stages with CalcID refs."""

    id: ProfileID
    stages: tuple[StageSpec, ...]  # ordered reaction coordinate
    selection_leader: bool = False  # True for full_cat — drives candidate choice
    ref_stage: str = "reactants"  # stage whose energies define the zero point


# ---------------------------------------------------------------------------
# Extraction result types
# ---------------------------------------------------------------------------


class ExtractedData(BaseModel):
    """Parsed result for a single calculation output file."""

    calc_id: CalcID
    status: str = ""

    # OPT fields
    energy: float | None = None  # E (kcal/mol)
    h_corr: float | None = None  # enthalpy correction
    s_corr: float | None = None  # total entropy correction
    s_trans: float | None = None  # translational entropy
    temperature: float | None = None
    zpve: float | None = None
    imag_freq: int | None = None

    # SP fields
    sp_energy: float | None = None  # may include EDA/BSSE corrections

    # Derived (computed after parsing)
    H: float | None = None  # E + h_corr
    G: float | None = None  # H - T·S

    # Geometry
    xyz_text: str | None = None  # formatted XYZ file content


class StageData(BaseModel, frozen=True):
    """Energy totals for one stage of a profile."""

    UNIT: ClassVar[str] = "kcal/mol"
    _ENERGY_TYPES: ClassVar[tuple[str, ...]] = ("E", "G")
    _BARRIER_SURFACES: ClassVar[tuple[str, ...]] = ("E", "G", "G_ni")

    name: str
    calc_type: str | None = None
    species_label: str = ""
    E: float | None = None
    G: float | None = None

    # Relative (normalised) energies — keyed by energy type, set during profile assembly.
    _rel: dict[str, float] = {}

    @classmethod
    def energy_types(cls) -> tuple[str, ...]:
        """Absolute energy field names."""
        return cls._ENERGY_TYPES

    @classmethod
    def barrier_surfaces(cls) -> tuple[str, ...]:
        """Energy surfaces for barrier/plot decomposition (includes G_ni)."""
        return cls._BARRIER_SURFACES

    def rel(self, etype: str) -> float | None:
        """Relative energy for the given energy type."""
        return self._rel.get(etype)


class ProfileData(BaseModel, frozen=True):
    """Assembled energy profile ready for plotting/export."""

    profile_id: ProfileID
    stages: tuple[StageData, ...] = ()


class DeltaDeltaData(BaseModel, frozen=True):
    """Barrier decomposition for one catalyst x method x energy type."""

    method_key: str
    catalyst: str
    energy_type: str  # "E" | "G" | "G_ni"
    mode: str = "opt"
    sp_subfolder: str | None = None

    barrier_uncat: float | None = None
    barrier_frz: float | None = None
    barrier_pol: float | None = None
    barrier_full: float | None = None

    barrier_ni: float | None = None

    dd_ni: float | None = None  # ni - uncat
    dd_frz: float | None = None  # frz - uncat (or frz - ni for G_ni)
    dd_pol: float | None = None  # pol - frz
    dd_ct: float | None = None  # full - pol
    dd_complete: float | None = None  # full - uncat

    # Optional pre-equilibrium correction (e.g. catalyst dimer dissociation),
    # applied by a post-extraction script; shown as a leading bar with FULL grown
    # by it. None for the normal pipeline.
    dd_dissoc: float | None = None
