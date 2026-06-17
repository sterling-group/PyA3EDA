# Kinetics, Barriers, and the A3EDA Decomposition

## 1. The Catalytic Reaction Coordinate

A catalysed bimolecular reaction passes through five stages:

$$
\underbrace{\text{Cat} + R_1 + R_2}_{\text{reactants}}
\;\rightleftharpoons\;
\underbrace{[\text{Cat}\!\cdot\!R_1\!\cdot\!R_2]}_{\text{preTS}}
\;\longrightarrow\;
\underbrace{[\text{Cat}\!\cdot\!R_1\!\cdot\!R_2]^\ddagger}_{\text{TS}}
\;\longrightarrow\;
\underbrace{[\text{Cat}\!\cdot\!P_1\!\cdot\!P_2]}_{\text{postTS}}
\;\rightleftharpoons\;
\underbrace{\text{Cat} + P_1 + P_2}_{\text{products}}
$$

| Stage | Species | Molecularity $m$ |
|-------|---------|:---:|
| Reactants | Cat + R₁ + R₂ | 3 |
| preTS | Cat·R₁·R₂ (+ any free reactants) | 1–2 |
| TS | [Cat·R₁·R₂]‡ | 1 |
| postTS | Cat·P₁·P₂ (+ any free products) | 1–2 |
| Products | Cat + P₁ + P₂ | 3 |

The uncatalysed reference reaction has three stages:

$$
R_1 + R_2 \;\longrightarrow\; [R_1\!\cdot\!R_2]^\ddagger
\;\longrightarrow\; P_1 + P_2
$$

For the purpose of comparing like with like, the **nocat** profile adds
the standalone catalyst as a non-interacting spectator to every
uncatalysed stage.  This ensures identical species composition across
all profiles.


## 2. Consecutive Reactions and Pre-Equilibrium

The catalytic cycle can be viewed as two consecutive steps:

**Step 1 — Association (fast, reversible):**

$$
\text{Cat} + R_1 + R_2 \;\rightleftharpoons\; [\text{Cat}\!\cdot\!R_1\!\cdot\!R_2]
\qquad
K_\text{assoc} = e^{-\Delta G_\text{assoc}/RT}
$$

where $\Delta G_\text{assoc} = G_\text{preTS} - G_\text{reactants}$.

**Step 2 — Activation (rate-determining):**

$$
[\text{Cat}\!\cdot\!R_1\!\cdot\!R_2]
\;\longrightarrow\;
[\text{Cat}\!\cdot\!R_1\!\cdot\!R_2]^\ddagger
\;\longrightarrow\;
\text{products}
$$

Under the **pre-equilibrium approximation** (Step 1 reaches equilibrium
before Step 2 proceeds appreciably):

$$
[\text{preTS}] = K_\text{assoc}\,[\text{Cat}]\,[R_1]\,[R_2]
$$

The overall rate becomes:

$$
\text{rate} = k_2\,[\text{preTS}]
= k_2\,K_\text{assoc}\,[\text{Cat}]\,[R_1]\,[R_2]
$$


## 3. Eyring Theory and the Observed Rate Constant

Transition-state theory gives the elementary rate constant for
crossing a barrier:

$$
k = \frac{k_\text{B} T}{h}\,
    \exp\!\Bigl(-\frac{\Delta G^\ddagger}{RT}\Bigr)
$$

Combining with the pre-equilibrium expression:

$$
\text{rate}
= \frac{k_\text{B} T}{h}\,
  \exp\!\Bigl(-\frac{G_\text{TS} - G_\text{preTS}}{RT}\Bigr)
  \times K_\text{assoc}\,[\text{Cat}]\,[R_1]\,[R_2]
$$

Since $K_\text{assoc} = \exp\!\bigl[-(G_\text{preTS} - G_\text{reactants})/RT\bigr]$,
the exponentials combine:

$$
\text{rate}
= \frac{k_\text{B} T}{h}\,
  \exp\!\Bigl(-\frac{G_\text{TS} - G_\text{reactants}}{RT}\Bigr)
  \,[\text{Cat}]\,[R_1]\,[R_2]
