# Contributing

## Development Setup

```bash
git clone https://github.com/sterling-group/PyA3EDA.git
cd PyA3EDA
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest                    # full suite
pytest -x -q              # stop on first failure, quiet output
pytest --cov=pya3eda      # with coverage report
```

Tests live in `tests/` and mirror the `src/pya3eda/` structure.

## Building Docs Locally

```bash
mkdocs serve
```

Open <http://127.0.0.1:8000> to preview. Changes to `docs/` and docstrings
are reflected live.

## Code Style

- Python ≥ 3.11 — use `X | Y` union syntax, not `Union[X, Y]`.
- All data models use Pydantic `BaseModel` with `frozen=True`.
- Prefer `tuple` over `list` for immutable sequences in specs.
- No mutable global state.

## Project Layout

```
src/pya3eda/
├── __init__.py        # Package root
├── cli.py             # Entry point
├── config.py          # YAML → Config
├── registry.py        # Config → CalcRegistry
├── ids.py             # Typed identifiers and data models
├── constants.py       # Physical constants
├── sanitize.py        # Filename sanitisation
├── utils.py           # File I/O, units, thermodynamics
├── builder/           # Q-Chem input generation
├── runner/            # Job submission
├── status/            # Status checking
├── parser/            # Output file parsing
├── extractor/         # Data extraction + profile assembly
├── exporter/          # CSV + XYZ export
└── plotter/           # SVG visualisation
```

## Branch & Pull-Request Workflow

`main` is protected — every change lands through a pull request with green CI.

1. Branch off `main`: `git checkout -b my-change`.
2. Commit and push, then open a PR against `main`: `gh pr create --base main`.
3. CI must pass — tests on Python 3.11–3.13, `ruff`, `mypy`, `interrogate`,
   the `mkdocs --strict` docs build, the package build, and CodeQL. The
   `required-checks-pass` job aggregates the required ones.
4. Merge once green. Each merge to `main` redeploys the docs automatically.

## Adding a New Backend

Implement the `ExecutionBackend` protocol (`runner/backend.py`):

```python
class MyBackend:
    name = "my_backend"

    def available(self) -> bool: ...
    def submit(self, script_path: Path, *, log_path: Path | None = None) -> str: ...
    def is_finished(self, job_id: str) -> bool: ...
```

Register it in the `BACKENDS` table in `runner/backend.py`; `get_backend("auto")`
then selects it. The shipped backends are `LocalBackend` (background `bash`) and
`SlurmBackend` (`sbatch`/`squeue`). The bash that actually runs a calculation
comes from a separate `Engine` protocol (`QChemEngine`), so a new program is a
new `Engine`, not a new backend.
