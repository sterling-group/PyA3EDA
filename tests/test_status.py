"""Tests for pya3eda.status.checker — status detection and validation."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

from pya3eda.ids import CalcID, CalcSpec
from pya3eda.status import checker as checker_module
from pya3eda.status.checker import (
    Status,
    _interleave_opt_sp,
    _validate_opt,
    check_all,
    get_status,
    should_process,
)


def test_report_logger_idempotent_on_reload() -> None:
    """Re-importing the module leaves the report handler set up exactly once."""
    before = len(checker_module._report.handlers)
    importlib.reload(checker_module)
    assert len(checker_module._report.handlers) == before


# ===================================================================
# Helpers
# ===================================================================


def _make_spec(
    *,
    stage: str = "reactants",
    mode: str = "opt",
    catalyst: str | None = None,
    calc_type: str | None = None,
    input_path: Path = Path("/fake/input_opt.in"),
    output_path: Path | None = None,
) -> CalcSpec:
    cid = CalcID(
        method_key="test",
        stage=stage,
        species="mol",
        mode=mode,
        catalyst=catalyst,
        calc_type=calc_type,
    )
    return CalcSpec(
        id=cid,
        input_path=input_path,
        output_path=output_path or input_path.with_suffix(".out"),
        method_name="HF",
        basis_set="STO-3G",
        dispersion="false",
        solvent="false",
    )


# ===================================================================
# _validate_opt
# ===================================================================


class TestValidateOpt:
    def test_min_with_zero_imag_ok(self) -> None:
        text = "**  OPTIMIZATION CONVERGED  **\nThis Molecule has  0 Imaginary Frequencies\n"
        spec = _make_spec(stage="reactants")
        status, _ = _validate_opt(text, spec)
        assert status is None  # No validation error

    def test_ts_with_one_imag_ok(self) -> None:
        text = "** TRANSITION STATE CONVERGED  **\nThis Molecule has  1 Imaginary Frequencies\n"
        spec = _make_spec(stage="ts")
        status, _ = _validate_opt(text, spec)
        assert status is None

    def test_min_with_imag_fails(self) -> None:
        text = "**  OPTIMIZATION CONVERGED  **\nThis Molecule has  1 Imaginary Frequencies\n"
        spec = _make_spec(stage="reactants")
        status, detail = _validate_opt(text, spec)
        assert status == Status.VALIDATION
        assert "Imag: 1" in detail

    def test_ts_with_wrong_imag_fails(self) -> None:
        text = "** TRANSITION STATE CONVERGED  **\nThis Molecule has  2 Imaginary Frequencies\n"
        spec = _make_spec(stage="ts")
        status, detail = _validate_opt(text, spec)
        assert status == Status.VALIDATION
        assert "Imag: 2" in detail


# ===================================================================
# Status enum
# ===================================================================


class TestStatusEnum:
    def test_all_members(self) -> None:
        members = {s.value for s in Status}
        assert "SUCCESSFUL" in members
        assert "CRASH" in members
        assert "running" in members
        assert "terminated" in members
        assert "nofile" in members
        assert "empty" in members
        assert "absent" in members
        assert "VALIDATION" in members


# ===================================================================
# should_process
# ===================================================================


class TestShouldProcess:
    def test_all_criteria(self, tmp_path: Path) -> None:
        spec = _make_spec(input_path=tmp_path / "mol_opt.in")
        assert should_process(spec, "all") is True

    def test_nofile_criteria_no_output(self, tmp_path: Path) -> None:
        spec = _make_spec(input_path=tmp_path / "mol_opt.in")
        # output doesn't exist → should process
        assert should_process(spec, "nofile") is True

    def test_nofile_criteria_output_exists(self, tmp_path: Path) -> None:
        inp = tmp_path / "mol_opt.in"
        out = tmp_path / "mol_opt.out"
        inp.touch()
        out.write_text("some content")
        spec = _make_spec(input_path=inp, output_path=out)
        assert should_process(spec, "nofile") is False

    def test_criteria_matches_status(self, tmp_path: Path) -> None:
        inp = tmp_path / "mol_opt.in"
        inp.touch()
        spec = _make_spec(input_path=inp)
        with patch("pya3eda.status.checker.get_status", return_value=(Status.CRASH, "err")):
            assert should_process(spec, "CRASH") is True
            assert should_process(spec, "SUCCESSFUL") is False


# ===================================================================
# get_status
# ===================================================================


class TestGetStatus:
    def test_absent_input(self, tmp_path: Path) -> None:
        spec = _make_spec(input_path=tmp_path / "missing.in")
        status, _ = get_status(spec)
        assert status == Status.ABSENT

    def test_nofile_output(self, tmp_path: Path) -> None:
        inp = tmp_path / "mol_opt.in"
        inp.touch()
        spec = _make_spec(input_path=inp)
        status, _ = get_status(spec)
        assert status == Status.NOFILE

    def test_successful_basic(self, tmp_path: Path) -> None:
        inp = tmp_path / "mol_opt.in"
        out = tmp_path / "mol_opt.out"
        inp.touch()
        out.write_text(
            "Running on machine\nThank you very much for using Q-Chem.\n"
            "Total job time: 100.00s(wall)\n"
        )
        spec = _make_spec(input_path=inp, output_path=out, mode="sp")
        status, _ = get_status(spec)
        assert status == Status.SUCCESSFUL

    def test_slurm_sentinel_running(self, tmp_path: Path) -> None:
        inp = tmp_path / "mol_opt.in"
        inp.touch()
        # Create a SLURM sentinel file
        sentinel = tmp_path / "mol_opt.in_12345.67890"
        sentinel.touch()
        spec = _make_spec(input_path=inp)
        status, _ = get_status(spec)
        assert status == Status.RUNNING

    def test_unknown_status_becomes_crash(self, tmp_path: Path) -> None:
        inp = tmp_path / "mol_opt.in"
        inp.touch()
        out = tmp_path / "mol_opt.out"
        out.write_text("some unknown content without any patterns")
        spec = _make_spec(input_path=inp, output_path=out)
        status, _ = get_status(spec)
        assert status == Status.CRASH

    def test_opt_validation_triggers(self, tmp_path: Path) -> None:
        """Successful OPT with wrong imaginary freq → VALIDATION."""
        inp = tmp_path / "mol_opt.in"
        out = tmp_path / "mol_opt.out"
        inp.touch()
        out.write_text(
            "Running on machine\nThank you very much for using Q-Chem.\n"
            "Total job time: 100.00s(wall)\n"
            "**  OPTIMIZATION CONVERGED  **\n"
            "This Molecule has  2 Imaginary Frequencies\n"
        )
        spec = _make_spec(input_path=inp, output_path=out, mode="opt", stage="reactants")
        status, _ = get_status(spec)
        assert status == Status.VALIDATION

    def test_opt_validation_ok_skipped_for_sp(self, tmp_path: Path) -> None:
        """SP mode doesn't trigger OPT validation even if content has freq info."""
        inp = tmp_path / "mol_opt.in"
        out = tmp_path / "mol_opt.out"
        inp.touch()
        out.write_text(
            "Running on machine\nThank you very much for using Q-Chem.\n"
            "Total job time: 100.00s(wall)\n"
            "**  OPTIMIZATION CONVERGED  **\n"
            "This Molecule has  2 Imaginary Frequencies\n"
        )
        spec = _make_spec(input_path=inp, output_path=out, mode="sp")
        status, _ = get_status(spec)
        assert status == Status.SUCCESSFUL

    def test_err_file_cancelled(self, tmp_path: Path) -> None:
        inp = tmp_path / "mol_opt.in"
        out = tmp_path / "mol_opt.out"
        err = tmp_path / "mol_opt.err"
        inp.touch()
        out.touch()
        err.write_text("CANCELLED AT 2024-01-01")
        spec = _make_spec(input_path=inp, output_path=out)
        status, _ = get_status(spec)
        assert status == Status.TERMINATED

    def test_err_file_crash(self, tmp_path: Path) -> None:
        inp = tmp_path / "mol_opt.in"
        out = tmp_path / "mol_opt.out"
        err = tmp_path / "mol_opt.err"
        inp.touch()
        out.touch()
        err.write_text("Error in Q-Chem run")
        spec = _make_spec(input_path=inp, output_path=out)
        status, _ = get_status(spec)
        assert status == Status.CRASH


