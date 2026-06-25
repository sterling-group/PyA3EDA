"""Enumerate every energy profile (``ProfileSpec``) from a config."""

from __future__ import annotations

from itertools import combinations

from pya3eda.config import Config, SpeciesConfig
from pya3eda.ids import CalcID, NiStageRef, ProfileID, ProfileSpec, StageAlt, StageSpec
from pya3eda.registry._common import (
    _CALC_TYPES,
    _FULL_CAT,
    _TS_SPECIES,
    _has_solvent,
    _sp_subfolder,
    build_method_key,
)
from pya3eda.sanitize import sanitize


def enumerate_profiles(config: Config) -> dict[ProfileID, ProfileSpec]:
    """Build all ProfileSpecs from config (forward composition)."""
    profiles: dict[ProfileID, ProfileSpec] = {}
    cfg = config
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
            _build_uncatalyzed_profile(cfg, profiles, method_key, mode, sp_subfolder=sp_sub)

            for cat in cfg.catalysts:
                _build_nocat_profile(cfg, profiles, method_key, mode, cat.name, sp_subfolder=sp_sub)
                for ct in _CALC_TYPES:
                    _build_catalyzed_profile(
                        cfg,
                        profiles,
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

    return profiles


def _build_uncatalyzed_profile(
    config: Config,
    profiles: dict[ProfileID, ProfileSpec],
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
        for r in config.reactants
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
        for p in config.products
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
            label=" + ".join(r.name for r in config.reactants),
        ),
        StageSpec(
            name="ts",
            calc_ids=(ts_id,),
            label=_TS_SPECIES,
        ),
        StageSpec(
            name="products",
            calc_ids=tuple(all_product_ids),
            label=" + ".join(p.name for p in config.products),
        ),
    )

    profiles[pid] = ProfileSpec(id=pid, stages=stages)


def _build_nocat_profile(
    config: Config,
    profiles: dict[ProfileID, ProfileSpec],
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
            for r in config.reactants
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
            for p in config.products
        ]
        + [cat_standalone]
    )

    reactant_label = " + ".join([r.name for r in config.reactants] + [cat_name])
    product_label = " + ".join([p.name for p in config.products] + [cat_name])

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

    profiles[pid] = ProfileSpec(id=pid, stages=stages)


def _build_catalyzed_profile(
    config: Config,
    profiles: dict[ProfileID, ProfileSpec],
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
        for r in config.reactants
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
    reactant_label = " + ".join([r.name for r in config.reactants] + [cat_name])

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
        for p in config.products
    ]
    product_ids.append(cat_standalone)
    product_label = " + ".join([p.name for p in config.products] + [cat_name])

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
        StageAlt(calc_ids=ids, label=lbl, ni_ref=_ni(r_ids, ids)) for ids, lbl, _ in pre_alt_data
    )
    post_alts = tuple(
        StageAlt(calc_ids=ids, label=lbl, ni_ref=_ni(p_ids, ids)) for ids, lbl, _ in post_alt_data
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

    profiles[pid] = ProfileSpec(
        id=pid,
        stages=stages,
        selection_leader=(calc_type == _FULL_CAT),
    )
