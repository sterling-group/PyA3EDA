"""Assemble energy profiles from extracted data + ProfileSpecs."""

from __future__ import annotations

import logging

from pya3eda import constants as C
from pya3eda.ids import (
    CalcID,
    ExtractedData,
    NiStageRef,
    ProfileData,
    ProfileID,
    ProfileSpec,
    StageData,
    StageSpec,
)
from pya3eda.registry import CalcRegistry
from pya3eda.utils import convert_unit, standard_state_correction

log = logging.getLogger(__name__)

_SelKey = tuple[str, str, str | None, str | None, str]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_profiles(
    registry: CalcRegistry,
    extracted: dict[CalcID, ExtractedData],
) -> dict[ProfileID, ProfileData]:
    """Assemble all profiles by summing energies per stage.

    For each ``ProfileSpec`` in the registry, look up each stage's
    ``CalcID`` list in *extracted* and sum E / G.  Missing data causes
    the stage (and profile) to be skipped.

    When stages carry ``alternatives`` (preTS / postTS complex subsets),
    selection leaders (full_cat) evaluate all candidates and record the
    best-E / best-G indices.  Followers (pol_cat, frz_cat) reuse those
    indices so every calc_type uses the same complex choice.
    """
    results: dict[ProfileID, ProfileData] = {}

    # Selection leaders determine which candidate complex to use.
    # key = (method_key, mode, sp_subfolder, catalyst, stage_name)
    # value = (best_E_index, best_G_index) into [primary, *alternatives]
    selections: dict[_SelKey, tuple[int, int]] = {}

    leaders = [p for p in registry.all_profiles if p.selection_leader]
    followers = [p for p in registry.all_profiles if not p.selection_leader]

    for pspec in leaders + followers:
        results[pspec.id] = _build_one(pspec, extracted, selections)

    # Build NI profiles from full_cat specs (same assembly, G from ni_ref)
    for pspec in leaders:
        ni_pd = _build_one(pspec, extracted, selections, is_ni=True)
        results[ni_pd.profile_id] = ni_pd

    log.info("Built %d profiles", len(results))
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sum_energies(
    calc_ids: tuple[CalcID, ...],
    extracted: dict[CalcID, ExtractedData],
) -> tuple[float | None, float | None]:
    """Sum E and G across a set of calculations."""
    E_total: float = 0.0
    G_total: float = 0.0
    has_E = True
    has_G = True

    for cid in calc_ids:
        data = extracted.get(cid)
        if data is None:
            # No fallback: a stage sum that references missing data is genuinely
            # underivable. Log so the resulting None is not silent.
            log.debug("Stage energy sum incomplete: no extracted data for %s", cid)
            return (None, None)

        e_val = data.energy if data.energy is not None else data.sp_energy
        if e_val is not None and has_E:
            E_total += e_val
        else:
            has_E = False

        if data.G is not None and has_G:
            G_total += data.G
        else:
            has_G = False

    return (E_total if has_E else None, G_total if has_G else None)


def _argmin(vals: list[float | None]) -> int:
    """Index of the smallest non-None value, or 0 if all are None."""
    best_idx = 0
    best_val = float("inf")
    for i, v in enumerate(vals):
        if v is not None and v < best_val:
            best_val = v
            best_idx = i
    return best_idx


def _sel_key(pid: ProfileID, stage_name: str) -> _SelKey:
    """Selection-map key scoping the candidate choice."""
    return (pid.method_key, pid.mode, pid.sp_subfolder, pid.catalyst, stage_name)


# ---------------------------------------------------------------------------
# Profile assembly
# ---------------------------------------------------------------------------


def _build_one(
    pspec: ProfileSpec,
    extracted: dict[CalcID, ExtractedData],
    selections: dict[_SelKey, tuple[int, int]],
    *,
    is_ni: bool = False,
) -> ProfileData:
    """Assemble a single profile from its spec and extracted energies.

    When *is_ni* is True the profile carries ``calc_type="ni"``:
    G is taken from the non-interacting reference (``ni_ref``) for
    complex stages, from the normal sum for endpoints, and E is
    always ``None``.
    """
    stages: list[StageData] = []

    for stage_spec in pspec.stages:
        if stage_spec.alternatives:
            sd = _build_stage_best(stage_spec, pspec, extracted, selections, is_ni=is_ni)
        else:
            E, G = _sum_energies(stage_spec.calc_ids, extracted)
            if is_ni and stage_spec.ni_ref is not None:
                G = _g_ni_for_stage(stage_spec.ni_ref, extracted)
            sd = StageData(
                name=stage_spec.name,
                calc_type="ni" if is_ni else pspec.id.calc_type,
                species_label=stage_spec.label,
                E=None if is_ni else E,
                G=G,
            )
        stages.append(sd)

    pid = pspec.id.model_copy(update={"calc_type": "ni"}) if is_ni else pspec.id
    return ProfileData(profile_id=pid, stages=_normalize(stages, pspec.ref_stage))