$$

!!! note "Key result"
    Expressed in terms of **free** reactant concentrations, the rate
    always depends on $G_\text{TS} - G_\text{reactants}$, regardless of
    how deep the preTS well is.

However, the **experimentally observed** rate constant depends on which
species dominates the catalyst speciation, which in turn determines the
appropriate barrier.


## 4. Two Kinetic Regimes

### 4.1 Unsaturated regime ($K_\text{assoc}[R] \ll 1$)

Most catalyst is free: $[\text{Cat}]_\text{total} \approx [\text{Cat}]_\text{free}$.

$$
\text{rate} \approx k_\text{eff}\,[\text{Cat}]_\text{total}\,[R_1]\,[R_2]
$$

$$
k_\text{eff} = \frac{k_\text{B} T}{h}\,
  \exp\!\Bigl(-\frac{G_\text{TS} - G_\text{reactants}}{RT}\Bigr)
$$

**Effective barrier:**  $\Delta G^\ddagger = G_\text{TS} - G_\text{reactants}$

This regime applies when the preTS complex is thermodynamically
unfavourable ($G_\text{preTS} \geq G_\text{reactants}$) or when
substrate concentrations are low.

### 4.2 Saturated regime ($K_\text{assoc}[R] \gg 1$, "overbinding")

Most catalyst is sequestered in the preTS complex:
$[\text{Cat}]_\text{total} \approx [\text{preTS}]$.

$$
\text{rate} \approx k_2\,[\text{Cat}]_\text{total}
$$

$$
k_2 = \frac{k_\text{B} T}{h}\,
  \exp\!\Bigl(-\frac{G_\text{TS} - G_\text{preTS}}{RT}\Bigr)
$$

**Effective barrier:**  $\Delta G^\ddagger = G_\text{TS} - G_\text{preTS}$

The reaction becomes **zero-order in substrates** — adding more
reactant does not speed it up because the catalyst is already fully
bound.


## 5. Baseline Selection in A3EDA

Since the EDA decomposition compares catalysts at the same conditions,
a consistent baseline is needed.  The A3EDA analysis uses:

| Condition | Baseline | Barrier | Physical picture |
|-----------|----------|---------|-----------------|
| $G_\text{preTS} < G_\text{reactants}$ | preTS | $G_\text{TS} - G_\text{preTS}$ | Catalyst rests in the bound complex; barrier is the activation from the resting state |
| $G_\text{preTS} \geq G_\text{reactants}$ | reactants | $G_\text{TS} - G_\text{reactants}$ | Complex is transient; the full association + activation cost matters |

This decision is made **once** on the `full_cat` G surface and applied
to all `calc_type`s for that catalyst.

For the **nocat** reference barrier, the baseline is always reactants
(there is no preTS on the nocat profile — no catalyst–substrate
interaction to form a complex).

!!! important "Implications for the decomposition"
    When baseline = preTS, both the baseline and the TS are single
    complexes with the same molecularity ($m = 1$).  The barrier
    differences across `calc_type`s then reflect **changes** in the
    EDA interactions from preTS to TS geometry.

    When baseline = reactants, the baseline is separated molecules
    ($m = 3$) and the TS is a single complex ($m = 1$).  The barrier
    now includes the full cost of bringing the molecules together.


## 6. Molecularity and the Standard-State Correction

### 6.1 The cost of association

Going from $n$ separate molecules to one complex changes the number of
translational degrees of freedom from $3n$ to $3$.  In solution at the
$c^\circ = 1\;\text{M}$ standard state, each independent molecule
carries a standard-state correction (SSC):

$$
\Delta G_\text{ssc} = RT\ln\!\Bigl(\frac{RT}{P^\circ V_m^\circ}\Bigr)
\approx 1.89\;\text{kcal/mol}\quad\text{at 298.15 K}
$$

