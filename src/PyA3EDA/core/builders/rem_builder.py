from pathlib import Path

from PyA3EDA.core.utils.file_utils import read_text


def _get_calc_type_rem(rem_dir: Path, calc_type: str) -> str:
    """Helper function to get REM fragment for a specific calc_type."""
    mapping = {
        "full_cat": "rem_full_cat.rem",
        "pol_cat": "rem_pol_cat.rem",
        "frz_cat": "rem_frz_cat.rem",
    }
    rem_file = mapping.get(calc_type)
    if not rem_file:
        raise ValueError(f"Unknown calc_type: {calc_type}")
    return read_text(rem_dir / rem_file)


def _build_rem_template(
    base_template_path: Path, calc_type: str = None, rem_dir: Path = None
) -> str:
    """Helper function to build a REM template by combining base and calc-type specific templates."""
    base_rem = read_text(base_template_path)

    if calc_type and rem_dir:
        specific_rem = _get_calc_type_rem(rem_dir, calc_type)
        return base_rem + "\n" + specific_rem
    else:
        return base_rem


def build_rem_section_for_calc_type(
    system_dir: Path,
    calc_type: str,
    method_name: str,
    basis_name: str,
    dispersion: str,
    jobtype: str,
) -> str:
    """
    Builds and returns the fully formatted REM section
    by combining the base REM template with a specific REM template based on the calc_type.
    """
    rem_dir = system_dir / "templates" / "rem"
    base_path = rem_dir / "rem_base.rem"

    template = _build_rem_template(base_path, calc_type, rem_dir)

    return template.format(
        method=method_name, basis=basis_name, dispersion=dispersion, jobtype=jobtype
    )


def build_rem_section_for_opt(
    system_dir: Path,
    calc_type: str,
    method: str,
    basis: str,
    dispersion: str,
    solvent: str,
    jobtype: str,
) -> str:
    """
    Builds and returns the fully formatted REM section for optimization calculations.

    Uses:
      - rem_opt_base.rem as the base REM template.
      - If calc_type is specified, appends the corresponding REM file.
    Substitutions include: method, basis, dispersion, jobtype, and solvent.
    """
    rem_dir = system_dir / "templates" / "rem"
    base_path = rem_dir / "rem_opt_base.rem"

    template = _build_rem_template(base_path, calc_type, rem_dir)

    return template.format(
        method=method,
        basis=basis,
        dispersion=dispersion,
        solvent=solvent,
        jobtype=jobtype,
    )


def build_rem_section_for_sp(
    system_dir: Path,
    method: str,
    basis: str,
    dispersion: str,
    solvent: str,
    eda2: str,
    scfmi_freeze_ss: str,
    eda_bsse: str = "false",
) -> str:
    """
    Builds and returns the REM section for single‐point (sp) calculations.

    Uses rem_sp_eda_base.rem as the base REM template.
    Substitutions include: method, basis, dispersion, solvent, eda2, scfmi_freeze_ss, and eda_bsse.
    """
    rem_dir = system_dir / "templates" / "rem"
    base_path = rem_dir / "rem_sp_eda_base.rem"

    # Load the template
    template = _build_rem_template(base_path)

    # Return the formatted template with all parameters
    return template.format(
        method=method,
        basis=basis,
        dispersion=dispersion,
        solvent=solvent,
        eda2=eda2,
        scfmi_freeze_ss=scfmi_freeze_ss,
        eda_bsse=eda_bsse,
    )
