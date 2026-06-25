# Cluster Configuration

`pya3eda run` and `pya3eda pipeline` submit Q-Chem jobs through a SLURM (or local)
backend. To generate correct `#SBATCH` headers and module/environment setup for a
given HPC system, PyA3EDA reads a **cluster configuration file** that describes one
or more clusters. This file is separate from the per-project `config.yaml` — it
describes the *machine*, not the *reaction*.

## File location

PyA3EDA looks for the file in this order:

1. `$QQCHEM_CLUSTERS` — a path to a YAML file (highest priority).
2. `~/.config/qqchem/clusters.yaml` — the default location.

If no file is found, `run`/`pipeline` fail with a clear message and
[exit code 8](cli.md#exit-codes) (`ClusterConfigError`).

## Cluster detection

When a run starts, the active cluster is chosen by:

1. `$CLUSTER_NAME` (lower-cased) if it matches an entry in the file;
2. otherwise the SLURM `ClusterName` from `scontrol show config`;
3. otherwise the **first** entry in the file (with a warning).

## Schema

Each top-level key is a cluster name. Every cluster is validated on load, so a
malformed file fails fast rather than at submission time.

| Field             | Type                       | Description                                            |
| ----------------- | -------------------------- | ------------------------------------------------------ |
| `default_partition` | str                      | Default SLURM partition (`#SBATCH --partition`).       |
| `mem_per_cpu`     | int                        | Default memory per CPU in MB.                          |
| `default_time`    | str                        | Default wall time (e.g. `"7-00:00:00"`).               |
| `scratch_base_dir`| str                        | Base scratch directory for Q-Chem (`$QCSCRATCH`).      |
| `exclude_nodes`   | mapping partition → list   | Optional nodes to exclude, per partition.             |
| `qchem_versions`  | mapping version → setup    | One entry per selectable `--qchem-version`.            |

Each `qchem_versions` entry has:

| Field          | Type        | Description                                     |
| -------------- | ----------- | ----------------------------------------------- |
| `module_loads` | list of str | `module load …` commands to run.                |
| `qcsetup_file` | str         | Optional path to a `qcsetup` file to `source`.  |
| `environment`  | list of str | Extra environment-variable export lines.        |
| `mpi_support`  | bool        | Whether this version supports MPI (`--parallel-type openmpi`). |
| `mpi_modules`  | list of str | MPI modules to load when running with MPI.      |

## Example

```yaml
# ~/.config/qqchem/clusters.yaml
# One entry per cluster. Cluster name is auto-detected via $CLUSTER_NAME or
# `scontrol show config`.

g2:
  default_partition: sterling
  mem_per_cpu: 4000            # MB
  default_time: "7-00:00:00"
  scratch_base_dir: "/scratch/ganymede2/$USER"
  exclude_nodes:
    sterling:
      - g-07-02
  qchem_versions:
    "6.2.1":
      module_loads: ["module load qchem/6.2.1"]
      qcsetup_file: ""
      environment: []
      mpi_support: true
      mpi_modules: ["gnu12/12.3.0", "openmpi4/4.1.6"]
```

The chosen Q-Chem version is selected at run time with `--qchem-version` (default
`6.2.1`); pass `--qcsetup PATH` with `--qchem-version modqchem` to source a custom
setup file instead.

---

**Next:** [CLI Reference](cli.md) — every command and option.
