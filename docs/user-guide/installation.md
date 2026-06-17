# Installation

## Requirements

- Python ≥ 3.10
- A working Q-Chem installation (for running calculations)

## Install from Source

```bash
git clone https://github.com/sterling-group/PyA3EDA.git
cd PyA3EDA
pip install .
```

## Development Install

For an editable install with test dependencies:

```bash
pip install -e ".[test]"
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

---

**Next:** [Configuration](configuration.md) — define your reaction, catalysts, and theory levels.