This SSC is applied **per molecule** at extraction time (when computing
$G$ from $H - TS$).  A barrier therefore naturally acquires a
molecularity-dependent SSC contribution:

$$
\Delta G^\ddagger_\text{ssc}
= (m_\text{TS} - m_\text{baseline}) \times \Delta G_\text{ssc}
$$

| Scenario | $m_\text{baseline}$ | $m_\text{TS}$ | SSC shift |
|----------|:---:|:---:|:---:|
| Baseline = reactants (3 molecules) | 3 | 1 | $-2\,\Delta G_\text{ssc} \approx -3.8$ kcal/mol |
| Baseline = preTS (1 complex) | 1 | 1 | $0$ |

When baseline = reactants, the $-3.8$ kcal/mol SSC lowers the computed
barrier.  This is a **real physical effect** — it reflects the
concentration-dependent gain in free energy from gathering dilute
molecules into a single encounter complex.

### 6.2 Why the nocat profile matters

The **nocat** profile ensures that both sides of every subtraction
contain the same set of atoms (reactants + catalyst), so the SSC
contribution is identical on both sides and cancels exactly in
$\Delta\Delta G^\ddagger$.  Without the nocat profile, the uncatalysed
barrier would have one fewer molecule on each side, creating a spurious
SSC imbalance.


## 7. The Three Energy Surfaces

The EDA decomposition can be performed on three surfaces:

| Surface | Symbol | What it captures |
|---------|--------|-----------------|
| Electronic energy | $E$ | Pure electronic interaction; no entropy, no thermal corrections |
| Gibbs energy | $G$ | Full thermodynamics including translational entropy changes |
| Non-interacting Gibbs energy | $G_\text{ni}$ | Gibbs energy with translational entropy evaluated as if molecules were independent |

$G_\text{ni}$ is described fully in [Non-Interacting Reference](g_ni.md).
The relationship:

$$
G = G_\text{ni} + \underbrace{T\,\Delta S_\text{trans}^\text{confinement}}_{\text{translational entropy lost by forming the complex}}
$$

On the $G_\text{ni}$ surface, the translational entropy is computed
from the independent-molecule partition functions, so the confinement
cost is removed.  The difference $G - G_\text{ni}$ is exactly the
translational entropy penalty of binding.


## 8. The 3-Level Decomposition (E, G)

On each surface separately, three $\Delta\Delta^\ddagger$ contributions
are computed:

$$
\Delta\Delta^\ddagger_\text{FRZ}
= \underbrace{\Delta^\ddagger_\text{frz}}_{\text{frozen barrier}}
- \underbrace{\Delta^\ddagger_\text{nocat}}_{\text{no-catalyst barrier}}
$$

$$
\Delta\Delta^\ddagger_\text{POL}
= \Delta^\ddagger_\text{pol} - \Delta^\ddagger_\text{frz}
$$

$$
\Delta\Delta^\ddagger_\text{CT}
= \Delta^\ddagger_\text{full} - \Delta^\ddagger_\text{pol}
$$

These sum to the complete catalytic effect:

$$
\Delta\Delta^\ddagger_\text{complete}
= \Delta^\ddagger_\text{full} - \Delta^\ddagger_\text{nocat}
= \Delta\Delta^\ddagger_\text{FRZ}
+ \Delta\Delta^\ddagger_\text{POL}
+ \Delta\Delta^\ddagger_\text{CT}
$$

### Interpretation on E vs. G

On the **E surface**, the decomposition isolates purely electronic
effects.  No entropy, no molecularity — just how the interaction
energy changes from baseline to TS.

On the **G surface**, $\Delta\Delta G^\ddagger_\text{FRZ}$ includes
**both** the electronic FRZ contribution **and** any change in
translational entropy (molecularity).  When the baseline is reactants,
the full translational entropy cost of association is folded into
$\Delta\Delta G^\ddagger_\text{FRZ}$.  To separate these, the 4-level
decomposition is needed.


## 9. The 4-Level Confinement Decomposition (G)

