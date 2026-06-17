# Contributing

## Development Setup

```bash
git clone https://github.com/sterling-group/PyA3EDA.git
cd PyA3EDA
pip install -e ".[test,docs]"
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

- Python ≥ 3.10 — use `X | Y` union syntax, not `Union[X, Y]`.
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

## Adding a New Backend

Implement the `SubmissionBackend` protocol:

```python
class MyBackend:
    name = "my_backend"

    def submit(self, input_path: Path, extra_argv: list[str] | None = None) -> bool:
        ...
```

Register it in `runner/backend.py` via `get_backend()`.
