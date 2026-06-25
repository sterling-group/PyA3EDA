"""Enumerate every energy profile (``ProfileSpec``) from a config."""

from __future__ import annotations

from itertools import combinations
from typing import Protocol

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


class _CidFactory(Protocol):
    """A CalcID builder with the per-profile method_key/mode/sp_subfolder bound."""

    def __call__(
        self,
        *,
        stage: str,
        species: str,
        catalyst: str | None = None,
        calc_type: str | None = None,
    ) -> CalcID: ...


def _calc_id_factory(method_key: str, mode: str, sp_subfolder: str | None) -> _CidFactory:
    """Return a :class:`CalcID` builder that closes over the constant id fields.

    Every ``CalcID`` within one profile shares ``method_key``/``mode``/
    ``sp_subfolder``; the factory fills them so call sites pass only the fields
    that actually vary (stage, species, catalyst, calc_type).
    """

    def make(
        *,
        stage: str,
        species: str,
        catalyst: str | None = None,
        calc_type: str | None = None,
    ) -> CalcID:
        return CalcID(
            method_key=method_key,
            catalyst=catalyst,
            stage=stage,
            species=species,
            calc_type=calc_type,
            mode=mode,
            sp_subfolder=sp_subfolder,
        )

    return make


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
    cid = _calc_id_factory(method_key, mode, sp_subfolder)
    pid = ProfileID(
        method_key=method_key,
        catalyst=None,
        calc_type=None,
        mode=mode,
        sp_subfolder=sp_subfolder,
    )

    all_reactant_ids = [cid(stage="reactants", species=sanitize(r.name)) for r in config.reactants]
    all_product_ids = [cid(stage="products", species=sanitize(p.name)) for p in config.products]
    ts_id = cid(stage="ts", species=_TS_SPECIES)

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
    cid = _calc_id_factory(method_key, mode, sp_subfolder)
    pid = ProfileID(
        method_key=method_key,
        catalyst=cat_s,
        calc_type="nocat",
        mode=mode,
        sp_subfolder=sp_subfolder,
    )

    cat_standalone = cid(catalyst=cat_s, stage="cat", species=cat_s)

    reactant_ids = tuple(
        [cid(stage="reactants", species=sanitize(r.name)) for r in config.reactants]
        + [cat_standalone]
    )
    uncat_ts_id = cid(stage="ts", species=_TS_SPECIES)
    ts_ids = (uncat_ts_id, cat_standalone)
    product_ids = tuple(
        [cid(stage="products", species=sanitize(p.name)) for p in config.products]
        + [cat_standalone]
    )

    reactant_label = " + ".join([r.name for r in config.reactants] + [cat_name])
    product_label = " + ".join([p.name for p in config.products] + [cat_name])

    stages = (
        StageSpec(name="reactants", calc_ids=reactant_ids, label=reactant_label),
        StageSpec(name="ts", calc_ids=ts_ids, label=f"{_TS_SPECIES} + {cat_name}"),
        StageSpec(name="products", calc_ids=product_ids, label=product_label),
    )

    profiles[pid] = ProfileSpec(id=pid, stages=stages)


