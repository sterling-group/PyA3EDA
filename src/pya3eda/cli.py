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

from pya3eda.config import load_config
from pya3eda.registry import CalcRegistry


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
    p_run.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "local", "slurm"],
        help="Execution backend (default: auto — SLURM if sbatch is present, else local)",
    )
    p_run.add_argument(
        "--max-cores",
        type=int,
        default=None,
        help="Core budget for throttled submission (default: local CPU count)",
    )
    p_run.add_argument(
        "--wait",
        action="store_true",
        help="Block until all jobs finish (implied for the local backend)",
    )
    # Q-Chem / SLURM job options
    p_run.add_argument("-c", "--cpus", type=int, default=1, help="CPUs per task (threads)")
    p_run.add_argument("-p", "--parallel", type=int, default=None, help="MPI processes")
    p_run.add_argument(
        "-P",
        "--parallel-type",
        choices=["openmp", "openmpi"],
        default="openmp",
        help="Parallelism mode (default: openmp)",
    )
    p_run.add_argument(
        "-m", "--memory", type=int, default=None, help="Set mem_total (MB) in inputs"
    )
    p_run.add_argument("-M", "--mem-per-cpu", type=int, default=None, help="Memory per CPU (MB)")
    p_run.add_argument(
        "-t", "--time", dest="walltime", default=None, help="Wall time (SLURM format)"
    )
    p_run.add_argument("-q", "--partition", default=None, help="Partition name")
    p_run.add_argument("-v", "--version", default="6.2.1", help="Q-Chem version (default: 6.2.1)")
    p_run.add_argument("--qcsetup", default=None, help="Path to a custom qcsetup file")
    p_run.add_argument("-s", "--scratch", default=None, help="Scratch directory")
    p_run.add_argument("-N", "--node", dest="nodename", default=None, help="Target node")
    p_run.add_argument("-x", "--exclude", default=None, help="Nodes to exclude (comma-separated)")
    p_run.add_argument("--save", action="store_true", help="Save essential scratch files")
    p_run.add_argument("-f", "--save-all", action="store_true", help="Save all scratch files")
    p_run.add_argument("--save-scratch", action="store_true", help="Keep the scratch directory")
    p_run.add_argument("-F", "--force", action="store_true", help="Proceed despite mismatches")

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
    from pya3eda.runner.executor import RunOptions, run_all

    options = RunOptions(
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
    run_all(
        registry,
        criteria=args.criteria,
        backend=args.backend,
        max_cores=args.max_cores,
        wait=args.wait,
        options=options,
    )


def _cmd_status(registry: CalcRegistry) -> None:
    """Print a status report for all registered calculations."""
    from pya3eda.status.checker import check_all

    check_all(registry)


def _cmd_extract(registry: CalcRegistry, base_dir: Path, args: argparse.Namespace) -> None:
    """Extract data, assemble profiles, export CSVs, and generate plots."""
    from pya3eda.exporter.results import export_all
    from pya3eda.extractor.barriers import compute_delta_delta
    from pya3eda.extractor.data import extract_all
    from pya3eda.extractor.stages import build_profiles

    extracted = extract_all(registry, criteria=args.criteria)
    profiles = build_profiles(registry, extracted)
    dd = compute_delta_delta(profiles, registry.catalyst_order)

    export_all(registry, extracted, profiles, dd, base_dir)

    if not args.no_plots:
        from pya3eda.plotter.contributions import plot_delta_delta_barplots
        from pya3eda.plotter.profile import plot_all_profiles

        plot_all_profiles(profiles, registry, base_dir)
        plot_delta_delta_barplots(dd, registry, base_dir)
