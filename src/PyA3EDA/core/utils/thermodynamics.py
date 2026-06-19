"""
Thermodynamics Utilities

Standard state corrections for converting between gas and solution phase.

References:
    Ben-Naim, A. (2007) J. Phys. Chem. B, 111(11), 2896-2902.
    Ribeiro, R. F., et al. (2011) J. Phys. Chem. B, 115(49), 14556-14562.
"""

import math

from PyA3EDA.core.constants import Constants
from PyA3EDA.core.utils.unit_converter import convert_unit


def calculate_standard_state_correction(temperature: float, pressure: float) -> float:
    """Calculate standard state correction: G(gas phase) -> G(1 M solution).

    Converts Gibbs free energy from gas phase standard state to 1 M solution
    standard state using: dG = RT ln(RT*C_1M / P)
    At 298.15 K, 1 atm: dG ≈ 1.89 kcal/mol

    Args:
        temperature: Temperature in Kelvin from calculation.
        pressure: Pressure in atm from calculation.

    Returns:
        Correction in kcal/mol to add to G(gas) to get G(1M).


    """
    pressure_pa = convert_unit(pressure, "atm", "Pa")
    ratio = (
        Constants.MOLAR_GAS_CONSTANT * temperature * Constants.M3_TO_L
    ) / pressure_pa
    correction_j_mol = Constants.MOLAR_GAS_CONSTANT * temperature * math.log(ratio)
    return convert_unit(correction_j_mol, "J/mol", "kcal/mol")
