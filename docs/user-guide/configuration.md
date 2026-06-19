# Configuration

PyA3EDA is driven by a single YAML configuration file that defines all
methods, catalysts, reactants, and products for your project.

## Minimal Example

```yaml
levels:
  - opt:
      method: wB97X-V
      basis: def2-TZVPD
      dispersion: ""
      solvent: ""
      eda2: 0

catalysts:
  - name: lip

reactants:
  - name: butadiene
    include: true
  - name: prop2enal
    include: true

products:
  - name: prop2enal-butadiene
    include: true
```

## Configuration Reference

### `levels`

Each level defines an optimisation theory and optional single-point theories.

| Field        | Type             | Description                            |
|--------------|------------------|----------------------------------------|
| `opt`        | TheoryConfig     | Level of theory for geometry optimisation |
| `sp`         | list[TheoryConfig] | Single-point levels (EDA calculations) |

#### TheoryConfig Fields

| Field        | Type   | Description                          |
|--------------|--------|--------------------------------------|
| `method`     | str    | DFT functional or method name        |
| `basis`      | str    | Basis set                            |
| `dispersion` | str    | Dispersion correction (empty = none) |
| `solvent`    | str    | Solvent model (empty = gas phase)    |
| `eda2`       | int    | EDA2 level (0 = no EDA)             |

### `catalysts`

List of catalysts. Each entry needs a `name`; set `dimer: true` for a catalyst
whose resting state is a dimer:

```yaml
catalysts:
  - name: lip
    dimer: true     # also run a `dimer` calc and add a DISS dissociation bar
  - name: nap       # dimer defaults to false
```

When `dimer: true`, PyA3EDA enumerates a `dimer` stage **alongside `cat`** at
`<method_key>/<catalyst>/dimer/` — built, run, and extracted by the normal
`build`/`run`/`extract` like any other calculation. It needs an initial geometry
template `templates/molecule/<catalyst>-dimer.xyz`. The barplot then gains a
leading **DISS** term (`correction = 2·E_cat − E_dimer`) so `FULL` includes the
cost of freeing one active monomer from the dimer. Catalysts without the flag are
untouched.

### `reactants` and `products`

List of species with optional `include` flag:

```yaml
reactants:
  - name: butadiene
    include: true
  - name: prop2enal
    include: true
```

Setting `include: false` excludes a species from profile assembly while
keeping it available for reference calculations.

## Template Files

Place template files in a `templates/` directory:

```
templates/
├── rem/
│   └── opt_base.rem           # Base $rem template for OPT jobs
├── base_template.in           # Input file skeleton
└── molecule/
    ├── butadiene.xyz          # Reactant XYZ files
    ├── prop2enal.xyz
    ├── prop2enal-butadiene.xyz
    └── lip.xyz                # Catalyst XYZ file
```

### XYZ File Format

Standard XYZ with charge and multiplicity on the comment line:

```
8
0 1
C    0.000000    0.000000    0.000000
...
```

For catalyst files, an optional `cat_atoms` token in the comment line
specifies which atoms belong to the catalyst fragment (for EDA fragmentation).

---

**Next:** [CLI Reference](cli.md) — learn the `build`, `run`, `status`, and `extract` subcommands.
