"""Data extraction — reads Q-Chem outputs and produces ExtractedData per CalcID.

Fail-loud policy: once a calculation's *primary* electronic energy is parsed (the
calc ran), every value derived from it — ``H``, ``G`` — must be computable. A
missing thermal/entropy/temperature input raises :class:`IncompleteDataError`
rather than silently yielding ``None`` (a free energy with a missing correction
"is not true"). A calc that did not run at all (no electronic energy) is simply
absent. ``extract_all`` aggregates these so one error lists every gap.
"""

from __future__ import annotations

import logging

from pya3eda.errors import IncompleteDataError
from pya3eda.ids import CalcID, CalcSpec, ExtractedData
from pya3eda.parser import qchem
from pya3eda.parser.xyz import format_xyz, parse_output_xyz
from pya3eda.registry import CalcRegistry
from pya3eda.status.checker import Status, get_status
from pya3eda.utils import convert_unit, read_text, standard_state_correction

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_all(
    registry: CalcRegistry,
    criteria: str = "SUCCESSFUL",
) -> dict[CalcID, ExtractedData]:
    """Extract data for every qualifying calculation in the registry.

    Parameters
    ----------
    registry : CalcRegistry
        The registry of all expected calculations.
    criteria : str
        Status-based filter (``"SUCCESSFUL"``, ``"all"``, etc.).

    Returns
    -------
    dict[CalcID, ExtractedData]
        Keyed by ``CalcID``.  Calcs that did not run are omitted.

    Raises
    ------
    IncompleteDataError
        If any calc ran but a value derived from its energy could not be
        computed (missing thermal correction, entropy, temperature, …). All such
        gaps are collected and reported together.
    """
    results: dict[CalcID, ExtractedData] = {}
    errors: list[str] = []

    # Process OPT first (SP needs OPT content for thermo corrections)
    opt_content_cache: dict[CalcID, str] = {}

    for mode in ("opt", "sp"):
        for spec in registry.all_calcs:
            if spec.id.mode != mode:
                continue
            try:
                data = extract_one(spec, criteria, opt_content_cache)
            except IncompleteDataError as exc:
                errors.append(str(exc))
                continue
            if data is not None:
                results[spec.id] = data

    if errors:
        raise IncompleteDataError.combine(errors)

    log.info("Extracted %d calculations", len(results))
    return results


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def extract_one(
    spec: CalcSpec,
    criteria: str,
    opt_cache: dict[CalcID, str],
) -> ExtractedData | None:
    """Extract data for a single CalcSpec."""
    # Status gate
    status, _ = get_status(spec)
    if criteria.lower() != "all" and status != Status.SUCCESSFUL:
        return None

    content = read_text(spec.output_path)
    if not content:
        return None

    cid = spec.id

    if cid.mode == "opt":
        opt_cache[cid] = content
        return _extract_opt(cid, spec, content)
    return _extract_sp(cid, spec, content, opt_cache)


def _extract_opt(
    cid: CalcID,
    spec: CalcSpec,
    content: str,
) -> ExtractedData | None:
    """Parse an OPT output and compute derived H/G (fail-loud on missing thermo)."""
    energy_result = qchem.parse_energy(content)
    if energy_result is None:
        return None  # primary energy absent → calc did not run / unparseable
    E = energy_result.value_kcal

    h_corr = qchem.parse_enthalpy(content)
    s_corr = qchem.parse_entropy(content)
    thermo = qchem.parse_thermo_conditions(content)
    temperature = thermo.temperature if thermo else None
    pressure = thermo.pressure if thermo else None
    H, G = _derive_hg(cid, E, h_corr, s_corr, temperature, pressure, spec.solvent)

    s_trans = qchem.parse_translational_entropy(content)
    zpve = qchem.parse_zpve(content)
    imag = qchem.parse_imaginary_freq(content)
    xyz_data = parse_output_xyz(content)
    xyz_text = format_xyz(xyz_data) if xyz_data is not None else None

    return ExtractedData(
        calc_id=cid,
        status="SUCCESSFUL",
        energy=E,
        h_corr=h_corr,
        s_corr=s_corr,
        s_trans=s_trans,
        temperature=temperature,
        zpve=zpve,
        imag_freq=imag,
        H=H,
        G=G,
        xyz_text=xyz_text,
    )


def _extract_sp(
    cid: CalcID,
    spec: CalcSpec,
    content: str,
    opt_cache: dict[CalcID, str],
) -> ExtractedData | None:
    """Parse an SP output; compute H/G from the OPT thermo (fail-loud)."""
    sp_energy_kcal = _parse_sp_energy(content, spec.id.calc_type)
    if sp_energy_kcal is None:
        return None  # primary energy absent → calc did not run / unparseable

    opt_id = cid.to_opt()
    opt_content = opt_cache.get(opt_id)
    if not opt_content:
        # The SP ran (has an electronic energy) but the OPT it depends on was not
        # extracted — H/G would be untrue. Fail loud rather than emit None.
        raise IncompleteDataError(
            f"{cid}: SP electronic energy present but its OPT thermo "
            f"({opt_id}) was not extracted — cannot compute H/G"
        )

    _validate_sp_cds(cid, content, opt_content, spec.solvent)

    h_corr, s_corr, s_trans, temperature, zpve, pressure = _opt_thermo(opt_content)
    H, G = _derive_hg(cid, sp_energy_kcal, h_corr, s_corr, temperature, pressure, spec.solvent)

    return ExtractedData(
        calc_id=cid,
        status="SUCCESSFUL",
        energy=None,
        sp_energy=sp_energy_kcal,
        h_corr=h_corr,
        s_corr=s_corr,
        s_trans=s_trans,
        temperature=temperature,
        zpve=zpve,
        H=H,
        G=G,
    )


