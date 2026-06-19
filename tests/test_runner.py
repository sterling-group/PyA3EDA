"""Tests for pya3eda.runner.executor (run_all + job-preparation helpers)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pya3eda.ids import CalcID, CalcSpec
from pya3eda.runner import executor
from pya3eda.runner.clusters import ClusterConfig, QChemVersion
from pya3eda.runner.executor import (
    RunOptions,
    _cores,
    _exclude_nodes,
    _resolve_parallel,
    _resolve_version,
    run_all,
)

# ===================================================================
# Fixtures / helpers
# ===================================================================


def _cluster() -> ClusterConfig:
    return ClusterConfig(
        default_partition="sterling",
        mem_per_cpu=4000,
        default_time="7-00:00:00",
        scratch_base_dir="/scratch/g2/$USER",
        exclude_nodes={"sterling": ["g-07-02"]},
        qchem_versions={
            "6.2.1": QChemVersion(
                module_loads=["module load qchem/6.2.1"],
                qcsetup_file="",
                mpi_support=True,
                mpi_modules=["openmpi4"],
            )
        },
    )


def _spec(
    tmp_path: Path, *, stage: str = "reactants", content: str = "$rem\n$end\n", create: bool = True
) -> CalcSpec:
    inp = tmp_path / f"{stage}_opt.in"
    if create:
        inp.write_text(content)
    cid = CalcID(method_key="m", stage=stage, species="mol", mode="opt")
    return CalcSpec(
        id=cid,
        input_path=inp,
        output_path=inp.with_suffix(".out"),
        method_name="HF",
        basis_set="STO-3G",
        dispersion="false",
        solvent="false",
    )


class FakeBackend:
    """Minimal ExecutionBackend stand-in that records submissions."""

    def __init__(self, name: str = "slurm") -> None:
        self.name = name
        self.submitted: list[Path] = []

    def available(self) -> bool:
        return True

    def submit(self, script_path: Path, *, log_path: Path | None = None) -> str:
        self.submitted.append(script_path)
        return f"job-{len(self.submitted)}"

    def is_finished(self, job_id: str) -> bool:
        return True


# ===================================================================
# run_all
# ===================================================================


class TestRunAll:
    def test_empty_criteria(self) -> None:
        assert run_all(MagicMock(), criteria="") == 0

    def test_missing_input_skipped(self, tmp_path: Path) -> None:
        reg = MagicMock(all_calcs=[_spec(tmp_path, create=False)])
        be = FakeBackend("slurm")
        with (
            patch.object(executor, "detect_cluster", return_value=("g2", _cluster())),
            patch.object(executor, "get_backend", return_value=be),
        ):
            assert run_all(reg, criteria="all") == 0
        assert be.submitted == []

    def test_criteria_filtering(self, tmp_path: Path) -> None:
        s1 = _spec(tmp_path, stage="reactants")
        s2 = _spec(tmp_path, stage="ts")
        reg = MagicMock(all_calcs=[s1, s2])
        be = FakeBackend("slurm")
        with (
            patch.object(executor, "detect_cluster", return_value=("g2", _cluster())),
            patch.object(executor, "get_backend", return_value=be),
            patch.object(executor, "should_process", side_effect=lambda s, c: s.id.stage == "ts"),
        ):
            assert run_all(reg, criteria="all") == 1
        assert len(be.submitted) == 1

    def test_slurm_fire_and_forget_no_throttle(self, tmp_path: Path) -> None:
        reg = MagicMock(all_calcs=[_spec(tmp_path)])
        be = FakeBackend("slurm")
        with (
            patch.object(executor, "detect_cluster", return_value=("g2", _cluster())),
            patch.object(executor, "get_backend", return_value=be),
            patch.object(executor, "should_process", return_value=True),
            patch("pya3eda.runner.throttle.Throttler") as throttler_cls,
        ):
            assert run_all(reg, criteria="all", wait=False) == 1
        throttler_cls.assert_not_called()  # fire-and-forget → no throttler

    def test_local_backend_throttles_and_waits(self, tmp_path: Path) -> None:
        reg = MagicMock(all_calcs=[_spec(tmp_path)])
        be = FakeBackend("local")
        with (
            patch.object(executor, "detect_cluster", return_value=("g2", _cluster())),
            patch.object(executor, "get_backend", return_value=be),
            patch.object(executor, "should_process", return_value=True),
        ):
            assert run_all(reg, criteria="all", max_cores=4) == 1
        assert (tmp_path / "reactants_opt.slurm").exists()  # local script written

    def test_slurm_wait_uses_throttler(self, tmp_path: Path) -> None:
        reg = MagicMock(all_calcs=[_spec(tmp_path)])
        be = FakeBackend("slurm")
        with (
            patch.object(executor, "detect_cluster", return_value=("g2", _cluster())),
            patch.object(executor, "get_backend", return_value=be),
            patch.object(executor, "should_process", return_value=True),
        ):
            assert run_all(reg, criteria="all", wait=True, max_cores=8) == 1

    def test_memory_overflow_skips_job(self, tmp_path: Path) -> None:
        # mem_total far exceeds the 1-cpu * 4000 MB budget → job skipped
        spec = _spec(tmp_path, content="$rem\nmem_total 999999\n$end\n")
        reg = MagicMock(all_calcs=[spec])
        be = FakeBackend("slurm")
        with (
            patch.object(executor, "detect_cluster", return_value=("g2", _cluster())),
            patch.object(executor, "get_backend", return_value=be),
            patch.object(executor, "should_process", return_value=True),
        ):
            assert run_all(reg, criteria="all") == 0
        assert be.submitted == []

    def test_max_cores_defaults_to_cpu_count(self, tmp_path: Path) -> None:
        reg = MagicMock(all_calcs=[_spec(tmp_path)])
        be = FakeBackend("local")
        with (
            patch.object(executor, "detect_cluster", return_value=("g2", _cluster())),
            patch.object(executor, "get_backend", return_value=be),
            patch.object(executor, "should_process", return_value=True),
            patch.object(
                executor.os, "cpu_count", return_value=None
            ),  # exercise the `or 1` fallback
        ):
            assert run_all(reg, criteria="all") == 1


# ===================================================================
# Helpers
# ===================================================================


class TestResolveParallel:
    def test_openmp(self) -> None:
        assert _resolve_parallel(RunOptions(cpus=4)) == (4, 1)

    def test_openmpi(self) -> None:
        assert _resolve_parallel(RunOptions(parallel_type="openmpi", cpus=2, parallel=3)) == (2, 3)

    def test_openmpi_requires_parallel(self) -> None:
        with pytest.raises(ValueError, match="--parallel is required"):
            _resolve_parallel(RunOptions(parallel_type="openmpi"))


class TestCores:
    def test_openmp(self) -> None:
        from pya3eda.runner.engine import JobSpec

        spec = JobSpec(
            input_path="i",
            output_file="o",
            error_file="e",
            job_name="j",
            partition="p",
            cpus=4,
            qchem_processors=1,
            mem_per_cpu=1000,
            walltime="t",
            parallel_type="openmp",
            scratch_base_dir="/s",
            cluster_name="c",
        )
        assert _cores(spec) == 4

    def test_openmpi(self) -> None:
        from pya3eda.runner.engine import JobSpec

        spec = JobSpec(
            input_path="i",
            output_file="o",
            error_file="e",
            job_name="j",
            partition="p",
            cpus=2,
            qchem_processors=3,
            mem_per_cpu=1000,
            walltime="t",
            parallel_type="openmpi",
            scratch_base_dir="/s",
            cluster_name="c",
        )
        assert _cores(spec) == 6


class TestResolveVersion:
    def test_known(self) -> None:
        mods, _qc, _env, mpi, mpimods = _resolve_version(RunOptions(), "g2", _cluster())
        assert mods == ["module load qchem/6.2.1"]
        assert mpi is True and mpimods == ["openmpi4"]

    def test_qcsetup_override(self) -> None:
        _mods, qc, env, _mpi, _m = _resolve_version(
            RunOptions(qcsetup="/my/qc.sh"), "g2", _cluster()
        )
        assert qc == "/my/qc.sh"
        assert env == []

    def test_unknown_version(self) -> None:
        with pytest.raises(ValueError, match="unknown for"):
            _resolve_version(RunOptions(version="9.9.9"), "g2", _cluster())

    def test_modqchem_requires_qcsetup(self) -> None:
        with pytest.raises(ValueError, match="--qcsetup is required"):
            _resolve_version(RunOptions(version="modqchem"), "g2", _cluster())

    def test_modqchem_with_qcsetup(self) -> None:
        mods, qc, env, mpi, mpimods = _resolve_version(
            RunOptions(version="modqchem", qcsetup="/qc.sh"), "g2", _cluster()
        )
        assert (mods, qc, env, mpi, mpimods) == ([], "/qc.sh", [], False, [])


class TestApplyMemory:
    def test_sets_memory_and_passes(self, tmp_path: Path) -> None:
        spec = _spec(tmp_path, content="$rem\nmethod b3lyp\n$end\n")
        ok = executor._apply_memory(
            spec, RunOptions(memory=2000), cpus=1, qchem_processors=1, mem_per_cpu=4000
        )
        assert ok is True
        assert "mem_total 2000" in spec.input_path.read_text()

    def test_memory_set_but_unchanged(self, tmp_path: Path) -> None:
        spec = _spec(tmp_path, content="$rem\nmem_total 2000\n$end\n")
        ok = executor._apply_memory(
            spec, RunOptions(memory=2000), cpus=1, qchem_processors=1, mem_per_cpu=4000
        )
        assert ok is True

    def test_openmpi_total_budget(self, tmp_path: Path) -> None:
        spec = _spec(tmp_path, content="$rem\nmem_total 8000\n$end\n")
        ok = executor._apply_memory(
            spec,
            RunOptions(parallel_type="openmpi", parallel=2, cpus=2),
            cpus=2,
            qchem_processors=2,
            mem_per_cpu=4000,  # budget = 2 * 2 * 4000 = 16000
        )
        assert ok is True

    def test_within_budget_passes(self, tmp_path: Path) -> None:
        spec = _spec(tmp_path, content="$rem\nmem_total 1000\n$end\n")
        assert (
            executor._apply_memory(spec, RunOptions(), cpus=1, qchem_processors=1, mem_per_cpu=4000)
            is True
        )


class TestExcludeNodes:
    def test_config_and_user(self) -> None:
        assert _exclude_nodes(RunOptions(exclude="n9"), _cluster()) == "n9,g-07-02"

    def test_config_only(self) -> None:
        assert _exclude_nodes(RunOptions(), _cluster()) == "g-07-02"

    def test_user_only(self) -> None:
        cluster = _cluster().model_copy(update={"exclude_nodes": {}})
        assert _exclude_nodes(RunOptions(exclude="n9"), cluster) == "n9"

    def test_none(self) -> None:
        cluster = _cluster().model_copy(update={"exclude_nodes": {}})
        assert _exclude_nodes(RunOptions(), cluster) is None
