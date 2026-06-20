"""Tests for pya3eda.cli — the Typer command-line interface.

Driven via ``typer.testing.CliRunner``; the heavy command bodies are patched at
their source modules (the commands import them lazily) so only parsing/dispatch
and the error→exit-code translation are exercised.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pya3eda.cli import app
from tests.synthetic_outputs import SAMPLE_CONFIG_YAML

runner = CliRunner()


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """Write a synthetic config to a temp file and return the path."""
    p = tmp_path / "new.yaml"
    p.write_text(SAMPLE_CONFIG_YAML)
    return p


class TestParsingAndDispatch:
    def test_no_args_shows_help(self) -> None:
        """Bare `pya3eda` prints help listing the commands (Click no-args convention)."""
        result = runner.invoke(app, [])
        assert result.exit_code == 2  # no_args_is_help exits like a usage error
        assert "build" in result.output and "pipeline" in result.output

    def test_build_calls_build_all(self, config_path: Path) -> None:
        with patch("pya3eda.builder.inputs.build_all") as mock_ba:
            result = runner.invoke(app, ["build", str(config_path), "--overwrite"])
        assert result.exit_code == 0
        assert mock_ba.call_args.kwargs["overwrite"] == "all"

    def test_build_sp_strategy(self, config_path: Path) -> None:
        with patch("pya3eda.builder.inputs.build_all") as mock_ba:
            result = runner.invoke(app, ["build", str(config_path), "--sp-strategy", "always"])
        assert result.exit_code == 0
        assert mock_ba.call_args.kwargs["sp_strategy"] == "always"

    def test_run_calls_run_all(self, config_path: Path) -> None:
        with patch("pya3eda.runner.executor.run_all") as mock_ra:
            result = runner.invoke(app, ["run", str(config_path), "CRASH"])
        assert result.exit_code == 0
        kwargs = mock_ra.call_args.kwargs
        assert kwargs["criteria"] == "CRASH"
        assert kwargs["backend"] == "auto"
        assert kwargs["wait"] is False
        assert kwargs["max_cores"] is None
        assert kwargs["options"].cpus == 1

    def test_run_parses_options(self, config_path: Path) -> None:
        with patch("pya3eda.runner.executor.run_all") as mock_ra:
            result = runner.invoke(
                app,
                ["run", str(config_path), "CRASH", "--cpus", "4", "--wait", "--max-cores", "8"],
            )
        assert result.exit_code == 0
        kwargs = mock_ra.call_args.kwargs
        assert kwargs["wait"] is True
        assert kwargs["max_cores"] == 8
        assert kwargs["options"].cpus == 4

    def test_run_with_backend(self, config_path: Path) -> None:
        with patch("pya3eda.runner.executor.run_all") as mock_ra:
            result = runner.invoke(app, ["run", str(config_path), "--backend", "local"])
        assert result.exit_code == 0
        assert mock_ra.call_args.kwargs["backend"] == "local"

    def test_pipeline_calls_run_pipeline(self, config_path: Path) -> None:
        with patch("pya3eda.pipeline.run_pipeline") as mock_rp:
            result = runner.invoke(
                app, ["pipeline", str(config_path), "--max-cores", "2", "--cpus", "4", "--no-plots"]
            )
        assert result.exit_code == 0
        kwargs = mock_rp.call_args.kwargs
        assert kwargs["max_cores"] == 2
        assert kwargs["plots"] is False
        assert kwargs["options"].cpus == 4

    def test_status_calls_check_all(self, config_path: Path) -> None:
        with patch("pya3eda.status.checker.check_all") as mock_ca:
            result = runner.invoke(app, ["status", str(config_path)])
        assert result.exit_code == 0
        mock_ca.assert_called_once()

    def test_unknown_flag_errors(self, config_path: Path) -> None:
        result = runner.invoke(app, ["build", str(config_path), "--bad-flag"])
        assert result.exit_code != 0


class TestExtract:
    def test_extract_full_pipeline(self, config_path: Path) -> None:
        with (
            patch("pya3eda.extractor.data.extract_all", return_value={}),
            patch("pya3eda.extractor.stages.build_profiles", return_value={}),
            patch("pya3eda.extractor.barriers.compute_delta_delta", return_value=[]),
            patch("pya3eda.exporter.results.export_all") as m_exp,
            patch("pya3eda.plotter.profile.plot_all_profiles") as m_pp,
            patch("pya3eda.plotter.contributions.plot_delta_delta_barplots") as m_pb,
        ):
            result = runner.invoke(app, ["extract", str(config_path)])
        assert result.exit_code == 0
        m_exp.assert_called_once()
        m_pp.assert_called_once()
        m_pb.assert_called_once()

    def test_extract_no_plots(self, config_path: Path) -> None:
        with (
            patch("pya3eda.extractor.data.extract_all", return_value={}),
            patch("pya3eda.extractor.stages.build_profiles", return_value={}),
            patch("pya3eda.extractor.barriers.compute_delta_delta", return_value=[]),
            patch("pya3eda.exporter.results.export_all"),
            patch("pya3eda.plotter.profile.plot_all_profiles") as m_pp,
            patch("pya3eda.plotter.contributions.plot_delta_delta_barplots") as m_pb,
        ):
            result = runner.invoke(app, ["extract", str(config_path), "--no-plots"])
        assert result.exit_code == 0
        m_pp.assert_not_called()
        m_pb.assert_not_called()


class TestErrorTranslation:
    def test_missing_config_rejected(self) -> None:
        """A non-existent config is rejected by the argument validator."""
        result = runner.invoke(app, ["status", "/nonexistent/config.yaml"])
        assert result.exit_code != 0

    def test_invalid_config_maps_to_exit_code(self, tmp_path: Path) -> None:
        """An existing-but-invalid config → ConfigError → its exit code (2)."""
        from pya3eda.errors import ConfigError

        bad = tmp_path / "bad.yaml"
        bad.write_text("- just a list\n")
        result = runner.invoke(app, ["status", str(bad)])
        assert result.exit_code == ConfigError.exit_code


class TestDunderMain:
    def test_main_runs_app(self) -> None:
        """The console-script entry point invokes the Typer app."""
        with patch("pya3eda.cli.app") as mock_app:
            from pya3eda.cli import main

            main()
            mock_app.assert_called_once()

    def test_main_module(self) -> None:
        """Importing __main__ calls main() → covers __main__.py."""
        with patch("pya3eda.cli.main") as mock_main:
            import importlib

            import pya3eda.__main__

            mock_main.reset_mock()
            importlib.reload(pya3eda.__main__)
            mock_main.assert_called_once()