def _parse_sp_energy(content: str, calc_type: str | None) -> float | None:
    """Parse the SP energy, applying EDA/BSSE/CDS corrections as needed."""
    if not calc_type:
        # Regular SP — just the total energy
        energy = qchem.parse_energy(content)
        if energy is None:
            return None
        return energy.value_kcal
    # EDA SP
    eda = qchem.parse_eda_energies(content, calc_type)
    if eda is None:
        return None
    sp_kcal = eda.sp_energy_kcal

    # CDS correction
    if eda.cds_kcal is not None:
        sp_kcal += eda.cds_kcal

    # BSSE correction
    if eda.bsse_kcal is not None:
        sp_kcal += eda.bsse_kcal

    return sp_kcal


# SP↔OPT G_CDS agreement tolerance (kcal/mol). CDS is geometry-only, and the SP
# runs on the OPT geometry, so the two must agree to well within this.
_CDS_TOLERANCE_KCAL = 1e-3


def _validate_sp_cds(cid: CalcID, sp_content: str, opt_content: str, solvent: str) -> None:
    """Warn if an EDA SMD SP's G_CDS disagrees with its OPT's G_CDS.

    G_CDS (cavity-dispersion-solvent-structure) depends only on geometry and the
    atomic radii, not on the electronic method, and the SP runs on the OPT
    geometry, so the SP's manually-added CDS must equal the OPT's
    ``G_S(liq) - G_ENP``. A mismatch points to a wrong OPT/SP geometry pairing or
    a parsing error that would silently corrupt the barrier. Non-fatal: logged as
    a warning (reinstates the cross-check the rewrite dropped). Only EDA SPs add
    CDS manually, so non-EDA / gas-phase calcs are skipped.
    """
    if cid.calc_type is None or not _solvent_active(solvent):
        return
    sp_cds = qchem.parse_cds_print(sp_content)
    opt_smd = qchem.parse_smd(opt_content)
    if sp_cds is None or opt_smd is None or opt_smd.g_s_ha is None or opt_smd.g_enp_ha is None:
        return
    opt_cds = convert_unit(opt_smd.g_s_ha - opt_smd.g_enp_ha, "hartree", "kcal/mol")
    diff = abs(sp_cds - opt_cds)
    if diff > _CDS_TOLERANCE_KCAL:
        log.warning(
            "CDS mismatch for %s: SP=%.4f vs OPT=%.4f kcal/mol (|Δ|=%.4f > %.0e) — "
            "the SP geometry may not match its OPT.",
            cid,
            sp_cds,
            opt_cds,
            diff,
            _CDS_TOLERANCE_KCAL,
        )


# ---------------------------------------------------------------------------
# Derived quantity helpers
# ---------------------------------------------------------------------------


def _solvent_active(solvent: str) -> bool:
    """True if *solvent* denotes an actual solvent (not gas phase)."""
    return bool(solvent) and solvent.lower() not in ("false", "gas")


def _derive_hg(
    cid: CalcID,
    energy: float,
    h_corr: float | None,
    s_corr: float | None,
    temperature: float | None,
    pressure: float | None,
    solvent: str,
) -> tuple[float, float]:
    """Compute ``(H, G)`` from a present electronic *energy* + thermo inputs.

    Raises :class:`IncompleteDataError` naming any input that is missing — the
    energy is present, so a silently-``None`` H/G "is not true".
    """
    if h_corr is None or s_corr is None or temperature is None:
        missing = [
            name
            for name, value in (
                ("h_corr (enthalpy correction)", h_corr),
                ("s_corr (entropy)", s_corr),
                ("temperature", temperature),
            )
            if value is None
        ]
        raise IncompleteDataError(
            f"{cid}: electronic energy present but cannot compute H/G — "
            f"missing {', '.join(missing)}"
        )

    H = energy + h_corr
    G = H - temperature * s_corr

    if _solvent_active(solvent):
        if pressure is None:
            raise IncompleteDataError(
                f"{cid}: electronic energy present but cannot apply the solvent "
                f"standard-state correction to G — missing pressure"
            )
        G += standard_state_correction(temperature, pressure)

    return H, G


def _opt_thermo(
    opt_text: str,
) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    """Return ``(h_corr, s_corr, s_trans, temperature, zpve, pressure)`` from an OPT output."""
    h_corr = qchem.parse_enthalpy(opt_text)
    s_corr = qchem.parse_entropy(opt_text)
    s_trans = qchem.parse_translational_entropy(opt_text)
    thermo = qchem.parse_thermo_conditions(opt_text)
    zpve = qchem.parse_zpve(opt_text)
    temperature = thermo.temperature if thermo else None
    pressure = thermo.pressure if thermo else None
    return h_corr, s_corr, s_trans, temperature, zpve, pressure
