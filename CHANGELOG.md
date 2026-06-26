# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Reinstated the EDA single-point ↔ OPT **CDS cross-check**: when an EDA SMD
  single point's cavity-dispersion-solvent term disagrees with its optimisation's
  (beyond 1 kcal/mol·10⁻³) a warning is logged, surfacing mismatched geometries.
- **Cluster-configuration exit code** (`8`) for a missing/invalid `clusters.yaml`,
  and a documented
  [exit-code table](https://sterling-group.github.io/PyA3EDA/user-guide/cli/) and
  [cluster-setup guide](https://sterling-group.github.io/PyA3EDA/user-guide/clusters/).
- **Typed domain vocabulary** (`Stage` / `Mode` / `CalcType` / `Surface`
  `StrEnum`s): out-of-vocabulary stage/mode/calc-type values now fail loudly at
  construction instead of silently mismatching.

### Changed

- **CLI startup ~2× faster** (`--version`/`--help` ≈ 0.24 s → ≈ 0.11 s) via a lazy
  `__version__` and deferred heavy imports.
- `ClusterConfigError` now belongs to the `PyA3EDAError` hierarchy, so a bad
  cluster config maps to a deterministic exit code instead of an uncaught crash.
- Internal: the 1,000-line `registry` module was split into a focused
  `registry/` package and its duplicated profile builders collapsed — a pure
  refactor with byte-identical enumeration (guarded by a parity oracle).

### Fixed

- A catalyst **dimer** single point was built as a fragment-EDA calculation (it is
  a standalone molecule); it now builds correctly so the dissociation correction
  works.
- **SLURM** robustness: a just-submitted job no longer reads as "finished" before
  it appears in `squeue` (submit→poll race), and a persistently failing `squeue`
  now fails loudly instead of hanging a waited run forever.
- Geometry parsing no longer over-captures a trailing coordinate-shaped table
  after the final optimised geometry.
- A job that died mid-run (crash/termination markers present) is reported as
  `CRASH`/`terminated` rather than staying `running` forever.
