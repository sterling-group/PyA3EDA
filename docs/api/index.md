# API Reference

Auto-generated reference documentation for all `pya3eda` modules.

The API follows a forward-composing design:

```
Config → CalcRegistry → Extractor → Exporter / Plotter
```

## Core

- [Configuration](config.md) — YAML loading and validated models
- [Registry](registry.md) — Single source of truth for all calculations
- [Identifiers](ids.md) — Typed IDs, specs, and data models
- [Constants](constants.md) — Physical constants and conversion factors

## Pipeline

- [Data Extraction](extractor/data.md) — Parse Q-Chem outputs
- [Profile Assembly](extractor/stages.md) — Sum energies into profiles
- [Barrier Decomposition](extractor/barriers.md) — ΔΔ‡ analysis

## Output

- [Exporter](exporter.md) — CSV and XYZ export
- [Energy Profiles](plotter/profile.md) — Reaction coordinate plots
- [Contribution Barplots](plotter/contributions.md) — ΔΔ‡ bar charts

## Input Generation

- [Input Builder](builder/inputs.md) — Generate Q-Chem input files
- [Molecule Section](builder/molecule.md) — `$molecule` construction
- [REM Section](builder/rem.md) — `$rem` construction

## Infrastructure

- [Runner](runner.md) — Job submission backends
- [Status](status.md) — Calculation status checking
- [Parser: Q-Chem](parser/qchem.md) — Output file parsing
- [Parser: XYZ](parser/xyz.md) — Coordinate parsing
- [Utilities](utils.md) — File I/O, unit conversion, thermodynamics
