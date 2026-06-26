"""Tests for pya3eda.pipeline — the dependency-aware OPT→SP→extract conductor.

Driven by a FakeBackend that "runs" each job by writing a canned Q-Chem output
next to the input, so the scheduler, live extraction, and finalisation are
exercised without a real backend.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from pya3eda.config import Config, LevelConfig, SpeciesConfig, TheoryConfig
from pya3eda.pipeline import _Pipeline, run_pipeline
from pya3eda.registry import CalcRegistry
from pya3eda.runner.clusters import ClusterConfig, QChemVersion
from pya3eda.runner.executor import RunOptions
from pya3eda.runner.throttle import Throttler
from tests.conftest import _make_template_dir, _write_xyz
from tests.synthetic_outputs import OPT_OUTPUT, SP_OUTPUT, TS_OUTPUT

_XYZ = "3\n0 1\nO 0 0 0\nH 0 0 1\nH 0 1 0\n"


def _config() -> Config:
    """Uncatalysed config (1 reactant, 1 product) with an OPT + SP level."""
    return Config(
        levels=[
            LevelConfig(
                opt=TheoryConfig(method="HF", basis="STO-3G", solvent="smd"),
                sp=[TheoryConfig(method="MP2", basis="cc-pVTZ", solvent="smd", eda2=1)],
            )
        ],
        reactants=[SpeciesConfig(name="mol_a")],
        products=[SpeciesConfig(name="mol_p")],
        catalysts=[],
    )


def _cluster() -> ClusterConfig:
    return ClusterConfig(
        default_partition="local",
        mem_per_cpu=4000,
        default_time="1:00:00",
        scratch_base_dir="/tmp/scratch",
        qchem_versions={"6.2.1": QChemVersion()},
    )


class FakeBackend:
    """Runs each job inline: writes a canned output, reports finished immediately."""

    name = "local"

    def __init__(self, *, crash: bool = False) -> None:
        self.crash = crash
        self.submitted: list[Path] = []

    def available(self) -> bool:
        return True

    def submit(self, script_path: Path, *, log_path: Path | None = None) -> str:
        self.submitted.append(script_path)
        out = Path(script_path).with_suffix(".out")
        stem = Path(script_path).stem
        if self.crash:
            content = "Running on host\nSCF failed to converge\n"
        elif "_sp" in stem:
            content = SP_OUTPUT
        elif "tscomplex" in stem:
            content = TS_OUTPUT
        else:
            content = OPT_OUTPUT
        out.write_text(content)
        return f"job-{len(self.submitted)}"

    def is_finished(self, job_id: str) -> bool:
        return True


@pytest.fixture
def project(tmp_path: Path) -> tuple[CalcRegistry, Path, Path]:
    """A registry + template dir + base dir with the XYZ templates the build needs."""
    tpl = _make_template_dir(tmp_path)
    for name in ("mol_a", "mol_p", "tscomplex"):
        _write_xyz(tpl, name, _XYZ)
    registry = CalcRegistry(_config(), tmp_path)
    return registry, tpl, tmp_path


def _run(registry: CalcRegistry, tpl: Path, base: Path, be: FakeBackend, **kw: Any) -> None:
    with (
        patch("pya3eda.pipeline.detect_cluster", return_value=("g2", _cluster())),
        patch("pya3eda.pipeline.get_backend", return_value=be),
    ):
        run_pipeline(registry, base, template_dir=tpl, options=RunOptions(), plots=False, **kw)


# ===================================================================
# End-to-end
# ===================================================================


class TestEndToEnd:
    def test_opt_then_sp_then_extract(self, project: tuple[CalcRegistry, Path, Path]) -> None:
        registry, tpl, base = project
        be = FakeBackend()
        _run(registry, tpl, base, be, max_cores=1)  # max_cores=1 exercises the budget break

        opt_outs = list(base.rglob("*_opt.out"))
        sp_ins = list(base.rglob("*_sp.in"))
        sp_outs = list(base.rglob("*_sp.out"))
        assert len(opt_outs) == 3  # reactant, product, ts
        assert len(sp_ins) == 3 and len(sp_outs) == 3  # SP built + run after their OPT
        # raw CSVs written live
        raw = base / "results" / "HF_STO-3G_smd" / "raw_data"
        assert (raw / "opt_HF_STO-3G_smd.csv").exists()
        assert (raw / "sp_HF_STO-3G_smd.csv").exists()

    def test_resume_skips_already_done(self, project: tuple[CalcRegistry, Path, Path]) -> None:
        registry, tpl, base = project
        # Pre-build + pre-run everything so the pipeline finds it all SUCCESSFUL.
        be = FakeBackend()
        _run(registry, tpl, base, be)
        # Second run: nothing should be submitted (all outputs already SUCCESSFUL).
        be2 = FakeBackend()
        _run(registry, tpl, base, be2)
        assert be2.submitted == []

    def test_opt_failure_skips_sps(self, project: tuple[CalcRegistry, Path, Path]) -> None:
        registry, tpl, base = project
        be = FakeBackend(crash=True)
        _run(registry, tpl, base, be)
        assert list(base.rglob("*_sp.in")) == []  # failed OPTs → no SP inputs built


# ===================================================================
# Scheduler branches
# ===================================================================


def _pipeline(
    registry: CalcRegistry, base: Path, tpl: Path, be: FakeBackend, **kw: Any
) -> _Pipeline:
    return _Pipeline(
        registry,
        base,
        be=be,
        throttler=Throttler(max_cores=4, poll_interval=0.0),
        cluster=_cluster(),
        cluster_name="g2",
        opts=RunOptions(),
        template_dir=tpl,
        overwrite=None,
        opt_criteria="NOFILE",
        extract_criteria="SUCCESSFUL",
        **kw,
    )


class TestSchedulerBranches:
    def test_waits_when_no_completion(
        self, project: tuple[CalcRegistry, Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry, tpl, base = project

        class SlowBackend(FakeBackend):
            def __init__(self) -> None:
                super().__init__()
                self._polls = 0

            def is_finished(self, job_id: str) -> bool:
                self._polls += 1
                return self._polls > 1  # not finished on the first poll

        sleeps: list[float] = []
        monkeypatch.setattr("pya3eda.pipeline.time.sleep", lambda s: sleeps.append(s))
        # max_cores=1 keeps a single job inflight, so its first (False) poll hits the sleep path
        _run(registry, tpl, base, SlowBackend(), max_cores=1)
        assert sleeps  # the idle-but-inflight sleep path was taken

    def test_submit_skips_missing_input(self, project: tuple[CalcRegistry, Path, Path]) -> None:
        registry, tpl, base = project
        be = FakeBackend()
        pipe = _pipeline(registry, base, tpl, be)
        ghost = next(s for s in registry.all_calcs if s.id.mode == "opt")
        pipe.ready.append(ghost)  # its input was never built
        pipe._submit_ready()
        assert be.submitted == []  # missing input → skipped, nothing submitted

    def test_submit_skips_when_prepare_returns_none(
        self, project: tuple[CalcRegistry, Path, Path]
    ) -> None:
        registry, tpl, base = project
        be = FakeBackend()
        pipe = _pipeline(registry, base, tpl, be)
        spec = next(s for s in registry.all_calcs if s.id.mode == "opt")
        # Build an input whose mem_total exceeds the budget → prepare_job returns None.
        spec.input_path.parent.mkdir(parents=True, exist_ok=True)
        spec.input_path.write_text("$rem\nmem_total 9999999\n$end\n")
        pipe.ready.append(spec)
        pipe._submit_ready()
        assert be.submitted == []

    def test_seed_skips_unsuccessful_opt(self, project: tuple[CalcRegistry, Path, Path]) -> None:
        registry, tpl, base = project
        pipe = _pipeline(registry, base, tpl, FakeBackend())
        opt = next(s for s in registry.all_calcs if s.id.mode == "opt" and s.id.species == "mol_a")
        # Output exists but is not SUCCESSFUL → neither submitted nor completed.
        opt.input_path.parent.mkdir(parents=True, exist_ok=True)
        opt.input_path.write_text("$rem\n$end\n")
        opt.output_path.write_text("Running on host\nstill going\n")
        pipe._seed()
        assert opt not in pipe.ready
        assert opt.id not in pipe.extracted

    def test_enqueue_skips_unbuilt_sp(self, tmp_path: Path) -> None:
        # Template dir has the base template + rem but NO molecule XYZ → SP build fails.
        tpl = _make_template_dir(tmp_path)
        registry = CalcRegistry(_config(), tmp_path)
        pipe = _pipeline(registry, tmp_path, tpl, FakeBackend())
        for s in registry.all_calcs:
            if s.id.mode == "sp":
                pipe.sp_by_opt.setdefault(s.id.to_opt(), []).append(s)
        opt = next(s for s in registry.all_calcs if s.id.mode == "opt" and s.id.species == "mol_a")
        pipe._enqueue_sps(opt)
        assert not pipe.ready  # SP molecule build failed → input not built → not enqueued
