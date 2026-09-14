# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0]

### Added

- **`pipeline --criteria`**: the pipeline's OPT (re)submission filter is now a
  CLI option (default `NOFILE`, same vocabulary as `run`), so crashed OPTs can
  be rerun with `--criteria CRASH` instead of deleting their outputs by hand.
  An OPT skipped at seed time (output exists but not `SUCCESSFUL`) is now
  warned about — per OPT plus a summary — instead of silently dropping its
  whole SP branch.
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

- **`--max-cores` and `--wait` are now independent**: `run --max-cores N` on
  SLURM throttles submission even without `--wait` (previously the flag was
  silently ignored there), returning after the last submission; `--wait` alone
  submits everything and blocks until completion. Budget defaults are
  backend-aware — no cap on SLURM (the scheduler manages the cluster; the old
  default capped runs at the *login node's* core count), usable host cores
  locally — and a single job larger than the budget now fails up front with
  exit code 6 in both `run` and `pipeline`, instead of raising mid-run or
  being silently over-subscribed.
- **SLURM submissions are acknowledgement-gated**: each `sbatch` now waits for the
  controller to list the job in `squeue` before the next one fires, so a large run
  is paced by the scheduler's real responsiveness instead of hammering it (or
  guessing at a fixed sleep). Costs one `squeue -j` call and no wait when the
  controller is healthy; a stalled or unusable `squeue` disables the gate for the
  rest of the run with a warning rather than slowing every submission.
- **CLI startup ~2× faster** (`--version`/`--help` ≈ 0.24 s → ≈ 0.11 s) via a lazy
  `__version__` and deferred heavy imports.
- `ClusterConfigError` now belongs to the `PyA3EDAError` hierarchy, so a bad
  cluster config maps to a deterministic exit code instead of an uncaught crash.
- Internal: the 1,000-line `registry` module was split into a focused
  `registry/` package and its duplicated profile builders collapsed — a pure
  refactor with byte-identical enumeration (guarded by a parity oracle).

### Fixed

- **EDA single points silently dropped atoms.** When an optimised geometry held more
  atoms than the catalyst/substrate templates declared — an OPT extended with explicit
  solvent molecules, say — the fragment split trimmed the surplus without a word, so the
  SP ran on a *different molecule* than the one that was optimised and returned
  plausible-looking energies for it. A fragmented SP now takes its split from the
  `$molecule` block echoed in the OPT output, so hand-extended optimisations carry through
  without editing a single template; when that is unavailable the template split must match
  the geometry exactly, and a disagreement is a logged error instead of a silent trim.
  (Coordinates still come from the last `Standard Nuclear Orientation` — only the
  fragmentation is read from the echoed block.)
- A composite template whose atom count disagrees with its own catalyst + substrate
  fragments now logs a warning naming the file, instead of passing unnoticed.
- A catalyst **dimer** single point was built as a fragment-EDA calculation (it is
  a standalone molecule); it now builds correctly so the dissociation correction
  works.
- A **negative dimer dissociation** (a dimer unbound relative to two monomers)
  was added to `FULL`/ΔΔ‡ as a *credit*, lowering the barrier. The **DISS** term
  is now floored at zero — `max(2·E_cat − E_dimer, 0)` — so such a dimer shows a
  zero bar and leaves the totals untouched; the raw value is still logged.
- **SLURM** robustness: a just-submitted job no longer reads as "finished" before
  it appears in `squeue` (submit→poll race), and a persistently failing `squeue`
  now fails loudly instead of hanging a waited run forever.
- Geometry parsing no longer over-captures a trailing coordinate-shaped table
  after the final optimised geometry.
- A job that died mid-run (crash/termination markers present) is reported as
  `CRASH`/`terminated` rather than staying `running` forever.
