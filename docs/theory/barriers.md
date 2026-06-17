# Barrier Decomposition (ΔΔ‡)

## Overview

The barrier decomposition quantifies how much each physical contribution
lowers or raises the catalytic barrier relative to the uncatalysed reaction.

On the **electronic-energy (E)** and **Gibbs-energy (G)** surfaces, three
contributions are resolved: frozen-density (FRZ), polarisation (POL), and
charge-transfer (CT).

On the Gibbs-energy surface a fourth **confinement (NI)** term can be
inserted before FRZ.  It captures the translational entropy effect of
confining the catalyst and substrate into the same translational frame —
a cost when the preTS complex is absent or poorly ordered, a benefit
when the preTS complex pre-orders both reactants into a TS-like geometry.

## 3-Level Decomposition (E, G)

$$
\Delta\Delta^\ddagger_\text{FRZ} = \Delta^\ddagger_\text{FRZ} - \Delta^\ddagger_\text{uncat}
$$

$$
\Delta\Delta^\ddagger_\text{POL} = \Delta^\ddagger_\text{POL} - \Delta^\ddagger_\text{FRZ}
$$

$$
\Delta\Delta^\ddagger_\text{CT} = \Delta^\ddagger_\text{FULL} - \Delta^\ddagger_\text{POL}
$$

These are additive:

$$
\Delta\Delta^\ddagger_\text{complete}
= \Delta\Delta^\ddagger_\text{FRZ}
+ \Delta\Delta^\ddagger_\text{POL}
+ \Delta\Delta^\ddagger_\text{CT}
= \Delta^\ddagger_\text{FULL} - \Delta^\ddagger_\text{uncat}
$$

All barriers above use the same energy surface (E or G) and the same
baseline decision (see [Baseline Selection](#baseline-selection)).

## 4-Level Confinement Decomposition

On the Gibbs-energy surface, a confinement contribution is inserted
before FRZ.  The barrier stack becomes:

| Layer | Formula |
|-------|---------|
| NI | $\Delta\Delta G^\ddagger_\text{NI} = \Delta G^\ddagger_\text{NI} - \Delta G^\ddagger_\text{uncat}$ |
| FRZ | $\Delta\Delta G^\ddagger_\text{FRZ} = \Delta G^\ddagger_\text{FRZ}(G) - \Delta G^\ddagger_\text{NI}$ |
| POL | $\Delta\Delta G^\ddagger_\text{POL} = \Delta G^\ddagger_\text{POL}(G) - \Delta G^\ddagger_\text{FRZ}(G)$ |
| CT | $\Delta\Delta G^\ddagger_\text{CT} = \Delta G^\ddagger_\text{FULL}(G) - \Delta G^\ddagger_\text{POL}(G)$ |

where:

- $\Delta G^\ddagger_\text{NI} = G_\text{ni}^\text{TS,full} - G_\text{ni}^\text{baseline,full}$
  — barrier on the G\_ni surface of the full\_cat profile, using the same
  baseline decision as the other energy types.
- $\Delta G^\ddagger_\text{uncat} = G^\text{TS,uncat} - G^\text{R,uncat}$
  — barrier on the regular G surface of the uncatalysed profile (always
  from reactants, never preTS).  Regular G is used because all
  uncatalysed species are separate molecules that already translate
  independently.
- FRZ, POL, CT barriers use the regular G surface (not G\_ni), so
  POL and CT contributions are identical to the 3-level G decomposition.

These are additive:

$$
\Delta\Delta G^\ddagger_\text{complete}
= \Delta\Delta G^\ddagger_\text{NI}
+ \Delta\Delta G^\ddagger_\text{FRZ}
+ \Delta\Delta G^\ddagger_\text{POL}
+ \Delta\Delta G^\ddagger_\text{CT}
= \Delta G^\ddagger_\text{FULL}(G) - \Delta G^\ddagger_\text{uncat}
$$

## Baseline Selection

The baseline decision is made once on the **full\_cat G** surface:

- If $G_\text{preTS,full} < G_\text{reactants,full}$, catalysed barriers
  use preTS as baseline: $\Delta^\ddagger = \text{TS} - \text{preTS}$.
- Otherwise, reactants: $\Delta^\ddagger = \text{TS} - \text{reactants}$.

This single decision applies to **all** energy types (E, G, G\_ni) and
all calc\_types (full\_cat, pol\_cat, frz\_cat).

Uncatalysed barriers always use reactants (the uncatalysed profile has no
preTS stage).
