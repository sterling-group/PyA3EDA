"""SLURM script generation and job submission."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def generate_slurm_script(
    *,
    input_path: Path,
    job_name: str,
    output_file: str,
    error_file: str,
    partition: str,
    cpus: int,
    qchem_processors: int,
    mem_per_cpu: int,
    walltime: str,
    parallel_type: str,
    module_load_commands: list[str],
    environment_vars: list[str],
    qcsetup_file: str,
    mpi_support: bool,
    mpi_modules: list[str],
    scratch: str | None,
    scratch_base_dir: str,
    nodename: str | None,
    exclude_nodes: str | None,
    save: bool,
    save_all: bool,
    save_scratch: bool,
    force: bool,
    cluster_name: str,
) -> str:
    """Generate a SLURM submission script and return its filename."""
    slurm_script = f"{job_name}.slurm"
    slurm_path = Path(slurm_script)

    with slurm_path.open("w") as f:
        f.write("#!/bin/bash\n")
        f.write("#SBATCH --export=ALL\n")
        f.write(f"#SBATCH --job-name={job_name}\n")
        f.write(f"#SBATCH --output={error_file}\n")
        f.write(f"#SBATCH --error={error_file}\n")
        f.write(f"#SBATCH --partition={partition}\n")
        f.write("#SBATCH --nodes=1\n")
        f.write(f"#SBATCH --ntasks={qchem_processors}\n")
        f.write(f"#SBATCH --cpus-per-task={cpus}\n")
        f.write(f"#SBATCH --mem-per-cpu={mem_per_cpu}\n")
        f.write(f"#SBATCH --time={walltime}\n")

        if nodename:
            f.write(f"#SBATCH --nodelist={nodename}\n")
        if exclude_nodes:
            f.write(f"#SBATCH --exclude={exclude_nodes}\n")

        f.write("\n# Load modules\n")
        f.write("module purge\n")
        for cmd in module_load_commands:
            f.write(f"{cmd}\n")

        if environment_vars:
            f.write("\n# Set cluster-specific environment variables\n")
            for var in environment_vars:
                f.write(f"{var}\n")

        if parallel_type == "openmpi":
            if not mpi_support:
                print(
                    f"Warning: Q-Chem version may not support MPI on {cluster_name}.",
                    file=sys.stderr,
                )
                if not force:
                    print("Use --force to proceed anyway.", file=sys.stderr)
                    sys.exit(1)
            if mpi_modules:
                f.write("\n# Load MPI modules\n")
                for mod in mpi_modules:
                    f.write(f"module load {mod}\n")

        if qcsetup_file:
            f.write(f"\n# Source qcsetup file\nsource {qcsetup_file}\n")

        f.write("export ORIG=$PWD\n")
        f.write("random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)\n")
        if scratch:
            f.write(f"export QCSCRATCH={scratch}\n")
        else:
            f.write(f"export QCSCRATCH={scratch_base_dir}\n")
            f.write("export scrname=q${SLURM_JOB_ID}${random_str}\n")

        f.write("\n# Start Q-Chem job\n")
        f.write('echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"\n')
        f.write('echo "Running on host $(hostname)"\n')
        f.write('echo "Time is $(date)"\n')
        f.write('echo "Directory is $ORIG"\n')
        f.write('echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"\n')
        f.write('echo "Cluster: $CLUSTER_NAME"\n')
        f.write("\n# Record start time\nstart_time=$(date +%s)\n")

        f.write("\n# Run Q-Chem job\n")

        qchem_cmd = "qchem "
        if save_all:
            qchem_cmd += "-save "

        if parallel_type == "openmpi":
            if cpus > 1:
                f.write(f"export OMP_NUM_THREADS={cpus}\n")
                qchem_cmd += f"-mpi -np {qchem_processors} -nt {cpus} "
            else:
                qchem_cmd += f"-mpi -np {qchem_processors} "
        elif parallel_type == "openmp" and cpus > 1:
            f.write(f"export OMP_NUM_THREADS={cpus}\n")
            qchem_cmd += f"-nt {cpus} "

        qchem_cmd += f"{input_path} {output_file} "
        if not scratch:
            qchem_cmd += "$scrname"

        f.write("echo $PWD\n\n")
        f.write(f'{qchem_cmd} || {{ echo "Warning: Q-Chem execution might have failed."; }}\n')

        f.write("\n# Record end time\n")
        f.write("end_time=$(date +%s)\n")
        f.write("elapsed=$((end_time - start_time))\n")
        f.write('echo "Q-Chem job finished at $(date)"\n')
        f.write('echo "Elapsed time: $elapsed seconds"\n\n')

        if save or save_all:
            f.write("# Copy saved files back to original directory\n")
            # Guard on a non-empty $scrname: a custom --scratch leaves it unset,
            # and "$QCSCRATCH/" would otherwise expand to the whole scratch dir.
            f.write('if [ -n "$scrname" ] && [ -d "$QCSCRATCH/$scrname" ]; then\n')
            f.write(
                f'  cp -r "$QCSCRATCH/$scrname" "$ORIG/{job_name}_scratch" || '
                '{ echo "Error: Failed to copy saved files"; exit 1; }\n'
            )
            f.write(f'  echo "Copied $QCSCRATCH/$scrname to $ORIG/{job_name}_scratch"\n')
            f.write("fi\n")

        if not save_scratch:
            f.write("\n# Clean up scratch directory\n")
            # Guard on a non-empty $scrname so a user-supplied --scratch directory
            # (which leaves $scrname unset) is never wiped by `rm -rf "$QCSCRATCH/"`.
            f.write(
                'if [ -n "$scrname" ]; then\n'
                '  rm -rf "$QCSCRATCH/$scrname" || '
                '{ echo "Warning: Failed to remove scratch directory"; }\n'
                "fi\n"
            )
        else:
            f.write('echo "Not deleting scratch directory due to --save-scratch option"\n')

    return slurm_script


def submit_job(slurm_script: str, *, dryrun: bool = False, save_slurm: bool = False) -> None:
    """Submit the SLURM script via ``sbatch``, or print it for dry runs."""
    if dryrun:
        print(f"Dry run: SLURM script written to {slurm_script}")
        return

    result = subprocess.run(
        ["sbatch", slurm_script],
        capture_output=True,
        text=True,
        check=True,
    )

    job_id = None
    for line in result.stdout.strip().split("\n"):
        if "Submitted batch job" in line:
            job_id = line.strip().split()[-1]
            break

    if job_id:
        print(f"Submitted job {job_id}")
    else:
        print("Error: Failed to parse job ID from sbatch output.", file=sys.stderr)
        sys.exit(1)

    if not save_slurm:
        path = Path(slurm_script)
        if path.exists():
            path.unlink()
