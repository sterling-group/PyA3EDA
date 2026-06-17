"""
Constants Module

Defines conversion factors and a mapping for sanitizing filenames.
"""


class Constants:
    """Physical and chemical constants and conversion factors.

    Details:
        Values are based on CODATA 2022 recommended values of fundamental physical constants unless otherwise stated.
        Reference: https://physics.nist.gov/constants https://physics.nist.gov/cuu/pdf/wall_2022.pdf
        DOI: 10.1103/RevModPhys.93.025010

        Constants and their units:
            HARTREE_TO_J: Hartree to Joules (J)
            TO_KILO: multiplier for kilo (1e-3)
            HARTREE_TO_KJ: Hartree to kilojoules (kJ)
            AVOGADRO: Avogadro's number (mol^-1)
            HARTREE_TO_KJMOL: Hartree to kilojoules per mole (kJ/mol)
            KJMOL_TO_KCALMOL: kilojoules per mole to kilocalories per mole (kcal/mol)
            HARTREE_TO_KCALMOL: Hartree to kilocalories per mole (kcal/mol)
            KJMOL_TO_HARTREE: kilojoules per mole to Hartree (not from CODATA 2022, used for back conversion until value is adjusted internally)
            BOLTZMANN: Boltzmann constant (J/K)
            MOLAR_GAS_CONSTANT: Gas constant R (J/(mol.K))
            M3_TO_L: cubic meter to liters (L)
    """

    HARTREE_TO_J = 4.3597447222060e-18  # Hartree to J
    TO_KILO = 1.0e-3
    HARTREE_TO_KJ = HARTREE_TO_J * TO_KILO  # Hartree to kJ
    AVOGADRO = 6.02214076e23  # Avogadro's number in mol^-1
    HARTREE_TO_KJMOL = HARTREE_TO_KJ * AVOGADRO  # Hartree to kJ/mol
    KJMOL_TO_KCALMOL = 1.0 / 4.184  # kJ/mol to kcal/mol
    HARTREE_TO_KCALMOL = HARTREE_TO_KJMOL * KJMOL_TO_KCALMOL  # Hartree to kcal/mol

    KJMOL_TO_HARTREE = 1.0 / 2625.5311584660003  # value for bsse conversion

    BOLTZMANN = 1.380649e-23  # Boltzmann constant in J/K
    MOLAR_GAS_CONSTANT = AVOGADRO * BOLTZMANN  # Gas constant R in J/(mol.K)
    ATM_TO_PA = 101325.0  # 1 atm = 101325 Pa
    M3_TO_L = 1000.0  # cubic meter (m^3) = 1000 liters (L) = 1000 dm^3

    # Default energy unit for output
    ENERGY_UNIT = "kcal/mol"

    ESCAPE_MAP = {
        " ": "-space-",
        "(": "-lparen-",
        ")": "-rparen-",
        "[": "-lbracket-",
        "]": "-rbracket-",
        "{": "-lbrace-",
        "}": "-rbrace-",
        ",": "-comma-",
        ";": "-semicolon-",
        "*": "-asterisk-",
        "?": "-qmark-",
        "&": "-and-",
        "|": "-pipe-",
        "<": "-lt-",
        ">": "-gt-",
        '"': "-dq-",
        "'": "-sq-",
        "\\": "-backslash-",
        ":": "-colon-",
        "$": "-dollar-",
        "~": "-tilde-",
        "!": "-exclamation-",
        "=": "-equal-",
        "\t": "-tab-",
        "\n": "-newline-",
    }