# ===================================================================
# _interleave_opt_sp
# ===================================================================


class TestInterleaveOptSp:
    def test_opt_followed_by_sp(self) -> None:
        opt = _make_spec(stage="reactants", mode="opt")
        sp = _make_spec(stage="reactants", mode="sp")
        result = _interleave_opt_sp([sp, opt])
        assert result[0].id.mode == "opt"
        assert result[1].id.mode == "sp"

    def test_multi_stage(self) -> None:
        r_opt = _make_spec(stage="reactants", mode="opt")
        r_sp = _make_spec(stage="reactants", mode="sp")
        t_opt = _make_spec(stage="ts", mode="opt")
        t_sp = _make_spec(stage="ts", mode="sp")
        result = _interleave_opt_sp([r_sp, t_sp, r_opt, t_opt])
        modes = [(s.id.stage, s.id.mode) for s in result]
        assert modes == [
            ("reactants", "opt"),
            ("reactants", "sp"),
            ("ts", "opt"),
            ("ts", "sp"),
        ]

    def test_orphan_sp(self) -> None:
        """SP without matching OPT → appended at end."""
        sp = _make_spec(stage="products", mode="sp")
        opt = _make_spec(stage="reactants", mode="opt")
        result = _interleave_opt_sp([sp, opt])
        assert result[0].id.stage == "reactants"
        assert result[0].id.mode == "opt"
        assert result[1].id.stage == "products"
        assert result[1].id.mode == "sp"


