"""Command-line interface for pya3eda.

Subcommands
-----------
build   - generate Q-Chem input files
run     - submit calculations
status  - check calculation status
extract - extract data, build profiles, export CSVs, generate plots
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from pya3eda.config import load_config
from pya3eda.registry import CalcRegistry

if TYPE_CHECKING:
    from pya3eda.runner.executor import RunOptions


def _add_job_options(p: argparse.ArgumentParser) -> None:
    """Add the shared backend / core-budget / Q-Chem job flags (run + pipeline)."""
    p.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "local", "slurm"],
        help="Execution backend (default: auto — SLURM if sbatch is present, else local)",
    )
    p.add_argument(
        "--max-cores",
        type=int,
        default=None,
        help="Core budget for throttled submission (default: local CPU count)",
    )
    p.add_argument("-c", "--cpus", type=int, default=1, help="CPUs per task (threads)")
    p.add_argument("-p", "--parallel", type=int, default=None, help="MPI processes")
    p.add_argument(
        "-P",
        "--parallel-type",
        choices=["openmp", "openmpi"],
        default="openmp",
        help="Parallelism mode (default: openmp)",
    )
    p.add_argument("-m", "--memory", type=int, default=None, help="Set mem_total (MB) in inputs")
    p.add_argument("-M", "--mem-per-cpu", type=int, default=None, help="Memory per CPU (MB)")
    p.add_argument("-t", "--time", dest="walltime", default=None, help="Wall time (SLURM format)")
    p.add_argument("-q", "--partition", default=None, help="Partition name")
    p.add_argument("-v", "--version", default="6.2.1", help="Q-Chem version (default: 6.2.1)")
    p.add_argument("--qcsetup", default=None, help="Path to a custom qcsetup file")
    p.add_argument("-s", "--scratch", default=None, help="Scratch directory")
    p.add_argument("-N", "--node", dest="nodename", default=None, help="Target node")
    p.add_argument("-x", "--exclude", default=None, help="Nodes to exclude (comma-separated)")
    p.add_argument("--save", action="store_true", help="Save essential scratch files")
    p.add_argument("-f", "--save-all", action="store_true", help="Save all scratch files")
    p.add_argument("--save-scratch", action="store_true", help="Keep the scratch directory")
    p.add_argument("-F", "--force", action="store_true", help="Proceed despite mismatches")


def _run_options(args: argparse.Namespace) -> RunOptions:
    """Build a ``RunOptions`` from parsed job flags (shared by run + pipeline)."""
    from pya3eda.runner.executor import RunOptions

    return RunOptions(
        cpus=args.cpus,
        parallel=args.parallel,
        parallel_type=args.parallel_type,
        memory=args.memory,
        mem_per_cpu=args.mem_per_cpu,
        walltime=args.walltime,
        partition=args.partition,
        version=args.version,
        qcsetup=args.qcsetup,
        scratch=args.scratch,
        nodename=args.nodename,
        exclude=args.exclude,
        save=args.save,
        save_all=args.save_all,
        save_scratch=args.save_scratch,
        force=args.force,
    )


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments, load configuration, and dispatch to a subcommand."""
    parser = argparse.ArgumentParser(
        prog="pya3eda",
        description="PyA3EDA — Python automation for Asymmetrically-constrained Adiabatic ALMO-EDA",
    )
    parser.add_argument("--log", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("config", help="Path to YAML config file")
    sub = parser.add_subparsers(dest="command")

    # build
    p_build = sub.add_parser("build", help="Generate Q-Chem input files")
    p_build.add_argument("--overwrite", action="store_true", help="Overwrite existing inputs")
    p_build.add_argument(
        "--sp-strategy",
        default="smart",
        choices=["always", "smart", "never"],
        help="When to write SP inputs (default: smart)",
    )
    p_build.add_argument("--template-dir", default="templates", help="Template directory")

    # run — submit Q-Chem jobs (local bash or SLURM)
    p_run = sub.add_parser("run", help="Submit calculations (local or SLURM)")
    p_run.add_argument(
        "criteria",
        nargs="?",
        default="NOFILE",
        help="Status filter for submission (default: NOFILE)",
    )
    _add_job_options(p_run)
    p_run.add_argument(
        "--wait",
        action="store_true",
        help="Block until all jobs finish (implied for the local backend)",
    )

    # pipeline — one command: build → run OPT → build/run SP (per OPT) → extract
    p_pipeline = sub.add_parser(
        "pipeline",
        help="Full run: build → OPT → SP (as each OPT succeeds) → extract",
    )
    _add_job_options(p_pipeline)
    p_pipeline.add_argument("--template-dir", default="templates", help="Template directory")
    p_pipeline.add_argument("--overwrite", action="store_true", help="Overwrite existing inputs")
    p_pipeline.add_argument("--no-plots", action="store_true", help="Skip plot generation")

    # status
    sub.add_parser("status", help="Check calculation status")

    # extract
    p_extract = sub.add_parser("extract", help="Extract data, profiles, plots")
    p_extract.add_argument("--criteria", default="SUCCESSFUL", help="Status filter")
    p_extract.add_argument("--no-plots", action="store_true", help="Skip plot generation")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    if not args.command:
        args.command = "status"

    config = load_config(args.config)
    base_dir = Path(args.config).resolve().parent
    registry = CalcRegistry(config, base_dir)

    if args.command == "build":
        _cmd_build(registry, args)
    elif args.command == "run":
        _cmd_run(registry, args)
    elif args.command == "pipeline":
        _cmd_pipeline(registry, base_dir, args)
    elif args.command == "status":
        _cmd_status(registry)
    else:  # "extract" — the only remaining valid subcommand
        _cmd_extract(registry, base_dir, args)


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_build(registry: CalcRegistry, args: argparse.Namespace) -> None:
    """Generate Q-Chem input files for all registered calculations."""
    from pya3eda.builder.inputs import build_all

    build_all(
        registry,
        template_dir=Path(args.template_dir),
        overwrite="all" if args.overwrite else None,
        sp_strategy=args.sp_strategy,
    )


def _cmd_run(registry: CalcRegistry, args: argparse.Namespace) -> None:
    """Submit calculations via the local or SLURM backend."""
    from pya3eda.runner.executor import run_all

    run_all(
        registry,
        criteria=args.criteria,
        backend=args.backend,
        max_cores=args.max_cores,
        wait=args.wait,
        options=_run_options(args),
    )


def _cmd_pipeline(registry: CalcRegistry, base_dir: Path, args: argparse.Namespace) -> None:
    """Run the full dependency-aware pipeline (build → OPT → SP → extract)."""
    from pya3eda.pipeline import run_pipeline

    run_pipeline(
        registry,
        base_dir,
        backend=args.backend,
        max_cores=args.max_cores,
        options=_run_options(args),
        template_dir=Path(args.template_dir),
        overwrite="all" if args.overwrite else None,
        plots=not args.no_plots,
    )


def _cmd_status(registry: CalcRegistry) -> None:
    """Print a status report for all registered calculations."""
    from pya3eda.status.checker import check_all

    check_all(registry)


def _cmd_extract(registry: CalcRegistry, base_dir: Path, args: argparse.Namespace) -> None:
    """Extract data, assemble profiles, export CSVs, and generate plots."""
    from pya3eda.extractor.data import extract_all
    from pya3eda.pipeline import finalize_extraction

    extracted = extract_all(registry, criteria=args.criteria)
    finalize_extraction(registry, extracted, base_dir, plots=not args.no_plots)
