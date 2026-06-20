"""Golden SLURM scripts — the byte-for-byte baseline for `test_slurm_golden`.

Captured from the original ``qqchem.slurm.generate_slurm_script`` and kept
inline (rather than as files under ``tests/data/``) so the whole fixture is
one importable module.
"""

from __future__ import annotations

GOLDENS: dict[str, str] = {
    "base_openmp": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=sterling
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4000
#SBATCH --time=7-00:00:00

# Load modules
module purge
module load qchem/6.2.1
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/scratch/ganymede2/$USER
export scrname=q${SLURM_JOB_ID}${random_str}

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
echo $PWD

qchem job.in job.out $scrname || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"


# Clean up scratch directory
if [ -n "$scrname" ]; then
  rm -rf "$QCSCRATCH/$scrname" || { echo "Warning: Failed to remove scratch directory"; }
fi
""",
    "cluster_juno": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=3000
#SBATCH --time=2-00:00:00

# Load modules
module purge
module load qchem/6.2.1
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/scratch/juno/$USER
export scrname=q${SLURM_JOB_ID}${random_str}

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
echo $PWD

qchem job.in job.out $scrname || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"


# Clean up scratch directory
if [ -n "$scrname" ]; then
  rm -rf "$QCSCRATCH/$scrname" || { echo "Warning: Failed to remove scratch directory"; }
fi
""",
    "envvars": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=sterling
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4000
#SBATCH --time=7-00:00:00

# Load modules
module purge
module load qchem/6.2.1

# Set cluster-specific environment variables
export QC=1
export FOO=bar
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/scratch/ganymede2/$USER
export scrname=q${SLURM_JOB_ID}${random_str}

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
echo $PWD

qchem job.in job.out $scrname || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"


# Clean up scratch directory
if [ -n "$scrname" ]; then
  rm -rf "$QCSCRATCH/$scrname" || { echo "Warning: Failed to remove scratch directory"; }
fi
""",
    "exclude": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=sterling
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4000
#SBATCH --time=7-00:00:00
#SBATCH --exclude=g-07-02,g-07-03

# Load modules
module purge
module load qchem/6.2.1
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/scratch/ganymede2/$USER
export scrname=q${SLURM_JOB_ID}${random_str}

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
echo $PWD

qchem job.in job.out $scrname || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"


# Clean up scratch directory
if [ -n "$scrname" ]; then
  rm -rf "$QCSCRATCH/$scrname" || { echo "Warning: Failed to remove scratch directory"; }
fi
""",
    "nodelist": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=sterling
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4000
#SBATCH --time=7-00:00:00
#SBATCH --nodelist=g-01-01

# Load modules
module purge
module load qchem/6.2.1
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/scratch/ganymede2/$USER
export scrname=q${SLURM_JOB_ID}${random_str}

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
echo $PWD

qchem job.in job.out $scrname || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"


# Clean up scratch directory
if [ -n "$scrname" ]; then
  rm -rf "$QCSCRATCH/$scrname" || { echo "Warning: Failed to remove scratch directory"; }
fi
""",
    "openmp_cpus4": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=sterling
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=4000
#SBATCH --time=7-00:00:00

# Load modules
module purge
module load qchem/6.2.1
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/scratch/ganymede2/$USER
export scrname=q${SLURM_JOB_ID}${random_str}

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
export OMP_NUM_THREADS=4
echo $PWD

qchem -nt 4 job.in job.out $scrname || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"


# Clean up scratch directory
if [ -n "$scrname" ]; then
  rm -rf "$QCSCRATCH/$scrname" || { echo "Warning: Failed to remove scratch directory"; }
fi
""",
    "openmpi": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=sterling
#SBATCH --nodes=1
#SBATCH --ntasks=2
#SBATCH --cpus-per-task=2
#SBATCH --mem-per-cpu=4000
#SBATCH --time=7-00:00:00

# Load modules
module purge
module load qchem/6.2.1

# Load MPI modules
module load gnu12/12.3.0
module load openmpi4/4.1.6
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/scratch/ganymede2/$USER
export scrname=q${SLURM_JOB_ID}${random_str}

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
export OMP_NUM_THREADS=2
echo $PWD

qchem -mpi -np 2 -nt 2 job.in job.out $scrname || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"


# Clean up scratch directory
if [ -n "$scrname" ]; then
  rm -rf "$QCSCRATCH/$scrname" || { echo "Warning: Failed to remove scratch directory"; }
fi
""",
    "openmpi_serial": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=sterling
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4000
#SBATCH --time=7-00:00:00

# Load modules
module purge
module load qchem/6.2.1

# Load MPI modules
module load gnu12/12.3.0
module load openmpi4/4.1.6
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/scratch/ganymede2/$USER
export scrname=q${SLURM_JOB_ID}${random_str}

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
echo $PWD

qchem -mpi -np 4 job.in job.out $scrname || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"


# Clean up scratch directory
if [ -n "$scrname" ]; then
  rm -rf "$QCSCRATCH/$scrname" || { echo "Warning: Failed to remove scratch directory"; }
fi
""",
    "qcsetup": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=sterling
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4000
#SBATCH --time=7-00:00:00

# Load modules
module purge

# Source qcsetup file
source /home/u/qcsetup.sh
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/scratch/ganymede2/$USER
export scrname=q${SLURM_JOB_ID}${random_str}

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
echo $PWD

qchem job.in job.out $scrname || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"


# Clean up scratch directory
if [ -n "$scrname" ]; then
  rm -rf "$QCSCRATCH/$scrname" || { echo "Warning: Failed to remove scratch directory"; }
fi
""",
    "save": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=sterling
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4000
#SBATCH --time=7-00:00:00

# Load modules
module purge
module load qchem/6.2.1
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/scratch/ganymede2/$USER
export scrname=q${SLURM_JOB_ID}${random_str}

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
echo $PWD

qchem job.in job.out $scrname || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"

# Copy saved files back to original directory
if [ -n "$scrname" ] && [ -d "$QCSCRATCH/$scrname" ]; then
  cp -r "$QCSCRATCH/$scrname" "$ORIG/job_scratch" || { echo "Error: Failed to copy saved files"; exit 1; }
  echo "Copied $QCSCRATCH/$scrname to $ORIG/job_scratch"
fi

# Clean up scratch directory
if [ -n "$scrname" ]; then
  rm -rf "$QCSCRATCH/$scrname" || { echo "Warning: Failed to remove scratch directory"; }
fi
""",
    "save_all": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=sterling
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4000
#SBATCH --time=7-00:00:00

# Load modules
module purge
module load qchem/6.2.1
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/scratch/ganymede2/$USER
export scrname=q${SLURM_JOB_ID}${random_str}

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
echo $PWD

qchem -save job.in job.out $scrname || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"

# Copy saved files back to original directory
if [ -n "$scrname" ] && [ -d "$QCSCRATCH/$scrname" ]; then
  cp -r "$QCSCRATCH/$scrname" "$ORIG/job_scratch" || { echo "Error: Failed to copy saved files"; exit 1; }
  echo "Copied $QCSCRATCH/$scrname to $ORIG/job_scratch"
fi

# Clean up scratch directory
if [ -n "$scrname" ]; then
  rm -rf "$QCSCRATCH/$scrname" || { echo "Warning: Failed to remove scratch directory"; }
fi
""",
    "save_scratch": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=sterling
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4000
#SBATCH --time=7-00:00:00

# Load modules
module purge
module load qchem/6.2.1
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/scratch/ganymede2/$USER
export scrname=q${SLURM_JOB_ID}${random_str}

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
echo $PWD

qchem job.in job.out $scrname || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"

echo "Not deleting scratch directory due to --save-scratch option"
""",
    "save_scratch_custom": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=sterling
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4000
#SBATCH --time=7-00:00:00

# Load modules
module purge
module load qchem/6.2.1
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/tmp/myscratch

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
echo $PWD

qchem job.in job.out  || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"

echo "Not deleting scratch directory due to --save-scratch option"
""",
    "scratch_set": """\
#!/bin/bash
#SBATCH --export=ALL
#SBATCH --job-name=job
#SBATCH --output=job.err
#SBATCH --error=job.err
#SBATCH --partition=sterling
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4000
#SBATCH --time=7-00:00:00

# Load modules
module purge
module load qchem/6.2.1
export ORIG=$PWD
random_str=$(tr -dc a-z0-9 </dev/urandom | head -c 3)
export QCSCRATCH=/tmp/myscratch

# Start Q-Chem job
echo "Starting Q-Chem job with SLURM job ID: $SLURM_JOB_ID"
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $ORIG"
echo "SCRATCH_DIR is set to $QCSCRATCH/$scrname"
echo "Cluster: $CLUSTER_NAME"

# Record start time
start_time=$(date +%s)

# Run Q-Chem job
echo $PWD

qchem job.in job.out  || { echo "Warning: Q-Chem execution might have failed."; }

# Record end time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Q-Chem job finished at $(date)"
echo "Elapsed time: $elapsed seconds"


# Clean up scratch directory
if [ -n "$scrname" ]; then
  rm -rf "$QCSCRATCH/$scrname" || { echo "Warning: Failed to remove scratch directory"; }
fi
""",
}
