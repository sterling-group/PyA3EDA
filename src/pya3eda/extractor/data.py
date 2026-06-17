"""Data extraction — reads Q-Chem outputs and produces ExtractedData per CalcID."""

from __future__ import annotations

import logging

from pya3eda.ids import CalcID, CalcSpec, ExtractedData
from pya3eda.parser import qchem
from pya3eda.parser.xyz import format_xyz, parse_output_xyz
from pya3eda.registry import CalcRegistry
from pya3eda.status.checker import Status, get_status
from pya3eda.utils import read_text, standard_state_correction

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
        Keyed by ``CalcID``.  Failed / skipped calcs are omitted.
    """
    results: dict[CalcID, ExtractedData] = {}

    # Process OPT first (SP needs OPT content for thermo corrections)
    opt_content_cache: dict[CalcID, str] = {}

    for spec in registry.all_calcs:
        if spec.id.mode != "opt":
            continue
        data = _extract_one(spec, criteria, opt_content_cache)
        if data is not None:
            results[spec.id] = data

    # Then SP
    for spec in registry.all_calcs:
        if spec.id.mode != "sp":
            continue
        data = _extract_one(spec, criteria, opt_content_cache)
        if data is not None:
            results[spec.id] = data

    log.info("Extracted %d calculations", len(results))
    return results


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _extract_one(
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
    else:
        return _extract_sp(cid, spec, content, opt_cache)


def _extract_opt(
    cid: CalcID,
    spec: CalcSpec,
    content: str,
) -> ExtractedData | None:
    """Parse an OPT output and compute derived H/G."""
    energy_result = qchem.parse_energy(content)
    if energy_result is None:
        return None

    h_corr = qchem.parse_enthalpy(content)
    s_corr = qchem.parse_entropy(content)
    s_trans = qchem.parse_translational_entropy(content)
    thermo = qchem.parse_thermo_conditions(content)
    zpve = qchem.parse_zpve(content)
    imag = qchem.parse_imaginary_freq(content)

    temperature = thermo.temperature if thermo else None
    pressure = thermo.pressure if thermo else None

    E = energy_result.value_kcal
    H = (E + h_corr) if h_corr is not None else None
    G = _compute_G(H, temperature, s_corr, spec.solvent, pressure)

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
    """Parse an SP output and compute derived H/G using OPT thermo corrections."""
    # Determine SP energy based on calc_type
    sp_energy_kcal = _parse_sp_energy(content, spec)
    if sp_energy_kcal is None:
        return None

    # Get OPT content for thermo corrections
    opt_id = CalcID(
        method_key=cid.method_key,
        catalyst=cid.catalyst,
        stage=cid.stage,
        species=cid.species,
        calc_type=cid.calc_type,
        mode="opt",
    )
    opt_content = opt_cache.get(opt_id)

    h_corr = s_corr = s_trans = temperature = zpve = None
    pressure: float | None = None

    if opt_content:
        h_corr = qchem.parse_enthalpy(opt_content)
        s_corr = qchem.parse_entropy(opt_content)
        s_trans = qchem.parse_translational_entropy(opt_content)
        thermo = qchem.parse_thermo_conditions(opt_content)
        zpve = qchem.parse_zpve(opt_content)
        if thermo:
            temperature = thermo.temperature
            pressure = thermo.pressure

    H = (sp_energy_kcal + h_corr) if h_corr is not None else None

    # Determine effective solvent for standard-state correction
    solvent = spec.solvent
    G = _compute_G(H, temperature, s_corr, solvent, pressure)

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


def _parse_sp_energy(content: str, spec: CalcSpec) -> float | None:
    """Parse the SP energy, applying EDA/BSSE/CDS corrections as needed."""
    calc_type = spec.id.calc_type

    if not calc_type:
        # Regular SP — just the total energy
        energy = qchem.parse_energy(content)
        if energy is None:
            return None
        return energy.value_kcal
    else:
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


# ---------------------------------------------------------------------------
# Derived quantity helpers
# ---------------------------------------------------------------------------


def _compute_G(
    H: float | None,
    temperature: float | None,
    s_corr: float | None,
    solvent: str,
    pressure: float | None,
) -> float | None:
    """G = H − T·S [+ standard-state correction if solvent]."""
    if H is None or temperature is None or s_corr is None:
        return None
    G = H - temperature * s_corr

    if solvent and solvent.lower() not in ("false", "gas") and pressure is not None:
        G += standard_state_correction(temperature, pressure)

    return G
