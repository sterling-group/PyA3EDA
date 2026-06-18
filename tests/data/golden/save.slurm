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