# ===================================================================
# check_all
# ===================================================================


class TestCheckAll:
    def test_grouped_report(self, tmp_path: Path) -> None:
        inp = tmp_path / "mol_opt.in"
        out = tmp_path / "mol_opt.out"
        inp.touch()
        out.write_text(
            "Running on machine\nThank you very much for using Q-Chem.\n"
            "Total job time: 100.00s(wall)\n"
        )
        spec = _make_spec(input_path=inp, output_path=out, mode="sp")

        reg = MagicMock()
        reg.base_dir = tmp_path
        reg.method_keys = ["test"]
        reg.by_method.return_value = [spec]

        # Should not raise
        check_all(reg)
        reg.by_method.assert_called_once_with("test")

    def test_empty_method(self) -> None:
        reg = MagicMock()
        reg.base_dir = Path("/tmp")
        reg.method_keys = ["empty"]
        reg.by_method.return_value = []
        # Should silently skip
        check_all(reg)


# ===================================================================
# _validate_opt — additional edge cases
# ===================================================================


class TestValidateOptExtra:
    def test_not_converged_no_freq(self) -> None:
        """Non-converged, no freq → no validation issue."""
        text = "some output text without convergence or freq info"
        spec = _make_spec(stage="ts")
        status, _ = _validate_opt(text, spec)
        assert status is None

    def test_ts_with_no_imag(self) -> None:
        """TS with converged but imag=0 → VALIDATION (expects 1)."""
        text = "** TRANSITION STATE CONVERGED  **\nThis Molecule has  0 Imaginary Frequencies\n"
        spec = _make_spec(stage="ts")
        status, detail = _validate_opt(text, spec)
        assert status == Status.VALIDATION
        assert "Imag: 0" in detail

    def test_non_ts_with_no_imag_ok(self) -> None:
        """Non-TS converged with 0 imag → OK."""
        text = "**  OPTIMIZATION CONVERGED  **\nThis Molecule has  0 Imaginary Frequencies\n"
        spec = _make_spec(stage="reactants")
        status, _ = _validate_opt(text, spec)
        assert status is None


# ===================================================================
# get_status — ValueError branch (unknown raw status → CRASH)
# ===================================================================


class TestGetStatusValueError:
    def test_unknown_raw_status_becomes_crash(self, tmp_path: Path) -> None:
        """parse_status returning an unknown string → CRASH via ValueError."""
        inp = tmp_path / "mol_opt.in"
        inp.touch()
        with patch(
            "pya3eda.status.checker.parse_status",
            return_value=("SOME_UNKNOWN_STATUS", "detail"),
        ):
            spec = _make_spec(input_path=inp, mode="sp")
            status, _ = get_status(spec)
            assert status == Status.CRASH


# ===================================================================
# _rel_display — ValueError branch (path not relative to base_dir)
# ===================================================================


class TestCheckAllRelDisplay:
    def test_non_relative_path(self, tmp_path: Path) -> None:
        """Input path not under base_dir → uses full path for display."""
        inp = Path("/other/dir/mol_opt.in")
        out = Path("/other/dir/mol_opt.out")
        spec = _make_spec(input_path=inp, output_path=out, mode="sp")

        reg = MagicMock()
        reg.base_dir = tmp_path  # base_dir != /other/dir
        reg.method_keys = ["test"]
        reg.by_method.return_value = [spec]

        with patch(
            "pya3eda.status.checker.get_status",
            return_value=(Status.NOFILE, "not found"),
        ):
            check_all(reg)
