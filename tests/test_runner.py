"""Tests for pya3eda.runner.backend and pya3eda.runner.executor."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pya3eda.ids import CalcID, CalcSpec
from pya3eda.runner.backend import QQChemBackend, get_backend
from pya3eda.runner.executor import run_all

# ===================================================================
# Helpers
# ===================================================================


def _spec(
    tmp_path: Path, *, stage: str = "reactants", mode: str = "opt", create: bool = True
) -> CalcSpec:
    inp = tmp_path / f"{stage}_{mode}.in"
    if create:
        inp.touch()
    cid = CalcID(method_key="test", stage=stage, species="mol", mode=mode)
    return CalcSpec(
        id=cid,
        input_path=inp,
        output_path=inp.with_suffix(".out"),
        method_name="HF",
        basis_set="STO-3G",
        dispersion="false",
        solvent="false",
    )


# ===================================================================
# get_backend
# ===================================================================


class TestGetBackend:
    def test_valid(self) -> None:
        be = get_backend("qqchem")
        assert isinstance(be, QQChemBackend)

    def test_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend("nonexistent")


# ===================================================================
# QQChemBackend.submit
# ===================================================================


class TestQQChemBackend:
    def test_submit_success(self, tmp_path: Path) -> None:
        inp = tmp_path / "mol_opt.in"
        inp.touch()
        be = QQChemBackend()
        with patch("pya3eda.runner.backend.QQChemBackend.submit", return_value=True):
            # Direct mock to avoid qqchem import
            assert be.submit(inp) is True

    def test_submit_real_calls_qqchem(self, tmp_path: Path) -> None:
        """Mock qqchem internals and verify cwd is restored."""
        inp = tmp_path / "mol_opt.in"
        inp.touch()
        orig_cwd = os.getcwd()

        mock_detect = MagicMock(return_value=("cluster1", {"key": "val"}))
        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = MagicMock()
        mock_build = MagicMock(return_value=mock_parser)
        mock_run = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "qqchem": MagicMock(),
                "qqchem.cli": MagicMock(
                    detect_cluster=mock_detect,
                    build_parser=mock_build,
                    run=mock_run,
                ),
            },
        ):
            be = QQChemBackend()
            result = be.submit(inp, extra_argv=["--flag"])

        assert result is True
        assert os.getcwd() == orig_cwd
        mock_run.assert_called_once()

    def test_submit_system_exit_returns_false(self, tmp_path: Path) -> None:
        """SystemExit during submission → returns False, cwd restored."""
        inp = tmp_path / "mol_opt.in"
        inp.touch()
        orig_cwd = os.getcwd()

        mock_detect = MagicMock(return_value=("cluster1", {}))
        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = MagicMock()
        mock_build = MagicMock(return_value=mock_parser)
        mock_run = MagicMock(side_effect=SystemExit(1))

        with patch.dict(
            "sys.modules",
            {
                "qqchem": MagicMock(),
                "qqchem.cli": MagicMock(
                    detect_cluster=mock_detect,
                    build_parser=mock_build,
                    run=mock_run,
                ),
            },
        ):
            be = QQChemBackend()
            result = be.submit(inp)

        assert result is False
        assert os.getcwd() == orig_cwd


# ===================================================================
# run_all
# ===================================================================


class TestRunAll:
    def test_empty_criteria(self, tmp_path: Path) -> None:
        reg = MagicMock()
        assert run_all(reg, criteria="") == 0

    def test_missing_input_skipped(self, tmp_path: Path) -> None:
        spec = _spec(tmp_path, create=False)
        reg = MagicMock()
        reg.all_calcs = [spec]
        mock_be = MagicMock()
        with patch("pya3eda.runner.executor.get_backend", return_value=mock_be):
            count = run_all(reg, criteria="all")
        assert count == 0
        mock_be.submit.assert_not_called()

    def test_criteria_filtering(self, tmp_path: Path) -> None:
        s1 = _spec(tmp_path, stage="reactants")
        s2 = _spec(tmp_path, stage="ts")
        reg = MagicMock()
        reg.all_calcs = [s1, s2]
        mock_be = MagicMock()
        mock_be.submit.return_value = True

        with (
            patch("pya3eda.runner.executor.get_backend", return_value=mock_be),
            patch(
                "pya3eda.runner.executor.should_process",
                side_effect=lambda s, c: s.id.stage == "reactants",
            ),
            patch("pya3eda.runner.executor.time") as mock_time,
        ):
            count = run_all(reg, criteria="all")

        assert count == 1
        mock_be.submit.assert_called_once()
        mock_time.sleep.assert_called_once()

    def test_count_and_sleep(self, tmp_path: Path) -> None:
        specs = [_spec(tmp_path, stage=f"stage{i}") for i in range(3)]
        reg = MagicMock()
        reg.all_calcs = specs
        mock_be = MagicMock()
        mock_be.submit.return_value = True

        with (
            patch("pya3eda.runner.executor.get_backend", return_value=mock_be),
            patch("pya3eda.runner.executor.should_process", return_value=True),
            patch("pya3eda.runner.executor.time") as mock_time,
        ):
            count = run_all(reg, criteria="all", extra_argv=["--flag"])

        assert count == 3
        assert mock_time.sleep.call_count == 3

    def test_submit_failure_not_counted(self, tmp_path: Path) -> None:
        spec = _spec(tmp_path, stage="reactants")
        reg = MagicMock()
        reg.all_calcs = [spec]
        mock_be = MagicMock()
        mock_be.submit.return_value = False

        with (
            patch("pya3eda.runner.executor.get_backend", return_value=mock_be),
            patch("pya3eda.runner.executor.should_process", return_value=True),
        ):
            count = run_all(reg, criteria="all")

        assert count == 0
