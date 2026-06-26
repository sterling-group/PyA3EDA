"""Dependency-aware OPT→SP run pipeline (the ``pipeline`` subcommand conductor).

One command that chains the staged workflow: **build OPT inputs → submit under a
core budget → as each OPT *succeeds*, build its SP input(s) from the optimised
geometry and submit them as cores free → extract each calc live → finalise
profiles / ΔΔ‡ / CSVs / plots when all finish.**

It composes the existing stages (builder, runner backends/throttle, status,
extractor, exporter, plotter) — the runner stays pure submission mechanics; this
module is the cross-stage conductor (like ``cli._cmd_extract`` coordinates
extract→export→plot). Resumable: an OPT whose output is already SUCCESSFUL skips
straight to its SP(s).
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from pathlib import Path

from pya3eda.builder.inputs import build_all, build_calc
from pya3eda.extractor.data import extract_one
from pya3eda.ids import CalcID, CalcSpec, ExtractedData
from pya3eda.registry import CalcRegistry
from pya3eda.runner.backend import ExecutionBackend, get_backend
from pya3eda.runner.clusters import ClusterConfig, detect_cluster
from pya3eda.runner.executor import RunOptions, cores_for, prepare_job, submit_job
from pya3eda.runner.throttle import Throttler
from pya3eda.status.checker import Status, get_status, should_process

log = logging.getLogger(__name__)


class _Pipeline:
    """Scheduler that submits OPTs, builds/submits SPs on OPT success, extracts live."""

    def __init__(
        self,
        registry: CalcRegistry,
        base_dir: Path,
        *,
        be: ExecutionBackend,
        throttler: Throttler,
        cluster: ClusterConfig,
        cluster_name: str,
        opts: RunOptions,
        template_dir: Path,
        overwrite: str | None,
        opt_criteria: str,
        extract_criteria: str,
    ) -> None:
        """Store the run context and initialise the scheduler state."""
        self.registry = registry
        self.base_dir = base_dir
        self.be = be
        self.throttler = throttler
        self.cluster = cluster
        self.cluster_name = cluster_name
        self.opts = opts
        self.template_dir = template_dir
        self.overwrite = overwrite
        self.opt_criteria = opt_criteria
        self.extract_criteria = extract_criteria

        self.sp_by_opt: dict[CalcID, list[CalcSpec]] = {}
        self.ready: deque[CalcSpec] = deque()
        self.inflight: dict[str, CalcSpec] = {}
        self.extracted: dict[CalcID, ExtractedData] = {}
        self.opt_cache: dict[CalcID, str] = {}

    def run(self) -> dict[CalcID, ExtractedData]:
        """Build OPT inputs, drive the scheduler to completion, return extracted data."""
        build_all(self.registry, self.template_dir, overwrite=self.overwrite, sp_strategy="never")
        for spec in self.registry.all_calcs:
            if spec.id.mode == "sp":
                self.sp_by_opt.setdefault(spec.id.to_opt(), []).append(spec)
        self._seed()
        self._loop()
        return self.extracted

    def _seed(self) -> None:
        """Queue OPTs that need running; complete (extract + enqueue SPs) already-done OPTs."""
        for spec in self.registry.all_calcs:
            if spec.id.mode != "opt":
                continue
            status, _ = get_status(spec)
            if status == Status.SUCCESSFUL:
                self._complete(spec)
            elif should_process(spec, self.opt_criteria):
                self.ready.append(spec)

    def _loop(self) -> None:
        """Submit ready jobs under the budget, reap completions, until everything drains."""
        while self.ready or self.inflight:
            self._submit_ready()
            finished = self.throttler.poll(self.be.is_finished)
            for jid in finished:
                self._complete(self.inflight.pop(jid))
            if not finished and self.inflight:
                time.sleep(self.throttler.poll_interval)

    def _submit_ready(self) -> None:
        """Submit queued specs while the core budget allows (never deadlock when idle)."""
        while self.ready:
            spec = self.ready[0]
            if not spec.input_path.exists():
                self.ready.popleft()
                log.warning("Missing input, skipping: %s", spec.input_path)
                continue
            job = prepare_job(spec, self.opts, self.cluster, self.cluster_name)
            if job is None:
                self.ready.popleft()
                continue
            cores = cores_for(job)
            in_use = self.throttler.cores_in_use
            if in_use and in_use + cores > self.throttler.max_cores:
                break  # busy and won't fit → wait for running jobs to finish
            self.ready.popleft()
            job_id = submit_job(spec, job, self.be)
            self.throttler.register(job_id, cores)
            self.inflight[job_id] = spec

    def _complete(self, spec: CalcSpec) -> None:
        """Extract a finished calc live; on a successful OPT, build/enqueue its SP(s)."""
        data = extract_one(spec, self.extract_criteria, self.opt_cache)
        if data is not None:
            self.extracted[spec.id] = data
            self._live_csv(spec.id.method_key)
        if spec.id.mode == "opt":
            status, _ = get_status(spec)
            if status == Status.SUCCESSFUL:
                self._enqueue_sps(spec)
            else:
                log.warning("OPT %s not SUCCESSFUL (%s); skipping its SP(s)", spec.id, status.value)

    def _enqueue_sps(self, opt_spec: CalcSpec) -> None:
        """Build and queue the SP inputs that depend on a just-finished OPT."""
        for sp_spec in self.sp_by_opt.get(opt_spec.id, []):
            status, _ = get_status(sp_spec)
            if status == Status.SUCCESSFUL:
                self._complete(sp_spec)  # already done on a prior run → just extract
                continue
            build_calc(sp_spec, self.registry, self.template_dir)
            if sp_spec.input_path.exists():
                self.ready.append(sp_spec)
            else:
                log.warning("SP input not built: %s", sp_spec.id)

    def _live_csv(self, method_key: str) -> None:
        """Re-write the raw-data CSVs for *method_key* so progress is visible mid-run."""
        from pya3eda.exporter.results import export_raw

        export_raw(self.extracted, method_key, self.base_dir / "results" / method_key / "raw_data")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_pipeline(
    registry: CalcRegistry,
    base_dir: Path,
    *,
    backend: str = "auto",
    max_cores: int | None = None,
    options: RunOptions | None = None,
    template_dir: Path = Path("templates"),
    overwrite: str | None = None,
    opt_criteria: str = "NOFILE",
    extract_criteria: str = "SUCCESSFUL",
    plots: bool = True,
) -> None:
    """Run the full dependency-aware build→run→SP→extract pipeline to completion."""
    cluster_name, cluster = detect_cluster()
    be = get_backend(backend)
    budget = max_cores if max_cores is not None else (os.cpu_count() or 1)
    log.info("Pipeline on %s backend, budget %d cores", be.name, budget)

    pipe = _Pipeline(
        registry,
        base_dir,
        be=be,
        throttler=Throttler(max_cores=budget),
        cluster=cluster,
        cluster_name=cluster_name,
        opts=options or RunOptions(),
        template_dir=Path(template_dir),
        overwrite=overwrite,
        opt_criteria=opt_criteria,
        extract_criteria=extract_criteria,
    )
    extracted = pipe.run()
    finalize_extraction(registry, extracted, base_dir, plots=plots)


def finalize_extraction(
    registry: CalcRegistry,
    extracted: dict[CalcID, ExtractedData],
    base_dir: Path,
    *,
    plots: bool = True,
) -> None:
    """Assemble profiles + ΔΔ‡ from *extracted*, export CSVs, and (optionally) plot.

    Shared by ``cli._cmd_extract`` and :func:`run_pipeline` so the extract tail
    lives in one place.
    """
    from pya3eda.exporter.results import export_all
    from pya3eda.extractor.barriers import compute_delta_delta
    from pya3eda.extractor.dimer import apply_dimer_corrections
    from pya3eda.extractor.stages import build_profiles

    profiles = build_profiles(registry, extracted)
    dd = compute_delta_delta(profiles, registry.catalyst_order)
    dd = apply_dimer_corrections(dd, registry, extracted)
    export_all(registry, extracted, profiles, dd, base_dir)

    if plots:
        from pya3eda.plotter.contributions import plot_delta_delta_barplots
        from pya3eda.plotter.profile import plot_all_profiles

        plot_all_profiles(profiles, registry, base_dir)
        plot_delta_delta_barplots(dd, registry, base_dir)
