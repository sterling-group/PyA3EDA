# EDA Decomposition

Energy Decomposition Analysis (EDA) partitions the interaction between a
catalyst and the reacting system into physically meaningful contributions.

## Calculation Types

PyA3EDA works with four calculation types per catalyst:

| Calc Type   | Label | Description                                     |
|-------------|-------|-------------------------------------------------|
| *(none)*    | uncat | Uncatalysed reference (no catalyst present)     |
| `frz_cat`   | FRZ   | Frozen-density: electrostatic + Pauli repulsion |
| `pol_cat`   | POL   | Polarisation: orbital relaxation on each fragment |
| `full_cat`  | FULL  | Full interaction (all contributions)            |

## Energy Surfaces

For each calculation type, three energy surfaces are tracked:

- **E** — Electronic energy (SCF energy, no thermal corrections)
- **G** — Gibbs energy (includes thermal + entropic corrections)
- **$G_\text{ni}$** — Non-interacting Gibbs energy (translational entropy
  corrected; see [Non-Interacting Reference](g_ni.md))

## Reaction Profile Stages

Uncatalysed profiles have three stages:

```
reactants → TS → products
```

Catalysed profiles have five stages:

```
reactants → preTS → TS → postTS → products
```

The preTS and postTS stages represent pre- and post-reactive complexes
where the catalyst is associated with the reacting system.

## Baseline Selection

When the preTS complex is lower in energy than separated reactants on the
G surface of the `full_cat` profile, the barrier is measured from preTS
rather than reactants.  This decision is made once on `full_cat` and
applied consistently across all calculation types (`pol_cat`, `frz_cat`).
