"""Pure Q-Chem output parsing functions.

Every function in this module takes a ``str`` (output file content) and returns
structured data.  No file I/O, no side-effects.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from pya3eda.utils import convert_unit

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_FINAL_ENERGY = re.compile(
    r"Final energy is\s+([-+]?\d+\.\d+)"
    r"(?:\s+([A-Za-z][A-Za-z0-9./\-]*))?\s*$",
    re.MULTILINE,
)
_TOTAL_ENERGY = re.compile(
    r"Total energy =\s+([-+]?\d+\.\d+)"
    r"(?:\s+([A-Za-z][A-Za-z0-9./\-]*))?\s*$",
    re.MULTILINE,
)
_OPT_CONVERGED = re.compile(r"(OPTIMIZATION CONVERGED|TRANSITION STATE CONVERGED)")
_THERMO_CONDS = re.compile(
    r"STANDARD THERMODYNAMIC QUANTITIES AT\s+"
    r"([-+]?\d+\.\d+)\s*K\s+AND\s+([-+]?\d+\.\d+)\s*ATM"
)
_IMAG_FREQ = re.compile(r"This Molecule has\s+(\d+)\s+Imaginary Frequencies")
_ZPVE = re.compile(
    r"Zero point vibrational energy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)",
    re.MULTILINE,
)
_QRRHO_ENTHALPY = re.compile(
    r"QRRHO-Total Enthalpy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)",
    re.MULTILINE,
)
_TOTAL_ENTHALPY = re.compile(
    r"Total Enthalpy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)",
    re.MULTILINE,
)
_QRRHO_ENTROPY = re.compile(
    r"QRRHO-Total Entropy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)",
    re.MULTILINE,
)
_TOTAL_ENTROPY = re.compile(
    r"Total Entropy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)",
    re.MULTILINE,
)
_TRANS_ENTROPY = re.compile(
    r"Translational Entropy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)",
    re.MULTILINE,
)
# SMD
_SMD_GENP = re.compile(
    r"\(3\)\s+G-ENP\(liq\) elect-nuc-pol free energy of system"
    r"\s+([-+]?\d+\.\d+)\s+(a\.u\.)",
    re.MULTILINE,
)
_SMD_GS = re.compile(
    r"\(6\)\s+G-S\(liq\) free energy of system"
    r"\s+([-+]?\d+\.\d+)\s+(a\.u\.)",
    re.MULTILINE,
)
_SMD_CDS_DETAIL = re.compile(
    r"\(4\)\s+G-CDS\(liq\) cavity-dispersion-solvent structure"
    r"\s+([-+]?\d+\.\d+)\s+(kcal/mol)",
    re.MULTILINE,
)
_SMD_CDS_SUMMARY = re.compile(
    r"G_CDS\s+=\s+([-+]?\d+\.\d+)\s+(kcal/mol)",
    re.MULTILINE,
)
_SMD_CDS_EXTENDED = re.compile(
    r"Total:\s+([-+]?\d+\.\d+)\s*\n\s*-+",
    re.MULTILINE,
)
# EDA / BSSE
_EDA_POL_ENERGY = re.compile(
    r"Energy prior to optimization \(guess energy\)\s*=\s*([-+]?\d+\.\d+)",
    re.MULTILINE,
)
_EDA_CONV_ENERGY = re.compile(
    r"^\s*\d+\s+([-+]?\d+\.\d+)\s+[\d.e-]+\s+\d+\s+Convergence criterion met",
    re.MULTILINE,
)
_BSSE_ENERGY = re.compile(
    r"BSSE \(kJ/mol\)\s*=\s*([-+]?\d+\.\d+)",
    re.MULTILINE,
)
# Status
_THANK_YOU = "Thank you very much"
_JOB_TIME = re.compile(r"Total job time:\s*(.*)")
_WALL_TIME = re.compile(r"(\d+(?:\.\d+)?)s\(wall\)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _last_match(
    pattern: re.Pattern[str],
    text: str,
    fallback: re.Pattern[str] | None = None,
) -> re.Match[str] | None:
    """Return the last match of *pattern* (or *fallback*) in *text*."""
    matches = list(pattern.finditer(text))
    if matches:
        return matches[-1]
    if fallback:
        matches = list(fallback.finditer(text))
        if matches:
            return matches[-1]
    return None


def _last_value_unit(
    pattern: re.Pattern[str],
    text: str,
    fallback: re.Pattern[str] | None = None,
    default_unit: str = "Ha",
) -> tuple[float, str] | None:
    """Extract ``(value, unit)`` from the last match of *pattern*."""
    m = _last_match(pattern, text, fallback)
    if m is None:
        return None
    val = float(m.group(1))
    unit = m.group(2) if m.lastindex and m.lastindex >= 2 and m.group(2) else default_unit
    if unit == "a.u.":
        unit = "Ha"
    return val, unit


# ---------------------------------------------------------------------------
# Public parsing API
# ---------------------------------------------------------------------------


class ThermoData(NamedTuple):
    """Temperature and pressure from the thermodynamics block."""

    temperature: float
    pressure: float


class EnergyResult(NamedTuple):
    """Final SCF energy in Hartree and kcal/mol."""

    value_ha: float
    value_kcal: float


class EntropyResult(NamedTuple):
    """Total entropy in kcal/(mol·K)."""

    value_kcal_k: float  # kcal/(mol·K)


def parse_energy(text: str) -> EnergyResult | None:
    """Parse the final energy (``Final energy is`` or ``Total energy =``)."""
    r = _last_value_unit(_FINAL_ENERGY, text, _TOTAL_ENERGY)
    if r is None:
        return None
    val, unit = r
    return EnergyResult(val, convert_unit(val, unit, "kcal/mol"))


def parse_thermo_conditions(text: str) -> ThermoData | None:
    """Parse temperature and pressure from the thermo block header."""
    m = _THERMO_CONDS.search(text)
    if m is None:
        return None
    return ThermoData(float(m.group(1)), float(m.group(2)))


def parse_imaginary_freq(text: str) -> int | None:
    """Return the number of imaginary frequencies, or ``None``."""
    m = _IMAG_FREQ.search(text)
    return int(m.group(1)) if m else None


def parse_zpve(text: str) -> float | None:
    """Parse zero-point vibrational energy (kcal/mol)."""
    r = _last_value_unit(_ZPVE, text, default_unit="kcal/mol")
    if r is None:
        return None
    return convert_unit(r[0], r[1], "kcal/mol")


def parse_enthalpy(text: str) -> float | None:
    """Parse total enthalpy correction (QRRHO preferred) → kcal/mol."""
    r = _last_value_unit(_QRRHO_ENTHALPY, text, _TOTAL_ENTHALPY)
    if r is None:
        return None
    return convert_unit(r[0], r[1], "kcal/mol")


def parse_entropy(text: str) -> float | None:
    """Parse total entropy (QRRHO preferred) → kcal/(mol·K)."""
    r = _last_value_unit(_QRRHO_ENTROPY, text, _TOTAL_ENTROPY)
    if r is None:
        return None
    return convert_unit(r[0], r[1], "kcal/mol.K")


def parse_translational_entropy(text: str) -> float | None:
    """Parse translational entropy → kcal/(mol·K)."""
    r = _last_value_unit(_TRANS_ENTROPY, text)
    if r is None:
        return None
    return convert_unit(r[0], r[1], "kcal/mol.K")


def parse_opt_converged(text: str) -> bool:
    """Return ``True`` if optimization / TS search converged."""
    return _OPT_CONVERGED.search(text) is not None


# -- SMD -------------------------------------------------------------------


class SMDData(NamedTuple):
    """SMD solvation components (G-ENP, G-S, CDS)."""

    g_enp_ha: float | None
    g_s_ha: float | None
    cds_kcal: float | None


def parse_smd(text: str) -> SMDData | None:
    """Parse SMD solvation components (G-ENP, G-S, CDS)."""
    g_enp = g_s = cds = None

    r = _last_value_unit(_SMD_GENP, text)
    if r:
        g_enp = r[0]
    r = _last_value_unit(_SMD_GS, text)
    if r:
        g_s = r[0]
    r = _last_value_unit(_SMD_CDS_DETAIL, text, _SMD_CDS_SUMMARY, default_unit="kcal/mol")
    if r:
        cds = r[0]

    if g_enp is None and g_s is None and cds is None:
        return None
    return SMDData(g_enp, g_s, cds)


def parse_cds_print(text: str) -> float | None:
    """Parse the SMD G_CDS from the extended-print per-atom table (``print=2``).

    Returns the *last* ``Total:`` value in kcal/mol. When per-fragment CDS tables
    are printed, the full-system CDS is the last one — taking the first would pick
    a fragment's value and mismatch the OPT's whole-system CDS. Used by both
    :func:`parse_eda_energies` and the SP↔OPT CDS cross-check.
    """
    matches = _SMD_CDS_EXTENDED.findall(text)
    return float(matches[-1]) if matches else None


# -- EDA / BSSE ------------------------------------------------------------


class EDAData(NamedTuple):
    """Parsed EDA single-point energy and corrections."""

    sp_energy_ha: float
    sp_energy_kcal: float
    bsse_kcal: float | None
    cds_kcal: float | None


def parse_eda_energies(
    text: str,
    calc_type: str,
) -> EDAData | None:
    """Parse energy from an EDA single-point output.

    *calc_type* selects the parsing strategy:
    - ``pol_cat``: uses the guess (prior-to-optimisation) energy
    - ``frz_cat`` / ``full_cat``: uses the convergence energy
    ``full_cat`` also extracts BSSE correction.
    """
    energy_ha: float | None = None

    if calc_type == "pol_cat":
        r = _last_value_unit(_EDA_POL_ENERGY, text, default_unit="Ha")
        if r:
            energy_ha = r[0]
    else:
        r = _last_value_unit(_EDA_CONV_ENERGY, text, default_unit="Ha")
        if r:
            energy_ha = r[0]

    if energy_ha is None:
        return None

    bsse_kcal: float | None = None
    if calc_type == "full_cat":
        m = _BSSE_ENERGY.search(text)
        if m:
            bsse_kcal = convert_unit(float(m.group(1)), "kJ/mol", "kcal/mol")

    cds_kcal = parse_cds_print(text)

    return EDAData(
        sp_energy_ha=energy_ha,
        sp_energy_kcal=convert_unit(energy_ha, "Ha", "kcal/mol"),
        bsse_kcal=bsse_kcal,
        cds_kcal=cds_kcal,
    )


# -- Status -----------------------------------------------------------------


def parse_status(
    out_text: str,
    err_text: str = "",
    submission_exists: bool = False,
) -> tuple[str, str]:
    """Determine the job status from output + error file contents.

    Returns ``(status, detail)`` where *status* is one of:
    ``SUCCESSFUL``, ``CRASH``, ``running``, ``terminated``, ``nofile``, ``empty``.
    """
    if "CANCELLED AT" in err_text:
        return "terminated", "Job cancelled by queue"

    if "Error in Q-Chem run" in err_text or "Aborted" in err_text:
        detail = _crash_detail(out_text)
        return "CRASH", detail

    if submission_exists:
        return "running", "Job submission file exists"

    if not out_text:
        return "nofile", "Output file not found"

    if _THANK_YOU in out_text:
        return "SUCCESSFUL", f"Completed in {_parse_wall_time(out_text)}"

    # Failure markers take precedence over the "still running" heuristic below: a
    # job that printed "Running on" and then died (fatal error / SGeom / SCF / OOM
    # / killed) must surface as CRASH/terminated, not be reported "running" forever
    # — the default NOFILE run filter would never resubmit such a stuck calc.
    if "Q-Chem fatal error occurred" in out_text:
        return "CRASH", _crash_detail(out_text)
    for tag, msg in (
        ("SGeom Failed", "Geometry optimization failed"),
        ("SCF failed to converge", "SCF convergence failure"),
        ("Insufficient memory", "Out of memory"),
    ):
        if tag in out_text:
            return "CRASH", msg

    if any(kw in out_text.lower() for kw in ("killed", "terminating")):
        return "terminated", "Job terminated unexpectedly"

    # Started, no completion, no failure marker → genuinely still in progress
    # (a live local job, or a SLURM job mid-flight whose sentinel we missed).
    if "Running on" in out_text:
        return "running", "Calculation in progress"

    if out_text.strip():
        return "CRASH", "Unknown failure"
    return "empty", "Output file is empty"


def _crash_detail(text: str) -> str:
    """Extract a human-readable crash reason from output text."""
    if not text:
        return "Q-Chem execution crashed"
    for tag, msg in (
        ("SGeom Failed", "Geometry optimization failed"),
        ("SCF failed to converge", "SCF convergence failure"),
        ("Insufficient memory", "Out of memory"),
    ):
        if tag in text:
            return msg
    if "error occurred" in text:
        m = re.search(r"error occurred.*?\n\s*(.*?)(?:\n{2,}|\Z)", text, re.DOTALL)
        if m:
            return re.split(r"[.;]", m.group(1).strip())[0].strip()
    return "Unknown failure"


def _parse_wall_time(text: str) -> str:
    """Extract wall-clock time as ``hh:mm:ss`` from Q-Chem output."""
    m = _JOB_TIME.search(text)
    if not m:
        return "unknown"
    wm = _WALL_TIME.search(m.group(1))
    if not wm:
        return m.group(1).strip()
    secs = float(wm.group(1))
    h, rem = divmod(secs, 3600)
    mins, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(mins):02d}:{int(s):02d}"
