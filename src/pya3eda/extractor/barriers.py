"""Compute ΔΔ‡ barrier decomposition from assembled profiles."""

from __future__ import annotations

import logging

from pya3eda.ids import DeltaDeltaData, ProfileData, ProfileID, StageData

log = logging.getLogger(__name__)


def compute_delta_delta(
    profiles: dict[ProfileID, ProfileData],
    catalyst_order: list[str],
) -> list[DeltaDeltaData]:
    """Compute ΔΔ‡ for every method_key x catalyst x energy_type.

    Baseline logic (for each catalyst):
      • Evaluate on the **full_cat** profile first.
      • If preTS_full < reactants → use preTS as baseline for **all** calc_types.
      • Otherwise → use reactants as baseline for all.
    """
    results: list[DeltaDeltaData] = []
    method_keys = sorted({pid.method_key for pid in profiles})

    for mk in method_keys:
        mk_profiles = {pid: pd for pid, pd in profiles.items() if pid.method_key == mk}

        # Discover (mode, sp_subfolder) pairs from actual profiles
        mode_sps = sorted({(pid.mode, pid.sp_subfolder) for pid in mk_profiles})

        for cat in catalyst_order:
            for mode, sp_sub in mode_sps:
                dd = _compute_for_catalyst(mk, cat, mode, sp_sub, mk_profiles)
                results.extend(dd)

    log.info("Computed %d delta-delta entries", len(results))
    return results


def _compute_for_catalyst(
    method_key: str,
    catalyst: str,
    mode: str,
    sp_subfolder: str | None,
    profiles: dict[ProfileID, ProfileData],
) -> list[DeltaDeltaData]:
    """Compute ΔΔ‡ for one method_key x one catalyst x one mode, across energy types."""

    # Gather relevant profiles → stage maps (dict lookup, no linear search)
    def _find(calc_type: str) -> dict[str, StageData] | None:
        """Look up a profile by calc_type and return its stage map."""
        pid = ProfileID(
            method_key=method_key,
            catalyst=catalyst,
            calc_type=calc_type,
            mode=mode,
            sp_subfolder=sp_subfolder,
        )
        pd = profiles.get(pid)
        return _stage_map(pd) if pd is not None else None

    full = _find("full_cat")
    pol = _find("pol_cat")
    frz = _find("frz_cat")
    nocat = _find("nocat")
    ni = _find("ni")

    out: list[DeltaDeltaData] = []
    for etype in StageData.barrier_surfaces():
        is_ni = etype == "G_ni"
        surface = "G" if is_ni else etype

        # Baseline decision driven by full_cat on the matching surface
        use_preTS = False
        if full:
            use_preTS = _should_use_preTS(
                full, "G"
            )  # change to surface if we want to decide separately per surface

        b_nocat = _barrier(nocat, surface, use_preTS=False)
        b_full = _barrier(full, surface, use_preTS=use_preTS)
        b_pol = _barrier(pol, surface, use_preTS=use_preTS)
        b_frz = _barrier(frz, surface, use_preTS=use_preTS)
        b_ni = _barrier(ni, "G", use_preTS=use_preTS) if is_ni else None

        # For G_ni the NI barrier sits between nocat and FRZ
        frz_base = b_ni if is_ni else b_nocat

        dd_ni = _diff(b_ni, b_nocat)
        dd_frz = _diff(b_frz, frz_base)
        dd_pol = _diff(b_pol, b_frz)
        dd_ct = _diff(b_full, b_pol)
        dd_complete = _diff(b_full, b_nocat)

        # Skip G_ni row when NI data is unavailable
        if is_ni and (b_ni is None or b_nocat is None):
            continue

        out.append(
            DeltaDeltaData(
                method_key=method_key,
                catalyst=catalyst,
                energy_type=etype,
                mode=mode,
                sp_subfolder=sp_subfolder,
                barrier_uncat=b_nocat,
                barrier_ni=b_ni,
                barrier_frz=b_frz,
                barrier_pol=b_pol,
                barrier_full=b_full,
                dd_ni=dd_ni,
                dd_frz=dd_frz,
                dd_pol=dd_pol,
                dd_ct=dd_ct,
                dd_complete=dd_complete,
            )
        )

    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stage_value(stage: StageData, etype: str) -> float | None:
    """Return the energy attribute *etype* from *stage*, or ``None``."""
    return getattr(stage, etype, None)


def _diff(a: float | None, b: float | None) -> float | None:
    """a - b, or None if either operand is missing."""
    return (a - b) if a is not None and b is not None else None


def _stage_map(pd: ProfileData) -> dict[str, StageData]:
    """Build a name → stage lookup from a profile's stage tuple."""
    return {s.name: s for s in pd.stages}


def _should_use_preTS(stages: dict[str, StageData], etype: str) -> bool:
    """True if preTS_full < reactants on the given energy surface."""
    reactants = stages.get("reactants")
    preTS = stages.get("preTS")
    if reactants is None or preTS is None:
        return False
    r_val = _stage_value(reactants, etype)
    p_val = _stage_value(preTS, etype)
    if r_val is None or p_val is None:
        return False
    return p_val < r_val


def _barrier(
    stages: dict[str, StageData] | None,
    etype: str,
    use_preTS: bool,
) -> float | None:
    """barrier = TS - baseline."""
    if stages is None:
        return None
    ts = stages.get("ts")
    if ts is None:
        return None
    ts_val = _stage_value(ts, etype)
    if ts_val is None:
        return None

    if use_preTS:
        preTS = stages.get("preTS")
        if preTS is not None:
            p_val = _stage_value(preTS, etype)
            if p_val is not None:
                return ts_val - p_val

    reactants = stages.get("reactants")
    if reactants is None:
        return None
    r_val = _stage_value(reactants, etype)
    if r_val is None:
        return None
    return ts_val - r_val
