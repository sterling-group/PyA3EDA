"""Export extracted data to CSV files and XYZ coordinate files."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from pya3eda.ids import (
    CalcID,
    DeltaDeltaData,
    ExtractedData,
    ProfileData,
    ProfileID,
    StageData,
)
from pya3eda.registry import CalcRegistry

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def export_all(
    registry: CalcRegistry,
    extracted: dict[CalcID, ExtractedData],
    profiles: dict[ProfileID, ProfileData],
    delta_delta: list[DeltaDeltaData],
    base_dir: Path,
) -> None:
    """Export all results to ``base_dir/results/{method_key}/...``."""
    results_dir = base_dir / "results"
    total = 0

    for mk in registry.method_keys:
        mk_dir = results_dir / mk

        # Raw calc data + per-profile CSVs
        total += _export_raw(extracted, mk, mk_dir / "raw_data")
        total += _export_raw_profiles(profiles, mk, mk_dir / "raw_data")

        # Combined profiles (per catalyst, mirroring plot traces)
        total += _export_profiles(profiles, mk, mk_dir / "profiles")

        # Delta-delta
        total += _export_delta_delta(delta_delta, mk, mk_dir / "delta_delta")

        # XYZ files
        total += _export_xyz(extracted, mk, mk_dir / "xyz_files")

    log.info("Exported %d files total", total)


# ---------------------------------------------------------------------------
# Raw calculation data
# ---------------------------------------------------------------------------


def _export_raw(
    extracted: dict[CalcID, ExtractedData],
    method_key: str,
    out_dir: Path,
) -> int:
    """Write per-calculation raw data CSVs; return number of files written."""
    rows_opt: list[dict] = []
    rows_sp: list[dict] = []

    for cid, data in extracted.items():
        if cid.method_key != method_key:
            continue
        row = {
            "catalyst": cid.catalyst or "no_cat",
            "stage": cid.stage,
            "species": cid.species,
            "calc_type": cid.calc_type or "",
            "mode": cid.mode,
            "status": data.status,
            "energy": data.energy,
            "sp_energy": data.sp_energy,
            "H": data.H,
            "G": data.G,
            "h_corr": data.h_corr,
            "s_corr": data.s_corr,
            "s_trans": data.s_trans,
            "temperature": data.temperature,
            "zpve": data.zpve,
            "imag_freq": data.imag_freq,
        }
        if cid.mode == "opt":
            rows_opt.append(row)
        else:
            rows_sp.append(row)

    count = 0
    if rows_opt:
        count += _write_csv(rows_opt, out_dir / f"opt_{method_key}.csv")
    if rows_sp:
        count += _write_csv(rows_sp, out_dir / f"sp_{method_key}.csv")
    return count


def _export_raw_profiles(
    profiles: dict[ProfileID, ProfileData],
    method_key: str,
    out_dir: Path,
) -> int:
    """Export one CSV per ProfileID (absolute + relative energies)."""
    count = 0
    unit = StageData.UNIT
    etypes = StageData.energy_types()

    for pid, pdata in profiles.items():
        if pid.method_key != method_key:
            continue

        cat_label = pid.catalyst or "no_cat"
        ct_label = pid.calc_type or "uncat"
        mlabel = ProfileID.method_label(method_key, pid.sp_subfolder)
        prefix = f"{pid.mode}_profile_{cat_label}_{ct_label}_{mlabel}"

        rows: list[dict] = []
        for stage in pdata.stages:
            row: dict = {
                "Stage": stage.name,
                "Calc_Type": stage.calc_type or "",
                "Species": stage.species_label,
            }
            for f in etypes:
                row[f"{f} ({unit})"] = getattr(stage, f)
                row[f"rel_{f} ({unit})"] = stage.rel(f)
            rows.append(row)

        if rows:
            count += _write_csv(rows, out_dir / f"{prefix}.csv")

    return count


# ---------------------------------------------------------------------------
# Profile export
# ---------------------------------------------------------------------------


def _export_profiles(
    profiles: dict[ProfileID, ProfileData],
    method_key: str,
    out_dir: Path,
) -> int:
    """Export one CSV per catalyst with all traces (uncat/NI/FRZ/POL/FULL), normalized."""
    unit = StageData.UNIT
    etypes = StageData.energy_types()
    traces = ProfileID.TRACE_ORDER
    count = 0

    # Discover catalysts and (mode, sp_subfolder) pairs
    catalysts: set[str] = set()
    mode_sps: set[tuple[str, str | None]] = set()
    for pid in profiles:
        if pid.method_key != method_key:
            continue
        mode_sps.add((pid.mode, pid.sp_subfolder))
        if pid.catalyst:
            catalysts.add(pid.catalyst)

    endpoints = {"reactants", "products"}

    for mode, sp_sub in sorted(mode_sps):
        for cat in sorted(catalysts):
            # Collect available profiles as name → stage maps
            available: list[tuple[str | None, str, dict[str, StageData]]] = []
            for calc_type, label in traces:
                pid = ProfileID(
                    method_key=method_key,
                    catalyst=None if calc_type is None else cat,
                    calc_type=calc_type,
                    mode=mode,
                    sp_subfolder=sp_sub,
                )
                pdata = profiles.get(pid)
                if pdata is not None:
                    available.append(
                        (calc_type, label, {s.name: s for s in pdata.stages})
                    )

            if not available:
                continue

            # Stage-major ordering; endpoints only for uncat
            rows: list[dict] = []
            for sname in ProfileID.STAGE_ORDER:
                for calc_type, label, smap in available:
                    if calc_type is not None and sname in endpoints:
                        continue
                    stage = smap.get(sname)
                    if stage is None:
                        continue
                    row: dict = {
                        "Trace": label,
                        "Stage": stage.name,
                        "Species": stage.species_label,
                    }
                    for f in etypes:
                        row[f"{f} ({unit})"] = stage.rel(f)
                    rows.append(row)

            if rows:
                mlabel = ProfileID.method_label(method_key, sp_sub)
                count += _write_csv(
                    rows, out_dir / f"{mode}_profile_{cat}_{mlabel}.csv"
                )

    return count


# ---------------------------------------------------------------------------
# Delta-delta export
# ---------------------------------------------------------------------------


def _export_delta_delta(
    delta_delta: list[DeltaDeltaData],
    method_key: str,
    out_dir: Path,
) -> int:
    """Export delta-delta barrier data to CSV for one method key."""
    mk_data = [dd for dd in delta_delta if dd.method_key == method_key]
    if not mk_data:
        return 0

    # Group by (mode, sp_subfolder) so OPT and SP get separate files
    mode_sps = sorted({(dd.mode, dd.sp_subfolder) for dd in mk_data})

    count = 0
    for mode, sp_sub in mode_sps:
        mlabel = ProfileID.method_label(method_key, sp_sub)
        subset = [dd for dd in mk_data if dd.mode == mode and dd.sp_subfolder == sp_sub]

        for etype in sorted({dd.energy_type for dd in subset}):
            rows = []
            for dd in subset:
                if dd.energy_type != etype:
                    continue
                row: dict = {
                    "Catalyst": dd.catalyst,
                    f"Barrier_uncat ({etype})": dd.barrier_uncat,
                }
                if etype == "G_ni":
                    row[f"Barrier_ni ({etype})"] = dd.barrier_ni
                row.update(
                    {
                        f"Barrier_frz ({etype})": dd.barrier_frz,
                        f"Barrier_pol ({etype})": dd.barrier_pol,
                        f"Barrier_full ({etype})": dd.barrier_full,
                    }
                )
                if etype == "G_ni":
                    row[f"DD_{etype}_ni"] = dd.dd_ni
                row.update(
                    {
                        f"DD_{etype}_frz": dd.dd_frz,
                        f"DD_{etype}_pol": dd.dd_pol,
                        f"DD_{etype}_ct": dd.dd_ct,
                        f"DD_{etype}_complete": dd.dd_complete,
                    }
                )
                rows.append(row)
            if rows:
                fname = f"{mode}_delta_delta_{etype}_{mlabel}.csv"
                count += _write_csv(rows, out_dir / fname)

    return count


# ---------------------------------------------------------------------------
# XYZ export
# ---------------------------------------------------------------------------


def _export_xyz(
    extracted: dict[CalcID, ExtractedData],
    method_key: str,
    out_dir: Path,
) -> int:
    """Export optimised XYZ geometries for one method key."""
    count = 0
    for cid, data in extracted.items():
        if cid.method_key != method_key:
            continue
        if data.xyz_text is None:
            continue

        out_dir.mkdir(parents=True, exist_ok=True)
        # Catalyzed stages need stage prefix (species is clean, no baked-in prefix)
        prefix = (
            f"{cid.stage}_"
            if cid.stage in ("preTS", "postTS", "ts") and cid.catalyst
            else ""
        )
        if cid.calc_type:
            out_path = out_dir / f"{prefix}{cid.species}_{cid.calc_type}.xyz"
        else:
            out_path = out_dir / f"{prefix}{cid.species}.xyz"
        out_path.write_text(data.xyz_text, encoding="utf-8")
        count += 1

    if count:
        log.info("Written %d XYZ files to %s", count, out_dir)
    return count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_csv(rows: list[dict], path: Path) -> int:
    """Write rows to CSV.  Returns 1 on success, 0 on failure."""
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    log.info("Saved %d rows to %s", len(rows), path)
    return 1