On the G surface, a fourth contribution — **confinement (NI)** — is
introduced before FRZ to separate the translational entropy cost from
the electronic interaction:

### 9.1 The catalysed NI barrier

$$
\Delta G^\ddagger_\text{cat,NI}
= G_\text{ni}^\text{TS,full} - G_\text{ni}^\text{baseline,full}
$$

where the baseline follows the same preTS/reactants selection rule.
This barrier uses the $G_\text{ni}$ surface of the `full_cat` profile:
the translational entropy at each stage is evaluated in the
non-interacting frame appropriate to that stage's composition.

### 9.2 The uncatalysed barrier

$$
\Delta G^\ddagger_\text{uncat}
= G^\text{TS,uncat} - G^\text{R,uncat}
$$

The uncatalysed barrier is computed on the regular G surface of the
uncatalysed (nocat) profile.  All species in this profile are separate
molecules (standalone reactants/products + standalone catalyst as
spectator), so they already translate independently and no NI stage
is needed.

### 9.3 The four contributions

$$
\Delta\Delta G^\ddagger_\text{NI}
= \Delta G^\ddagger_\text{cat,NI} - \Delta G^\ddagger_\text{uncat}
$$

$$
\Delta\Delta G^\ddagger_\text{FRZ}
= \Delta G^\ddagger_\text{frz}(G) - \Delta G^\ddagger_\text{cat,NI}
$$

$$
\Delta\Delta G^\ddagger_\text{POL}
= \Delta G^\ddagger_\text{pol}(G) - \Delta G^\ddagger_\text{frz}(G)
$$

$$
\Delta\Delta G^\ddagger_\text{CT}
= \Delta G^\ddagger_\text{full}(G) - \Delta G^\ddagger_\text{pol}(G)
$$

These sum exactly:

$$
\Delta\Delta G^\ddagger_\text{complete}
= \Delta G^\ddagger_\text{full}(G) - \Delta G^\ddagger_\text{uncat}
= \Delta\Delta G^\ddagger_\text{NI}
+ \Delta\Delta G^\ddagger_\text{FRZ}
+ \Delta\Delta G^\ddagger_\text{POL}
+ \Delta\Delta G^\ddagger_\text{CT}
$$


## 10. Physical Interpretation of Each Contribution

### $\Delta\Delta G^\ddagger_\text{NI}$ — Confinement

$$
\Delta\Delta G^\ddagger_\text{NI}
= \Delta G^\ddagger_\text{cat,NI} - \Delta G^\ddagger_\text{uncat}
$$

#### Physical mechanism

$\Delta G^\ddagger_\text{uncat}$ is computed on the regular G surface and
therefore carries the full **translational entropy penalty** of assembling
the separate reactant molecules into the TS complex.  This is an inherent
cost of every bimolecular reaction.

$\Delta G^\ddagger_\text{cat,NI}$ is computed on the $G_\text{ni}$
surface, where translational entropy is reconstructed stage-by-stage for
the appropriate number of independent particles
(see [Non-Interacting Reference](g_ni.md)).  Each complex stage uses the
**internal** (rotational + vibrational) entropy from its reference
fragments, while translational entropy is taken from the actual complex
species at that stage.

#### Sign

**Baseline = reactants** ($G_\text{preTS} \geq G_\text{reactants}$):
The catalyst has not formed a stable preTS complex; the full translational
entropy cost of going from three separate molecules to the TS complex is
not yet paid.  $\Delta G^\ddagger_\text{cat,NI}$ and
$\Delta G^\ddagger_\text{uncat}$ bridge the same translational gap, so
NI is **positive** (an unfavourable confinement cost, typically a few
kcal/mol after SSC).

**Baseline = preTS** ($G_\text{preTS} < G_\text{reactants}$):
Both baseline and TS stages of the $G_\text{ni}$ surface are single
complexes ($m = 1$) with the same total atoms; their translational
entropy contributions largely cancel.  The NI barrier then primarily
captures the **internal** free energy change from preTS to TS, while
$\Delta G^\ddagger_\text{uncat}$ still carries its inherent translational
entropy cost.  The NI term is therefore **typically negative** in this
regime.

