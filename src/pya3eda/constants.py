"""Physical constants and conversion factors (CODATA 2022)."""

# Energy conversions
HARTREE_TO_J: float = 4.3597447222060e-18
HARTREE_TO_KJ: float = HARTREE_TO_J * 1.0e-3
AVOGADRO: float = 6.02214076e23
HARTREE_TO_KJMOL: float = HARTREE_TO_KJ * AVOGADRO
KJMOL_TO_KCALMOL: float = 1.0 / 4.184
HARTREE_TO_KCALMOL: float = HARTREE_TO_KJMOL * KJMOL_TO_KCALMOL
KJMOL_TO_HARTREE: float = 1.0 / 2625.5311584660003

# Thermodynamic constants
BOLTZMANN: float = 1.380649e-23  # J/K
MOLAR_GAS_CONSTANT: float = AVOGADRO * BOLTZMANN  # J/(mol·K)
ATM_TO_PA: float = 101325.0
M3_TO_L: float = 1000.0