def _build_stage_best(
    stage_spec: StageSpec,
    pspec: ProfileSpec,
    extracted: dict[CalcID, ExtractedData],
    selections: dict[_SelKey, tuple[int, int]],
    *,
    is_ni: bool = False,
) -> StageData:
    """Build a stage by selecting the best candidate composition.

    For *selection leaders* (full_cat), all candidates are evaluated and
    the best-E / best-G indices are recorded in *selections*.  Followers
    reuse the recorded indices so every calc_type shares the same complex.
    """
    key = _sel_key(pspec.id, stage_spec.name)

    # All candidates: primary first, then alternatives
    candidates: list[tuple[tuple[CalcID, ...], str, NiStageRef | None]] = [
        (stage_spec.calc_ids, stage_spec.label, stage_spec.ni_ref),
    ]
    for alt in stage_spec.alternatives:
        candidates.append((alt.calc_ids, alt.label, alt.ni_ref))

    # Evaluate energy sums for every candidate
    evals = [_sum_energies(cids, extracted) for cids, _, _ in candidates]

    if pspec.selection_leader or key not in selections:
        e_idx = _argmin([e for e, _ in evals])
        g_idx = _argmin([g for _, g in evals])
        selections[key] = (e_idx, g_idx)
    else:
        e_idx, g_idx = selections[key]

    E_val = evals[e_idx][0]
    G_val = evals[g_idx][1]
    _, g_label, g_ni_ref = candidates[g_idx]

    # Followers reuse the leader's candidate index for geometry consistency.
    # If that candidate lacks data for this calc_type the value stays None by
    # design (no fallback) — log so the gap is visible rather than silent.
    if not pspec.selection_leader and (E_val is None or G_val is None):
        log.warning(
            "Profile %s stage '%s': leader-selected candidate has no %s data "
            "(E=%s, G=%s); left as None (no fallback).",
            pspec.id,
            stage_spec.name,
            pspec.id.calc_type,
            E_val,
            G_val,
        )

    if is_ni and g_ni_ref is not None:
        G_val = _g_ni_for_stage(g_ni_ref, extracted)

    return StageData(
        name=stage_spec.name,
        calc_type="ni" if is_ni else pspec.id.calc_type,
        species_label=g_label,
        E=None if is_ni else E_val,
        G=G_val,
    )


def _normalize(stages: list[StageData], ref_stage: str) -> tuple[StageData, ...]:
    """Subtract the reference stage energies to produce relative values."""
    ref = next((s for s in stages if s.name == ref_stage), None)
    if ref is None:
        return tuple(stages)
    return tuple(
        s.model_copy(
            update={
                "_rel": {
                    f: getattr(s, f) - getattr(ref, f)
                    for f in StageData.energy_types()
                    if getattr(s, f) is not None and getattr(ref, f) is not None
                }
            }
        )
        for s in stages
    )


def _g_ni_for_stage(
    ni: NiStageRef,
    extracted: dict[CalcID, ExtractedData],
) -> float | None:
    """Non-interacting free energy for one stage.

    *ni.ref_cids*   provide H (electronic + enthalpy correction) and
                    non-translational entropy (rot + vib).
    *ni.trans_cids* provide translational entropy only.
    *ni.apply_ssc_to_g_ni*  whether to add standard-state correction to G_ni (solvent).

    G_ni = Σ_ref(H - H_trans) + m·H_trans
           - T·[Σ_ref(S_tot - S_trans) + Σ_trans(S_trans)]
           + m · ssc

    where m = len(trans_cids).
    """
    ref = [extracted.get(c) for c in ni.ref_cids]
    if not all(
        d and d.H is not None and d.s_corr is not None and d.s_trans is not None for d in ref
    ):
        return None
    trans = [extracted.get(c) for c in ni.trans_cids]
    if not all(d and d.s_trans is not None for d in trans):
        return None
    # Both guards above proved every entry is present with the fields used
    # below; rebuild as non-optional lists so the arithmetic type-checks.
    ref_data = [d for d in ref if d is not None]
    trans_data = [d for d in trans if d is not None]
    temp = next((d.temperature for d in ref_data if d.temperature), None)
    if not temp:
        return None

    h_trans = convert_unit(2.5 * C.MOLAR_GAS_CONSTANT * temp, "J/mol", "kcal/mol")
    m = len(trans_data)

    h_nontrans = sum(d.H - h_trans for d in ref_data if d.H is not None)
    s_nontrans = sum(
        d.s_corr - d.s_trans for d in ref_data if d.s_corr is not None and d.s_trans is not None
    )
    s_trans_sum = sum(d.s_trans for d in trans_data if d.s_trans is not None)
    g_ni = h_nontrans + m * h_trans - temp * (s_nontrans + s_trans_sum)

    if ni.apply_ssc_to_g_ni:
        g_ni += m * standard_state_correction(temp)

    return g_ni
