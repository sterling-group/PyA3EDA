"""Shared fixtures and helpers for the pya3eda test suite.

All tests are fully self-contained — no external data directory required.
Synthetic Q-Chem output snippets are provided by ``tests.synthetic_outputs``;
the template-tree builders below are shared by the builder and pipeline tests so
no test module has to import another test module's private helpers.
"""

from __future__ import annotations

from pathlib import Path

# Minimal base + REM template contents for a self-contained template tree.
_BASE_TEMPLATE = "$rem\n{rem_section}\n$end\n\n$molecule\n{molecule_section}\n$end\n"

_REM_OPT_BASE = """\
method = {method}
basis = {basis}
jobtype = {jobtype}
dft_d = {dispersion}
solvent_method = {solvent}"""

_REM_SP_EDA_BASE = """\
method = {method}
basis = {basis}
jobtype = sp
dft_d = {dispersion}
solvent_method = {solvent}
eda2 = {eda2}
scfmi_freeze_ss = {scfmi_freeze_ss}
eda_bsse = {eda_bsse}"""

_REM_FULL_CAT = "\nfull_cat_extra = true"
_REM_POL_CAT = "\npol_cat_extra = true"
_REM_FRZ_CAT = "\nfrz_cat_extra = true"

_GEOM_OPT = """\
geom_opt_max_cycles = 200
geom_opt_tol_gradient = 300"""

_SOLVENT_SMD = """\
$smx
solvent water
$end"""


def _make_template_dir(tmp_path: Path) -> Path:
    """Create a template directory with all required template files."""
    tpl = tmp_path / "templates"
    rem = tpl / "rem"
    mol = tpl / "molecule"
    rem.mkdir(parents=True)
    mol.mkdir(parents=True)

    (tpl / "base_template.in").write_text(_BASE_TEMPLATE)
    (rem / "opt_base.rem").write_text(_REM_OPT_BASE)
    (rem / "sp_eda_base.rem").write_text(_REM_SP_EDA_BASE)
    (rem / "full_cat.rem").write_text(_REM_FULL_CAT)
    (rem / "pol_cat.rem").write_text(_REM_POL_CAT)
    (rem / "frz_cat.rem").write_text(_REM_FRZ_CAT)
    (rem / "geom_opt.rem").write_text(_GEOM_OPT)
    (rem / "solvent_smd.rem").write_text(_SOLVENT_SMD)
    return tpl


def _write_xyz(template_dir: Path, name: str, content: str, calc_type: str | None = None) -> None:
    """Write an XYZ template into the molecule sub-directory."""
    mol_dir = template_dir / "molecule"
    mol_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{name}_{calc_type}.xyz" if calc_type else f"{name}.xyz"
    (mol_dir / fname).write_text(content)
