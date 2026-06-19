"""Calculation engines: the bash *run block* that actually invokes a program.

Q-Chem is the only engine today, but the :class:`Engine` Protocol keeps the
"what runs" concern separate from "where it runs" (the execution backend) and
from "how the SLURM wrapper is assembled" (:mod:`pya3eda.runner.script`), so a
future program slots in without touching the orchestrator (OCP/DIP).

The :class:`QChemEngine` run block is the body of the original ``qqchem`` SLURM
script verbatim (module loads → ``qcsetup`` → scratch setup → ``qchem`` →
timing → save/cleanup); :mod:`pya3eda.runner.script` prepends the ``#SBATCH``
header for SLURM and omits it for local runs.  The byte-for-byte equivalence to
the original generator is locked by ``tests/test_slurm_golden.py``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class JobSpec:
    """Everything needed to render one job's SLURM/bash script.

    Body fields (used by :meth:`Engine.run_block`) and header fields (used by
    :func:`pya3eda.runner.script.sbatch_header`) live together because they
    describe a single job; each consumer reads only the fields it needs.
    """

    input_path: Path | str
    output_file: str
    error_file: str
    job_name: str
    partition: str
    cpus: int
    qchem_processors: int
    mem_per_cpu: int
    walltime: str
    parallel_type: str
    scratch_base_dir: str
    cluster_name: str
    module_load_commands: list[str] = field(default_factory=list)
    environment_vars: list[str] = field(default_factory=list)
    qcsetup_file: str = ""
    mpi_support: bool = False
    mpi_modules: list[str] = field(default_factory=list)
    scratch: str | None = None
    nodename: str | None = None
    exclude_nodes: str | None = None
    save: bool = False
    save_all: bool = False
    save_scratch: bool = False
    force: bool = False


class Engine(Protocol):
    """A calculation program: produces the bash that runs one job."""

    name: str
    output_globs: tuple[str, ...]

    def run_block(self, spec: JobSpec) -> str:
        """Return the bash run block (everything after the ``#SBATCH`` header)."""
        ...


class QChemEngine:
    """Q-Chem engine — the run block is the original ``qqchem`` script body."""

    name = "qchem"
    # Q-Chem writes its ``.out`` directly in the submit directory, so there is
    # nothing to copy back beyond the optional scratch save handled in-band.
    output_globs: tuple[str, ...] = ()

    def run_block(self, spec: JobSpec) -> str:
        """Assemble the Q-Chem bash run block for *spec* (byte-identical to qqchem)."""
        b: list[str] = []
        b.append("\n# Load modules\n")
        b.append("module purge\n")
        for cmd in spec.module_load_commands:
            b.append(f"{cmd}\n")

        if spec.environment_vars:
            b.append("\n# Set cluster-specific environment variables\n")
            for var in spec.environment_vars:
                b.append(f"{var}\n")

        if spec.parallel_type == "openmpi":
            if not spec.mpi_support:
                print(
                    f"Warning: Q-Chem version may not support MPI on {spec.cluster_name}.",
                    file=sys.stderr,
                )
                if not spec.force:
                    print("Use --force to proceed anyway.", file=sys.stderr)
                    sys.exit(1)
            if spec.mpi_modules:
                b.append("\n# Load MPI modules\n")
                for mod in spec.mpi_modules:
                    b.append(f"module load {mod}\n")

        if spec.qcsetup_file:
            b.append(f"\n# Source qcsetup file\nsource {spec.qcsetup_file}\n")

        b.append("export ORIG=$PWD\n")
        b.append("random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)\n")
        if spec.scratch:
            b.append(f"export QCSCRATCH={spec.scratch}\n")
        else:
            b.append(f"export QCSCRATCH={spec.scratch_base_dir}\n")
            b.append("export scrname=q${SLURM_JOB_ID}${random_str}\n")

        b.append("\n# Start Q-Chem job\n")
        b.append('echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"\n')
        b.append('echo "Running on host $(hostname)"\n')
        b.append('echo "Time is $(date)"\n')
        b.append('echo "Directory is $ORIG"\n')
        b.append('echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"\n')
        b.append('echo "Cluster: $CLUSTER_NAME"\n')
        b.append("\n# Record start time\nstart_time=$(date +%s)\n")

        b.append("\n# Run Q-Chem job\n")

        qchem_cmd = "qchem "
        if spec.save_all:
            qchem_cmd += "-save "

        if spec.parallel_type == "openmpi":
            if spec.cpus > 1:
                b.append(f"export OMP_NUM_THREADS={spec.cpus}\n")
                qchem_cmd += f"-mpi -np {spec.qchem_processors} -nt {spec.cpus} "
            else:
                qchem_cmd += f"-mpi -np {spec.qchem_processors} "
        elif spec.parallel_type == "openmp" and spec.cpus > 1:
            b.append(f"export OMP_NUM_THREADS={spec.cpus}\n")
            qchem_cmd += f"-nt {spec.cpus} "

        qchem_cmd += f"{spec.input_path} {spec.output_file} "
        if not spec.scratch:
            qchem_cmd += "$scrname"

        b.append("echo $PWD\n\n")
        b.append(f'{qchem_cmd} || {{ echo "Warning: Q-Chem execution might have failed."; }}\n')

        b.append("\n# Record end time\n")
        b.append("end_time=$(date +%s)\n")
        b.append("elapsed=$((end_time - start_time))\n")
        b.append('echo "Q-Chem job finished at $(date)"\n')
        b.append('echo "Elapsed time: $elapsed seconds"\n\n')

        if spec.save or spec.save_all:
            b.append("# Copy saved files back to original directory\n")
            b.append('if [ -n "$scrname" ] && [ -d "$QCSCRATCH/$scrname" ]; then\n')
            b.append(
                f'  cp -r "$QCSCRATCH/$scrname" "$ORIG/{spec.job_name}_scratch" || '
                '{ echo "Error: Failed to copy saved files"; exit 1; }\n'
            )
            b.append(f'  echo "Copied $QCSCRATCH/$scrname to $ORIG/{spec.job_name}_scratch"\n')
            b.append("fi\n")

        if not spec.save_scratch:
            b.append("\n# Clean up scratch directory\n")
            b.append(
                'if [ -n "$scrname" ]; then\n'
                '  rm -rf "$QCSCRATCH/$scrname" || '
                '{ echo "Warning: Failed to remove scratch directory"; }\n'
                "fi\n"
            )
        else:
            b.append('echo "Not deleting scratch directory due to --save-scratch option"\n')

        return "".join(b)


ENGINES: dict[str, Engine] = {"qchem": QChemEngine()}
