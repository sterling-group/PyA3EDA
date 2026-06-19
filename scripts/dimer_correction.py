#!/usr/bin/env python
"""Apply a catalyst-dimer dissociation correction to the ΔΔ‡ barplot.

Some catalysts (e.g. Schreiner-type H-bond donors) have a *dimer* resting state.
The standard barplot references the catalyst monomer (which cancels on both
sides of every barrier); when the true resting state is a dimer, freeing one
active monomer costs the dimer dissociation energy and leaves the second monomer
as a spectator. The net effect on the overall catalysis is a per-(catalyst,
surface) shift::

    correction = 2*E_cat - E_dimer        ( = -binding energy = +dissociation cost )

This script re-runs the normal extraction pipeline, computes that correction
from the monomer-catalyst energies already in the run plus the dimer OPT/SP
outputs you point it at, adds it as a leading ``DISS`` contribution (so ``FULL``
grows by it), and re-renders the ΔΔ‡ CSVs + barplots.

    PYTHONPATH=src python scripts/dimer_correction.py config.yaml \\
        --catalyst lip --dimer-opt dimer_opt.out --dimer-sp dimer_sp.out \\
        --out-dir corrected/

``--out-dir`` defaults to the config directory (overwrites the delta_delta CSVs
and barplots in place); point it elsewhere for a non-destructive copy.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pya3eda.config import load_config
from pya3eda.exporter.results import export_all
from pya3eda.extractor.barriers import compute_delta_delta
from pya3eda.extractor.data import (
    extract_all,
    extract_opt_energies,
    extract_sp_energies,
)
from pya3eda.extractor.stages import build_profiles
from pya3eda.ids import CalcID, DeltaDeltaData
from pya3eda.plotter.contributions import plot_delta_delta_barplots
from pya3eda.plotter.profile import plot_all_profiles
from pya3eda.registry import CalcRegistry
from pya3eda.sanitize import sanitize
from pya3eda.utils import read_text

log = logging.getLogger("pya3eda.dimer_correction")

_Cache = dict[tuple[str, str | None], tuple[float | None, float | None]]


def _dimer_energies(
    mode: str,
    sp_subfolder: str | None,
    solvent: str,
    opt_text: str,
    sp_text: str | None,
    cache: _Cache,
) -> tuple[float | None, float | None]:
    """Return ``(E, G)`` of the dimer at one level, memoised per (mode, sp_subfolder)."""
    key = (mode, sp_subfolder)
    if key not in cache:
        if mode == "opt":
            cache[key] = extract_opt_energies(opt_text, solvent)
        elif sp_text is None:
            cache[key] = (None, None)
        else:
            cache[key] = extract_sp_energies(sp_text, opt_text, solvent, None)
    return cache[key]


def correct_delta_delta(
    dd_list: list[DeltaDeltaData],
    registry: CalcRegistry,
    extracted: dict[CalcID, object],
    *,
    catalyst: str,
    opt_text: str,
    sp_text: str | None,
) -> list[DeltaDeltaData]:
    """Return *dd_list* with the dimer dissociation correction applied to *catalyst*."""
    cat_s = sanitize(catalyst)
    cache: _Cache = {}
    out: list[DeltaDeltaData] = []
    for dd in dd_list:
        if sanitize(dd.catalyst) != cat_s:
            out.append(dd)
            continue

        cid = CalcID(
            method_key=dd.method_key,
            catalyst=cat_s,
            stage="cat",
            species=cat_s,
            mode=dd.mode,
            sp_subfolder=dd.sp_subfolder,
        )
        cat_data = extracted.get(cid)
        try:
            solvent = registry.get(cid).solvent
        except KeyError:
            solvent = "false"
        if cat_data is None or dd.dd_complete is None:
            log.warning(
                "No monomer-catalyst data for %s; leaving %s uncorrected", cid, dd.energy_type
            )
            out.append(dd)
            continue

        e_dimer, g_dimer = _dimer_energies(
            dd.mode, dd.sp_subfolder, solvent, opt_text, sp_text, cache
        )
        if dd.energy_type == "E":
            cat_x = cat_data.energy if cat_data.energy is not None else cat_data.sp_energy
            dimer_x = e_dimer
        else:  # "G" | "G_ni"
            cat_x = cat_data.G
            dimer_x = g_dimer

        if cat_x is None or dimer_x is None:
            log.warning(
                "Missing %s energy for dimer correction (%s); skipping", dd.energy_type, cid
            )
            out.append(dd)
            continue

        corr = 2.0 * cat_x - dimer_x
        barrier_full = dd.barrier_full + corr if dd.barrier_full is not None else None
        out.append(
            dd.model_copy(
                update={
                    "dd_dissoc": corr,
                    "dd_complete": dd.dd_complete + corr,
                    "barrier_full": barrier_full,
                }
            )
        )
        log.info("Corrected %s/%s %s by %+.3f kcal/mol", dd.method_key, cat_s, dd.energy_type, corr)
    return out


def build_parser() -> argparse.ArgumentParser:
    """Build the dimer-correction CLI parser."""
    p = argparse.ArgumentParser(
        prog="dimer_correction",
        description="Apply a catalyst-dimer dissociation correction to the ΔΔ‡ barplot.",
    )
    p.add_argument("config", help="Path to the YAML config file")
    p.add_argument("--catalyst", required=True, help="Catalyst that forms the dimer")
    p.add_argument("--dimer-opt", required=True, help="Dimer OPT output file (thermo → G)")
    p.add_argument(
        "--dimer-sp", default=None, help="Dimer SP output file (electronic → E); optional"
    )
    p.add_argument("--out-dir", default=None, help="Output dir (default: config dir, overwrites)")
    p.add_argument("--log", default="INFO", help="Logging level")
    return p


def main(argv: list[str] | None = None) -> None:
    """Run the dimer correction from CLI arguments."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log.upper(), logging.INFO))

    config = load_config(args.config)
    base_dir = Path(args.config).resolve().parent
    registry = CalcRegistry(config, base_dir)

    opt_text = read_text(args.dimer_opt)
    if opt_text is None:
        raise FileNotFoundError(f"Dimer OPT output not found: {args.dimer_opt}")
    sp_text = read_text(args.dimer_sp) if args.dimer_sp else None

    extracted = extract_all(registry)
    profiles = build_profiles(registry, extracted)
    dd = compute_delta_delta(profiles, registry.catalyst_order)
    dd_corrected = correct_delta_delta(
        dd, registry, extracted, catalyst=args.catalyst, opt_text=opt_text, sp_text=sp_text
    )

    out_dir = Path(args.out_dir) if args.out_dir else base_dir
    export_all(registry, extracted, profiles, dd_corrected, out_dir)
    plot_all_profiles(profiles, registry, out_dir)
    plot_delta_delta_barplots(dd_corrected, registry, out_dir)
    log.info("Wrote dimer-corrected results to %s", out_dir / "results")


if __name__ == "__main__":
    main()
