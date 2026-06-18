# PyA3EDA

[![CI](https://github.com/sterling-group/PyA3EDA/actions/workflows/ci.yml/badge.svg)](https://github.com/sterling-group/PyA3EDA/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](https://github.com/sterling-group/PyA3EDA/actions/workflows/ci.yml)
[![Docs](https://github.com/sterling-group/PyA3EDA/actions/workflows/docs.yml/badge.svg)](https://sterling-group.github.io/PyA3EDA/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/license-GPL%20v3-blue.svg)](LICENSE)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**Python automation for Asymmetrically-constrained Adiabatic ALMO-EDA (A3EDA)**

PyA3EDA automates the full computational workflow for
**Asymmetrically-constrained Adiabatic ALMO-EDA (A3EDA)** calculations in
[Q-Chem](https://www.q-chem.com/).  A3EDA decomposes catalytic barriers
into physically meaningful contributions — frozen-density (FRZ),
polarisation (POL), and charge-transfer (CT) on the electronic-energy
surface, plus an additional confinement (NI) term on the Gibbs-energy
surface — revealing *how* a catalyst lowers (or raises) a reaction barrier.

> **Reference** — The A3EDA method is described in:
> M. G. S. Weiss, A. J. Sterling, *manuscript in preparation*.
> (DOI to be added upon publication.)

---

## Features

| | |
|---|---|
| **A3EDA barrier decomposition** | Decomposes ΔΔG‡ into FRZ, POL, and CT on the E surface; adds a confinement (NI) term on the G surface to separate the cost of bringing fragments together from genuine interaction contributions. |
| **Non-interacting reference** | Separates the confinement cost of bringing fragments together from genuine catalyst–substrate interactions via a reconstructed non-interacting surface. |
| **Configuration-driven** | One YAML file defines theory levels, basis sets, catalysts, and species. Everything else is derived automatically. |
| **Candidate selection** | Automatically picks the lowest-energy preTS / postTS complex when multiple compositions exist. |
| **Local & SLURM execution** | Runs Q-Chem jobs on a laptop (background `bash`) or an HPC cluster (`sbatch`), auto-detected, throttled by a `--max-cores` budget; new backends slot in behind the `ExecutionBackend` protocol. |
| **Publication-ready plots** | Energy-profile diagrams and grouped ΔΔ‡ barplots exported as SVG. |

## Workflow

```text
config.yaml
    │
    ▼
┌────────┐    ┌────────┐    ┌────────┐    ┌──────────┐
│ build  │ →  │  run   │ →  │ status │ →  │ extract  │
│ inputs │    │  jobs  │    │ check  │    │ & plot   │
└────────┘    └────────┘    └────────┘    └──────────┘
  Q-Chem        SLURM        progress      CSVs, SVGs,
  .in files     submit       report        profiles
```

## Installation

```bash
pip install .
```

For development (with tests and documentation tooling):

```bash
pip install -e ".[dev,docs]"
```

> **Prerequisite** — Q-Chem must be available on the target HPC cluster.
> PyA3EDA generates and parses Q-Chem files but does not bundle the
> electronic-structure code itself.

## Quick start

```bash
# 1. Generate Q-Chem input files from templates + config
pya3eda config.yaml build

# 2. Submit jobs to the cluster
pya3eda config.yaml run

# 3. Check calculation progress
pya3eda config.yaml status

# 4. Extract data, export CSVs, and generate plots
pya3eda config.yaml extract
```

Each subcommand is incremental — you can re-run `extract` after new jobs
finish without repeating earlier steps.

See [`examples/diels-alder/`](examples/diels-alder/) for a complete
worked example (Lewis-acid catalysed Diels–Alder reaction with BF₃).

## Project layout

```text
src/pya3eda/
├── cli.py              # command-line entry point
├── config.py           # YAML → validated Pydantic models
├── registry.py         # enumerates all expected calculations
├── ids.py              # CalcID, ProfileID, data containers
├── builder/            # Q-Chem input file generation
├── runner/             # HPC submission backends
├── status/             # calculation progress checking
├── extractor/          # output parsing → profiles → ΔΔ‡
├── exporter/           # CSV + XYZ export
└── plotter/            # energy-profile & barplot SVGs
```

## Documentation

Full documentation (user guide, theory, API reference, developer guide)
is available at **<https://sterling-group.github.io/PyA3EDA/>**.

## License

This project is licensed under the
[GNU General Public License v3.0](LICENSE).
