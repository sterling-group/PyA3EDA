"""Tests for pya3eda.cli — CLI argument parsing and dispatch.

All tests are self-contained using synthetic YAML config written to tmp_path.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tests.synthetic_outputs import SAMPLE_CONFIG_YAML


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """Write a synthetic config to a temp file and return the path."""
    p = tmp_path / "new.yaml"
    p.write_text(SAMPLE_CONFIG_YAML)
    return p


class TestCLIParsing:
    """Test argument parsing without actually running subcommands."""

    def test_status_is_default(self, config_path: Path) -> None:
        """When no subcommand given, default to 'status'."""
        with patch("pya3eda.cli._cmd_status") as mock_status:
            from pya3eda.cli import main

            main([str(config_path)])
            mock_status.assert_called_once()

    def test_build_subcommand(self, config_path: Path) -> None:
        with patch("pya3eda.cli._cmd_build") as mock_build:
            from pya3eda.cli import main

            main([str(config_path), "build"])
            mock_build.assert_called_once()

    def test_extract_subcommand(self, config_path: Path) -> None:
        with patch("pya3eda.cli._cmd_extract") as mock_extract:
            from pya3eda.cli import main

            main([str(config_path), "extract"])
            mock_extract.assert_called_once()

    def test_run_subcommand_with_backend(self, config_path: Path) -> None:
        with patch("pya3eda.cli._cmd_run") as mock_run:
            from pya3eda.cli import main

            main([str(config_path), "run", "--backend", "qqchem"])
            mock_run.assert_called_once()
            args = mock_run.call_args[0][1]
            assert args.backend == "qqchem"

    def test_run_forwards_extra_argv(self, config_path: Path) -> None:
        with patch("pya3eda.cli._cmd_run") as mock_run:
            from pya3eda.cli import main

            main([str(config_path), "run", "--extra-flag", "val"])
            args = mock_run.call_args[0][1]
            assert "--extra-flag" in args.extra_argv or "val" in args.extra_argv

    def test_unknown_args_non_run_raises(self, config_path: Path) -> None:
        """Unrecognised args for non-run subcommand → SystemExit."""
        from pya3eda.cli import main

        with pytest.raises(SystemExit):
            main([str(config_path), "build", "--bad-flag"])


class TestCLIConfigLoading:
    """Test that the CLI properly loads config and creates registry."""

    def test_missing_config_raises(self) -> None:
        from pya3eda.cli import main

        with pytest.raises((FileNotFoundError, SystemExit)):
            main(["/nonexistent/config.yaml", "status"])


# ===================================================================
# Subcommand handler tests (lines 85-132)
# ===================================================================


class TestCmdBuild:
    def test_build_calls_build_all(self, config_path: Path) -> None:
        with patch("pya3eda.builder.inputs.build_all") as mock_ba:
            from pya3eda.cli import main

            main([str(config_path), "build", "--overwrite"])
            mock_ba.assert_called_once()
            _, kwargs = mock_ba.call_args
            assert kwargs["overwrite"] == "all"

    def test_build_sp_strategy(self, config_path: Path) -> None:
        with patch("pya3eda.builder.inputs.build_all") as mock_ba:
            from pya3eda.cli import main

            main([str(config_path), "build", "--sp-strategy", "always"])
            _, kwargs = mock_ba.call_args
            assert kwargs["sp_strategy"] == "always"


class TestCmdRun:
    def test_run_calls_run_all(self, config_path: Path) -> None:
        with patch("pya3eda.runner.executor.run_all") as mock_ra:
            from pya3eda.cli import main

            main([str(config_path), "run", "--criteria", "CRASH"])
            mock_ra.assert_called_once()
            _, kwargs = mock_ra.call_args
            assert kwargs["criteria"] == "CRASH"
            assert kwargs["backend"] == "qqchem"


class TestCmdExtract:
    def test_extract_full_pipeline(self, config_path: Path) -> None:
        with (
            patch("pya3eda.extractor.data.extract_all", return_value={}) as m_ea,
            patch("pya3eda.extractor.stages.build_profiles", return_value={}) as m_bp,
            patch("pya3eda.extractor.barriers.compute_delta_delta", return_value={}) as m_dd,
            patch("pya3eda.exporter.results.export_all") as m_exp,
            patch("pya3eda.plotter.profile.plot_all_profiles") as m_pp,
            patch("pya3eda.plotter.contributions.plot_delta_delta_barplots") as m_pb,
        ):
            from pya3eda.cli import main

            main([str(config_path), "extract"])
            m_ea.assert_called_once()
            m_bp.assert_called_once()
            m_dd.assert_called_once()
            m_exp.assert_called_once()
            m_pp.assert_called_once()
            m_pb.assert_called_once()

    def test_extract_no_plots(self, config_path: Path) -> None:
        with (
            patch("pya3eda.extractor.data.extract_all", return_value={}),
            patch("pya3eda.extractor.stages.build_profiles", return_value={}),
            patch("pya3eda.extractor.barriers.compute_delta_delta", return_value={}),
            patch("pya3eda.exporter.results.export_all"),
            patch("pya3eda.plotter.profile.plot_all_profiles") as m_pp,
            patch("pya3eda.plotter.contributions.plot_delta_delta_barplots") as m_pb,
        ):
            from pya3eda.cli import main

            main([str(config_path), "extract", "--no-plots"])
            m_pp.assert_not_called()
            m_pb.assert_not_called()


class TestCmdStatus:
    def test_status_calls_check_all(self, config_path: Path) -> None:
        """Verify _cmd_status actually calls check_all (covers L109-111)."""
        with patch("pya3eda.status.checker.check_all") as mock_ca:
            from pya3eda.cli import main

            main([str(config_path), "status"])
            mock_ca.assert_called_once()


class TestDunderMain:
    def test_main_module(self) -> None:
        """Importing __main__ calls main() → covers __main__.py."""
        with patch("pya3eda.cli.main") as mock_main:
            import importlib

            import pya3eda.__main__

            mock_main.reset_mock()
            importlib.reload(pya3eda.__main__)
            mock_main.assert_called_once()
