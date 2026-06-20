# Installation

## Requirements

- Python ≥ 3.11
- A working Q-Chem installation (for running calculations)

## Install from PyPI

```bash
pip install pya3eda
```

## Install from GitHub

The latest `main`:

```bash
pip install git+https://github.com/sterling-group/PyA3EDA.git
```

## Development Install

An editable clone with the dev + docs tooling (tests, ruff, mypy, mkdocs):

```bash
git clone https://github.com/sterling-group/PyA3EDA.git
cd PyA3EDA
pip install -e ".[dev]"
```

## Building the Documentation Locally

```bash
pip install -e ".[docs]"
mkdocs serve
```

Then open <http://127.0.0.1:8000> in your browser.

## Dependencies

PyA3EDA depends on:

| Package    | Purpose                          |
|------------|----------------------------------|
| pydantic   | Configuration validation         |
| pandas     | Tabular data export              |
| pyyaml     | YAML config parsing              |
| matplotlib | Energy profile and bar plots     |
| numpy      | Numerical operations             |
| typer      | Command-line interface           |

---

**Next:** [Configuration](configuration.md) — define your reaction, catalysts, and theory levels.
