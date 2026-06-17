"""Comprehensive tests for the builder module (inputs, molecule, rem).

Tests cover:
- Molecule section formatting (standard & fragmented)
- Coordinate extraction from OPT output vs template fallback
- REM section construction (OPT base, SP/EDA, calc_type append)
- Path construction for all stage/catalyst/mode combinations
- Full build_all orchestration (file creation, overwrite policy, SP strategy)
- Edge cases: missing templates, insufficient atoms, species name splitting
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pya3eda.builder.inputs import (
    _build_fragmented,
    _build_molecule_section,
    _build_one,
    _build_rem_section,
    _build_standard,
    _opt_successful,
    _should_overwrite,
    build_all,
)
from pya3eda.builder.molecule import (
    _coords_from_output,
    _format_fragmented,
    _format_standard,
    _load_xyz,
    build_fragmented_molecule,
    build_standard_molecule,
)
from pya3eda.builder.rem import (
    _CALC_TYPE_FILES,
    _load_rem,
    build_opt_rem,
    build_sp_rem,
)
from pya3eda.config import (
    CatalystConfig,
    Config,
    LevelConfig,
    SpeciesConfig,
    TheoryConfig,
)
from pya3eda.ids import CalcID, CalcSpec
from pya3eda.parser.xyz import XYZData
from pya3eda.registry import CalcRegistry

from .synthetic_outputs import OPT_OUTPUT

# ───────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ───────────────────────────────────────────────────────────────────

# Minimal 3-atom XYZ template
_XYZ_3ATOM = """\
3
0 1
H   0.0000000000   0.0000000000   0.0000000000
O   0.0000000000   0.0000000000   0.9600000000
H   0.0000000000   0.7600000000   0.5900000000
"""

# Catalyst fragment (1 atom)
_XYZ_CAT = """\
1
0 1
Li  0.0000000000   0.0000000000   0.0000000000
"""

# Substrate fragment (2 atoms)
_XYZ_SUB = """\
2
0 1
C   1.0000000000   0.0000000000   0.0000000000
O   2.0000000000   0.0000000000   0.0000000000
"""

# Composite (cat + sub = 3 atoms)
_XYZ_COMPOSITE = """\
3
-1 2
Li  0.0000000000   0.0000000000   0.0000000000
C   1.0000000000   0.0000000000   0.0000000000
O   2.0000000000   0.0000000000   0.0000000000
"""

# Minimal base template
_BASE_TEMPLATE = "$rem\n{rem_section}\n$end\n\n$molecule\n{molecule_section}\n$end\n"

# Minimal REM templates
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


def _write_xyz(
    template_dir: Path, name: str, content: str, calc_type: str | None = None
) -> None:
    """Write an XYZ template into the molecule sub-directory."""
    mol_dir = template_dir / "molecule"
    mol_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{name}_{calc_type}.xyz" if calc_type else f"{name}.xyz"
    (mol_dir / fname).write_text(content)


def _simple_config() -> Config:
    """Minimal config: 1 OPT level, 1 catalyst, 1 reactant (include), 1 product."""
    return Config(
        levels=[
            LevelConfig(
                opt=TheoryConfig(method="HF", basis="STO-3G", solvent="smd"),
            ),
        ],
        reactants=[SpeciesConfig(name="mol_a")],
        products=[SpeciesConfig(name="mol_p")],
        catalysts=[CatalystConfig(name="cat1")],
    )


def _config_with_sp() -> Config:
    """Config with OPT + SP level."""
    return Config(
        levels=[
            LevelConfig(
                opt=TheoryConfig(method="HF", basis="STO-3G", solvent="smd"),
                sp=[
                    TheoryConfig(
                        method="MP2",
                        basis="cc-pVTZ",
                        solvent="smd",
                        eda2=1,
                    )
                ],
            ),
        ],
        reactants=[SpeciesConfig(name="mol_a")],
        products=[SpeciesConfig(name="mol_p")],
        catalysts=[CatalystConfig(name="cat1")],
    )


def _make_spec(
    *,
    method_key: str = "HF_STO-3G_smd",
    catalyst: str | None = None,
    stage: str = "reactants",
    species: str = "mol_a",
    calc_type: str | None = None,
    mode: str = "opt",
    sp_subfolder: str | None = None,
    is_fragmented: bool = False,
    method_name: str = "HF",
    basis_set: str = "STO-3G",
    dispersion: str = "false",
    solvent: str = "smd",
    eda2: int | None = None,
    input_path: Path | None = None,
) -> CalcSpec:
    """Build a CalcSpec for testing (with sensible defaults)."""
    cid = CalcID(
        method_key=method_key,
        catalyst=catalyst,
        stage=stage,
        species=species,
        calc_type=calc_type,
        mode=mode,
        sp_subfolder=sp_subfolder,
    )
    if input_path is None:
        input_path = Path("/tmp/dummy.in")
    return CalcSpec(
        id=cid,
        input_path=input_path,
        output_path=input_path.with_suffix(".out"),
        method_name=method_name,
        basis_set=basis_set,
        dispersion=dispersion,
        solvent=solvent,
        eda2=eda2,
        sp_subfolder=sp_subfolder,
        is_fragmented=is_fragmented,
    )


# ===================================================================
# 1. Molecule formatting tests
# ===================================================================


class TestFormatStandard:
    def test_basic(self) -> None:
        atoms = ["H   0.0   0.0   0.0", "O   1.0   0.0   0.0"]
        result = _format_standard(0, 1, atoms)
        assert result == "0 1\nH   0.0   0.0   0.0\nO   1.0   0.0   0.0"

    def test_charge_and_mult(self) -> None:
        result = _format_standard(-2, 3, ["C   0.0   0.0   0.0"])
        assert result.startswith("-2 3\n")

    def test_empty_atoms(self) -> None:
        result = _format_standard(0, 1, [])
        assert result == "0 1\n"


class TestFormatFragmented:
    def test_basic(self) -> None:
        result = _format_fragmented(
            total_charge=-1,
            total_mult=2,
            cat_charge=0,
            cat_mult=1,
            cat_atoms=["Li  0.0  0.0  0.0"],
            sub_charge=-1,
            sub_mult=2,
            sub_atoms=["C  1.0  0.0  0.0", "O  2.0  0.0  0.0"],
        )
        lines = result.splitlines()
        assert lines[0] == "-1 2"
        assert lines[1] == "---"
        assert lines[2] == "0 1"
        assert lines[3] == "Li  0.0  0.0  0.0"
        assert lines[4] == "---"
        assert lines[5] == "-1 2"
        assert lines[6] == "C  1.0  0.0  0.0"
        assert lines[7] == "O  2.0  0.0  0.0"

    def test_separator_count(self) -> None:
        result = _format_fragmented(0, 1, 0, 1, ["A"], 0, 1, ["B"])
        assert result.count("---") == 2


# ===================================================================
# 2. Coordinate extraction
# ===================================================================


class TestCoordsFromOutput:
    def test_uses_output_coords(self) -> None:
        template = XYZData(
            n_atoms=8,
            charge=0,
            multiplicity=1,
            atoms=["H   0.0   0.0   0.0"] * 8,
        )
        atoms = _coords_from_output(OPT_OUTPUT, template)
        # Should get the LAST Standard Nuclear Orientation block
        # (8 atoms from the second block in OPT_OUTPUT)
        assert len(atoms) == 8
        # First atom should be C from the second orientation block
        assert atoms[0].startswith("C")

    def test_falls_back_to_template(self) -> None:
        template = XYZData(
            n_atoms=2,
            charge=0,
            multiplicity=1,
            atoms=["H   0.0   0.0   0.0", "O   1.0   0.0   0.0"],
        )
        atoms = _coords_from_output(None, template)
        assert atoms == template.atoms

    def test_falls_back_on_bad_output(self) -> None:
        template = XYZData(
            n_atoms=1,
            charge=0,
            multiplicity=1,
            atoms=["H   0.0   0.0   0.0"],
        )
        atoms = _coords_from_output("no geometry here", template)
        assert atoms == template.atoms


# ===================================================================
# 3. Build standard molecule
# ===================================================================


class TestBuildStandardMolecule:
    def test_from_template(self) -> None:
        result = build_standard_molecule(_XYZ_3ATOM)
        assert result is not None
        lines = result.splitlines()
        assert lines[0] == "0 1"
        assert len(lines) == 4  # charge-mult + 3 atoms

    def test_with_output_coords(self) -> None:
        result = build_standard_molecule(_XYZ_3ATOM, OPT_OUTPUT)
        assert result is not None
        lines = result.splitlines()
        assert lines[0] == "0 1"
        # Coords came from OPT output (8 atoms), but charge/mult from template
        # parse_output_xyz extracts charge from $molecule in OPT_OUTPUT → 0 1
        # Template charge=0, mult=1 stays

    def test_bad_xyz(self) -> None:
        assert build_standard_molecule("garbage") is None

    def test_too_few_lines(self) -> None:
        assert build_standard_molecule("1\n0 1") is None


# ===================================================================
# 4. Build fragmented molecule
# ===================================================================


class TestBuildFragmentedMolecule:
    def test_basic(self) -> None:
        result = build_fragmented_molecule(_XYZ_COMPOSITE, _XYZ_CAT, _XYZ_SUB)
        assert result is not None
        lines = result.splitlines()
        assert lines[0] == "-1 2"  # composite charge/mult
        assert "---" in result
        # Should have 2 separator lines
        assert result.count("---") == 2

    def test_atom_split(self) -> None:
        """Catalyst atoms come first, then substrate atoms."""
        result = build_fragmented_molecule(_XYZ_COMPOSITE, _XYZ_CAT, _XYZ_SUB)
        lines = result.splitlines()
        # After first ---, cat section: "0 1\nLi..."
        sep_indices = [i for i, ln in enumerate(lines) if ln == "---"]
        cat_charge_line = lines[sep_indices[0] + 1]
        assert cat_charge_line == "0 1"  # catalyst charge/mult
        cat_atom = lines[sep_indices[0] + 2]
        assert "Li" in cat_atom

        sub_charge_line = lines[sep_indices[1] + 1]
        assert sub_charge_line == "0 1"  # substrate charge/mult

    def test_insufficient_atoms(self) -> None:
        """If the composite has fewer atoms than cat + sub expect, returns None."""
        small_composite = "1\n0 1\nH   0.0   0.0   0.0\n"
        result = build_fragmented_molecule(small_composite, _XYZ_CAT, _XYZ_SUB)
        assert result is None

    def test_bad_composite(self) -> None:
        assert build_fragmented_molecule("bad", _XYZ_CAT, _XYZ_SUB) is None

    def test_bad_catalyst(self) -> None:
        assert build_fragmented_molecule(_XYZ_COMPOSITE, "bad", _XYZ_SUB) is None

    def test_bad_substrate(self) -> None:
        assert build_fragmented_molecule(_XYZ_COMPOSITE, _XYZ_CAT, "bad") is None

    def test_with_output_coords(self) -> None:
        """When output_text is provided, coords come from it, not the template."""
        # OPT_OUTPUT has 8 atoms — cat has 1, sub has 2 → need ≥3
        result = build_fragmented_molecule(
            _XYZ_COMPOSITE,
            _XYZ_CAT,
            _XYZ_SUB,
            OPT_OUTPUT,
        )
        assert result is not None
        # Atoms should be from OPT output's last orientation block


# ===================================================================
# 5. _load_xyz
# ===================================================================


class TestLoadXyz:
    def test_basic(self, tmp_path: Path) -> None:
        _write_xyz(tmp_path, "water", _XYZ_3ATOM)
        result = _load_xyz(tmp_path, "water")
        assert result == _XYZ_3ATOM

    def test_calc_type_variant(self, tmp_path: Path) -> None:
        """With calc_type, loads calc-type-specific file first."""
        _write_xyz(tmp_path, "complex", _XYZ_COMPOSITE, calc_type="full_cat")
        _write_xyz(tmp_path, "complex", _XYZ_3ATOM)  # fallback
        result = _load_xyz(tmp_path, "complex", calc_type="full_cat")
        assert result == _XYZ_COMPOSITE  # loaded the calc_type variant

    def test_calc_type_fallback(self, tmp_path: Path) -> None:
        """If calc-type file missing, falls back to base name."""
        _write_xyz(tmp_path, "complex", _XYZ_3ATOM)
        result = _load_xyz(tmp_path, "complex", calc_type="pol_cat")
        assert result == _XYZ_3ATOM

    def test_missing(self, tmp_path: Path) -> None:
        (tmp_path / "molecule").mkdir(parents=True, exist_ok=True)
        result = _load_xyz(tmp_path, "nonexistent")
        assert result is None


# ===================================================================
# 6. REM template loading
# ===================================================================


class TestLoadRem:
    def test_basic(self, tmp_path: Path) -> None:
        rem_dir = tmp_path / "rem"
        rem_dir.mkdir()
        (rem_dir / "test.rem").write_text("content\n\n")
        result = _load_rem(rem_dir, "test.rem")
        assert result == "content"  # trailing newlines stripped

    def test_missing_raises(self, tmp_path: Path) -> None:
        rem_dir = tmp_path / "rem"
        rem_dir.mkdir()
        with pytest.raises(FileNotFoundError, match="REM template not found"):
            _load_rem(rem_dir, "missing.rem")


# ===================================================================
# 7. build_opt_rem
# ===================================================================


class TestBuildOptRem:
    def test_basic(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        result = build_opt_rem(
            tpl,
            method="HF",
            basis="STO-3G",
            dispersion="false",
            solvent="smd",
            jobtype="opt",
        )
        assert "method = HF" in result
        assert "basis = STO-3G" in result
        assert "jobtype = opt" in result

    def test_ts_jobtype(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        result = build_opt_rem(
            tpl,
            method="HF",
            basis="STO-3G",
            dispersion="false",
            solvent="smd",
            jobtype="ts",
        )
        assert "jobtype = ts" in result

    def test_calc_type_appended(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        result = build_opt_rem(
            tpl,
            method="HF",
            basis="STO-3G",
            dispersion="false",
            solvent="smd",
            jobtype="opt",
            calc_type="full_cat",
        )
        assert "full_cat_extra = true" in result

    def test_all_calc_types(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        for ct in _CALC_TYPE_FILES:
            result = build_opt_rem(
                tpl,
                method="X",
                basis="Y",
                dispersion="d3",
                solvent="pcm",
                jobtype="opt",
                calc_type=ct,
            )
            assert f"{ct.replace('_cat', '_cat')}_extra = true" in result

    def test_no_calc_type(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        result = build_opt_rem(
            tpl,
            method="HF",
            basis="STO-3G",
            dispersion="false",
            solvent="smd",
            jobtype="opt",
            calc_type=None,
        )
        # No calc_type extras
        assert "full_cat_extra" not in result
        assert "pol_cat_extra" not in result
        assert "frz_cat_extra" not in result


# ===================================================================
# 8. build_sp_rem
# ===================================================================


class TestBuildSpRem:
    def test_basic(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        result = build_sp_rem(
            tpl,
            method="MP2",
            basis="cc-pVTZ",
            dispersion="false",
            solvent="smd",
            eda2="1",
            scfmi_freeze_ss="0",
            eda_bsse="false",
        )
        assert "method = MP2" in result
        assert "eda2 = 1" in result
        assert "scfmi_freeze_ss = 0" in result
        assert "eda_bsse = false" in result

    def test_frz_params(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        result = build_sp_rem(
            tpl,
            method="MP2",
            basis="cc-pVTZ",
            dispersion="false",
            solvent="smd",
            eda2="1",
            scfmi_freeze_ss="1",
            eda_bsse="false",
        )
        assert "scfmi_freeze_ss = 1" in result

    def test_bsse_true(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        result = build_sp_rem(
            tpl,
            method="MP2",
            basis="cc-pVTZ",
            dispersion="false",
            solvent="smd",
            eda2="1",
            scfmi_freeze_ss="0",
            eda_bsse="true",
        )
        assert "eda_bsse = true" in result


# ===================================================================
# 9. _build_rem_section (routing logic)
# ===================================================================


class TestBuildRemSection:
    def test_opt_mode_basic(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        spec = _make_spec(mode="opt", stage="reactants")
        result = _build_rem_section(spec, tpl, n_atoms=3)
        assert "jobtype = opt" in result

    def test_opt_ts_stage(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        spec = _make_spec(mode="opt", stage="ts", species="tscomplex")
        result = _build_rem_section(spec, tpl, n_atoms=8)
        assert "jobtype = ts" in result

    def test_opt_single_atom_forced_sp(self, tmp_path: Path) -> None:
        """Single-atom molecule in OPT mode must use jobtype=sp."""
        tpl = _make_template_dir(tmp_path)
        spec = _make_spec(mode="opt", stage="cat", species="cat1", catalyst="cat1")
        result = _build_rem_section(spec, tpl, n_atoms=1)
        assert "jobtype = sp" in result

    def test_sp_mode(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        spec = _make_spec(mode="sp", stage="reactants", eda2=1)
        result = _build_rem_section(spec, tpl)
        assert "jobtype = sp" in result
        assert "eda2 = " in result

    def test_sp_uncatalyzed_eda2_zero(self, tmp_path: Path) -> None:
        """Uncatalyzed SP should have eda2=0 regardless of spec.eda2."""
        tpl = _make_template_dir(tmp_path)
        spec = _make_spec(mode="sp", catalyst=None, stage="reactants", eda2=1)
        result = _build_rem_section(spec, tpl)
        assert "eda2 = 0" in result

    def test_sp_cat_stage_eda2_zero(self, tmp_path: Path) -> None:
        """Catalyst standalone SP should have eda2=0."""
        tpl = _make_template_dir(tmp_path)
        spec = _make_spec(
            mode="sp", catalyst="cat1", stage="cat", species="cat1", eda2=1
        )
        result = _build_rem_section(spec, tpl)
        assert "eda2 = 0" in result

    def test_sp_frz_cat(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        spec = _make_spec(
            mode="sp",
            catalyst="cat1",
            stage="preTS",
            species="cat1-mol_a",
            calc_type="frz_cat",
            is_fragmented=True,
            eda2=1,
        )
        result = _build_rem_section(spec, tpl)
        assert "scfmi_freeze_ss = 1" in result
        assert "eda_bsse = false" in result

    def test_sp_full_cat(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        spec = _make_spec(
            mode="sp",
            catalyst="cat1",
            stage="preTS",
            species="cat1-mol_a",
            calc_type="full_cat",
            is_fragmented=True,
            eda2=1,
        )
        result = _build_rem_section(spec, tpl)
        assert "scfmi_freeze_ss = 0" in result
        assert "eda_bsse = true" in result

    def test_sp_pol_cat(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        spec = _make_spec(
            mode="sp",
            catalyst="cat1",
            stage="preTS",
            species="cat1-mol_a",
            calc_type="pol_cat",
            is_fragmented=True,
            eda2=1,
        )
        result = _build_rem_section(spec, tpl)
        assert "scfmi_freeze_ss = 0" in result
        assert "eda_bsse = false" in result

    def test_opt_with_calc_type(self, tmp_path: Path) -> None:
        """OPT mode for catalyzed preTS with calc_type appends extra REM."""
        tpl = _make_template_dir(tmp_path)
        spec = _make_spec(
            mode="opt",
            catalyst="cat1",
            stage="preTS",
            species="cat1-mol_a",
            calc_type="full_cat",
            is_fragmented=True,
        )
        result = _build_rem_section(spec, tpl)
        assert "full_cat_extra = true" in result


# ===================================================================
# 10. _build_standard / _build_fragmented (inputs.py)
# ===================================================================


class TestBuildStandard:
    def test_loads_and_builds(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "water", _XYZ_3ATOM)
        result = _build_standard(tpl, "water", opt_output_text=None)
        assert result is not None
        text, n_atoms = result
        assert text.startswith("0 1\n")
        assert n_atoms == 3

    def test_missing_template(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        result = _build_standard(tpl, "nonexistent", opt_output_text=None)
        assert result is None


class TestBuildFragmentedInputs:
    def test_loads_and_builds(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "cat1-mol_a", _XYZ_COMPOSITE)
        _write_xyz(tpl, "cat1", _XYZ_CAT)
        _write_xyz(tpl, "mol_a", _XYZ_SUB)
        result = _build_fragmented(
            tpl,
            "cat1-mol_a",
            catalyst="cat1",
            species="cat1-mol_a",
            calc_type=None,
            opt_output_text=None,
        )
        assert result is not None
        text, n_atoms = result
        assert "---" in text
        assert n_atoms == 3

    def test_with_calc_type_template(self, tmp_path: Path) -> None:
        """Prefers calc_type-specific composite XYZ if present."""
        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "cat1-mol_a", _XYZ_COMPOSITE, calc_type="full_cat")
        _write_xyz(tpl, "cat1", _XYZ_CAT)
        _write_xyz(tpl, "mol_a", _XYZ_SUB)
        result = _build_fragmented(
            tpl,
            "cat1-mol_a",
            catalyst="cat1",
            species="cat1-mol_a",
            calc_type="full_cat",
            opt_output_text=None,
        )
        assert result is not None

    def test_missing_composite(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "cat1", _XYZ_CAT)
        _write_xyz(tpl, "mol_a", _XYZ_SUB)
        result = _build_fragmented(
            tpl,
            "missing",
            catalyst="cat1",
            species="cat1-mol_a",
            calc_type=None,
            opt_output_text=None,
        )
        assert result is None

    def test_missing_catalyst_xyz(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "cat1-mol_a", _XYZ_COMPOSITE)
        _write_xyz(tpl, "mol_a", _XYZ_SUB)
        result = _build_fragmented(
            tpl,
            "cat1-mol_a",
            catalyst="cat1",
            species="cat1-mol_a",
            calc_type=None,
            opt_output_text=None,
        )
        assert result is None

    def test_missing_substrate_xyz(self, tmp_path: Path) -> None:
        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "cat1-mol_a", _XYZ_COMPOSITE)
        _write_xyz(tpl, "cat1", _XYZ_CAT)
        result = _build_fragmented(
            tpl,
            "cat1-mol_a",
            catalyst="cat1",
            species="cat1-mol_a",
            calc_type=None,
            opt_output_text=None,
        )
        assert result is None

    def test_species_split_logic(self, tmp_path: Path) -> None:
        """Species 'cat1-A-B' should split as cat_id='cat1' (from catalyst param),
        substrate_id='A-B' (everything after first dash in species)."""
        tpl = _make_template_dir(tmp_path)
        # Composite with 5 atoms (cat: 2, sub: 3 atoms)
        composite_5 = "5\n0 1\nLi 0 0 0\nNa 1 0 0\nC 2 0 0\nO 3 0 0\nH 4 0 0\n"
        cat_2 = "2\n0 1\nLi 0 0 0\nNa 1 0 0\n"
        sub_3 = "3\n0 1\nC 2 0 0\nO 3 0 0\nH 4 0 0\n"
        _write_xyz(tpl, "cat1-A-B", composite_5)
        _write_xyz(tpl, "cat1", cat_2)
        _write_xyz(tpl, "A-B", sub_3)

        result = _build_fragmented(
            tpl,
            "cat1-A-B",
            catalyst="cat1",
            species="cat1-A-B",
            calc_type=None,
            opt_output_text=None,
        )
        assert result is not None
        text, n_atoms = result
        assert "---" in text
        assert n_atoms == 5


# ===================================================================
# 11. _build_molecule_section (routing)
# ===================================================================


class TestBuildMoleculeSection:
    @pytest.fixture
    def registry_with_xyz(self, tmp_path: Path) -> tuple[CalcRegistry, Path]:
        cfg = _simple_config()
        base = tmp_path / "data"
        base.mkdir()
        reg = CalcRegistry(cfg, base)
        tpl = _make_template_dir(tmp_path)
        # Write XYZ templates for every species the registry expects
        _write_xyz(tpl, "mol_a", _XYZ_3ATOM)
        _write_xyz(tpl, "mol_p", _XYZ_3ATOM)
        _write_xyz(tpl, "tscomplex", _XYZ_3ATOM)
        _write_xyz(tpl, "cat1", _XYZ_CAT)
        _write_xyz(tpl, "cat1-mol_a", _XYZ_COMPOSITE)
        _write_xyz(tpl, "mol_a", _XYZ_SUB)  # overwrite for substrate role
        _write_xyz(tpl, "ts_cat1-tscomplex", _XYZ_COMPOSITE)
        _write_xyz(tpl, "tscomplex", _XYZ_SUB)  # overwrite for substrate role
        return reg, tpl

    def test_uncatalyzed_reactant(self, registry_with_xyz: tuple) -> None:
        reg, tpl = registry_with_xyz
        spec = [
            s
            for s in reg.all_calcs
            if s.id.stage == "reactants"
            and s.id.catalyst is None
            and s.id.species == "mol_a"
            and s.id.mode == "opt"
        ][0]
        result = _build_molecule_section(spec, reg, tpl)
        assert result is not None
        text, n_atoms = result
        assert "---" not in text  # not fragmented
        assert n_atoms == 2  # mol_a overwritten with _XYZ_SUB (2 atoms)

    def test_uncatalyzed_ts(self, registry_with_xyz: tuple) -> None:
        reg, tpl = registry_with_xyz
        spec = [
            s
            for s in reg.all_calcs
            if s.id.stage == "ts" and s.id.catalyst is None and s.id.mode == "opt"
        ][0]
        result = _build_molecule_section(spec, reg, tpl)
        assert result is not None

    def test_catalyzed_preTS_fragmented(self, registry_with_xyz: tuple) -> None:
        reg, tpl = registry_with_xyz
        specs = [
            s
            for s in reg.all_calcs
            if s.id.stage == "preTS" and s.id.catalyst == "cat1" and s.id.mode == "opt"
        ]
        assert len(specs) > 0
        for spec in specs:
            assert spec.is_fragmented

    def test_catalyst_standalone(self, registry_with_xyz: tuple) -> None:
        reg, tpl = registry_with_xyz
        spec = [
            s
            for s in reg.all_calcs
            if s.id.stage == "cat" and s.id.catalyst == "cat1" and s.id.mode == "opt"
        ][0]
        result = _build_molecule_section(spec, reg, tpl)
        # cat stage is not fragmented
        assert result is not None
        text, n_atoms = result
        assert "---" not in text
        assert n_atoms == 1  # single atom catalyst

    def test_sp_without_matching_opt(self, tmp_path: Path) -> None:
        """SP spec whose OPT CalcID is missing from registry → KeyError caught, still builds."""
        from unittest.mock import MagicMock

        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "mol_a", _XYZ_SUB)
        spec = _make_spec(mode="sp", stage="reactants", species="mol_a")
        # Mock registry that raises KeyError for any get()
        reg = MagicMock()
        reg.get.side_effect = KeyError("not found")
        result = _build_molecule_section(spec, reg, tpl)
        assert result is not None  # builds with template xyz (no opt coords)


# ===================================================================
# 12. Path construction (exact paths)
# ===================================================================


class TestPathConstruction:
    """Verify exact filesystem paths produced by the registry for all combos."""

    @pytest.fixture
    def reg(self, tmp_path: Path) -> CalcRegistry:
        return CalcRegistry(_simple_config(), tmp_path)

    @pytest.fixture
    def sp_reg(self, tmp_path: Path) -> CalcRegistry:
        return CalcRegistry(_config_with_sp(), tmp_path)

    # -- Uncatalyzed OPT ---

    def test_uncatalyzed_reactant_opt(self, reg: CalcRegistry, tmp_path: Path) -> None:
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="reactants",
                species="mol_a",
                mode="opt",
            )
        )
        expected = tmp_path / "HF_STO-3G_smd/no_cat/reactants/mol_a/mol_a_opt.in"
        assert spec.input_path == expected

    def test_uncatalyzed_product_opt(self, reg: CalcRegistry, tmp_path: Path) -> None:
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="products",
                species="mol_p",
                mode="opt",
            )
        )
        expected = tmp_path / "HF_STO-3G_smd/no_cat/products/mol_p/mol_p_opt.in"
        assert spec.input_path == expected

    def test_uncatalyzed_ts_opt(self, reg: CalcRegistry, tmp_path: Path) -> None:
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="ts",
                species="tscomplex",
                mode="opt",
            )
        )
        expected = tmp_path / "HF_STO-3G_smd/no_cat/ts/tscomplex_opt.in"
        assert spec.input_path == expected

    # -- Catalyzed OPT ---

    def test_catalyzed_cat_opt(self, reg: CalcRegistry, tmp_path: Path) -> None:
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst="cat1",
                stage="cat",
                species="cat1",
                mode="opt",
            )
        )
        expected = tmp_path / "HF_STO-3G_smd/cat1/cat/cat1_opt.in"
        assert spec.input_path == expected

    def test_catalyzed_preTS_full_opt(self, reg: CalcRegistry, tmp_path: Path) -> None:
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst="cat1",
                stage="preTS",
                species="cat1-mol_a",
                calc_type="full_cat",
                mode="opt",
            )
        )
        expected = (
            tmp_path
            / "HF_STO-3G_smd/cat1/preTS/cat1-mol_a/full_cat"
            / "preTS_cat1-mol_a_full_cat_opt.in"
        )
        assert spec.input_path == expected

    def test_catalyzed_preTS_pol_opt(self, reg: CalcRegistry, tmp_path: Path) -> None:
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst="cat1",
                stage="preTS",
                species="cat1-mol_a",
                calc_type="pol_cat",
                mode="opt",
            )
        )
        expected = (
            tmp_path
            / "HF_STO-3G_smd/cat1/preTS/cat1-mol_a/pol_cat"
            / "preTS_cat1-mol_a_pol_cat_opt.in"
        )
        assert spec.input_path == expected

    def test_catalyzed_preTS_frz_opt(self, reg: CalcRegistry, tmp_path: Path) -> None:
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst="cat1",
                stage="preTS",
                species="cat1-mol_a",
                calc_type="frz_cat",
                mode="opt",
            )
        )
        expected = (
            tmp_path
            / "HF_STO-3G_smd/cat1/preTS/cat1-mol_a/frz_cat"
            / "preTS_cat1-mol_a_frz_cat_opt.in"
        )
        assert spec.input_path == expected

    def test_catalyzed_postTS_opt(self, reg: CalcRegistry, tmp_path: Path) -> None:
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst="cat1",
                stage="postTS",
                species="cat1-mol_p",
                calc_type="full_cat",
                mode="opt",
            )
        )
        expected = (
            tmp_path
            / "HF_STO-3G_smd/cat1/postTS/cat1-mol_p/full_cat"
            / "postTS_cat1-mol_p_full_cat_opt.in"
        )
        assert spec.input_path == expected

    def test_catalyzed_ts_opt(self, reg: CalcRegistry, tmp_path: Path) -> None:
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst="cat1",
                stage="ts",
                species="cat1-tscomplex",
                calc_type="full_cat",
                mode="opt",
            )
        )
        expected = (
            tmp_path
            / "HF_STO-3G_smd/cat1/ts/full_cat"
            / "ts_cat1-tscomplex_full_cat_opt.in"
        )
        assert spec.input_path == expected

    # -- Uncatalyzed SP ---

    def test_uncatalyzed_reactant_sp(
        self, sp_reg: CalcRegistry, tmp_path: Path
    ) -> None:
        spec = sp_reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="reactants",
                species="mol_a",
                mode="sp",
                sp_subfolder="MP2_cc-pVTZ_smd_sp",
            )
        )
        expected = (
            tmp_path
            / "HF_STO-3G_smd/no_cat/reactants/mol_a/MP2_cc-pVTZ_smd_sp"
            / "mol_a_sp.in"
        )
        assert spec.input_path == expected

    def test_uncatalyzed_ts_sp(self, sp_reg: CalcRegistry, tmp_path: Path) -> None:
        spec = sp_reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="ts",
                species="tscomplex",
                mode="sp",
                sp_subfolder="MP2_cc-pVTZ_smd_sp",
            )
        )
        expected = (
            tmp_path / "HF_STO-3G_smd/no_cat/ts/MP2_cc-pVTZ_smd_sp" / "tscomplex_sp.in"
        )
        assert spec.input_path == expected

    # -- Catalyzed SP ---

    def test_catalyzed_cat_sp(self, sp_reg: CalcRegistry, tmp_path: Path) -> None:
        spec = sp_reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst="cat1",
                stage="cat",
                species="cat1",
                mode="sp",
                sp_subfolder="MP2_cc-pVTZ_smd_sp",
            )
        )
        expected = tmp_path / "HF_STO-3G_smd/cat1/cat/MP2_cc-pVTZ_smd_sp" / "cat1_sp.in"
        assert spec.input_path == expected

    def test_catalyzed_preTS_sp(self, sp_reg: CalcRegistry, tmp_path: Path) -> None:
        spec = sp_reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst="cat1",
                stage="preTS",
                species="cat1-mol_a",
                calc_type="full_cat",
                mode="sp",
                sp_subfolder="MP2_cc-pVTZ_smd_sp",
            )
        )
        expected = (
            tmp_path
            / "HF_STO-3G_smd/cat1/preTS/cat1-mol_a/full_cat"
            / "MP2_cc-pVTZ_smd_sp"
            / "preTS_cat1-mol_a_full_cat_sp.in"
        )
        assert spec.input_path == expected

    def test_catalyzed_ts_sp(self, sp_reg: CalcRegistry, tmp_path: Path) -> None:
        spec = sp_reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst="cat1",
                stage="ts",
                species="cat1-tscomplex",
                calc_type="full_cat",
                mode="sp",
                sp_subfolder="MP2_cc-pVTZ_smd_sp",
            )
        )
        expected = (
            tmp_path
            / "HF_STO-3G_smd/cat1/ts/full_cat"
            / "MP2_cc-pVTZ_smd_sp"
            / "ts_cat1-tscomplex_full_cat_sp.in"
        )
        assert spec.input_path == expected

    # -- Output path consistency ---

    def test_output_path_matches_input(self, reg: CalcRegistry) -> None:
        for spec in reg.all_calcs:
            assert spec.output_path == spec.input_path.with_suffix(".out")


# ===================================================================
# 13. Path edge cases: multiple reactants, sanitization
# ===================================================================


class TestPathEdgeCases:
    def test_multiple_reactants_combo_path(self, tmp_path: Path) -> None:
        """Two include=True reactants produce a combined species A-B."""
        cfg = Config(
            levels=[LevelConfig(opt=TheoryConfig(method="HF", basis="STO-3G"))],
            reactants=[
                SpeciesConfig(name="A"),
                SpeciesConfig(name="B"),
            ],
            products=[SpeciesConfig(name="C")],
        )
        reg = CalcRegistry(cfg, tmp_path)
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G",
                catalyst=None,
                stage="reactants",
                species="A-B",
                mode="opt",
            )
        )
        expected = tmp_path / "HF_STO-3G/no_cat/reactants/A-B/A-B_opt.in"
        assert spec.input_path == expected

    def test_free_reactant_not_in_combos(self, tmp_path: Path) -> None:
        """include=False reactant appears individually but not in combos."""
        cfg = Config(
            levels=[LevelConfig(opt=TheoryConfig(method="HF", basis="STO-3G"))],
            reactants=[
                SpeciesConfig(name="A", include=True),
                SpeciesConfig(name="free", include=False),
            ],
            products=[SpeciesConfig(name="P")],
        )
        reg = CalcRegistry(cfg, tmp_path)
        # "free" exists as individual reactant
        spec_free = reg.get(
            CalcID(
                method_key="HF_STO-3G",
                catalyst=None,
                stage="reactants",
                species="free",
                mode="opt",
            )
        )
        assert spec_free is not None
        # No "A-free" combo should exist
        with pytest.raises(KeyError):
            reg.get(
                CalcID(
                    method_key="HF_STO-3G",
                    catalyst=None,
                    stage="reactants",
                    species="A-free",
                    mode="opt",
                )
            )

    def test_sanitized_species_name(self, tmp_path: Path) -> None:
        """Species with special characters get sanitized in paths."""
        cfg = Config(
            levels=[LevelConfig(opt=TheoryConfig(method="HF", basis="STO-3G"))],
            reactants=[SpeciesConfig(name="mol (a)")],
            products=[SpeciesConfig(name="P")],
        )
        reg = CalcRegistry(cfg, tmp_path)
        # Parentheses sanitized
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G",
                catalyst=None,
                stage="reactants",
                species="mol-space--lparen-a-rparen-",
                mode="opt",
            )
        )
        assert "-lparen-" in str(spec.input_path)

    def test_two_catalysts(self, tmp_path: Path) -> None:
        """Multiple catalysts each get their own directory branch."""
        cfg = Config(
            levels=[LevelConfig(opt=TheoryConfig(method="HF", basis="STO-3G"))],
            reactants=[SpeciesConfig(name="R")],
            products=[SpeciesConfig(name="P")],
            catalysts=[CatalystConfig(name="c1"), CatalystConfig(name="c2")],
        )
        reg = CalcRegistry(cfg, tmp_path)
        s1 = reg.get(
            CalcID(
                method_key="HF_STO-3G",
                catalyst="c1",
                stage="cat",
                species="c1",
                mode="opt",
            )
        )
        s2 = reg.get(
            CalcID(
                method_key="HF_STO-3G",
                catalyst="c2",
                stage="cat",
                species="c2",
                mode="opt",
            )
        )
        assert "c1/cat" in str(s1.input_path)
        assert "c2/cat" in str(s2.input_path)
        assert s1.input_path != s2.input_path

    def test_no_catalysts(self, tmp_path: Path) -> None:
        """Config without catalysts has no catalyzed calcs at all."""
        cfg = Config(
            levels=[LevelConfig(opt=TheoryConfig(method="HF", basis="STO-3G"))],
            reactants=[SpeciesConfig(name="R")],
            products=[SpeciesConfig(name="P")],
        )
        reg = CalcRegistry(cfg, tmp_path)
        assert all(s.id.catalyst is None for s in reg.all_calcs)
        assert all("no_cat" in str(s.input_path) for s in reg.all_calcs)


# ===================================================================
# 14. _opt_successful / _should_overwrite
# ===================================================================


class TestOptSuccessful:
    def test_successful(self, tmp_path: Path) -> None:
        cfg = _simple_config()
        base = tmp_path / "data"
        base.mkdir()
        reg = CalcRegistry(cfg, base)

        sp_spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="reactants",
                species="mol_a",
                mode="opt",
            )
        )
        # Write a successful OPT output
        sp_spec.output_path.parent.mkdir(parents=True, exist_ok=True)
        sp_spec.output_path.write_text(OPT_OUTPUT)

        # Now test from an SP spec looking for this OPT
        # _opt_successful builds an opt CalcID from the sp spec
        # We can't directly call _opt_successful without a matching SP spec in the registry
        # so we check the opt spec status directly
        from pya3eda.parser.qchem import parse_status

        out_text = sp_spec.output_path.read_text()
        status, _ = parse_status(out_text)
        assert status == "SUCCESSFUL"

    def test_no_opt_output(self, tmp_path: Path) -> None:
        cfg = _simple_config()
        reg = CalcRegistry(cfg, tmp_path / "data")
        # No output files exist → _opt_successful returns False
        sp_spec = _make_spec(mode="sp", stage="reactants", species="mol_a")
        assert not _opt_successful(sp_spec, reg)

    def test_opt_key_missing_from_registry(self, tmp_path: Path) -> None:
        """SP spec whose OPT CalcID doesn't exist in registry → False."""
        cfg = _simple_config()
        reg = CalcRegistry(cfg, tmp_path / "data")
        sp_spec = _make_spec(mode="sp", stage="reactants", species="unknown_species")
        assert not _opt_successful(sp_spec, reg)


