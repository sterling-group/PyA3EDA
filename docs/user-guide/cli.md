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

Submit Q-Chem jobs via a pluggable backend.

```bash
pya3eda config.yaml run [--backend BACKEND] [--criteria CRITERIA] [EXTRA_FLAGS...]
```

| Option       | Default      | Description                              |
|-------------|-------------|------------------------------------------|
| `--backend`  | `qqchem`    | Submission backend (`qqchem` for SLURM)  |
| `--criteria` | `all`       | Status filter for which jobs to submit    |

Extra flags after `--` are forwarded to the backend.

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
