# Tutorial — Diels–Alder with BF₃

Now that you have PyA3EDA [installed](installation.md), understand the
[configuration format](configuration.md), and know the
[CLI subcommands](cli.md), let’s put it all together with a real example.

This walkthrough uses the ready-to-run example shipped with the
repository (`examples/diels-alder/`) to take you from an empty directory
to energy profiles and ΔΔ‡ barplots.

!!! info "Source files"
    All files referenced below live in
    [`examples/diels-alder/`](https://github.com/sterling-group/PyA3EDA/tree/rewrite/examples/diels-alder).

## The reaction

Lewis-acid catalysed Diels–Alder cycloaddition of **acrolein**
(prop-2-enal) with **1,3-butadiene**, producing **cyclohex-3-ene-1-carbaldehyde**.

```text
prop2enal  +  buta13diene  ──BF₃──▶  cyclohex3ene1carbaldehyde
```

The dienophile (acrolein) **coordinates** to the Lewis acid; butadiene
does not.  This is expressed in the config by setting `include: false` on
butadiene.

---

## 1 — Write the configuration

The YAML file defines the full computational setup in one place:

```yaml title="config.yaml"
levels:
  - opt:
      method: wB97X-V
      basis: def2-SVP
      solvent: smd
    sp:
      - method: wB97M-V
        basis: def2-TZVPPD
        solvent: smd
        eda2: 1

catalysts:
  - name: bf3

reactants:
  - name: prop2enal
    include: true          # coordinates to catalyst
  - name: buta13diene
    include: false         # free spectator

products:
  - name: cyclohex3ene1carbaldehyde
    include: true
```

**What each section does:**

| Section | Purpose |
|---|---|
| `levels.opt` | Geometry optimisation level of theory. |
| `levels.sp` | Single-point EDA levels (run after OPT converges). |
| `catalysts` | Lewis acids to analyse. Add more entries to compare catalysts. |
| `reactants` | Species on the reactant side. `include: true` means it forms a complex with the catalyst. |
| `products` | Species on the product side. |

!!! tip "Multiple catalysts"
    Adding more catalysts (e.g. `lip`, `alcl3`) is a single YAML change —
    PyA3EDA generates all the extra inputs, profiles, and plots
    automatically.

---

## 2 — Prepare template files

PyA3EDA needs three kinds of template:

### Base template

The Q-Chem input skeleton with `{rem_section}` and `{molecule_section}`
placeholders:

```text title="templates/base_template.in"
$rem
{rem_section}
$end

$molecule
{molecule_section}
$end
```

### REM templates

Keyword blocks under `templates/rem/`.  The `opt_base.rem` and
`sp_eda_base.rem` files contain placeholders (`{method}`, `{basis}`, etc.)
that PyA3EDA fills in from the config:

```text title="templates/rem/opt_base.rem"
METHOD            = {method}
BASIS             = {basis}
JOBTYPE           = {jobtype}
DFT_D             = {dispersion}
SOLVENT_METHOD    = {solvent}
SCF_CONVERGENCE   = 8
MAX_SCF_CYCLES    = 200
SYM_IGNORE        = true
```

Calc-type REM snippets (`full_cat.rem`, `pol_cat.rem`, `frz_cat.rem`) are
appended automatically for catalysed calculations.  Additional blocks
(`geom_opt.rem`, `solvent_smd.rem`) are appended for OPT and solvated
jobs.

### XYZ files

Molecular coordinates under `templates/molecule/`.  Standard XYZ format
with charge and multiplicity on the comment line:

```text title="templates/molecule/prop2enal.xyz"
8
0 1
C   0.0000   0.0000   0.0000
C   1.3400   0.0000   0.0000
...
```

**Composite XYZ files** (for catalysed stages) list the catalyst atoms
first, followed by the substrate atoms.  PyA3EDA splits them into
fragments for the `$molecule` section:

```text title="templates/molecule/preTS_bf3-prop2enal.xyz"
12
0 1
B   4.0000   1.2100   0.0000    ← catalyst atoms (4)
F   5.3100   1.2100   0.0000
F   3.3450   2.3440   0.0000
F   3.3450   0.0760   0.0000
C   0.0000   0.0000   0.0000    ← substrate atoms (8)
C   1.3400   0.0000   0.0000
...
```

The naming convention:

| Stage | File name pattern |
|---|---|
| Individual species | `{species}.xyz` |
| Uncatalysed TS | `tscomplex.xyz` |
| Pre-TS complex | `preTS_{catalyst}-{substrate}.xyz` |
| Post-TS complex | `postTS_{catalyst}-{product}.xyz` |
| Catalysed TS | `ts_{catalyst}-tscomplex.xyz` |

---

## 3 — Generate input files

```bash
cd examples/diels-alder
pya3eda config.yaml build --template-dir templates
```

This creates a directory tree under `wB97X-V_def2-SVP_smd/`:

```text
wB97X-V_def2-SVP_smd/
├── no_cat/                        # uncatalysed
│   ├── reactants/
│   │   ├── prop2enal/             # prop2enal_opt.in
│   │   └── buta13diene/           # buta13diene_opt.in
│   ├── ts/                        # tscomplex_opt.in
│   └── products/
│       └── cyclohex3ene1carbaldehyde/
└── bf3/                           # BF₃-catalysed
    ├── cat/                       # bf3_opt.in (standalone catalyst)
    ├── preTS/bf3-prop2enal/
    │   ├── full_cat/              # preTS_bf3-prop2enal_full_cat_opt.in
    │   ├── pol_cat/
    │   └── frz_cat/
    ├── ts/
    │   ├── full_cat/              # ts_bf3-tscomplex_full_cat_opt.in
    │   ├── pol_cat/
    │   └── frz_cat/
    └── postTS/bf3-cyclohex3ene1carbaldehyde/
        ├── full_cat/
        ├── pol_cat/
        └── frz_cat/
```

Each catalysed stage gets three input files for the ALMO-EDA
decomposition: **full** (unconstrained), **pol** (polarisation only), and
**frz** (frozen density).

---

## 4 — Submit, monitor, extract

```bash
# Submit all OPT jobs to the cluster
pya3eda config.yaml run

# Check progress (re-run as needed)
pya3eda config.yaml status

# Once jobs finish — extract data, export CSVs, generate plots
pya3eda config.yaml extract
```

`status` prints a colour-coded table showing SUCCESSFUL / running /
CRASH for every registered calculation.

`extract` produces:

- **CSV files** — raw energies and assembled profiles under `results/`.
- **Energy-profile SVGs** — reaction-coordinate diagrams per catalyst.
- **ΔΔ‡ barplots** — grouped contribution charts (FRZ / POL / CT / FULL).

All output lands in `results/{method_key}/`.

---

## 5 — Interpret the output

After extraction you will find files like:

```text
results/wB97X-V_def2-SVP_smd/
├── raw_data/          # per-calculation CSVs
├── profiles/          # combined energy profiles per catalyst
├── delta_delta/       # ΔΔ‡ barrier decomposition CSVs
├── plots/             # SVG diagrams
│   ├── opt_profile_G_bf3_wB97X-V_def2-SVP_smd.svg
│   └── opt_delta_delta_barplot_G_bf3_wB97X-V_def2-SVP_smd.svg
└── xyz_files/         # optimised XYZ coordinates
```

The **profile plot** shows normalised energies along the reaction
coordinate for each trace (uncat, FRZ, POL, FULL).  The **barplot** shows
the ΔΔ‡ contributions that decompose how each interaction type stabilises
or destabilises the barrier.

---

## Next steps

- **Add catalysts** — add entries to the `catalysts:` list and supply the
  corresponding XYZ files.  Re-run `build` and `run`.
- **Add SP levels** — append more entries under `sp:` to evaluate different
  functionals or basis sets at the same optimised geometries.
- **Non-interacting reference** — G\_ni traces appear automatically when
  the extractor detects the required thermodynamic data.

For deeper background on the physics, continue to the
[Theory](../theory/index.md) section.  For implementation details, see
the [API Reference](../api/index.md).
