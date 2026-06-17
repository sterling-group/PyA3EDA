"""Tests for qqchem.cli — cluster detection, arg parsing, processing, run/main."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qqchem import cli

CFG: dict = {
    "default_partition": "normal",
    "default_time": "1-00:00:00",
    "mem_per_cpu": 2000,
    "scratch_base_dir": "/scratch/$USER",
    "exclude_nodes": {"normal": ["node99"]},
    "qchem_versions": {
        "6.2.1": {
            "module_loads": ["module load qchem/6.2.1"],
            "qcsetup_file": "",
            "environment": [],
            "mpi_support": True,
            "mpi_modules": ["openmpi4/4.1.6"],
        },
    },
}


@pytest.fixture
def cfg() -> dict:
    return deepcopy(CFG)


def _scontrol_result(stdout: str) -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    return m


# ===================================================================
# detect_cluster
# ===================================================================


class TestDetectCluster:
    def test_env_match(self, monkeypatch: pytest.MonkeyPatch, cfg: dict) -> None:
        monkeypatch.setenv("CLUSTER_NAME", "juno")
        with patch.object(cli, "load_cluster_configs", return_value={"juno": cfg}):
            name, config = cli.detect_cluster()
        assert name == "juno"
        assert config is cfg

    def test_env_no_match_falls_back(
        self, monkeypatch: pytest.MonkeyPatch, cfg: dict
    ) -> None:
        monkeypatch.setenv("CLUSTER_NAME", "ghost")
        with (
            patch.object(cli, "load_cluster_configs", return_value={"juno": cfg}),
            patch.object(cli.subprocess, "run", side_effect=FileNotFoundError()),
        ):
            name, _ = cli.detect_cluster()
        assert name == "juno"  # fell back to first config

    def test_scontrol_match(self, monkeypatch: pytest.MonkeyPatch, cfg: dict) -> None:
        monkeypatch.delenv("CLUSTER_NAME", raising=False)
        result = _scontrol_result("ClusterName    = juno\nOther = x\n")
        with (
            patch.object(cli, "load_cluster_configs", return_value={"juno": cfg}),
            patch.object(cli.subprocess, "run", return_value=result),
        ):
            name, config = cli.detect_cluster()
        assert name == "juno"
        assert config is cfg

    def test_scontrol_name_not_in_configs(
        self, monkeypatch: pytest.MonkeyPatch, cfg: dict
    ) -> None:
        monkeypatch.delenv("CLUSTER_NAME", raising=False)
        result = _scontrol_result("ClusterName = othercluster\n")
        with (
            patch.object(cli, "load_cluster_configs", return_value={"juno": cfg}),
            patch.object(cli.subprocess, "run", return_value=result),
        ):
            name, _ = cli.detect_cluster()
        assert name == "juno"  # fallback

    def test_scontrol_index_error(
        self, monkeypatch: pytest.MonkeyPatch, cfg: dict
    ) -> None:
        monkeypatch.delenv("CLUSTER_NAME", raising=False)
        result = _scontrol_result("ClusterName\n")  # no '=' -> IndexError
        with (
            patch.object(cli, "load_cluster_configs", return_value={"juno": cfg}),
            patch.object(cli.subprocess, "run", return_value=result),
        ):
            name, _ = cli.detect_cluster()
        assert name == "juno"

    def test_scontrol_subprocess_error(
        self, monkeypatch: pytest.MonkeyPatch, cfg: dict
    ) -> None:
        monkeypatch.delenv("CLUSTER_NAME", raising=False)
        with (
            patch.object(cli, "load_cluster_configs", return_value={"juno": cfg}),
            patch.object(
                cli.subprocess, "run", side_effect=cli.subprocess.SubprocessError()
            ),
        ):
            name, _ = cli.detect_cluster()
        assert name == "juno"


# ===================================================================
# build_parser
# ===================================================================


class TestBuildParser:
    def test_defaults_from_config(self, cfg: dict) -> None:
        parser = cli.build_parser(cfg)
        args = parser.parse_args(["job.in"])
        assert args.input_file == "job.in"
        assert args.partition == "normal"
        assert args.walltime == "1-00:00:00"
        assert args.parallel_type == "openmp"

    def test_calls_detect_when_no_config(self, cfg: dict) -> None:
        with patch.object(cli, "detect_cluster", return_value=("juno", cfg)):
            parser = cli.build_parser()
        args = parser.parse_args(["job.in"])
        assert args.partition == "normal"


# ===================================================================
# _process_parallel
# ===================================================================


class TestProcessParallel:
    def test_openmp(self) -> None:
        args = argparse.Namespace(parallel_type="openmp", cpus=2, parallel=None)
        assert cli._process_parallel(args) == (2, 1)

    def test_openmp_default_cpus(self) -> None:
        args = argparse.Namespace(parallel_type="openmp", cpus=None, parallel=None)
        assert cli._process_parallel(args) == (1, 1)

    def test_openmpi(self) -> None:
        args = argparse.Namespace(parallel_type="openmpi", cpus=2, parallel=4)
        assert cli._process_parallel(args) == (2, 4)

    def test_openmpi_without_parallel_exits(self) -> None:
        args = argparse.Namespace(parallel_type="openmpi", cpus=2, parallel=None)
        with pytest.raises(SystemExit):
            cli._process_parallel(args)


# ===================================================================
# _check_memory
# ===================================================================


class TestCheckMemory:
    def test_openmp_within_limit(self) -> None:
        args = argparse.Namespace(parallel_type="openmp")
        cli._check_memory(args, [1000], cpus=2, qchem_processors=1, mem_per_cpu=2000)

    def test_openmpi_total(self) -> None:
        args = argparse.Namespace(parallel_type="openmpi")
        # total = 2 procs * 2 cpus * 2000 = 8000; 5000 is fine
        cli._check_memory(args, [5000], cpus=2, qchem_processors=2, mem_per_cpu=2000)

    def test_exceeds_limit_exits(self) -> None:
        args = argparse.Namespace(parallel_type="openmp")
        with pytest.raises(SystemExit):
            cli._check_memory(
                args, [9999], cpus=1, qchem_processors=1, mem_per_cpu=2000
            )


# ===================================================================
# _process_memory
# ===================================================================


class TestProcessMemory:
    def _args(self, memory: int | None) -> argparse.Namespace:
        return argparse.Namespace(parallel_type="openmp", memory=memory)

    def test_memory_set_and_changed(self, tmp_path: Path) -> None:
        p = tmp_path / "job.in"
        p.write_text("$rem\nmem_total 1000\n$end\n")
        lines = p.read_text().splitlines(keepends=True)
        values, new_lines = cli._process_memory(
            self._args(4000),
            lines,
            cpus=4,
            qchem_processors=1,
            input_path=p,
            mem_per_cpu=2000,
        )
        assert values == [4000]
        assert "mem_total 4000" in p.read_text()  # file rewritten

    def test_memory_set_no_change(self, tmp_path: Path) -> None:
        p = tmp_path / "job.in"
        p.write_text("$rem\nmem_total 4000\n$end\n")
        lines = p.read_text().splitlines(keepends=True)
        values, _ = cli._process_memory(
            self._args(4000),
            lines,
            cpus=4,
            qchem_processors=1,
            input_path=p,
            mem_per_cpu=2000,
        )
        assert values == [4000]

    def test_no_memory_with_values(self, tmp_path: Path) -> None:
        p = tmp_path / "job.in"
        lines = ["$rem\nmem_total 1000\n$end\n"]
        values, _ = cli._process_memory(
            self._args(None),
            lines,
            cpus=4,
            qchem_processors=1,
            input_path=p,
            mem_per_cpu=2000,
        )
        assert values == [1000]

    def test_no_memory_no_values(self, tmp_path: Path) -> None:
        p = tmp_path / "job.in"
        lines = ["$rem\nmethod hf\n$end\n"]
        values, _ = cli._process_memory(
            self._args(None),
            lines,
            cpus=1,
            qchem_processors=1,
            input_path=p,
            mem_per_cpu=2000,
        )
        assert values == []


# ===================================================================
# _resolve_version
# ===================================================================


class TestResolveVersion:
    def _args(self, version: str, qcsetup: str | None = None) -> argparse.Namespace:
        return argparse.Namespace(version=version, qcsetup=qcsetup)

    def test_modqchem_without_qcsetup_exits(self, cfg: dict) -> None:
        with pytest.raises(SystemExit):
            cli._resolve_version(self._args("modqchem"), "juno", cfg)

    def test_modqchem_with_qcsetup(self, cfg: dict) -> None:
        result = cli._resolve_version(
            self._args("modqchem", "/path/setup"), "juno", cfg
        )
        assert result == ([], "/path/setup", [], False, [])

    def test_unknown_version_exits(self, cfg: dict) -> None:
        with pytest.raises(SystemExit):
            cli._resolve_version(self._args("9.9.9"), "juno", cfg)

    def test_valid_version(self, cfg: dict) -> None:
        module_cmds, qcsetup, env, mpi, mpi_mods = cli._resolve_version(
            self._args("6.2.1"), "juno", cfg
        )
        assert module_cmds == ["module load qchem/6.2.1"]
        assert mpi is True
        assert mpi_mods == ["openmpi4/4.1.6"]

    def test_custom_qcsetup_override(self, cfg: dict) -> None:
        _, qcsetup, env, _, _ = cli._resolve_version(
            self._args("6.2.1", "/custom/setup"), "juno", cfg
        )
        assert qcsetup == "/custom/setup"
        assert env == []


# ===================================================================
# run / main
# ===================================================================


class TestRun:
    def _args(self, cfg: dict, argv: list[str]) -> argparse.Namespace:
        return cli.build_parser(cfg).parse_args(argv)

    def test_run_with_cluster_name(self, cfg: dict) -> None:
        args = self._args(cfg, ["job.in"])
        with (
            patch.object(cli, "load_cluster_configs", return_value={"juno": cfg}),
            patch.object(cli, "read_input_file", return_value=["$rem\n", "$end\n"]),
            patch.object(cli, "generate_slurm_script", return_value="job.slurm") as gen,
            patch.object(cli, "submit_job") as sub,
        ):
            cli.run(args, cluster_name="juno")
        gen.assert_called_once()
        sub.assert_called_once()
        # config exclude_nodes for 'normal' partition is merged in
        assert gen.call_args.kwargs["exclude_nodes"] == "node99"

    def test_run_detects_cluster_when_none(self, cfg: dict) -> None:
        args = self._args(cfg, ["job.in"])
        with (
            patch.object(cli, "detect_cluster", return_value=("juno", cfg)),
            patch.object(cli, "read_input_file", return_value=["$rem\n", "$end\n"]),
            patch.object(cli, "generate_slurm_script", return_value="job.slurm"),
            patch.object(cli, "submit_job") as sub,
        ):
            cli.run(args, cluster_name=None)
        sub.assert_called_once()

    def test_run_merges_user_and_config_excludes(self, cfg: dict) -> None:
        args = self._args(cfg, ["job.in", "--exclude", "usernode"])
        with (
            patch.object(cli, "load_cluster_configs", return_value={"juno": cfg}),
            patch.object(cli, "read_input_file", return_value=["$rem\n", "$end\n"]),
            patch.object(cli, "generate_slurm_script", return_value="job.slurm") as gen,
            patch.object(cli, "submit_job"),
        ):
            cli.run(args, cluster_name="juno")
        assert gen.call_args.kwargs["exclude_nodes"] == "usernode,node99"


class TestMain:
    def test_main_dispatches(self, cfg: dict) -> None:
        with (
            patch.object(cli, "detect_cluster", return_value=("juno", cfg)),
            patch.object(cli, "run") as run,
        ):
            cli.main(["job.in"])
        run.assert_called_once()

    def test_dunder_main(self, cfg: dict) -> None:
        """Importing qqchem.__main__ runs main() → covers __main__.py."""
        import importlib

        with (
            patch.object(cli, "detect_cluster", return_value=("juno", cfg)),
            patch.object(cli, "build_parser") as bp,
            patch.object(cli, "run"),
        ):
            bp.return_value.parse_args.return_value = argparse.Namespace()
            import qqchem.__main__

            importlib.reload(qqchem.__main__)
