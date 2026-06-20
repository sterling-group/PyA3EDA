# CLI Reference

PyA3EDA provides the `pya3eda` command with the subcommands below. The staged
commands (`build` → `run` → `status` → `extract`) can be run individually, or the
`pipeline` subcommand chains them into one dependency-aware run.

## General Usage

```bash
pya3eda COMMAND CONFIG_FILE [OPTIONS]
```

Running `pya3eda` with no command prints the help listing every command. Each
command takes the YAML config as its first argument.

---

## `build` — Generate Input Files

Create Q-Chem input files for all calculations defined by the configuration.

```bash
pya3eda build config.yaml [--overwrite MODE] [--sp-strategy STRATEGY] [--template-dir DIR]
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
pya3eda run config.yaml [CRITERIA] [--backend auto|local|slurm] [--max-cores N] [--wait] [JOB OPTIONS...]
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

## `pipeline` — Full Dependency-Aware Run

One command that chains the whole workflow: build OPT inputs → submit them under
the `--max-cores` budget → as each OPT *succeeds*, build its single-point input(s)
from the optimised geometry and submit them as cores free → extract each result
live → assemble profiles / ΔΔ‡ / CSVs / plots when all finish. Resumable —
calculations already SUCCESSFUL are skipped (an already-done OPT goes straight to
its SPs).

```bash
pya3eda pipeline config.yaml [--max-cores N] [--template-dir DIR] [--overwrite] [--no-plots] [JOB OPTIONS...]
```

| Option           | Default     | Description                                  |
|------------------|-------------|----------------------------------------------|
| `--max-cores`    | CPU count   | Core budget for throttled submission         |
| `--template-dir` | `templates` | Template directory (OPT/SP inputs are built) |
| `--overwrite`    | off         | Rebuild existing input files                 |
| `--no-plots`     | off         | Skip plot generation in the final extract    |

Accepts the same backend (`--backend`) and job options as `run`. The local backend
runs jobs in the background under the core budget; SLURM submits via `sbatch` and
polls `squeue`.

---

## `status` — Check Progress

Display a status report for all calculations.

```bash
pya3eda status config.yaml
```

Status values: `SUCCESSFUL`, `CRASH`, `running`, `terminated`, `nofile`,
`empty`, `absent`, `VALIDATION`.

---

## `extract` — Extract and Analyse

Extract energies from completed calculations, assemble profiles, compute
barrier decompositions, export CSVs, and generate plots.

```bash
pya3eda extract config.yaml [--criteria CRITERIA] [--no-plots]
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
