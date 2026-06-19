"""Job submission orchestration over the registry.

``run_all`` picks an execution backend (local bash / SLURM), assembles a
Q-Chem script per matching calculation, and submits it. Under ``--wait`` (and
always for local, whose background processes die with the CLI) submissions are
bounded by a CPU-core :class:`~pya3eda.runner.throttle.Throttler` and the call
blocks until every job finishes; the default SLURM path stays fire-and-forget
(submit and return, preserving the staged build→run→status→extract workflow).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from pya3eda.errors import RunOptionError
from pya3eda.ids import CalcSpec
from pya3eda.registry import CalcRegistry
from pya3eda.runner.backend import ExecutionBackend, get_backend
from pya3eda.runner.clusters import ClusterConfig, detect_cluster
from pya3eda.runner.engine import JobSpec
from pya3eda.runner.script import (
    adjust_mem_total,
    local_script_text,
    parse_mem_total,
    read_input_file,
    slurm_script_text,
)
from pya3eda.status.checker import should_process
from pya3eda.utils import write_text

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunOptions:
    """Per-run Q-Chem/SLURM knobs (the former ``qqchem`` CLI flags)."""

    cpus: int = 1
    parallel: int | None = None
    parallel_type: str = "openmp"  # openmp | openmpi
    memory: int | None = None  # mem_total (MB) to set in the input
    mem_per_cpu: int | None = None
    walltime: str | None = None
    partition: str | None = None
    version: str = "6.2.1"
    qcsetup: str | None = None
    scratch: str | None = None
    nodename: str | None = None
    exclude: str | None = None
    save: bool = False
    save_all: bool = False
    save_scratch: bool = False
    force: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_all(
    registry: CalcRegistry,
    criteria: str,
    *,
    backend: str = "auto",
    max_cores: int | None = None,
    wait: bool = False,
    options: RunOptions | None = None,
) -> int:
    """Submit jobs for every calculation matching *criteria*; return the count submitted."""
    if not criteria:
        log.warning("No run criteria specified")
        return 0

    opts = options or RunOptions()
    cluster_name, cluster = detect_cluster()
    be = get_backend(backend)
    must_wait = wait or be.name == "local"
    throttler = None
    if must_wait:
        from pya3eda.runner.throttle import Throttler

        budget = max_cores if max_cores is not None else (os.cpu_count() or 1)
        throttler = Throttler(max_cores=budget)
        log.info("Throttling submissions to %d cores (%s backend)", budget, be.name)

    count = 0
    for spec in registry.all_calcs:
        if not spec.input_path.exists():
            continue
        if not should_process(spec, criteria):
            continue

        job = _prepare_job(spec, opts, cluster, cluster_name)
        if job is None:
            continue
        cores = _cores(job)

        if throttler is not None:
            throttler.wait_for_room(cores, is_finished=be.is_finished)
        job_id = _write_and_submit(spec, job, be)
        if throttler is not None:
            throttler.register(job_id, cores)
        count += 1

    if throttler is not None:
        throttler.wait_all(is_finished=be.is_finished)

    log.info("Total jobs submitted: %d", count)
    return count


def _write_and_submit(spec: CalcSpec, job: JobSpec, be: ExecutionBackend) -> str:
    """Write *spec*'s script (local or SLURM) and submit it; return the job id.

    Shared by ``run_all`` and the dependency-aware pipeline; the caller owns the
    core-budget accounting (``Throttler``) around it.
    """
    text = local_script_text(job) if be.name == "local" else slurm_script_text(job)
    script_path = spec.input_path.with_suffix(".slurm")
    write_text(script_path, text)
    log.info("Submitting: %s", spec.input_path)
    job_id = be.submit(script_path)
    log.info("Submitted %s as %s", spec.input_path, job_id)
    return job_id


# ---------------------------------------------------------------------------
# Job preparation
# ---------------------------------------------------------------------------


def _prepare_job(
    spec: CalcSpec,
    opts: RunOptions,
    cluster: ClusterConfig,
    cluster_name: str,
) -> JobSpec | None:
    """Resolve parallel/memory/version/exclude settings into a :class:`JobSpec`.

    Returns ``None`` to skip the calculation (e.g. memory exceeds the budget).
    """
    cpus, qchem_processors = _resolve_parallel(opts)
    mem_per_cpu = opts.mem_per_cpu or cluster.mem_per_cpu

    if not _apply_memory(spec, opts, cpus, qchem_processors, mem_per_cpu):
        return None

    module_cmds, qcsetup, env_vars, mpi_support, mpi_modules = _resolve_version(
        opts, cluster_name, cluster
    )

    stem = spec.input_path.stem
    return JobSpec(
        input_path=spec.input_path.name,
        output_file=f"{stem}.out",
        error_file=f"{stem}.err",
        job_name=stem,
        partition=opts.partition or cluster.default_partition,
        cpus=cpus,
        qchem_processors=qchem_processors,
        mem_per_cpu=mem_per_cpu,
        walltime=opts.walltime or cluster.default_time,
        parallel_type=opts.parallel_type,
        scratch_base_dir=cluster.scratch_base_dir,
        cluster_name=cluster_name,
        module_load_commands=module_cmds,
        environment_vars=env_vars,
        qcsetup_file=qcsetup,
        mpi_support=mpi_support,
        mpi_modules=mpi_modules,
        scratch=opts.scratch,
        nodename=opts.nodename,
        exclude_nodes=_exclude_nodes(opts, cluster),
        save=opts.save,
        save_all=opts.save_all,
        save_scratch=opts.save_scratch,
        force=opts.force,
    )


def _resolve_parallel(opts: RunOptions) -> tuple[int, int]:
    """Return ``(cpus, qchem_processors)`` for the parallel mode."""
    if opts.parallel_type == "openmpi":
        if opts.parallel is None:
            raise RunOptionError("--parallel is required with --parallel-type openmpi")
        return (opts.cpus or 1), opts.parallel
    return (opts.cpus or 1), 1


def _cores(job: JobSpec) -> int:
    """Total cores a job charges against the throttler budget."""
    if job.parallel_type == "openmpi":
        return job.qchem_processors * job.cpus
    return job.cpus


def _apply_memory(
    spec: CalcSpec,
    opts: RunOptions,
    cpus: int,
    qchem_processors: int,
    mem_per_cpu: int,
) -> bool:
    """Optionally set ``mem_total`` in the input and validate against the budget.

    Returns ``False`` (skip the job) if a ``mem_total`` exceeds the SLURM budget.
    """
    lines = read_input_file(spec.input_path)
    if opts.memory is not None:
        new_lines, changed = adjust_mem_total(lines, opts.memory)
        if changed:
            spec.input_path.write_text("".join(new_lines), encoding="utf-8")
            lines = new_lines

    if opts.parallel_type == "openmpi":
        total = qchem_processors * cpus * mem_per_cpu
    else:
        total = cpus * mem_per_cpu
    for idx, val in enumerate(parse_mem_total(lines), 1):
        if val > total:
            log.error(
                "Skipping %s: mem_total (%d MB) in $rem block %d exceeds budget (%d MB)",
                spec.input_path,
                val,
                idx,
                total,
            )
            return False
    return True


def _resolve_version(
    opts: RunOptions,
    cluster_name: str,
    cluster: ClusterConfig,
) -> tuple[list[str], str, list[str], bool, list[str]]:
    """Return ``(module_cmds, qcsetup, env_vars, mpi_support, mpi_modules)``."""
    if opts.version == "modqchem":
        if not opts.qcsetup:
            raise RunOptionError("--qcsetup is required with version 'modqchem'")
        return [], opts.qcsetup, [], False, []

    versions = cluster.qchem_versions
    if opts.version not in versions:
        available = ", ".join([*versions, "modqchem"])
        raise RunOptionError(
            f"Q-Chem version '{opts.version}' unknown for '{cluster_name}'. Available: {available}"
        )

    info = versions[opts.version]
    if opts.qcsetup:
        return info.module_loads, opts.qcsetup, [], info.mpi_support, info.mpi_modules
    return (
        info.module_loads,
        info.qcsetup_file,
        info.environment,
        info.mpi_support,
        info.mpi_modules,
    )


def _exclude_nodes(opts: RunOptions, cluster: ClusterConfig) -> str | None:
    """Combine config-level and user-supplied excluded nodes."""
    partition = opts.partition or cluster.default_partition
    cfg = cluster.exclude_nodes.get(partition, [])
    user = opts.exclude
    if cfg:
        cfg_str = ",".join(cfg)
        return f"{user},{cfg_str}" if user else cfg_str
    return user
