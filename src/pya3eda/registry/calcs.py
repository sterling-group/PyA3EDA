"""Enumerate every expected calculation (``CalcSpec``) from a config."""

from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import TypedDict

from pya3eda.config import Config, TheoryConfig
from pya3eda.ids import CalcID, CalcSpec
from pya3eda.registry._common import _CALC_TYPES, _TS_SPECIES, _sp_subfolder, build_method_key
from pya3eda.registry.paths import build_input_path
from pya3eda.sanitize import sanitize
from pya3eda.vocab import Mode, Stage


class _CommonCalcKwargs(TypedDict):
    """Theory/context kwargs shared by every ``add_calc`` call in a level."""

    method_name: str
    basis_set: str
    dispersion: str
    solvent: str
    eda2: int | None
    sp_subfolder: str | None
    all_reactants: tuple[str, ...]
    all_products: tuple[str, ...]
    all_catalysts: tuple[str, ...]


def enumerate_calcs(config: Config, base_dir: Path) -> tuple[dict[CalcID, CalcSpec], list[str]]:
    """Enumerate all calc specs, returning ``(calcs, ordered_method_keys)``."""
    calcs: dict[CalcID, CalcSpec] = {}
    seen_method_keys: list[str] = []

    for level in config.levels:
        method_key = build_method_key(level.opt)
        if method_key not in seen_method_keys:
            seen_method_keys.append(method_key)

        # OPT calcs
        _enumerate_calcs_for_theory(config, calcs, base_dir, level.opt, method_key, Mode.OPT)

        # SP calcs (one round per SP theory)
        for sp_theory in level.sp:
            _enumerate_calcs_for_theory(
                config,
                calcs,
                base_dir,
                sp_theory,
                method_key,
                Mode.SP,
                sp_subfolder=_sp_subfolder(sp_theory),
            )

    return calcs, seen_method_keys


def _enumerate_calcs_for_theory(
    config: Config,
    calcs: dict[CalcID, CalcSpec],
    base_dir: Path,
    theory: TheoryConfig,
    method_key: str,
    mode: str,
    sp_subfolder: str | None = None,
) -> None:
    """Enumerate all calc specs for one theory (opt or sp) under one level."""
    cfg = config
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
        "eda2": theory.eda2 if mode == Mode.SP else None,
        "sp_subfolder": sp_subfolder,
        "all_reactants": all_r,
        "all_products": all_p,
        "all_catalysts": all_c,
    }

    # ── uncatalyzed ────────────────────────────────────────────────
    # Individual reactants
    for r in cfg.reactants:
        add_calc(
            calcs,
            base_dir,
            method_key=method_key,
            catalyst=None,
            stage=Stage.REACTANTS,
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
                add_calc(
                    calcs,
                    base_dir,
                    method_key=method_key,
                    catalyst=None,
                    stage=Stage.REACTANTS,
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
        add_calc(
            calcs,
            base_dir,
            method_key=method_key,
            catalyst=None,
            stage=Stage.PRODUCTS,
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
    add_calc(
        calcs,
        base_dir,
        method_key=method_key,
        catalyst=None,
        stage=Stage.TS,
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
        add_calc(
            calcs,
            base_dir,
            method_key=method_key,
            catalyst=cat_s,
            stage=Stage.CAT,
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
            add_calc(
                calcs,
                base_dir,
                method_key=method_key,
                catalyst=cat_s,
                stage=Stage.DIMER,
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
                    add_calc(
                        calcs,
                        base_dir,
                        method_key=method_key,
                        catalyst=cat_s,
                        stage=Stage.PRETS,
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
                    add_calc(
                        calcs,
                        base_dir,
                        method_key=method_key,
                        catalyst=cat_s,
                        stage=Stage.POSTTS,
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
            add_calc(
                calcs,
                base_dir,
                method_key=method_key,
                catalyst=cat_s,
                stage=Stage.TS,
                species=f"{cat_s}-{_TS_SPECIES}",
                calc_type=ct,
                mode=mode,
                is_fragmented=True,
                present_reactants=all_r,
                present_products=all_p,
                present_catalysts=(cat.name,),
                **common,
            )


def add_calc(
    calcs: dict[CalcID, CalcSpec],
    base_dir: Path,
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
    """Create CalcID + CalcSpec and register them in *calcs*."""
    cid = CalcID(
        method_key=method_key,
        catalyst=catalyst,
        stage=stage,
        species=species,
        calc_type=calc_type,
        mode=mode,
        sp_subfolder=sp_subfolder,
    )
    if cid in calcs:
        return  # duplicate id (e.g. OPT theories differing only in SP-only fields)

    input_path = build_input_path(
        base_dir,
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
    calcs[cid] = spec
