"""Typer command-line interface for pya3eda.

Each command takes the YAML config as its first argument:

* ``pya3eda build CONFIG``    — generate Q-Chem input files
* ``pya3eda run CONFIG``      — submit calculations (local or SLURM)
* ``pya3eda status CONFIG``   — check calculation status
* ``pya3eda extract CONFIG``  — extract data, profiles, CSVs, plots
* ``pya3eda pipeline CONFIG`` — build → OPT → SP (as each OPT succeeds) → extract

Running ``pya3eda`` with no command prints this help. This is the only module
that drives process exit: every :class:`~pya3eda.errors.PyA3EDAError` is caught
and translated into its documented exit code.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from pya3eda.config import load_config
from pya3eda.errors import PyA3EDAError
from pya3eda.registry import CalcRegistry

if TYPE_CHECKING:
    from pya3eda.runner.executor import RunOptions

log = logging.getLogger("pya3eda")

app = typer.Typer(
    name="pya3eda",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
    help="PyA3EDA — Python automation for Asymmetrically-constrained Adiabatic ALMO-EDA.",
)


def _version_callback(value: bool) -> None:
    """Eager ``--version`` — print the package version and exit."""
    if value:
        from pya3eda import __version__

        typer.echo(f"pya3eda {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    log_level: Annotated[
        str, typer.Option("--log", help="Logging level (DEBUG, INFO, WARNING, ERROR).")
    ] = "INFO",
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            help="Show the pya3eda version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Configure logging for the rest of the invocation."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


# ---------------------------------------------------------------------------
# Shared parameter types
# ---------------------------------------------------------------------------

ConfigArg = Annotated[
    Path, typer.Argument(exists=True, dir_okay=False, readable=True, help="YAML config file.")
]

BackendOpt = Annotated[
    str, typer.Option("--backend", help="Execution backend: auto, local, or slurm.")
]
MaxCoresOpt = Annotated[
    int | None, typer.Option("--max-cores", help="Core budget for throttled submission.")
]
CpusOpt = Annotated[int, typer.Option("-c", "--cpus", help="CPUs per task (threads).")]
ParallelOpt = Annotated[int | None, typer.Option("-p", "--parallel", help="MPI processes.")]
ParallelTypeOpt = Annotated[
    str, typer.Option("-P", "--parallel-type", help="Parallelism mode: openmp or openmpi.")
]
MemoryOpt = Annotated[
    int | None, typer.Option("-m", "--memory", help="Set mem_total (MB) in inputs.")
]
MemPerCpuOpt = Annotated[
    int | None, typer.Option("-M", "--mem-per-cpu", help="Memory per CPU (MB).")
]
TimeOpt = Annotated[str | None, typer.Option("-t", "--time", help="Wall time (SLURM format).")]
PartitionOpt = Annotated[str | None, typer.Option("-q", "--partition", help="Partition name.")]
VersionOpt = Annotated[str, typer.Option("-v", "--qchem-version", help="Q-Chem version.")]
QcsetupOpt = Annotated[str | None, typer.Option("--qcsetup", help="Path to a custom qcsetup file.")]
ScratchOpt = Annotated[str | None, typer.Option("-s", "--scratch", help="Scratch directory.")]
NodeOpt = Annotated[str | None, typer.Option("-N", "--node", help="Target node.")]
ExcludeOpt = Annotated[
    str | None, typer.Option("-x", "--exclude", help="Nodes to exclude (comma-separated).")
]
SaveOpt = Annotated[bool, typer.Option("--save", help="Save essential scratch files.")]
SaveAllOpt = Annotated[bool, typer.Option("-f", "--save-all", help="Save all scratch files.")]
SaveScratchOpt = Annotated[bool, typer.Option("--save-scratch", help="Keep the scratch directory.")]
ForceOpt = Annotated[bool, typer.Option("-F", "--force", help="Proceed despite mismatches.")]
TemplateDirOpt = Annotated[Path, typer.Option("--template-dir", help="Template directory.")]
NoPlotsOpt = Annotated[bool, typer.Option("--no-plots", help="Skip plot generation.")]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def _errors() -> Iterator[None]:
    """Translate any domain error into its deterministic exit code."""
    try:
        yield
    except PyA3EDAError as exc:
        log.error("%s", exc)
        raise typer.Exit(code=exc.exit_code) from exc


def _registry(config_path: Path) -> tuple[CalcRegistry, Path]:
    """Load the config and build the registry (base dir = the config's directory)."""
    config = load_config(config_path)
    base_dir = config_path.resolve().parent
    return CalcRegistry(config, base_dir), base_dir


def _run_options(
    *,
    cpus: int,
    parallel: int | None,
    parallel_type: str,
    memory: int | None,
    mem_per_cpu: int | None,
    walltime: str | None,
    partition: str | None,
    version: str,
    qcsetup: str | None,
    scratch: str | None,
    nodename: str | None,
    exclude: str | None,
    save: bool,
    save_all: bool,
    save_scratch: bool,
    force: bool,
) -> RunOptions:
    """Build a ``RunOptions`` from the shared job flags (run + pipeline)."""
    from pya3eda.runner.executor import RunOptions

    return RunOptions(
        cpus=cpus,
        parallel=parallel,
        parallel_type=parallel_type,
        memory=memory,
        mem_per_cpu=mem_per_cpu,
        walltime=walltime,
        partition=partition,
        version=version,
        qcsetup=qcsetup,
        scratch=scratch,
        nodename=nodename,
        exclude=exclude,
        save=save,
        save_all=save_all,
        save_scratch=save_scratch,
        force=force,
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def build(
    config_path: ConfigArg,
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Overwrite existing inputs.")
    ] = False,
    sp_strategy: Annotated[
        str, typer.Option("--sp-strategy", help="When to write SP inputs: always, smart, never.")
    ] = "smart",
    template_dir: TemplateDirOpt = Path("templates"),
) -> None:
    """Generate Q-Chem input files for all registered calculations."""
    with _errors():
        from pya3eda.builder.inputs import build_all

        registry, _ = _registry(config_path)
        build_all(
            registry,
            template_dir=template_dir,
            overwrite="all" if overwrite else None,
            sp_strategy=sp_strategy,
        )


@app.command()
def run(
    config_path: ConfigArg,
    criteria: Annotated[str, typer.Argument(help="Status filter for submission.")] = "NOFILE",
    backend: BackendOpt = "auto",
    max_cores: MaxCoresOpt = None,
    cpus: CpusOpt = 1,
    parallel: ParallelOpt = None,
    parallel_type: ParallelTypeOpt = "openmp",
    memory: MemoryOpt = None,
    mem_per_cpu: MemPerCpuOpt = None,
    walltime: TimeOpt = None,
    partition: PartitionOpt = None,
    version: VersionOpt = "6.2.1",
    qcsetup: QcsetupOpt = None,
    scratch: ScratchOpt = None,
    nodename: NodeOpt = None,
    exclude: ExcludeOpt = None,
    save: SaveOpt = False,
    save_all: SaveAllOpt = False,
    save_scratch: SaveScratchOpt = False,
    force: ForceOpt = False,
    wait: Annotated[
        bool, typer.Option("--wait", help="Block until all jobs finish (implied for local).")
    ] = False,
) -> None:
    """Submit calculations via the local or SLURM backend."""
    with _errors():
        from pya3eda.runner.executor import run_all

        registry, _ = _registry(config_path)
        run_all(
            registry,
            criteria=criteria,
            backend=backend,
            max_cores=max_cores,
            wait=wait,
            options=_run_options(
                cpus=cpus,
                parallel=parallel,
                parallel_type=parallel_type,
                memory=memory,
                mem_per_cpu=mem_per_cpu,
                walltime=walltime,
                partition=partition,
                version=version,
                qcsetup=qcsetup,
                scratch=scratch,
                nodename=nodename,
                exclude=exclude,
                save=save,
                save_all=save_all,
                save_scratch=save_scratch,
                force=force,
            ),
        )


@app.command()
def status(config_path: ConfigArg) -> None:
    """Print a status report for all registered calculations."""
    with _errors():
        from pya3eda.status.checker import check_all

        registry, _ = _registry(config_path)
        check_all(registry)


@app.command()
def extract(
    config_path: ConfigArg,
    criteria: Annotated[str, typer.Option("--criteria", help="Status filter.")] = "SUCCESSFUL",
    no_plots: NoPlotsOpt = False,
) -> None:
    """Extract data, assemble profiles, export CSVs, and generate plots."""
    with _errors():
        from pya3eda.extractor.data import extract_all
        from pya3eda.pipeline import finalize_extraction

        registry, base_dir = _registry(config_path)
        extracted = extract_all(registry, criteria=criteria)
        finalize_extraction(registry, extracted, base_dir, plots=not no_plots)


@app.command()
def pipeline(
    config_path: ConfigArg,
    backend: BackendOpt = "auto",
    max_cores: MaxCoresOpt = None,
    cpus: CpusOpt = 1,
    parallel: ParallelOpt = None,
    parallel_type: ParallelTypeOpt = "openmp",
    memory: MemoryOpt = None,
    mem_per_cpu: MemPerCpuOpt = None,
    walltime: TimeOpt = None,
    partition: PartitionOpt = None,
    version: VersionOpt = "6.2.1",
    qcsetup: QcsetupOpt = None,
    scratch: ScratchOpt = None,
    nodename: NodeOpt = None,
    exclude: ExcludeOpt = None,
    save: SaveOpt = False,
    save_all: SaveAllOpt = False,
    save_scratch: SaveScratchOpt = False,
    force: ForceOpt = False,
    template_dir: TemplateDirOpt = Path("templates"),
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Overwrite existing inputs.")
    ] = False,
    no_plots: NoPlotsOpt = False,
) -> None:
    """Run the full dependency-aware pipeline (build → OPT → SP → extract)."""
    with _errors():
        from pya3eda.pipeline import run_pipeline

        registry, base_dir = _registry(config_path)
        run_pipeline(
            registry,
            base_dir,
            backend=backend,
            max_cores=max_cores,
            options=_run_options(
                cpus=cpus,
                parallel=parallel,
                parallel_type=parallel_type,
                memory=memory,
                mem_per_cpu=mem_per_cpu,
                walltime=walltime,
                partition=partition,
                version=version,
                qcsetup=qcsetup,
                scratch=scratch,
                nodename=nodename,
                exclude=exclude,
                save=save,
                save_all=save_all,
                save_scratch=save_scratch,
                force=force,
            ),
            template_dir=template_dir,
            overwrite="all" if overwrite else None,
            plots=not no_plots,
        )


_COMMANDS = frozenset({"build", "run", "status", "extract", "pipeline"})


def _default_command(argv: list[str]) -> list[str]:
    """Default to ``status`` when the first positional is a config path, not a command.

    Restores the pre-Typer shorthand ``pya3eda CONFIG`` (== ``pya3eda status CONFIG``).
    ``--help`` / ``--version`` and explicit commands pass through unchanged.
    """
    if any(a in ("-h", "--help", "--version") for a in argv):
        return argv
    i = 0
    while i < len(argv):
        if argv[i] == "--log":
            i += 2  # skip the global option and its value
            continue
        if argv[i].startswith("-"):
            i += 1
            continue
        # First positional: a known command runs as-is; anything else → status CONFIG.
        return argv if argv[i] in _COMMANDS else [*argv[:i], "status", *argv[i:]]
    return argv  # only options / empty → let Typer handle (no_args_is_help, --version)


def main() -> None:
    """Console-script entry point."""
    import sys

    app(args=_default_command(sys.argv[1:]))
