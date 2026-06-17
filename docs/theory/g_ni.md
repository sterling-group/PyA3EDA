# Non-Interacting Reference ($G_\text{ni}$)

## Motivation

When reactants associate into a complex (preTS), the system loses
translational degrees of freedom. This translational entropy loss is an
artefact of the supramolecular approach — it reflects the cost of bringing
species together, not a genuine catalytic interaction.

The non-interacting reference $G_\text{ni}$ removes this artefact by
computing what the free energy *would be* if the fragments did not interact
but occupied the same translational frame.

## Formula

For a stage composed of reference fragments (ref) and translationally
independent species (trans):

$$
G_\text{ni} = \sum_\text{ref}(H - H_\text{trans}) + m \cdot H_\text{trans}
- T\!\left[\sum_\text{ref}(S_\text{tot} - S_\text{trans})
+ \sum_\text{trans} S_\text{trans}\right]
+ m \cdot \Delta G_\text{ssc}
$$

where:

- $H_\text{trans} = \tfrac{5}{2} R T$ — translational enthalpy contribution
- $S_\text{tot}$ — total entropy of each reference fragment
- $S_\text{trans}$ — translational entropy (from the ideal-gas partition function)
- $m = |\text{trans}|$ — number of translationally independent species
- $\Delta G_\text{ssc}$ — standard-state correction (1 atm → 1 M, for solution-phase)

## Physical Interpretation

| Term | Meaning |
|------|---------|
| $\sum_\text{ref}(H - H_\text{trans})$ | Internal (rot + vib) enthalpy from real fragments |
| $m \cdot H_\text{trans}$ | Translational enthalpy for $m$ independent particles |
| $\sum_\text{ref}(S_\text{tot} - S_\text{trans})$ | Internal entropy (rot + vib) from real fragments |
| $\sum_\text{trans} S_\text{trans}$ | Translational entropy from independent particles |

The key insight: **rotational and vibrational contributions come from the
actual computed fragments**, while **translational contributions are
reconstructed as if each species were independent**.

## NI Stage References

The registry assigns each catalysed complex stage an `NiStageRef` that
specifies:

- `ref_cids` — Calculations providing H and non-translational S (the real fragments)
- `trans_cids` — Calculations providing translational S (the independent species)
- `apply_ssc_to_g_ni` — Whether to add the standard-state correction (True when using implicit solvent)

Each stage has its own translational frame:

| Stage | `ref_cids` (H, rot+vib S) | `trans_cids` (translational S) |
|-------|---------------------------|-------------------------------|
| **preTS** | standalone reactants + standalone catalyst | the preTS complex species — places reactants and catalyst in the same translational frame as the preTS complex |
| **TS** | uncatalysed TS + standalone catalyst | catalysed TS complex (single body, $m=1$) |
| **postTS** | standalone products + standalone catalyst | the postTS complex species — places products and catalyst in the same translational frame as the postTS complex |