#### Negative NI — pre-ordering catalysis

A more negative $\Delta\Delta G^\ddagger_\text{NI}$ (baseline = preTS) is
the quantitative signature of **geometric pre-ordering catalysis**.  Two
conditions must hold simultaneously:

1. **Both reactants are bound in the preTS complex.**  If the catalyst
   binds only one reactant (e.g. Cat·R1, with R2 still free), the preTS
   complex is far from the TS structure, which requires both R1 and R2 in
   proximity.  The remaining translational entropy of bringing in the
   second reactant has not been paid, so the confinement contribution is
   likely still **positive** in that case.  Genuine pre-ordering requires
   the preTS to contain the full ternary complex [Cat·R1·R2].

2. **The [Cat·R1·R2] geometry closely resembles the TS.**  When both
   reactants are positioned relative to each other and to the catalyst in
   a way that is close to the TS arrangement, the remaining internal
   (rotational + vibrational) reorganisation from preTS to TS is small,
   reducing $\Delta G^\ddagger_\text{cat,NI}$ below the uncatalysed
   baseline.

When both conditions are met, $\Delta\Delta G^\ddagger_\text{NI}$ is
driven strongly negative: confinement becomes a **catalytic benefit**
rather than a cost.  A catalyst that achieves a TS-like ternary preTS
geometry shows the largest negative NI; one that binds both reactants
without geometric pre-ordering shows a less negative NI; one that forces
a geometry far from the TS, or that binds only one reactant, can produce
a positive NI even with a preTS baseline.

**Achievability is mechanism-dependent.**  Whether a TS-like ternary
preTS complex [Cat·R1·R2] is geometrically accessible depends on the
reaction mechanism.  For some mechanisms — a bifunctional catalyst that
simultaneously activates both coupling partners, or a scaffold that
templates the reactive geometry — genuine pre-ordering is achievable and
a negative NI is possible.  For others, the preTS is an encounter complex
with only one reactant bound, or the geometry imposed by the catalyst is
structurally incompatible with the TS: in these cases NI remains positive
regardless of how stable the preTS well is.

### $\Delta\Delta G^\ddagger_\text{FRZ}$ — Frozen-Density Interaction

Electrostatic attraction and Pauli repulsion at the frozen electron
densities of the fragments, **after removing the confinement cost**
(in the 4-level scheme).  This includes:

- **Pauli repulsion** (steric clashes) — raises the barrier
- **Electrostatic stabilisation** (dipole–charge, hydrogen bonds) —
  lowers the barrier
- **Changes in rotational/vibrational entropy** from geometric
  distortion upon binding

A negative $\Delta\Delta G^\ddagger_\text{FRZ}$ signals direct
electrostatic stabilisation — the catalyst's electric field stabilises
the TS geometry more than the baseline geometry.  A positive value
denotes net destabilisation (Pauli repulsion and/or steric strain
outweighs the electrostatic attraction).

### $\Delta\Delta G^\ddagger_\text{POL}$ — Polarisation

Mutual induction: each fragment's electron density relaxes in the
field of the other fragments.  This is **always stabilising**
($\leq 0$).  A large magnitude indicates significant polarisation
assistance at the TS.

### $\Delta\Delta G^\ddagger_\text{CT}$ — Charge Transfer

Covalent orbital interactions: electron density is transferred between
fragments.  This is **always stabilising** ($\leq 0$).  It captures
the orbital-level catalytic effect — formation of new bonds, breaking
of old ones, and any donor–acceptor stabilisation facilitated by the
catalyst.


## 11. Preorganisation, Overbinding, and Catalytic Efficiency

### 11.1 Benefit of preorganisation

