"""Build the ``$rem`` section for Q-Chem input files.

All functions are pure: they take a template directory and theory parameters,
read the appropriate ``.rem`` template files, fill in placeholders, and return
the formatted text.
"""

from __future__ import annotations

from pathlib import Path

from pya3eda.errors import TemplateNotFoundError
from pya3eda.utils import read_text

# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

_CALC_TYPE_FILES = {
    "full_cat": "full_cat.rem",
    "pol_cat": "pol_cat.rem",
    "frz_cat": "frz_cat.rem",
}


def _load_rem(rem_dir: Path, filename: str) -> str:
    """Read a REM template file, raising if missing."""
    content = read_text(rem_dir / filename)
    if content is None:
        raise TemplateNotFoundError(f"REM template not found: {rem_dir / filename}")
    return content.strip("\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_opt_rem(
    template_dir: Path,
    *,
    method: str,
    basis: str,
    dispersion: str,
    solvent: str,
    jobtype: str,
    calc_type: str | None = None,
) -> str:
    """Build the ``$rem`` block for an optimisation / frequency job.

    Parameters
    ----------
    template_dir : Path
        Directory containing ``templates/rem/*.rem`` template files.
    method, basis, dispersion, solvent, jobtype
        Values substituted into the template.
    calc_type
        If given (``full_cat``, ``pol_cat``, ``frz_cat``), the corresponding
        calc-type-specific REM snippet is appended.
    """
    rem_dir = template_dir / "rem"
    text = _load_rem(rem_dir, "opt_base.rem")

    if calc_type and calc_type in _CALC_TYPE_FILES:
        text += "\n" + _load_rem(rem_dir, _CALC_TYPE_FILES[calc_type])

    return text.format(
        method=method,
        basis=basis,
        dispersion=dispersion,
        solvent=solvent,
        jobtype=jobtype,
    )


def build_sp_rem(
    template_dir: Path,
    *,
    method: str,
    basis: str,
    dispersion: str,
    solvent: str,
    eda2: str,
    scfmi_freeze_ss: str,
    eda_bsse: str = "false",
) -> str:
    """Build the ``$rem`` block for an EDA single-point job.

    Parameters
    ----------
    template_dir : Path
        Directory containing ``templates/rem/*.rem`` template files.
    method, basis, dispersion, solvent
        Level of theory values.
    eda2
        EDA2 flag (``"0"``, ``"1"``, or ``"2"``).
    scfmi_freeze_ss
        ``"1"`` for ``frz_cat``, ``"0"`` otherwise.
    eda_bsse
        ``"true"`` for ``full_cat``, ``"false"`` otherwise.
    """
    rem_dir = template_dir / "rem"
    text = _load_rem(rem_dir, "sp_eda_base.rem")

    return text.format(
        method=method,
        basis=basis,
        dispersion=dispersion,
        solvent=solvent,
        eda2=eda2,
        scfmi_freeze_ss=scfmi_freeze_ss,
        eda_bsse=eda_bsse,
    )
