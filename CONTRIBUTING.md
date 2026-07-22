# Contributing to PyA3EDA

Thanks for your interest in improving PyA3EDA!

## Development setup

```bash
git clone https://github.com/sterling-group/PyA3EDA.git
cd PyA3EDA
pip install -e ".[dev]"
pre-commit install
```

## Quality gates

Every change must keep the full gate green (CI enforces it):

```bash
pytest --cov=pya3eda --cov-branch     # 100% line + branch coverage
ruff check . && ruff format --check . # lint + format
mypy src/pya3eda                      # types
interrogate -c pyproject.toml src/    # 100% docstrings
mkdocs build --strict                 # docs
```

## Workflow

`main` is protected. Land changes through a pull request:

1. Branch off `main`: `git checkout -b my-change`.
2. Commit, push, and open a PR against `main` (`gh pr create --base main`).
3. CI must be green — the `required-checks-pass` job aggregates the required checks.
4. PRs are **squash-merged** to keep a linear history; each merge to `main`
   redeploys the docs.

## GitHub Actions

Every `uses:` in `.github/workflows/` is pinned to a full 40-character commit SHA
with the release tag in a trailing comment:

```yaml
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
```

Tags are mutable — a compromised maintainer account can re-point `v1` at any
commit, which is how the `tj-actions/changed-files` supply-chain attack leaked
CI secrets from every repo tracking a tag. Dependabot keeps the pins current, so
please don't add a step that references a bare tag or branch.

See the [Developer Guide](https://sterling-group.github.io/PyA3EDA/developer/contributing/)
for the architecture, coding conventions, and how to add a backend.
