"""CalcRegistry — the single source of truth for all calculations and profiles.

Built once from a ``Config`` and a base directory.  Pure derivation — no
filesystem access.  Every downstream module receives the registry and looks up
calculations by ``CalcID`` or profiles by ``ProfileID``.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import TypedDict

from pya3eda.config import Config, SpeciesConfig, TheoryConfig
from pya3eda.ids import (
    CalcID,
    CalcSpec,
    NiStageRef,
    ProfileID,
    ProfileSpec,
    StageAlt,
    StageSpec,
)
from pya3eda.sanitize import sanitize


class _CommonCalcKwargs(TypedDict):
    """Theory/context kwargs shared by every ``_add_calc`` call in a level."""

    method_name: str
    basis_set: str
    dispersion: str
    solvent: str
    eda2: int | None
    sp_subfolder: str | None
    all_reactants: tuple[str, ...]
    all_products: tuple[str, ...]
    all_catalysts: tuple[str, ...]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# CalcRegistry
# ---------------------------------------------------------------------------

_FULL_CAT = "full_cat"
_CALC_TYPES = (_FULL_CAT, "pol_cat", "frz_cat")
_TS_SPECIES = "tscomplex"
_NO_CAT_DIR = "no_cat"


class CalcRegistry:
    """Enumerates every expected calculation and energy profile from config.

    Parameters
    ----------
    config : Config
        Validated configuration.
    base_dir : Path
        Root directory beneath which all method-key folders live.
    """

    def __init__(self, config: Config, base_dir: Path) -> None:
        """Initialise the registry by enumerating all calcs and profiles."""
        self._config = config
        self._base_dir = Path(base_dir)

        # Primary stores
        self._calcs: dict[CalcID, CalcSpec] = {}
        self._profiles: dict[ProfileID, ProfileSpec] = {}

        # Derived ordering helpers
        self._method_keys: list[str] = []
        self._catalyst_order: list[str] = [c.name for c in config.catalysts]
        self._dimer_catalysts: set[str] = {sanitize(c.name) for c in config.catalysts if c.dimer}

        self._enumerate_calcs()
        self._enumerate_profiles()

    # -- public API ---------------------------------------------------------

    @property
    def config(self) -> Config:
        """The validated configuration this registry was built from."""
        return self._config

    @property
    def base_dir(self) -> Path:
        """Root directory beneath which all method-key folders live."""
        return self._base_dir

    @property
    def all_calcs(self) -> list[CalcSpec]:
        """All registered calculation specs."""
        return list(self._calcs.values())

    def get(self, calc_id: CalcID) -> CalcSpec:
        """Look up a CalcSpec by its CalcID."""
        return self._calcs[calc_id]

    def by_method(self, method_key: str) -> list[CalcSpec]:
        """Return all CalcSpecs matching the given method key."""
        return [c for c in self._calcs.values() if c.id.method_key == method_key]

    def by_mode(self, mode: str) -> list[CalcSpec]:
        """Return all CalcSpecs matching the given mode ('opt' or 'sp')."""
        return [c for c in self._calcs.values() if c.id.mode == mode]

    @property
    def all_profiles(self) -> list[ProfileSpec]:
        """All registered energy-profile specs."""
        return list(self._profiles.values())

    def get_profile(self, profile_id: ProfileID) -> ProfileSpec:
        """Look up a ProfileSpec by its ProfileID."""
        return self._profiles[profile_id]

    def profiles_for_method(self, method_key: str) -> list[ProfileSpec]:
        """Return all ProfileSpecs matching the given method key."""
        return [p for p in self._profiles.values() if p.id.method_key == method_key]

    @property
    def method_keys(self) -> list[str]:
        """Ordered list of method keys from config levels."""
        return list(self._method_keys)

    @property
    def catalyst_order(self) -> list[str]:
        """Ordered list of catalyst names from config."""
        return list(self._catalyst_order)

    @property
    def dimer_catalysts(self) -> set[str]:
        """Sanitised names of catalysts declared with ``dimer: true``."""
        return set(self._dimer_catalysts)

    # -- private: enumeration -----------------------------------------------

    def _enumerate_calcs(self) -> None:
        """Populate ``self._calcs`` by iterating config levels x species."""
        seen_method_keys: list[str] = []

        for level in self._config.levels:
            method_key = build_method_key(level.opt)
            if method_key not in seen_method_keys:
                seen_method_keys.append(method_key)

            # OPT calcs
            self._enumerate_calcs_for_theory(level.opt, method_key, "opt")

            # SP calcs (one round per SP theory)
            for sp_theory in level.sp:
                self._enumerate_calcs_for_theory(
                    sp_theory,
                    method_key,
                    "sp",
                    sp_subfolder=_sp_subfolder(sp_theory),
                )

        self._method_keys = seen_method_keys

    def _enumerate_calcs_for_theory(
        self,
        theory: TheoryConfig,
        method_key: str,
        mode: str,
        sp_subfolder: str | None = None,
    ) -> None:
        """Enumerate all calc specs for one theory (opt or sp) under one level."""
        cfg = self._config
        all_r = tuple(r.name for r in cfg.reactants)
        all_p = tuple(p.name for p in cfg.products)
        all_c = tuple(c.name for c in cfg.catalysts)

        incl_r = [r for r in cfg.reactants if r.include]
        incl_p = [p for p in cfg.products if p.include]

        common: _CommonCalcKwargs = {
            "method_name": theory.method,
            "basis_set": theory.basis,
            "dispersion": theory.dispersion or "False",
            "solvent": theory.solvent or "false",
            "eda2": theory.eda2 if mode == "sp" else None,
            "sp_subfolder": sp_subfolder,
            "all_reactants": all_r,
            "all_products": all_p,
            "all_catalysts": all_c,
        }

        # ── uncatalyzed ────────────────────────────────────────────────
        # Individual reactants
        for r in cfg.reactants:
            self._add_calc(
                method_key=method_key,
                catalyst=None,
                stage="reactants",
                species=sanitize(r.name),
                calc_type=None,
                mode=mode,
                is_fragmented=False,
                present_reactants=(r.name,),
                present_products=(),
                present_catalysts=(),
                **common,
            )

        # Reactant combinations (include=True, ≥2)
        if len(incl_r) > 1:
            for size in range(2, len(incl_r) + 1):
                for combo in combinations(incl_r, size):
                    species_name = "-".join(sanitize(s.name) for s in combo)
                    self._add_calc(
                        method_key=method_key,
                        catalyst=None,
                        stage="reactants",
                        species=species_name,
                        calc_type=None,
                        mode=mode,
                        is_fragmented=False,
                        present_reactants=tuple(s.name for s in combo),
                        present_products=(),
                        present_catalysts=(),
                        **common,
                    )

        # Individual products
        for p in cfg.products:
            self._add_calc(
                method_key=method_key,
                catalyst=None,
                stage="products",
                species=sanitize(p.name),
                calc_type=None,
                mode=mode,
                is_fragmented=False,
                present_reactants=(),
                present_products=(p.name,),
                present_catalysts=(),
                **common,
            )

        # TS (uncatalyzed)
        self._add_calc(
            method_key=method_key,
            catalyst=None,
            stage="ts",
            species=_TS_SPECIES,
            calc_type=None,
            mode=mode,
            is_fragmented=False,
            present_reactants=all_r,
            present_products=all_p,
            present_catalysts=(),
            **common,
        )

        # ── catalyzed ──────────────────────────────────────────────────
        for cat in cfg.catalysts:
            cat_s = sanitize(cat.name)

            # Catalyst standalone
            self._add_calc(
                method_key=method_key,
                catalyst=cat_s,
                stage="cat",
                species=cat_s,
                calc_type=None,
                mode=mode,
                is_fragmented=False,
                present_reactants=(),
                present_products=(),
                present_catalysts=(cat.name,),
                **common,
            )

            # Catalyst dimer (optional) — a standalone calc alongside `cat`, used
            # only for the dissociation (DISS) correction on the ΔΔ‡ barplot.
            if cat.dimer:
                self._add_calc(
                    method_key=method_key,
                    catalyst=cat_s,
                    stage="dimer",
                    species=f"{cat_s}-dimer",
                    calc_type=None,
                    mode=mode,
                    is_fragmented=False,
                    present_reactants=(),
                    present_products=(),
                    present_catalysts=(cat.name,),
                    **common,
                )

            # preTS: catalyst-reactant complexes (include=True combos, ≥1)
            for size in range(1, len(incl_r) + 1):
                for combo in combinations(incl_r, size):
                    combo_name = "-".join(sanitize(s.name) for s in combo)
                    species_name = f"{cat_s}-{combo_name}"
                    for ct in _CALC_TYPES:
                        self._add_calc(
                            method_key=method_key,
                            catalyst=cat_s,
                            stage="preTS",
                            species=species_name,
                            calc_type=ct,
                            mode=mode,
                            is_fragmented=True,
                            present_reactants=tuple(s.name for s in combo),
                            present_products=(),
                            present_catalysts=(cat.name,),
                            **common,
                        )

            # postTS: catalyst-product complexes (include=True combos, ≥1)
            for size in range(1, len(incl_p) + 1):
                for combo in combinations(incl_p, size):
                    combo_name = "-".join(sanitize(s.name) for s in combo)
                    species_name = f"{cat_s}-{combo_name}"
                    for ct in _CALC_TYPES:
                        self._add_calc(
                            method_key=method_key,
                            catalyst=cat_s,
                            stage="postTS",
                            species=species_name,
                            calc_type=ct,
                            mode=mode,
                            is_fragmented=True,
                            present_reactants=(),
                            present_products=tuple(s.name for s in combo),
                            present_catalysts=(cat.name,),
                            **common,
                        )

            # TS (catalyzed)
            for ct in _CALC_TYPES:
                self._add_calc(
                    method_key=method_key,
                    catalyst=cat_s,
                    stage="ts",
                    species=f"{cat_s}-{_TS_SPECIES}",
                    calc_type=ct,
                    mode=mode,
                    is_fragmented=True,
                    present_reactants=all_r,
                    present_products=all_p,
                    present_catalysts=(cat.name,),
                    **common,
                )

    def _add_calc(
        self,
        *,
        method_key: str,
        catalyst: str | None,
        stage: str,
        species: str,
        calc_type: str | None,
        mode: str,
        is_fragmented: bool,
        method_name: str,
        basis_set: str,
        dispersion: str,
        solvent: str,
        eda2: int | None,
        sp_subfolder: str | None,
        present_reactants: tuple[str, ...],
        present_products: tuple[str, ...],
        present_catalysts: tuple[str, ...],
        all_reactants: tuple[str, ...],
        all_products: tuple[str, ...],
        all_catalysts: tuple[str, ...],
    ) -> None:
        """Create CalcID + CalcSpec and register them."""
        cid = CalcID(
            method_key=method_key,
            catalyst=catalyst,
            stage=stage,
            species=species,
            calc_type=calc_type,
            mode=mode,
            sp_subfolder=sp_subfolder,
        )
        if cid in self._calcs:
            return  # duplicate id (e.g. OPT theories differing only in SP-only fields)

        input_path = self._build_input_path(
            method_key,
            catalyst,
            stage,
            species,
            calc_type,
            mode,
            sp_subfolder,
        )
        output_path = input_path.with_suffix(".out")

        spec = CalcSpec(
            id=cid,
            input_path=input_path,
            output_path=output_path,
            method_name=method_name,
            basis_set=basis_set,
            dispersion=dispersion,
            solvent=solvent,
            eda2=eda2,
            sp_subfolder=sp_subfolder,
            is_fragmented=is_fragmented,
            present_reactants=present_reactants,
            present_products=present_products,
            present_catalysts=present_catalysts,
            all_reactants=all_reactants,
            all_products=all_products,
            all_catalysts=all_catalysts,
        )
        self._calcs[cid] = spec

    # -- path construction --------------------------------------------------

    def _build_input_path(
        self,
        method_key: str,
        catalyst: str | None,
        stage: str,
        species: str,
        calc_type: str | None,
        mode: str,
        sp_subfolder: str | None,
    ) -> Path:
        """Build the relative input-file path (relative to ``base_dir``).

        Mirrors the directory tree documented in the old builder module.
        """
        suffix = f"_{mode}.in"
        base = self._base_dir / method_key

        # Filesystem directory: None → _NO_CAT_DIR, else the catalyst name
        cat_dir = catalyst or _NO_CAT_DIR

        if catalyst is None:
            if stage in ("reactants", "products"):
                parts = Path(cat_dir) / stage / species
                filename = f"{species}{suffix}"
            elif stage == "ts":
                parts = Path(cat_dir) / "ts"
                filename = f"{_TS_SPECIES}{suffix}"
            else:
                raise ValueError(f"Unknown uncatalyzed stage: {stage}")

            if mode == "sp" and sp_subfolder:
                parts = parts / sp_subfolder
            return base / parts / filename

        # Catalyzed — cat_dir is the catalyst name
        if stage == "cat":
            parts = Path(cat_dir) / "cat"
            filename = f"{cat_dir}{suffix}"
            if mode == "sp" and sp_subfolder:
                parts = parts / sp_subfolder
            return base / parts / filename

        if stage == "dimer":
            parts = Path(cat_dir) / "dimer"
            filename = f"{cat_dir}-dimer{suffix}"
            if mode == "sp" and sp_subfolder:
                parts = parts / sp_subfolder
            return base / parts / filename

        if stage in ("preTS", "postTS"):
            assert calc_type is not None  # preTS/postTS calcs always carry a calc_type
            prefix = stage  # "preTS" or "postTS"
            parts = Path(cat_dir) / stage / species / calc_type
            filename = f"{prefix}_{species}_{calc_type}{suffix}"
            if mode == "sp" and sp_subfolder:
                parts = parts / sp_subfolder
            return base / parts / filename

        if stage == "ts":
            assert calc_type is not None  # TS calcs always carry a calc_type
            parts = Path(cat_dir) / "ts" / calc_type
            filename = f"ts_{species}_{calc_type}{suffix}"
            if mode == "sp" and sp_subfolder:
                parts = parts / sp_subfolder
            return base / parts / filename

        raise ValueError(f"Unknown stage: {stage}")

    # -- profile enumeration ------------------------------------------------

    def _enumerate_profiles(self) -> None:
        """Build all ProfileSpecs from config (forward composition)."""
        cfg = self._config
        incl_r = [r for r in cfg.reactants if r.include]
        free_r = [r for r in cfg.reactants if not r.include]
        incl_p = [p for p in cfg.products if p.include]
        free_p = [p for p in cfg.products if not p.include]

        for level in cfg.levels:
            method_key = build_method_key(level.opt)

            # Resolve solvent per (mode, sp_subfolder)
            mode_sps: list[tuple[str, str | None, bool]] = [
                ("opt", None, _has_solvent(level.opt)),
            ]
            if level.sp:
                for sp_theory in level.sp:
                    mode_sps.append(("sp", _sp_subfolder(sp_theory), _has_solvent(sp_theory)))

            for mode, sp_sub, apply_ssc in mode_sps:
                self._build_uncatalyzed_profile(method_key, mode, sp_subfolder=sp_sub)

                for cat in cfg.catalysts:
                    self._build_nocat_profile(method_key, mode, cat.name, sp_subfolder=sp_sub)
                    for ct in _CALC_TYPES:
                        self._build_catalyzed_profile(
                            method_key,
                            mode,
                            cat.name,
                            ct,
                            incl_r,
                            free_r,
                            incl_p,
                            free_p,
                            sp_subfolder=sp_sub,
                            apply_ssc=apply_ssc,
                        )

    def _build_uncatalyzed_profile(
        self,
        method_key: str,
        mode: str,
        *,
        sp_subfolder: str | None = None,
    ) -> None:
        """Build the uncatalysed reaction profile (reactants → TS → products)."""
        pid = ProfileID(
            method_key=method_key,
            catalyst=None,
            calc_type=None,
            mode=mode,
            sp_subfolder=sp_subfolder,
        )

        all_reactant_ids = [
            CalcID(
                method_key=method_key,
                catalyst=None,
                stage="reactants",
                species=sanitize(r.name),
                mode=mode,
                sp_subfolder=sp_subfolder,
            )
            for r in self._config.reactants
        ]
        all_product_ids = [
            CalcID(
                method_key=method_key,
                catalyst=None,
                stage="products",
                species=sanitize(p.name),
                mode=mode,
                sp_subfolder=sp_subfolder,
            )
            for p in self._config.products
        ]
        ts_id = CalcID(
            method_key=method_key,
            catalyst=None,
            stage="ts",
            species=_TS_SPECIES,
            mode=mode,
            sp_subfolder=sp_subfolder,
        )

        stages = (
            StageSpec(
                name="reactants",
                calc_ids=tuple(all_reactant_ids),
                label=" + ".join(r.name for r in self._config.reactants),
            ),
            StageSpec(
                name="ts",
                calc_ids=(ts_id,),
                label=_TS_SPECIES,
            ),
            StageSpec(
                name="products",
                calc_ids=tuple(all_product_ids),
                label=" + ".join(p.name for p in self._config.products),
            ),
        )

        self._profiles[pid] = ProfileSpec(id=pid, stages=stages)

    def _build_nocat_profile(
        self,
        method_key: str,
        mode: str,
        cat_name: str,
        *,
        sp_subfolder: str | None = None,
    ) -> None:
        """Build a no-catalyst reference profile.

        Uncatalysed reaction stages with the standalone catalyst added
        as a non-interacting spectator.  Ensures the same species
        composition as the catalysed profiles so barriers are directly
        comparable (catalyst energy cancels exactly).

        No NI refs: the nocat profile is used only on the G surface for
        barrier baselines, never for G_ni decomposition.
        """
        cat_s = sanitize(cat_name)
        pid = ProfileID(
            method_key=method_key,
            catalyst=cat_s,
            calc_type="nocat",
            mode=mode,
            sp_subfolder=sp_subfolder,
        )

        cat_standalone = CalcID(
            method_key=method_key,
            catalyst=cat_s,
            stage="cat",
            species=cat_s,
            mode=mode,
            sp_subfolder=sp_subfolder,
        )

        reactant_ids = tuple(
            [
                CalcID(
                    method_key=method_key,
                    catalyst=None,
                    stage="reactants",
                    species=sanitize(r.name),
                    mode=mode,
                    sp_subfolder=sp_subfolder,
                )
                for r in self._config.reactants
            ]
            + [cat_standalone]
        )

        uncat_ts_id = CalcID(
            method_key=method_key,
            catalyst=None,
            stage="ts",
            species=_TS_SPECIES,
            mode=mode,
            sp_subfolder=sp_subfolder,
        )
        ts_ids = (uncat_ts_id, cat_standalone)

        product_ids = tuple(
            [
                CalcID(
                    method_key=method_key,
                    catalyst=None,
                    stage="products",
                    species=sanitize(p.name),
                    mode=mode,
                    sp_subfolder=sp_subfolder,
                )
                for p in self._config.products
            ]
            + [cat_standalone]
        )

        reactant_label = " + ".join([r.name for r in self._config.reactants] + [cat_name])
        product_label = " + ".join([p.name for p in self._config.products] + [cat_name])

        stages = (
            StageSpec(
                name="reactants",
                calc_ids=reactant_ids,
                label=reactant_label,
            ),
            StageSpec(
                name="ts",
                calc_ids=ts_ids,
                label=f"{_TS_SPECIES} + {cat_name}",
            ),
            StageSpec(
                name="products",
                calc_ids=product_ids,
                label=product_label,
            ),
        )

        self._profiles[pid] = ProfileSpec(id=pid, stages=stages)

    def _build_catalyzed_profile(
        self,
        method_key: str,
        mode: str,
        cat_name: str,
        calc_type: str,
        incl_r: list[SpeciesConfig],
        free_r: list[SpeciesConfig],
        incl_p: list[SpeciesConfig],
        free_p: list[SpeciesConfig],
        *,
        sp_subfolder: str | None = None,
        apply_ssc: bool = False,
    ) -> None:
        """Build a catalysed profile with preTS/TS/postTS stages."""
        cat_s = sanitize(cat_name)
        pid = ProfileID(
            method_key=method_key,
            catalyst=cat_s,
            calc_type=calc_type,
            mode=mode,
            sp_subfolder=sp_subfolder,
        )

        # --- reactants stage ---
        # All standalone reactants + standalone catalyst
        reactant_ids: list[CalcID] = [
            CalcID(
                method_key=method_key,
                catalyst=None,
                stage="reactants",
                species=sanitize(r.name),
                mode=mode,
                sp_subfolder=sp_subfolder,
            )
            for r in self._config.reactants
        ]
        cat_standalone = CalcID(
            method_key=method_key,
            catalyst=cat_s,
            stage="cat",
            species=cat_s,
            mode=mode,
            sp_subfolder=sp_subfolder,
        )
        reactant_ids.append(cat_standalone)
        reactant_label = " + ".join([r.name for r in self._config.reactants] + [cat_name])

        # --- preTS stage ---
        # Complex of catalyst + included reactants, plus free reactants standalone
        incl_r_combo_name = "-".join(sanitize(r.name) for r in incl_r)
        pre_complex_species = f"{cat_s}-{incl_r_combo_name}" if incl_r else cat_s
        pre_ts_ids: list[CalcID] = [
            CalcID(
                method_key=method_key,
                catalyst=cat_s,
                stage="preTS",
                species=pre_complex_species,
                calc_type=calc_type,
                mode=mode,
                sp_subfolder=sp_subfolder,
            ),
        ]
        pre_label_parts = [f"{cat_name}-{'-'.join(r.name for r in incl_r)}"]
        for fr in free_r:
            pre_ts_ids.append(
                CalcID(
                    method_key=method_key,
                    catalyst=None,
                    stage="reactants",
                    species=sanitize(fr.name),
                    mode=mode,
                    sp_subfolder=sp_subfolder,
                )
            )
            pre_label_parts.append(fr.name)

        # preTS alternatives: proper subsets of included reactants
        pre_alt_data: list[tuple[tuple[CalcID, ...], str, tuple[SpeciesConfig, ...]]] = []
        if len(incl_r) > 1:
            for size in range(1, len(incl_r)):
                for combo in combinations(incl_r, size):
                    remaining = [r for r in incl_r if r not in combo]
                    combo_name = "-".join(sanitize(r.name) for r in combo)
                    alt_species = f"{cat_s}-{combo_name}"
                    alt_ids: list[CalcID] = [
                        CalcID(
                            method_key=method_key,
                            catalyst=cat_s,
                            stage="preTS",
                            species=alt_species,
                            calc_type=calc_type,
                            mode=mode,
                            sp_subfolder=sp_subfolder,
                        ),
                    ]
                    alt_lbl = [f"{cat_name}-{'-'.join(r.name for r in combo)}"]
                    for s in (*remaining, *free_r):
                        alt_ids.append(
                            CalcID(
                                method_key=method_key,
                                catalyst=None,
                                stage="reactants",
                                species=sanitize(s.name),
                                mode=mode,
                                sp_subfolder=sp_subfolder,
                            )
                        )
                        alt_lbl.append(s.name)
                    pre_alt_data.append((tuple(alt_ids), " + ".join(alt_lbl), combo))
        ts_id = CalcID(
            method_key=method_key,
            catalyst=cat_s,
            stage="ts",
            species=f"{cat_s}-{_TS_SPECIES}",
            calc_type=calc_type,
            mode=mode,
            sp_subfolder=sp_subfolder,
        )
        # Uncatalyzed TS complex — needed for NI translational frame
        uncat_ts_id = CalcID(
            method_key=method_key,
            catalyst=None,
            stage="ts",
            species=_TS_SPECIES,
            mode=mode,
            sp_subfolder=sp_subfolder,
        )

        # --- postTS stage ---
        incl_p_combo_name = "-".join(sanitize(p.name) for p in incl_p)
        post_complex_species = f"{cat_s}-{incl_p_combo_name}" if incl_p else cat_s
        post_ts_ids: list[CalcID] = [
            CalcID(
                method_key=method_key,
                catalyst=cat_s,
                stage="postTS",
                species=post_complex_species,
                calc_type=calc_type,
                mode=mode,
                sp_subfolder=sp_subfolder,
            ),
        ]
        post_label_parts = [f"{cat_name}-{'-'.join(p.name for p in incl_p)}"]
        for fp in free_p:
            post_ts_ids.append(
                CalcID(
                    method_key=method_key,
                    catalyst=None,
                    stage="products",
                    species=sanitize(fp.name),
                    mode=mode,
                    sp_subfolder=sp_subfolder,
                )
            )
            post_label_parts.append(fp.name)

        # postTS alternatives: proper subsets of included products
        post_alt_data: list[tuple[tuple[CalcID, ...], str, tuple[SpeciesConfig, ...]]] = []
        if len(incl_p) > 1:
            for size in range(1, len(incl_p)):
                for combo in combinations(incl_p, size):
                    remaining = [p for p in incl_p if p not in combo]
                    combo_name = "-".join(sanitize(p.name) for p in combo)
                    alt_species = f"{cat_s}-{combo_name}"
                    alt_ids = [
                        CalcID(
                            method_key=method_key,
                            catalyst=cat_s,
                            stage="postTS",
                            species=alt_species,
                            calc_type=calc_type,
                            mode=mode,
                            sp_subfolder=sp_subfolder,
                        ),
                    ]
                    alt_lbl = [f"{cat_name}-{'-'.join(p.name for p in combo)}"]
                    for s in (*remaining, *free_p):
                        alt_ids.append(
                            CalcID(
                                method_key=method_key,
                                catalyst=None,
                                stage="products",
                                species=sanitize(s.name),
                                mode=mode,
                                sp_subfolder=sp_subfolder,
                            )
                        )
                        alt_lbl.append(s.name)
                    post_alt_data.append((tuple(alt_ids), " + ".join(alt_lbl), combo))

        # --- products stage ---
        product_ids: list[CalcID] = [
            CalcID(
                method_key=method_key,
                catalyst=None,
                stage="products",
                species=sanitize(p.name),
                mode=mode,
                sp_subfolder=sp_subfolder,
            )
            for p in self._config.products
        ]
        product_ids.append(cat_standalone)
        product_label = " + ".join([p.name for p in self._config.products] + [cat_name])

        # --- NI references (full_cat only) ---
        r_ids = tuple(reactant_ids)
        p_ids = tuple(product_ids)

        def _ni(ref: tuple[CalcID, ...], trans: tuple[CalcID, ...]) -> NiStageRef | None:
            """Build NI reference for full_cat profiles, None otherwise."""
            if calc_type != _FULL_CAT:
                return None
            return NiStageRef(ref_cids=ref, trans_cids=trans, apply_ssc_to_g_ni=apply_ssc)

        # Build StageAlt objects now that _ni is available
        pre_alts = tuple(
            StageAlt(calc_ids=ids, label=lbl, ni_ref=_ni(r_ids, ids))
            for ids, lbl, _ in pre_alt_data
        )
        post_alts = tuple(
            StageAlt(calc_ids=ids, label=lbl, ni_ref=_ni(p_ids, ids))
            for ids, lbl, _ in post_alt_data
        )

        stages = (
            StageSpec(
                name="reactants",
                calc_ids=r_ids,
                label=reactant_label,
            ),
            StageSpec(
                name="preTS",
                calc_ids=tuple(pre_ts_ids),
                label=" + ".join(pre_label_parts),
                ni_ref=_ni(r_ids, tuple(pre_ts_ids)),
                alternatives=pre_alts,
            ),
            StageSpec(
                name="ts",
                calc_ids=(ts_id,),
                label=f"ts_{cat_name}-{_TS_SPECIES}",
                ni_ref=_ni((uncat_ts_id, cat_standalone), (ts_id,)),
            ),
            StageSpec(
                name="postTS",
                calc_ids=tuple(post_ts_ids),
                label=" + ".join(post_label_parts),
                ni_ref=_ni(p_ids, tuple(post_ts_ids)),
                alternatives=post_alts,
            ),
            StageSpec(
                name="products",
                calc_ids=p_ids,
                label=product_label,
            ),
        )

        self._profiles[pid] = ProfileSpec(
            id=pid,
            stages=stages,
            selection_leader=(calc_type == _FULL_CAT),
        )
