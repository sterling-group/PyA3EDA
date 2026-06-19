# Architecture

## Design Principles

1. **Forward composition** — Data flows in one direction. No module reaches
   back into an earlier stage to reconstruct information.
2. **Single source of truth** — The `CalcRegistry` derives all calculations
   and profiles from a validated `Config`. Downstream modules receive
   pre-built specs.
3. **Immutable data** — All Pydantic models are frozen. Once built, they
   are never mutated.

## Data Flow

```
┌──────────┐
│  YAML    │
│  Config  │
└────┬─────┘
     │ load_config()
     ▼
┌──────────┐
│  Config  │   Validated, immutable configuration
└────┬─────┘
     │ CalcRegistry(config, base_dir)
     ▼
┌──────────────┐
│ CalcRegistry │   All CalcSpecs + ProfileSpecs derived
└──┬───────────┘
   │
   ├─── build_all()        → Q-Chem .in files
   │
   ├─── run_all()          → Job submission
   │
   ├─── check_all()        → Status report
   │
   ├─── extract_all()      → dict[CalcID, ExtractedData]
   │         │
   │         ▼
   │    build_profiles()   → dict[ProfileID, ProfileData]
   │         │
   │         ▼
   │    compute_delta_delta() → list[DeltaDeltaData]
   │         │
   │         ├─── export_all()              → CSV + XYZ files
   │         ├─── plot_all_profiles()       → Profile SVGs
   │         └─── plot_delta_delta_barplots()→ Barplot SVGs
```

## Module Map

### Core

| Module        | Responsibility                                   |
|---------------|--------------------------------------------------|
| `config`      | YAML parsing → validated `Config`                |
| `registry`    | `Config` → `CalcSpec` + `ProfileSpec` derivation |
| `ids`         | Typed identifiers and data model definitions     |
| `constants`   | Physical constants (CODATA 2022)                 |
| `sanitize`    | Filesystem-safe name conversion                  |
| `utils`       | File I/O, unit conversion, thermodynamics        |

### Pipeline

| Module              | Input                     | Output                  |
|---------------------|---------------------------|-------------------------|
| `builder.inputs`    | Registry + templates      | Q-Chem `.in` files      |
| `runner.executor`   | Registry + backend        | Submitted jobs          |
| `status.checker`    | Registry                  | Status report           |
| `extractor.data`    | Registry + output files   | `ExtractedData` per calc |
| `extractor.stages`  | `ExtractedData` + specs   | `ProfileData` per profile |
| `extractor.barriers`| `ProfileData` map         | `DeltaDeltaData` list   |
| `exporter.results`  | All extracted data        | CSV + XYZ files         |
| `plotter.profile`   | `ProfileData` map         | SVG diagrams            |
| `plotter.contributions` | `DeltaDeltaData` list | SVG barplots            |

### Support

| Module             | Responsibility                      |
|--------------------|-------------------------------------|
| `parser.qchem`     | Regex-based Q-Chem output parsing   |
| `parser.xyz`       | XYZ coordinate parsing/formatting   |
| `builder.molecule` | `$molecule` section construction    |
| `builder.rem`      | `$rem` section construction         |
| `runner.backend`   | Pluggable submission backends       |

## Key Design Decisions

### Candidate Selection

When multiple preTS/postTS complex compositions exist (e.g. catalyst + one
reactant vs catalyst + both reactants), the `full_cat` profile acts as the
**selection leader**: it evaluates all candidates and picks the lowest-energy
one. Follower profiles (`pol_cat`, `frz_cat`) reuse the same selection
indices, ensuring all EDA calc types use the same molecular geometry.

### NI References

The complex stages (preTS, TS, postTS) carry `NiStageRef` objects that
define how $G_\text{ni}$ is computed for that stage.
When a preTS/postTS stage has alternative complex compositions, each
`StageAlt` carries its own `ni_ref` for the corresponding translational
frame.

### Profile Assembly

Profiles store absolute energies on each stage. Normalisation (relative to
reactants) happens only at the plotting step. The barrier decomposition
module works with absolute values and computes differences directly.