Preorganisation refers specifically to the **geometric/entropic** effect
of the catalyst forming a preTS complex that positions the reactants in a
TS-like arrangement before the TS is reached.  When the preTS complex
contains **both** reactants bound to the catalyst in a geometry closely
resembling the TS, the translational entropy cost of TS formation is
pre-paid and the remaining geometric reorganisation from preTS to TS is
minimised.  This manifests as a **negative**
$\Delta\Delta G^\ddagger_\text{NI}$: confinement becomes a catalytic
contribution rather than a cost.

This benefit is only achievable when the reaction mechanism permits a
ternary [Cat·R1·R2] preTS with a TS-like geometry (see
[§10](#10-physical-interpretation-of-each-contribution) for conditions
and mechanism-dependence).

The direct electronic interaction effects at the TS (electrostatics,
Pauli repulsion, polarisation, charge transfer) are captured by
$\Delta\Delta G^\ddagger_\text{FRZ}$, $\Delta\Delta G^\ddagger_\text{POL}$,
and $\Delta\Delta G^\ddagger_\text{CT}$ — these are not preorganisation
effects and are discussed in §10 and §11.5.

### 11.2 Cost of preorganisation

Preorganisation has a thermodynamic cost:

1. **Translational entropy** ($\Delta\Delta G^\ddagger_\text{NI}$):
   When baseline = reactants, confining three molecules into one complex
   costs $\approx 2 \times T\Delta S_\text{trans}$ in entropy, partially
   offset by the concentration-dependent SSC, and NI is positive.  When
   baseline = preTS, the translational cost has already been embedded in
   the preTS well; NI is then typically negative and its magnitude encodes
   how well the preTS complex pre-orders the reactants
   (see [§10](#10-physical-interpretation-of-each-contribution)).

2. **Rotational/vibrational entropy**: The complex has fewer soft modes
   than the separated molecules (captured in $\Delta\Delta G^\ddagger_\text{FRZ}$).

3. **Pauli repulsion**: Close contact between catalyst and substrates
   raises the energy (also in $\Delta\Delta G^\ddagger_\text{FRZ}$).

Effective catalysis requires the sum of all contributions
($\Delta\Delta G^\ddagger_\text{NI} + \Delta\Delta G^\ddagger_\text{FRZ}
+ \Delta\Delta G^\ddagger_\text{POL} + \Delta\Delta G^\ddagger_\text{CT}$)
to be negative.  A negative NI (pre-ordering benefit) and/or a negative
FRZ (electrostatic stabilisation) reduce the load on POL + CT.

### 11.3 Overbinding

A catalyst that binds reactants **too strongly** in the preTS complex
creates a deep well before the TS.  Consequences:

- The effective barrier becomes $G_\text{TS} - G_\text{preTS}$
  (the catalyst is trapped in the preTS complex).
- Even though $G_\text{TS} - G_\text{reactants}$ is low (good
  absolute catalysis), the rate from the resting state is slow
  because the preTS well must be climbed out of.
- The system enters the **saturated regime** — zero-order in
  substrates.

In the EDA decomposition, overbinding manifests as:

- A large **negative** $\Delta G_\text{assoc} = G_\text{preTS} - G_\text{reactants}$
- The baseline switches to preTS, making the barrier larger
- $\Delta\Delta G^\ddagger$ contributions now measure **changes** from
  preTS to TS rather than the total effect from reactants

### 11.4 No binding (preTS above reactants)

When the preTS complex is unstable ($G_\text{preTS} > G_\text{reactants}$):

- The catalyst does not form a persistent complex with the substrates.
- The full barrier from separated reactants includes all costs
  (association + distortion + activation).
- The decomposition captures the total catalytic effect in one shot.
- $\Delta\Delta G^\ddagger_\text{NI}$ carries the full confinement cost,
  and $\Delta\Delta G^\ddagger_\text{FRZ}$ reflects how the electronic
  interaction changes across the entire reactants → TS coordinate.

### 11.5 The ideal catalyst

An ideal catalyst optimises the balance:

$$
\underbrace{\Delta\Delta G^\ddagger_\text{NI}}_{\text{confinement}\;(\text{mixed sign})}
+ \underbrace{\Delta\Delta G^\ddagger_\text{FRZ}}_{\text{steric + electrostatic}}
+ \underbrace{\Delta\Delta G^\ddagger_\text{POL}}_{\text{polarisation}\;(\leq 0)}
+ \underbrace{\Delta\Delta G^\ddagger_\text{CT}}_{\text{charge transfer}\;(\leq 0)}
= \Delta\Delta G^\ddagger_\text{complete} \ll 0
$$

The best catalyst:

1. **Maximises the confinement benefit** — when the reaction mechanism
   allows it, binds **both** reactants in the preTS complex and positions
   them in a TS-like geometry, driving $\Delta\Delta G^\ddagger_\text{NI}$
   strongly negative and turning confinement into a catalytic contribution.
   When a TS-like ternary preTS is not accessible (mechanism-dependent),
   moderate binding avoids the positive NI penalty of overbinding a complex
   that lacks geometric pre-ordering.
2. **Maximises electrostatic TS stabilisation** — the frozen-density
   electric field of the catalyst stabilises the TS charge distribution
   more than the baseline geometry, driving $\Delta\Delta G^\ddagger_\text{FRZ}$
   negative.
3. **Maximises POL + CT at the TS** — orbital interactions that
   specifically lower the TS energy.

The A3EDA decomposition reveals **which of these factors** dominates for
a given catalyst, guiding rational catalyst design.


## 12. Summary of Barrier Formulas

### 3-Level (E and G surfaces)

| Quantity | Formula | Sign convention |
|----------|---------|-----------------|
| $\Delta^\ddagger_\text{nocat}$ | $\text{TS}_\text{nocat} - R_\text{nocat}$ | Reference barrier |
| $\Delta^\ddagger_\text{frz}$ | $\text{TS}_\text{frz} - \text{baseline}_\text{frz}$ | |
| $\Delta^\ddagger_\text{pol}$ | $\text{TS}_\text{pol} - \text{baseline}_\text{pol}$ | |
| $\Delta^\ddagger_\text{full}$ | $\text{TS}_\text{full} - \text{baseline}_\text{full}$ | |
| $\Delta\Delta^\ddagger_\text{FRZ}$ | $\Delta^\ddagger_\text{frz} - \Delta^\ddagger_\text{nocat}$ | mixed sign |
| $\Delta\Delta^\ddagger_\text{POL}$ | $\Delta^\ddagger_\text{pol} - \Delta^\ddagger_\text{frz}$ | ≤ 0 |
| $\Delta\Delta^\ddagger_\text{CT}$ | $\Delta^\ddagger_\text{full} - \Delta^\ddagger_\text{pol}$ | ≤ 0 |

### 4-Level (G surface with confinement)

| Quantity | Formula | Sign convention |
|----------|---------|-----------------|
| $\Delta G^\ddagger_\text{cat,NI}$ | $G_\text{ni}^\text{TS,full} - G_\text{ni}^\text{baseline,full}$ | NI barrier (full\_cat) |
| $\Delta G^\ddagger_\text{nocat,NI}$ | $G^\text{TS,nocat} - G_\text{ni}^\text{R,full}$ | NI barrier (nocat) |
| $\Delta\Delta G^\ddagger_\text{NI}$ | $\Delta G^\ddagger_\text{cat,NI} - \Delta G^\ddagger_\text{nocat,NI}$ | mixed sign (see §10) |
| $\Delta\Delta G^\ddagger_\text{FRZ}$ | $\Delta G^\ddagger_\text{frz}(G) - \Delta G^\ddagger_\text{cat,NI}$ | Electrostatic + steric |
| $\Delta\Delta G^\ddagger_\text{POL}$ | $\Delta G^\ddagger_\text{pol}(G) - \Delta G^\ddagger_\text{frz}(G)$ | ≤ 0 |
| $\Delta\Delta G^\ddagger_\text{CT}$ | $\Delta G^\ddagger_\text{full}(G) - \Delta G^\ddagger_\text{pol}(G)$ | ≤ 0 |
