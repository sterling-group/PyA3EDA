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

    # run — accepts all backend-specific flags after pya3eda's own flags
    p_run = sub.add_parser(
        "run",
        help="Submit calculations (extra flags forwarded to backend)",
    )
    p_run.add_argument(
        "criteria",
        nargs="?",
        default="NOFILE",
        help="Status filter for submission (default: NOFILE)",
    )
    p_run.add_argument("--backend", default="qqchem", help="Submission backend (default: qqchem)")

    # status
    sub.add_parser("status", help="Check calculation status")

    # extract
    p_extract = sub.add_parser("extract", help="Extract data, profiles, plots")
    p_extract.add_argument("--criteria", default="SUCCESSFUL", help="Status filter")
    p_extract.add_argument("--no-plots", action="store_true", help="Skip plot generation")

    args, remaining = parser.parse_known_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    if not args.command:
        args.command = "status"

    # Stash extra args so the run subcommand can forward them to the backend
    args.extra_argv = remaining if args.command == "run" else []
    if remaining and args.command != "run":
        parser.error(f"unrecognized arguments: {' '.join(remaining)}")

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
    """Submit calculations to the configured HPC backend."""
    from pya3eda.runner.executor import run_all

    run_all(
        registry,
        criteria=args.criteria,
        backend=args.backend,
        extra_argv=args.extra_argv,
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
