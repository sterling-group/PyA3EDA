<div align="center" markdown>
![PyA3EDA logo](assets/logo.svg){ width="160" }
</div>

# **Python automation for Asymmetrically-constrained Adiabatic ALMO-EDA**

PyA3EDA automates the full A3EDA workflow — Q-Chem input generation,
job submission, status monitoring, data extraction, energy-profile
assembly, and publication-ready plots — all driven by a single YAML
configuration file.

## Documentation Sections

<div class="grid cards" markdown>

-   :material-book-open-variant:{ .lg .middle } **User Guide**

    ---

    Installation, configuration, CLI reference, and a full tutorial.

    [:octicons-arrow-right-24: Get started](user-guide/index.md)

-   :material-flask:{ .lg .middle } **Theory**

    ---

    EDA decomposition methodology, G\_ni formula, barrier analysis.

    [:octicons-arrow-right-24: Learn the science](theory/index.md)

-   :material-api:{ .lg .middle } **API Reference**

    ---

    Auto-generated reference for all modules and classes.

    [:octicons-arrow-right-24: Browse the API](api/index.md)

-   :material-wrench:{ .lg .middle } **Developer Guide**

    ---

    Architecture overview, module responsibilities, contributing.

    [:octicons-arrow-right-24: Contribute](developer/index.md)

</div>

## Citing PyA3EDA

If you use PyA3EDA in your research, please cite:

!!! quote "Reference"

    M. G. S. Weiss, A. J. Sterling,
    *Asymmetrically-constrained Adiabatic ALMO-EDA for Catalytic Barrier Decomposition*,
    manuscript in preparation (2026).

    DOI to be added upon publication.

## Key Features

- **Configuration-driven** — A single YAML file defines methods, basis sets,
  catalysts, and reactants. Everything else is derived automatically.
- **Forward-composing architecture** — Data flows in one direction:
  `Config → Registry → Extractor → Plotter`. No reverse look-ups.
- **EDA decomposition** — Decomposes catalytic barriers into FRZ, POL,
  and CT on the E surface; adds a confinement (NI) term on the G surface.
- **Non-interacting reference (G\_ni)** — Separates the confinement cost
  of bringing fragments together from genuine interaction contributions.
- **Candidate selection** — Automatically picks the lowest-energy preTS/postTS
  complex when multiple compositions exist.

## Quick Start

```bash
# Install
pip install .

# Run the full workflow
pya3eda config.yaml build      # generate Q-Chem inputs
pya3eda config.yaml run        # submit jobs
pya3eda config.yaml status     # check progress
pya3eda config.yaml extract    # extract data, export CSVs, generate plots
```
