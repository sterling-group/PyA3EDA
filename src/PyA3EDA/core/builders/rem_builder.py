from pathlib import Path
from PyA3EDA.core.utils.file_utils import read_text

def build_rem_section_for_calc_type(system_dir: Path, calc_type: str, method_name: str,
                                    basis_name: str, dispersion: str, jobtype: str) -> str:
    """
    Builds and returns the fully formatted REM section
    by combining the base REM template with a specific REM template based on the calc_type.
    """
    rem_dir = system_dir / "templates" / "rem"
    if calc_type:
        base_rem = read_text(rem_dir / "rem_base.rem")
        mapping = {
            "full_cat": "rem_full_cat.rem",
            "pol_cat": "rem_pol_cat.rem",
            "frz_cat": "rem_frz_cat.rem"
        }
        rem_file = mapping.get(calc_type)
        if not rem_file:
            raise ValueError(f"Unknown calc_type: {calc_type}")
        specific_rem = read_text(rem_dir / rem_file)
        template = base_rem + "\n" + specific_rem
    else:
        template = read_text(rem_dir / "rem_base.rem")
    return template.format(method=method_name, basis=basis_name, dispersion=dispersion, jobtype=jobtype)

def build_rem_section_for_opt(system_dir: Path, calc_type: str, method: str,
                              basis: str, dispersion: str, solvent: str,
                              jobtype: str) -> str:
    """
    Builds and returns the fully formatted REM section for optimization calculations.
    
    Uses:
      - rem_opt_base.rem as the base REM template.
      - If calc_type is specified, appends the corresponding REM file.
    Substitutions include: method, basis, dispersion, jobtype, and solvent.
    """
    rem_dir = system_dir / "templates" / "rem"
    base_rem = read_text(rem_dir / "rem_opt_base.rem")
    
    spec_rem = ""
    if calc_type:
        mapping = {
            "full_cat": "rem_full_cat.rem",
            "pol_cat":  "rem_pol_cat.rem",
            "frz_cat":  "rem_frz_cat.rem"
        }
        rem_file = mapping.get(calc_type)
        if not rem_file:
            raise ValueError(f"Unknown calc_type: {calc_type}")
        spec_rem = read_text(rem_dir / rem_file)
    
    template = base_rem
    if spec_rem:
        template += "\n" + spec_rem
    
    return template.format(method=method,
                           basis=basis,
                           dispersion=dispersion,
                           solvent=solvent,
                           jobtype=jobtype,)

def build_rem_section_for_sp(system_dir: Path, method: str, basis: str,
                             dispersion: str, solvent: str, eda2: str) -> str:
    """
    Builds and returns the REM section for single‐point (sp) calculations.
    
    Uses rem_sp_eda_base.rem as the base REM template.
    Substitutions include: method, basis, dispersion, solvent, and eda2.
    
    Note: Additional solvent REM text (if any) should be appended later (e.g. in the base_template.in).
    """
    rem_dir = system_dir / "templates" / "rem"
    base_rem = read_text(rem_dir / "rem_sp_eda_base.rem")
    
    return base_rem.format(method=method,
                           basis=basis,
                           dispersion=dispersion,
                           solvent=solvent,
                           eda2=eda2)