def _build_complex_stage(
    cid: _CidFactory,
    cat_s: str,
    cat_name: str,
    calc_type: str,
    incl: list[SpeciesConfig],
    free: list[SpeciesConfig],
    complex_stage: str,
    free_stage: str,
) -> tuple[list[CalcID], str, list[tuple[tuple[CalcID, ...], str]]]:
    """Build one complex stage (preTS or postTS) — mirror-shared by both sides.

    Returns the primary ``(calc_ids, label, alternatives)`` for a stage made of
    the catalyst+included-species complex plus the free species standalone, where
    *alternatives* are the proper-subset complexes (each as ``(calc_ids, label)``).
    The reactant side passes ``("preTS", "reactants")`` and ``incl_r``/``free_r``;
    the product side passes ``("postTS", "products")`` and ``incl_p``/``free_p``.
    """
    combo_name = "-".join(sanitize(s.name) for s in incl)
    complex_species = f"{cat_s}-{combo_name}" if incl else cat_s
    ids: list[CalcID] = [
        cid(catalyst=cat_s, stage=complex_stage, species=complex_species, calc_type=calc_type)
    ]
    label_parts = [f"{cat_name}-{'-'.join(s.name for s in incl)}"]
    for fs in free:
        ids.append(cid(stage=free_stage, species=sanitize(fs.name)))
        label_parts.append(fs.name)

    # Alternatives: proper subsets of the included species
    alt_data: list[tuple[tuple[CalcID, ...], str]] = []
    if len(incl) > 1:
        for size in range(1, len(incl)):
            for combo in combinations(incl, size):
                remaining = [s for s in incl if s not in combo]
                alt_species = f"{cat_s}-{'-'.join(sanitize(s.name) for s in combo)}"
                alt_ids: list[CalcID] = [
                    cid(
                        catalyst=cat_s,
                        stage=complex_stage,
                        species=alt_species,
                        calc_type=calc_type,
                    )
                ]
                alt_lbl = [f"{cat_name}-{'-'.join(s.name for s in combo)}"]
                for s in (*remaining, *free):
                    alt_ids.append(cid(stage=free_stage, species=sanitize(s.name)))
                    alt_lbl.append(s.name)
                alt_data.append((tuple(alt_ids), " + ".join(alt_lbl)))
    return ids, " + ".join(label_parts), alt_data


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
    cid = _calc_id_factory(method_key, mode, sp_subfolder)
    pid = ProfileID(
        method_key=method_key,
        catalyst=cat_s,
        calc_type=calc_type,
        mode=mode,
        sp_subfolder=sp_subfolder,
    )

    # --- reactants / products endpoint stages (standalone species + catalyst) ---
    cat_standalone = cid(catalyst=cat_s, stage="cat", species=cat_s)
    reactant_ids = [cid(stage="reactants", species=sanitize(r.name)) for r in config.reactants]
    reactant_ids.append(cat_standalone)
    reactant_label = " + ".join([r.name for r in config.reactants] + [cat_name])

    product_ids = [cid(stage="products", species=sanitize(p.name)) for p in config.products]
    product_ids.append(cat_standalone)
    product_label = " + ".join([p.name for p in config.products] + [cat_name])

    # --- preTS / postTS complex stages (mirror-shared) ---
    pre_ts_ids, pre_label, pre_alt_data = _build_complex_stage(
        cid, cat_s, cat_name, calc_type, incl_r, free_r, "preTS", "reactants"
    )
    post_ts_ids, post_label, post_alt_data = _build_complex_stage(
        cid, cat_s, cat_name, calc_type, incl_p, free_p, "postTS", "products"
    )

    # --- TS stage (+ uncatalyzed TS for the NI translational frame) ---
    ts_id = cid(catalyst=cat_s, stage="ts", species=f"{cat_s}-{_TS_SPECIES}", calc_type=calc_type)
    uncat_ts_id = cid(stage="ts", species=_TS_SPECIES)

    # --- NI references (full_cat only) ---
    r_ids = tuple(reactant_ids)
    p_ids = tuple(product_ids)

    def _ni(ref: tuple[CalcID, ...], trans: tuple[CalcID, ...]) -> NiStageRef | None:
        """Build NI reference for full_cat profiles, None otherwise."""
        if calc_type != _FULL_CAT:
            return None
        return NiStageRef(ref_cids=ref, trans_cids=trans, apply_ssc_to_g_ni=apply_ssc)

    pre_alts = tuple(
        StageAlt(calc_ids=ids, label=lbl, ni_ref=_ni(r_ids, ids)) for ids, lbl in pre_alt_data
    )
    post_alts = tuple(
        StageAlt(calc_ids=ids, label=lbl, ni_ref=_ni(p_ids, ids)) for ids, lbl in post_alt_data
    )

    stages = (
        StageSpec(name="reactants", calc_ids=r_ids, label=reactant_label),
        StageSpec(
            name="preTS",
            calc_ids=tuple(pre_ts_ids),
            label=pre_label,
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
            label=post_label,
            ni_ref=_ni(p_ids, tuple(post_ts_ids)),
            alternatives=post_alts,
        ),
        StageSpec(name="products", calc_ids=p_ids, label=product_label),
    )

    profiles[pid] = ProfileSpec(
        id=pid,
        stages=stages,
        selection_leader=(calc_type == _FULL_CAT),
    )
