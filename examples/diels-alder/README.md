# Diels–Alder Example

Lewis-acid catalysed Diels–Alder reaction of **acrolein** (prop-2-enal)
with **1,3-butadiene**, catalysed by **BF₃**.

```text
prop2enal  +  buta13diene  ──BF₃──▶  cyclohex3ene1carbaldehyde
```

## What this example contains

```text
examples/diels-alder/
├── config.yaml                 # reaction definition
└── templates/
    ├── base_template.in        # Q-Chem input skeleton
    ├── rem/
    │   ├── opt_base.rem        # OPT $rem keywords
    │   ├── sp_eda_base.rem     # SP EDA $rem keywords
    │   ├── full_cat.rem        # unconstrained ALMO-EDA
    │   ├── pol_cat.rem         # polarisation-only
    │   ├── frz_cat.rem         # frozen-density
    │   ├── geom_opt.rem        # geometry convergence criteria
    │   └── solvent_smd.rem     # SMD solvation block
    └── molecule/
        ├── prop2enal.xyz       # dienophile (acrolein)
        ├── buta13diene.xyz     # diene (1,3-butadiene)
        ├── bf3.xyz             # catalyst (BF₃)
        ├── tscomplex.xyz       # uncatalysed TS
        ├── cyclohex3ene1carbaldehyde.xyz  # product
        ├── preTS_bf3-prop2enal.xyz        # pre-TS complex (BF₃ · acrolein)
        ├── ts_bf3-tscomplex.xyz           # catalysed TS
        └── postTS_bf3-cyclohex3ene1carbaldehyde.xyz  # post-TS complex
```

## Running the example

```bash
# 1. Install pya3eda (from the repo root)
pip install .

# 2. Navigate to this example directory
cd examples/diels-alder

# 3. Generate Q-Chem input files
pya3eda config.yaml build --template-dir templates

# 4. Inspect the generated directory tree
find wB97X-V_def2-SVP_smd -name '*.in' | sort

# 5. Check status (will show "nofile" for all — no outputs yet)
pya3eda config.yaml status
```

> **Note** — The XYZ coordinates in this example are approximate
> placeholders for demonstration purposes. Replace them with optimised
> geometries before running production calculations.

## What `build` generates

After step 3, the directory tree under `wB97X-V_def2-SVP_smd/` will
contain Q-Chem `.in` files for:

| Stage | Uncatalysed | BF₃-catalysed (×3 calc_types) |
|---|---|---|
| **reactants** | prop2enal, buta13diene | — (shared) |
| **preTS** | — | bf3-prop2enal |
| **TS** | tscomplex | bf3-tscomplex |
| **postTS** | — | bf3-cyclohex3ene1carbaldehyde |
| **products** | cyclohex3ene1carbaldehyde | — (shared) |
| **catalyst** | — | bf3 |

Each catalysed stage gets three input files — `full_cat`, `pol_cat`, and
`frz_cat` — for the ALMO-EDA decomposition.

## Next steps

Once you have access to a Q-Chem cluster:

```bash
# Submit all jobs
pya3eda config.yaml run

# Monitor progress
pya3eda config.yaml status

# Extract results, export CSVs, generate plots
pya3eda config.yaml extract
```