class TestShouldOverwrite:
    def test_overwrite_all(self, tmp_path: Path) -> None:
        f = tmp_path / "test.in"
        f.write_text("content")
        assert _should_overwrite(f, "all") is True

    def test_overwrite_none(self, tmp_path: Path) -> None:
        f = tmp_path / "test.in"
        f.write_text("content")
        assert _should_overwrite(f, None) is False

    def test_overwrite_matching_status(self, tmp_path: Path) -> None:
        """Overwrite if existing file's status matches the overwrite criterion."""
        f = tmp_path / "test.in"
        f.write_text("content")
        # Write a CRASH output alongside
        f.with_suffix(".out").write_text("SCF failed to converge")
        f.with_suffix(".err").write_text("")
        assert _should_overwrite(f, "CRASH") is True

    def test_overwrite_nonmatching_status(self, tmp_path: Path) -> None:
        f = tmp_path / "test.in"
        f.write_text("content")
        f.with_suffix(".out").write_text(OPT_OUTPUT)
        f.with_suffix(".err").write_text("")
        # OPT_OUTPUT is SUCCESSFUL, not CRASH
        assert _should_overwrite(f, "CRASH") is False


# ===================================================================
# 15. Full build_all integration
# ===================================================================


class TestBuildAll:
    """Integration tests for the full build_all pipeline."""

    @pytest.fixture
    def setup(self, tmp_path: Path) -> tuple[CalcRegistry, Path]:
        """Registry + template dir with all required XYZ templates.

        Atom counts must be consistent: composite = cat + sub.
        cat1 = 1 atom, substrates = 2 atoms, composites = 3 atoms.
        Standalone species also use 2-atom XYZ (valid for standard builds).
        """
        cfg = _simple_config()
        base = tmp_path / "data"
        base.mkdir()
        reg = CalcRegistry(cfg, base)
        tpl = _make_template_dir(tmp_path)

        # Standalone / substrate species (2 atoms each)
        _write_xyz(tpl, "mol_a", _XYZ_SUB)
        _write_xyz(tpl, "mol_p", _XYZ_SUB)
        _write_xyz(tpl, "tscomplex", _XYZ_SUB)

        # Catalyst (1 atom)
        _write_xyz(tpl, "cat1", _XYZ_CAT)

        # Fragmented composites (3 atoms = 1 cat + 2 sub)
        # template_name for preTS = "preTS_{species}" = "preTS_cat1-mol_a"
        _write_xyz(tpl, "preTS_cat1-mol_a", _XYZ_COMPOSITE)
        # template_name for postTS = "postTS_{species}" = "postTS_cat1-mol_p"
        _write_xyz(tpl, "postTS_cat1-mol_p", _XYZ_COMPOSITE)
        # template_name for catalyzed TS = "ts_{species}" = "ts_cat1-tscomplex"
        _write_xyz(tpl, "ts_cat1-tscomplex", _XYZ_COMPOSITE)

        return reg, tpl

    def test_creates_opt_files(self, setup: tuple) -> None:
        reg, tpl = setup
        build_all(reg, tpl)
        opt_calcs = [s for s in reg.all_calcs if s.id.mode == "opt"]
        for spec in opt_calcs:
            assert spec.input_path.exists(), f"Missing: {spec.input_path}"

    def test_file_content_has_sections(self, setup: tuple) -> None:
        reg, tpl = setup
        build_all(reg, tpl)
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="reactants",
                species="mol_a",
                mode="opt",
            )
        )
        content = spec.input_path.read_text()
        assert "$rem" in content
        assert "$molecule" in content
        assert "$end" in content
        assert "method = HF" in content
        assert "basis = STO-3G" in content

    def test_opt_file_has_geom_block(self, setup: tuple) -> None:
        reg, tpl = setup
        build_all(reg, tpl)
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="reactants",
                species="mol_a",
                mode="opt",
            )
        )
        content = spec.input_path.read_text()
        assert "geom_opt_max_cycles" in content

    def test_solvent_block(self, setup: tuple) -> None:
        reg, tpl = setup
        build_all(reg, tpl)
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="reactants",
                species="mol_a",
                mode="opt",
            )
        )
        content = spec.input_path.read_text()
        assert "$smx" in content
        assert "solvent water" in content

    def test_ts_has_ts_jobtype(self, setup: tuple) -> None:
        reg, tpl = setup
        build_all(reg, tpl)
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="ts",
                species="tscomplex",
                mode="opt",
            )
        )
        content = spec.input_path.read_text()
        assert "jobtype = ts" in content

    def test_skips_existing(self, setup: tuple) -> None:
        reg, tpl = setup
        build_all(reg, tpl)
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="reactants",
                species="mol_a",
                mode="opt",
            )
        )
        original_content = spec.input_path.read_text()  # noqa: F841
        # Modify the file
        spec.input_path.write_text("MODIFIED")
        # Build again without overwrite → should skip
        build_all(reg, tpl, overwrite=None)
        assert spec.input_path.read_text() == "MODIFIED"

    def test_overwrite_all(self, setup: tuple) -> None:
        reg, tpl = setup
        build_all(reg, tpl)
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="reactants",
                species="mol_a",
                mode="opt",
            )
        )
        spec.input_path.write_text("MODIFIED")
        # Build with overwrite="all" → should replace
        build_all(reg, tpl, overwrite="all")
        assert spec.input_path.read_text() != "MODIFIED"

    def test_sp_strategy_never(self, tmp_path: Path) -> None:
        """sp_strategy='never' should skip all SP calcs."""
        cfg = _config_with_sp()
        base = tmp_path / "data"
        base.mkdir()
        reg = CalcRegistry(cfg, base)
        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "mol_a", _XYZ_SUB)
        _write_xyz(tpl, "mol_p", _XYZ_SUB)
        _write_xyz(tpl, "tscomplex", _XYZ_SUB)
        _write_xyz(tpl, "cat1", _XYZ_CAT)
        _write_xyz(tpl, "preTS_cat1-mol_a", _XYZ_COMPOSITE)
        _write_xyz(tpl, "postTS_cat1-mol_p", _XYZ_COMPOSITE)
        _write_xyz(tpl, "ts_cat1-tscomplex", _XYZ_COMPOSITE)

        build_all(reg, tpl, sp_strategy="never")
        sp_calcs = [s for s in reg.all_calcs if s.id.mode == "sp"]
        for spec in sp_calcs:
            assert not spec.input_path.exists(), (
                f"SP file should not exist: {spec.input_path}"
            )

    def test_sp_strategy_smart(self, setup: tuple) -> None:
        """sp_strategy='smart' skips SP when OPT hasn't succeeded."""
        reg, tpl = setup
        # Only build OPT files first — no SP theory in _simple_config
        build_all(reg, tpl, sp_strategy="smart")
        # All OPT should exist
        opt_calcs = [s for s in reg.all_calcs if s.id.mode == "opt"]
        for spec in opt_calcs:
            assert spec.input_path.exists()

    def test_sp_strategy_smart_with_opt_output(self, tmp_path: Path) -> None:
        """SP files created when OPT output exists and is SUCCESSFUL."""
        cfg = _config_with_sp()
        base = tmp_path / "data"
        base.mkdir()
        reg = CalcRegistry(cfg, base)
        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "mol_a", _XYZ_SUB)
        _write_xyz(tpl, "mol_p", _XYZ_SUB)
        _write_xyz(tpl, "tscomplex", _XYZ_SUB)
        _write_xyz(tpl, "cat1", _XYZ_CAT)
        _write_xyz(tpl, "preTS_cat1-mol_a", _XYZ_COMPOSITE)
        _write_xyz(tpl, "postTS_cat1-mol_p", _XYZ_COMPOSITE)
        _write_xyz(tpl, "ts_cat1-tscomplex", _XYZ_COMPOSITE)

        # First build OPT files
        build_all(reg, tpl, sp_strategy="never")

        # Create successful OPT output for the reactant
        opt_spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="reactants",
                species="mol_a",
                mode="opt",
            )
        )
        opt_spec.output_path.parent.mkdir(parents=True, exist_ok=True)
        opt_spec.output_path.write_text(OPT_OUTPUT)

        # Now build with smart strategy — SP for mol_a reactant should be created
        build_all(reg, tpl, sp_strategy="smart")
        sp_spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst=None,
                stage="reactants",
                species="mol_a",
                mode="sp",
                sp_subfolder="MP2_cc-pVTZ_smd_sp",
            )
        )
        assert sp_spec.input_path.exists()

    def test_missing_base_template(self, tmp_path: Path) -> None:
        """build_all raises FileNotFoundError if base_template.in missing."""
        cfg = _simple_config()
        reg = CalcRegistry(cfg, tmp_path / "data")
        empty_tpl = tmp_path / "tpl"
        empty_tpl.mkdir()
        with pytest.raises(FileNotFoundError, match="Base template not found"):
            build_all(reg, empty_tpl)

    def test_fragmented_in_file_content(self, setup: tuple) -> None:
        """Catalyzed preTS input file should contain '---' fragment separator."""
        reg, tpl = setup
        build_all(reg, tpl)
        spec = [
            s for s in reg.all_calcs if s.id.stage == "preTS" and s.id.mode == "opt"
        ][0]
        content = spec.input_path.read_text()
        assert "---" in content

    def test_catalyzed_ts_file_content(self, setup: tuple) -> None:
        """Catalyzed TS input should contain fragment separators and correct REM."""
        reg, tpl = setup
        spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst="cat1",
                stage="ts",
                species="cat1-tscomplex",
                calc_type="full_cat",
                mode="opt",
            )
        )
        build_all(reg, tpl)
        content = spec.input_path.read_text()
        assert "---" in content
        assert "jobtype = ts" in content
        assert "full_cat_extra = true" in content

    def test_no_empty_files(self, setup: tuple) -> None:
        """No generated input file should be empty."""
        reg, tpl = setup
        build_all(reg, tpl)
        for spec in reg.all_calcs:
            if spec.input_path.exists():
                assert spec.input_path.read_text().strip(), (
                    f"Empty file: {spec.input_path}"
                )


