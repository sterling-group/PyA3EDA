# CLI Reference

PyA3EDA provides the `pya3eda` command with four subcommands.

## General Usage

```bash
pya3eda CONFIG_FILE SUBCOMMAND [OPTIONS]
```

If no subcommand is given, `status` is used by default.

---

## `build` — Generate Input Files

Create Q-Chem input files for all calculations defined by the configuration.

```bash
pya3eda config.yaml build [--overwrite MODE] [--sp-strategy STRATEGY] [--template-dir DIR]
```

| Option            | Default    | Description                                |
|-------------------|-----------|--------------------------------------------|
| `--overwrite`     | *(none)*  | `all`, `CRASH`, or `terminated` — controls which existing inputs to regenerate |
| `--sp-strategy`   | `smart`   | `always` / `smart` / `never` — when to generate single-point inputs |
| `--template-dir`  | `templates` | Path to template directory               |

---

## `run` — Submit Calculations

Submit Q-Chem jobs locally (background `bash`) or to SLURM (`sbatch`).

```bash
pya3eda config.yaml run [CRITERIA] [--backend auto|local|slurm] [--max-cores N] [--wait] [JOB OPTIONS...]
```

| Option         | Default  | Description                                                        |
|----------------|----------|--------------------------------------------------------------------|
| `CRITERIA`     | `NOFILE` | Status filter for which jobs to submit (positional)                |
| `--backend`    | `auto`   | `auto` (SLURM if `sbatch` is present, else `local`), `local`, `slurm` |
| `--max-cores`  | CPU count | Core budget for throttled submission                              |
| `--wait`       | off      | Block until all jobs finish (implied for the `local` backend)      |

Job options (passed to the Q-Chem SLURM/bash script): `-c/--cpus`, `-p/--parallel`,
`-P/--parallel-type`, `-m/--memory`, `-M/--mem-per-cpu`, `-t/--time`, `-q/--partition`,
`-v/--version`, `--qcsetup`, `-s/--scratch`, `-N/--node`, `-x/--exclude`, `--save`,
`-f/--save-all`, `--save-scratch`, `-F/--force`.

The default SLURM path submits and returns; `--wait` (and the local backend) throttle
submissions to `--max-cores` and block until completion. Cluster settings are read from
`$QQCHEM_CLUSTERS` or `~/.config/qqchem/clusters.yaml`.

---

## `status` — Check Progress

Display a status report for all calculations.

```bash
pya3eda config.yaml status
```

Status values: `SUCCESSFUL`, `CRASH`, `running`, `terminated`, `nofile`,
`empty`, `absent`, `VALIDATION`.

---

## `extract` — Extract and Analyse

Extract energies from completed calculations, assemble profiles, compute
barrier decompositions, export CSVs, and generate plots.

```bash
pya3eda config.yaml extract [--criteria CRITERIA] [--no-plots]
```

| Option       | Default       | Description                          |
|-------------|--------------|--------------------------------------|
| `--criteria` | `SUCCESSFUL` | Status filter for extraction          |
| `--no-plots` | *(off)*      | Skip SVG plot generation             |

### Output Structure

```
results/
└── {method_key}/
    ├── opt_{method_key}.csv       # Raw OPT data
    ├── sp_{method_key}.csv        # Raw SP data
    ├── raw_data/                  # Per-profile CSVs
    ├── profiles/                  # Combined energy profiles
    ├── delta_delta/               # ΔΔ‡ decomposition CSVs
    ├── plots/                     # Energy profile SVGs
    ├── barplots/                  # Contribution barplot SVGs
    └── xyz_files/                 # Optimised geometries
```

---

**Next:** [Tutorial](tutorial.md) — run through a complete Diels–Alder example from config to plots.
