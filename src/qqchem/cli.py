"""Command-line interface for qqchem.

Usage (standalone)::

    qqchem [options] input_file

Usage (via pya3eda)::

    pya3eda config.yaml run [qqchem options ...]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from os import environ
from pathlib import Path

from qqchem.clusters import load_cluster_configs
from qqchem.qchem_input import adjust_mem_total, parse_mem_total, read_input_file
from qqchem.slurm import generate_slurm_script, submit_job


# ------------------------------------------------------------------
# Cluster detection
# ------------------------------------------------------------------


def detect_cluster() -> tuple[str, dict]:
    """Detect which cluster the script is running on.

    Detection hierarchy:
      1. ``CLUSTER_NAME`` environment variable
      2. SLURM ``ClusterName`` from ``scontrol``
      3. First entry in the config file
    """
    configs = load_cluster_configs()

    env_name = environ.get("CLUSTER_NAME", "").lower()
    if env_name:
        if env_name in configs:
            return env_name, configs[env_name]
        print(
            f"Warning: CLUSTER_NAME='{env_name}' not in clusters.yaml",
            file=sys.stderr,
        )

    try:
        result = subprocess.run(
            ["scontrol", "show", "config"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=5,
        )
        for line in result.stdout.split("\n"):
            if line.strip().startswith("ClusterName"):
                slurm_name = line.split("=")[1].strip().lower()
                if slurm_name in configs:
                    environ["CLUSTER_NAME"] = slurm_name
                    print(f"Detected SLURM cluster: {slurm_name}", file=sys.stderr)
                    return slurm_name, configs[slurm_name]
                print(
                    f"Warning: Detected SLURM cluster '{slurm_name}' not in clusters.yaml",
                    file=sys.stderr,
                )
                break
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        IndexError,
        TimeoutError,
    ) as exc:
        print(f"Warning: Could not detect cluster from SLURM: {exc}", file=sys.stderr)

    # Fall back to first entry in config
    first = next(iter(configs))
    print(f"Warning: Falling back to '{first}' cluster settings", file=sys.stderr)
    return first, configs[first]


# ------------------------------------------------------------------
# Argument parser (exposed for reuse by pya3eda)
# ------------------------------------------------------------------


def build_parser(
    cluster_config: dict | None = None,
) -> argparse.ArgumentParser:
    """Build the qqchem argument parser.

    Parameters
    ----------
    cluster_config
        Cluster configuration dict used to set defaults.  When *None*,
        ``detect_cluster`` is called.
    """
    if cluster_config is None:
        _, cluster_config = detect_cluster()

    default_partition = cluster_config["default_partition"]
    default_time = cluster_config["default_time"]

    parser = argparse.ArgumentParser(
        prog="qqchem",
        description="Submit Q-Chem job to SLURM",
    )
    parser.add_argument("input_file", help="Q-Chem input file")

    parser.add_argument(
        "-c", "--cpus", type=int, help="Number of CPUs per task (threads)"
    )
    parser.add_argument("-p", "--parallel", type=int, help="Number of MPI processes")
    parser.add_argument(
        "-m",
        "--memory",
        type=int,
        help="Set or overwrite mem_total in Q-Chem input file (MB)",
    )
    parser.add_argument("-M", "--mem-per-cpu", type=int, help="Memory per CPU in MB")
    parser.add_argument(
        "-t",
        "--time",
        dest="walltime",
        default=default_time,
        help=f"Wall time in SLURM format (default: {default_time})",
    )
    parser.add_argument(
        "--partition",
        "-q",
        default=default_partition,
        help=f"Partition name (default: {default_partition})",
    )
    parser.add_argument("--name", "-n", dest="job_name", help="Job name")
    parser.add_argument("--output", "-o", help="Output file name")
    parser.add_argument("--error", "-e", help="Error file name")
    parser.add_argument("--scratch", "-s", type=str, help="Scratch directory name")
    parser.add_argument(
        "--dryrun",
        "-d",
        action="store_true",
        default=False,
        help="Create script without submitting",
    )
    parser.add_argument(
        "--save-scratch", action="store_true", help="Keep scratch directory"
    )
    parser.add_argument("--node", "-N", dest="nodename", help="Target node")
    parser.add_argument("--exclude", "-x", help="Nodes to exclude (comma-separated)")
    parser.add_argument(
        "--force",
        "-F",
        action="store_true",
        help="Proceed despite mismatches",
    )
    parser.add_argument(
        "--version",
        "-v",
        type=str,
        default="6.2.1",
        help="Q-Chem version (default: 6.2.1)",
    )
    parser.add_argument("--qcsetup", type=str, help="Path to custom qcsetup file")
    parser.add_argument(
        "--parallel-type",
        "-P",
        type=str,
        choices=["openmp", "openmpi"],
        default="openmp",
        help="Parallelism mode (default: openmp)",
    )
    parser.add_argument(
        "--save", action="store_true", help="Save essential scratch files"
    )
    parser.add_argument(
        "--save-all", "-f", action="store_true", help="Save all scratch files"
    )
    parser.add_argument(
        "--save-slurm", "-k", action="store_true", help="Keep SLURM script"
    )

    return parser


# ------------------------------------------------------------------
# Processing helpers
# ------------------------------------------------------------------


def _process_parallel(args: argparse.Namespace) -> tuple[int, int]:
    """Return ``(cpus, qchem_processors)``."""
    if args.parallel_type == "openmpi":
        if args.parallel is None:
            print(
                "Error: --parallel (-p) is required with --parallel-type openmpi.",
                file=sys.stderr,
            )
            sys.exit(1)
        return (args.cpus or 1), args.parallel

    return (args.cpus or 1), 1


def _check_memory(
    args: argparse.Namespace,
    mem_total_values: list[int],
    cpus: int,
    qchem_processors: int,
    mem_per_cpu: int,
) -> None:
    """Exit if any mem_total exceeds total SLURM memory."""
    if args.parallel_type == "openmpi":
        total = qchem_processors * cpus * mem_per_cpu
    else:
        total = cpus * mem_per_cpu

    for idx, val in enumerate(mem_total_values, 1):
        if val > total:
            print(
                f"Error: mem_total ({val} MB) in $rem block {idx} exceeds "
                f"total SLURM memory ({total} MB).",
                file=sys.stderr,
            )
            sys.exit(1)


def _process_memory(
    args: argparse.Namespace,
    lines: list[str],
    cpus: int,
    qchem_processors: int,
    input_path: Path,
    mem_per_cpu: int,
) -> tuple[list[int], list[str]]:
    """Handle memory settings and adjust the input file when ``--memory`` is given."""
    if args.memory is not None:
        new_lines, changed = adjust_mem_total(lines, args.memory)
        if changed:
            input_path.write_text("".join(new_lines))
            print(
                f"Updated mem_total to {args.memory} MB in '{input_path}'.",
                file=sys.stderr,
            )
            lines = new_lines

        mem_total_values = parse_mem_total(lines)
        _check_memory(args, mem_total_values, cpus, qchem_processors, mem_per_cpu)
    else:
        mem_total_values = parse_mem_total(lines)
        if mem_total_values:
            _check_memory(args, mem_total_values, cpus, qchem_processors, mem_per_cpu)

    return mem_total_values, lines


def _resolve_version(
    args: argparse.Namespace,
    cluster_name: str,
    cluster_config: dict,
) -> tuple[list[str], str, list[str], bool, list[str]]:
    """Return ``(module_cmds, qcsetup, env_vars, mpi_support, mpi_modules)``."""
    versions = cluster_config["qchem_versions"]

    if args.version == "modqchem":
        if not args.qcsetup:
            print(
                "Error: --qcsetup is required with version 'modqchem'.", file=sys.stderr
            )
            sys.exit(1)
        return [], args.qcsetup, [], False, []

    if args.version not in versions:
        available = list(versions) + ["modqchem"]
        print(
            f"Error: Q-Chem version '{args.version}' unknown for '{cluster_name}'. "
            f"Available: {', '.join(available)}.",
            file=sys.stderr,
        )
        sys.exit(1)

    info = versions[args.version]
    module_cmds = info.get("module_loads", [])
    qcsetup = info.get("qcsetup_file", "")
    env_vars = info.get("environment", [])
    mpi_support = info.get("mpi_support", False)
    mpi_modules = info.get("mpi_modules", [])

    if args.qcsetup and args.version != "modqchem":
        print(f"Using custom qcsetup: {args.qcsetup}", file=sys.stderr)
        qcsetup = args.qcsetup
        env_vars = []

    return module_cmds, qcsetup, env_vars, mpi_support, mpi_modules


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def run(args: argparse.Namespace, cluster_name: str | None = None) -> None:
    """Execute qqchem from a pre-parsed *args* namespace.

    This is the programmatic entry point used by ``pya3eda run``.
    """
    if cluster_name is None:
        cluster_name, cluster_config = detect_cluster()
    else:
        configs = load_cluster_configs()
        cluster_config = configs[cluster_name]

    mem_per_cpu = getattr(args, "mem_per_cpu", None) or cluster_config["mem_per_cpu"]

    input_path = Path(args.input_file)
    lines = read_input_file(input_path)

    cpus, qchem_processors = _process_parallel(args)
    _mem_values, lines = _process_memory(
        args, lines, cpus, qchem_processors, input_path, mem_per_cpu
    )

    module_cmds, qcsetup, env_vars, mpi_support, mpi_modules = _resolve_version(
        args, cluster_name, cluster_config
    )

    # Combine user and config node exclusions
    exclude_config = cluster_config.get("exclude_nodes", {})
    partition_excludes = exclude_config.get(args.partition, [])
    exclude_nodes = args.exclude
    if partition_excludes:
        cfg_str = ",".join(partition_excludes)
        exclude_nodes = f"{exclude_nodes},{cfg_str}" if exclude_nodes else cfg_str

    job_name = args.job_name or input_path.stem
    output_file = args.output or f"{input_path.stem}.out"
    error_file = args.error or f"{input_path.stem}.err"

    slurm_script = generate_slurm_script(
        input_path=input_path,
        job_name=job_name,
        output_file=output_file,
        error_file=error_file,
        partition=args.partition,
        cpus=cpus,
        qchem_processors=qchem_processors,
        mem_per_cpu=mem_per_cpu,
        walltime=args.walltime,
        parallel_type=args.parallel_type,
        module_load_commands=module_cmds,
        environment_vars=env_vars,
        qcsetup_file=qcsetup,
        mpi_support=mpi_support,
        mpi_modules=mpi_modules,
        scratch=args.scratch,
        scratch_base_dir=cluster_config["scratch_base_dir"],
        nodename=args.nodename,
        exclude_nodes=exclude_nodes,
        save=args.save,
        save_all=args.save_all,
        save_scratch=args.save_scratch,
        force=args.force,
        cluster_name=cluster_name,
    )

    submit_job(slurm_script, dryrun=args.dryrun, save_slurm=args.save_slurm)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for standalone ``qqchem`` usage."""
    cluster_name, cluster_config = detect_cluster()
    parser = build_parser(cluster_config)
    args = parser.parse_args(argv)
    run(args, cluster_name=cluster_name)