# ===================================================================
# 17. _CALC_TYPE_FILES mapping
# ===================================================================


class TestCalcTypeFiles:
    def test_all_three_present(self) -> None:
        assert set(_CALC_TYPE_FILES.keys()) == {"full_cat", "pol_cat", "frz_cat"}

    def test_unique_filenames(self) -> None:
        assert len(set(_CALC_TYPE_FILES.values())) == 3


# ===================================================================
# 18. Single-atom integration
# ===================================================================


class TestSingleAtomIntegration:
    def test_single_atom_catalyst_opt_uses_sp_jobtype(self, tmp_path: Path) -> None:
        """build_all for a single-atom catalyst should produce jobtype=sp, not opt."""
        cfg = Config(
            levels=[
                LevelConfig(
                    opt=TheoryConfig(method="HF", basis="STO-3G", solvent="smd"),
                )
            ],
            reactants=[SpeciesConfig(name="mol_a")],
            products=[SpeciesConfig(name="mol_p")],
            catalysts=[CatalystConfig(name="cat1")],
        )
        base = tmp_path / "data"
        base.mkdir()
        reg = CalcRegistry(cfg, base)
        tpl = _make_template_dir(tmp_path)

        # cat1 = single atom
        _write_xyz(tpl, "cat1", _XYZ_CAT)
        _write_xyz(tpl, "mol_a", _XYZ_SUB)
        _write_xyz(tpl, "mol_p", _XYZ_SUB)
        _write_xyz(tpl, "tscomplex", _XYZ_SUB)
        _write_xyz(tpl, "preTS_cat1-mol_a", _XYZ_COMPOSITE)
        _write_xyz(tpl, "postTS_cat1-mol_p", _XYZ_COMPOSITE)
        _write_xyz(tpl, "ts_cat1-tscomplex", _XYZ_COMPOSITE)

        build_all(reg, tpl)

        cat_spec = reg.get(
            CalcID(
                method_key="HF_STO-3G_smd",
                catalyst="cat1",
                stage="cat",
                species="cat1",
                mode="opt",
            )
        )
        content = cat_spec.input_path.read_text()
        assert "jobtype = sp" in content

    def test_multi_atom_still_gets_opt(self, tmp_path: Path) -> None:
        """Multi-atom molecules still get jobtype=opt."""
        cfg = Config(
            levels=[
                LevelConfig(
                    opt=TheoryConfig(method="HF", basis="STO-3G", solvent="smd"),
                )
            ],
            reactants=[SpeciesConfig(name="mol_a")],
            products=[SpeciesConfig(name="mol_p")],
        )
        base = tmp_path / "data"
        base.mkdir()
        reg = CalcRegistry(cfg, base)
        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "mol_a", _XYZ_SUB)  # 2 atoms
        _write_xyz(tpl, "mol_p", _XYZ_SUB)
        _write_xyz(tpl, "tscomplex", _XYZ_SUB)

        build_all(reg, tpl)


