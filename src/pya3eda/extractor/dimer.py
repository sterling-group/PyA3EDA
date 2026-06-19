"""Catalyst-dimer dissociation (DISS) correction for the ΔΔ‡ barplot.

A catalyst declared ``dimer: true`` has a dimer resting state; freeing one active
monomer costs the dimer dissociation energy (the second monomer is a spectator).
The net per-(catalyst, surface) shift is::

    correction = 2 * X_cat - X_dimer

added as a leading **DISS** contribution (:attr:`DeltaDeltaData.dd_dissoc`) so
``FULL`` grows by it. The dimer is a normal ``dimer``-stage calculation in the
tree, so both ``X_cat`` (monomer) and ``X_dimer`` come from the standard
extraction — nothing here parses files.
"""

from __future__ import annotations

import logging

from pya3eda.errors import IncompleteDataError
from pya3eda.ids import CalcID, DeltaDeltaData, ExtractedData
from pya3eda.registry import CalcRegistry
from pya3eda.sanitize import sanitize

log = logging.getLogger(__name__)


def _surface_value(data: ExtractedData, energy_type: str) -> float | None:
    """Electronic energy for ``E``; free energy for ``G``/``G_ni``."""
    if energy_type == "E":
        return data.energy if data.energy is not None else data.sp_energy
    return data.G


def apply_dimer_corrections(
    dd_list: list[DeltaDeltaData],
    registry: CalcRegistry,
    extracted: dict[CalcID, ExtractedData],
) -> list[DeltaDeltaData]:
    """Add the dimer dissociation (DISS) term for every ``dimer: true`` catalyst.

    Non-dimer catalysts pass through unchanged (``dd_dissoc`` stays ``None`` so the
    normal barplots are byte-identical). A dimer whose calc was not extracted is
    logged and skipped; a dimer that *ran* but lacks the value the surface needs
    fails loud via :class:`IncompleteDataError`.
    """
    dimer_cats = registry.dimer_catalysts
    if not dimer_cats:
        return dd_list

    out: list[DeltaDeltaData] = []
    errors: list[str] = []

    for dd in dd_list:
        cat_s = sanitize(dd.catalyst)
        if cat_s not in dimer_cats:
            out.append(dd)
            continue

        cat_cid = CalcID(
            method_key=dd.method_key,
            catalyst=cat_s,
            stage="cat",
            species=cat_s,
            mode=dd.mode,
            sp_subfolder=dd.sp_subfolder,
        )
        dimer_cid = CalcID(
            method_key=dd.method_key,
            catalyst=cat_s,
            stage="dimer",
            species=f"{cat_s}-dimer",
            mode=dd.mode,
            sp_subfolder=dd.sp_subfolder,
        )
        cat_data = extracted.get(cat_cid)
        dimer_data = extracted.get(dimer_cid)

        if cat_data is None or dimer_data is None or dd.dd_complete is None:
            missing = "monomer" if cat_data is None else "dimer"
            log.warning(
                "Dimer correction for %s/%s (%s) skipped — %s data not extracted",
                dd.method_key,
                cat_s,
                dd.energy_type,
                missing,
            )
            out.append(dd)
            continue

        x_cat = _surface_value(cat_data, dd.energy_type)
        x_dimer = _surface_value(dimer_data, dd.energy_type)
        if x_cat is None or x_dimer is None:
            which = "monomer" if x_cat is None else "dimer"
            errors.append(
                f"{dd.method_key}/{cat_s} {dd.energy_type}: {which} ran but has no "
                f"{dd.energy_type} value — cannot compute the dimer correction"
            )
            out.append(dd)
            continue

        corr = 2.0 * x_cat - x_dimer
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
        log.info(
            "Dimer correction %s/%s %s: %+.3f kcal/mol",
            dd.method_key,
            cat_s,
            dd.energy_type,
            corr,
        )

    if errors:
        raise IncompleteDataError.combine(errors)
    return out