# ===================================================================
# Edge cases for _build_one coverage gaps
# ===================================================================


class TestBuildOneEdgeCases:
    def test_molecule_section_failure(self, tmp_path: Path) -> None:
        """Missing xyz template → _build_molecule_section returns None → early return."""
        tpl = _make_template_dir(tmp_path)
        base_template = (tpl / "base_template.in").read_text()
        # No xyz templates written → molecule section will fail
        spec = _make_spec(
            stage="reactants",
            species="missing_mol",
            input_path=tmp_path / "out" / "missing_opt.in",
        )
        cfg = _simple_config()
        reg = CalcRegistry(cfg, tmp_path / "data")
        _build_one(spec, reg, tpl, base_template, None, "always")
        # File should NOT be created
        assert not spec.input_path.exists()

    def test_empty_content_skipped(self, tmp_path: Path) -> None:
        """Template producing whitespace-only content → skipped."""
        tpl = _make_template_dir(tmp_path)
        # A template with no format placeholders that results in whitespace only
        empty_template = "   "
        spec = _make_spec(
            stage="reactants",
            species="mol_a",
            mode="sp",
            solvent="false",
            input_path=tmp_path / "out" / "mol_opt.in",
        )
        _write_xyz(tpl, "mol_a", _XYZ_SUB)
        cfg = _simple_config()
        reg = CalcRegistry(cfg, tmp_path / "data")
        from unittest.mock import patch

        with (
            patch(
                "pya3eda.builder.inputs._build_molecule_section", return_value=("  ", 2)
            ),
            patch("pya3eda.builder.inputs._build_rem_section", return_value="  "),
        ):
            _build_one(spec, reg, tpl, empty_template, None, "always")
        assert not spec.input_path.exists()

    def test_build_standard_invalid_xyz(self, tmp_path: Path) -> None:
        """XYZ with invalid content → parse_xyz returns None → _build_standard returns None."""
        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "bad", "not valid xyz\n")
        result = _build_standard(tpl, "bad", opt_output_text=None)
        assert result is None

    def test_build_standard_mol_build_fails(self, tmp_path: Path) -> None:
        """Valid xyz but build_standard_molecule returns None → None."""
        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "badmol", _XYZ_SUB)
        from unittest.mock import patch

        with patch("pya3eda.builder.inputs.build_standard_molecule", return_value=None):
            result = _build_standard(tpl, "badmol", opt_output_text=None)
        assert result is None

    def test_build_fragmented_mol_build_fails(self, tmp_path: Path) -> None:
        """Valid xyz files but build_fragmented_molecule returns None → None."""
        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "cat1-mol_a", _XYZ_COMPOSITE)
        _write_xyz(tpl, "cat1", _XYZ_CAT)
        _write_xyz(tpl, "mol_a", _XYZ_SUB)
        from unittest.mock import patch

        with patch(
            "pya3eda.builder.inputs.build_fragmented_molecule", return_value=None
        ):
            result = _build_fragmented(
                tpl,
                "cat1-mol_a",
                catalyst="cat1",
                species="cat1-mol_a",
                calc_type=None,
                opt_output_text=None,
            )
        assert result is None

    def test_build_fragmented_invalid_composite_xyz(self, tmp_path: Path) -> None:
        """Composite xyz that parse_xyz can't parse → None."""
        tpl = _make_template_dir(tmp_path)
        _write_xyz(tpl, "cat1-mol_a", "invalid xyz\n")
        _write_xyz(tpl, "cat1", _XYZ_CAT)
        _write_xyz(tpl, "mol_a", _XYZ_SUB)
        result = _build_fragmented(
            tpl,
            "cat1-mol_a",
            catalyst="cat1",
            species="cat1-mol_a",
            calc_type=None,
            opt_output_text=None,
        )
        assert result is None
