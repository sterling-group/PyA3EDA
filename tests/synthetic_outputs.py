"""Synthetic Q-Chem output snippets for fully self-contained tests.

Each string mimics the relevant sections of a real Q-Chem output, trimmed
to just the lines that the parser expects.  Where the parser picks the *last*
match, the snippets include earlier decoy entries so that behaviour is tested.
"""

from __future__ import annotations

# ===================================================================
# OPT output — minimum (prop2enal-like, 8-atom molecule)
# ===================================================================

OPT_OUTPUT = """\
Running on host compute01
 $molecule
 0 1
 C   0.4264  -1.6581  -0.2980
 H   0.5113  -1.4491  -1.3693
 O  -2.6743   0.0080   0.3121
 C  -0.6299  -1.2095   0.4031
 H  -0.7473  -1.4003   1.4769
 C  -1.6981  -0.4255  -0.2570
 H  -1.5427  -0.2518  -1.3530
 H   1.2220  -2.2369   0.1735
 $end

 Total energy =  -191.50000000

 Total energy =  -191.60000000

 Total energy =  -191.70000000

 Standard Nuclear Orientation (Angstroms)
    I     Atom           X            Y            Z
 ----------------------------------------------------------------
    1      C       0.0000000    0.0000000    0.0000000
    2      H       1.0000000    0.0000000    0.0000000
    3      O       0.0000000    1.0000000    0.0000000
    4      C       0.0000000    0.0000000    1.0000000
    5      H       1.0000000    1.0000000    0.0000000
    6      C       0.0000000    1.0000000    1.0000000
    7      H       1.0000000    0.0000000    1.0000000
    8      H       1.0000000    1.0000000    1.0000000
 ----------------------------------------------------------------

 Final energy is -191.709724458668

        ******************************
        **  OPTIMIZATION CONVERGED  **
        ******************************

 STANDARD THERMODYNAMIC QUANTITIES AT   298.15 K  AND     1.00 ATM

   This Molecule has  0 Imaginary Frequencies
   Zero point vibrational energy:       38.832 kcal/mol

   Translational Entropy:        37.991  cal/mol.K
   Rotational Entropy:           23.366  cal/mol.K
   Vibrational Entropy:           5.187  cal/mol.K

   Total Enthalpy:               42.162 kcal/mol
   Total Entropy:                66.544  cal/mol.K

   QRRHO-Total Enthalpy:         42.119 kcal/mol
   QRRHO-Total Entropy:          66.534  cal/mol.K

 Standard Nuclear Orientation (Angstroms)
    I     Atom           X            Y            Z
 ----------------------------------------------------------------
    1      C       0.4205497061    -1.6552069740    -0.2948977242
    2      H       0.5113499338    -1.4491233769    -1.3693384794
    3      O      -2.6742667923     0.0079944211     0.3121436067
    4      C      -0.6299042871    -1.2095136751     0.4031142044
    5      H      -0.7472844868    -1.4002899188     1.4768601673
    6      C      -1.6980593642    -0.4255425136    -0.2570126405
    7      H      -1.5426968323    -0.2517608576    -1.3529938192
    8      H       1.2220261228    -2.2368881052     0.1735096850
 ----------------------------------------------------------------

 Total job time:  180.20s(wall), 5455.65s(cpu)
 Mon Feb 23 11:08:44 2026

        *************************************************************
        *                                                           *
        *  Thank you very much for using Q-Chem.  Have a nice day.  *
        *                                                           *
        *************************************************************
"""


# ===================================================================
# TS output — transition state (1 imaginary frequency)
# ===================================================================

TS_OUTPUT = """\
Running on host compute02
 $molecule
 0 1
 C   0.0  0.0  0.0
 C   1.0  0.0  0.0
 C   0.0  1.0  0.0
 C   0.0  0.0  1.0
 O   1.0  1.0  0.0
 H   0.0  1.0  1.0
 H   1.0  0.0  1.0
 H   1.0  1.0  1.0
 H   2.0  0.0  0.0
 H   0.0  2.0  0.0
 H   0.0  0.0  2.0
 H   2.0  1.0  0.0
 $end

 Total energy =  -347.51400000

 Total energy =  -347.51446000

 Standard Nuclear Orientation (Angstroms)
    I     Atom           X            Y            Z
 ----------------------------------------------------------------
    1      C       0.0000000    0.0000000    0.0000000
 ----------------------------------------------------------------

 Final energy is -347.514465274291

        ******************************
        ** TRANSITION STATE CONVERGED  **
        ******************************

 STANDARD THERMODYNAMIC QUANTITIES AT   298.15 K  AND     1.00 ATM

   This Molecule has  1 Imaginary Frequencies
   Zero point vibrational energy:       98.200 kcal/mol

   Translational Entropy:        39.500  cal/mol.K
   Rotational Entropy:           28.100  cal/mol.K
   Vibrational Entropy:          12.300  cal/mol.K

   Total Enthalpy:              103.450 kcal/mol
   Total Entropy:                79.900  cal/mol.K

   QRRHO-Total Enthalpy:        103.200 kcal/mol
   QRRHO-Total Entropy:          79.800  cal/mol.K

 Standard Nuclear Orientation (Angstroms)
    I     Atom           X            Y            Z
 ----------------------------------------------------------------
    1      C       1.0000000    2.0000000    3.0000000
 ----------------------------------------------------------------

 Total job time:  3600.50s(wall), 86400.00s(cpu)

        *************************************************************
        *                                                           *
        *  Thank you very much for using Q-Chem.  Have a nice day.  *
        *                                                           *
        *************************************************************
"""


# ===================================================================
# SP output — single point with SMD solvation
# ===================================================================

SP_OUTPUT = """\
Running on host compute01
 $molecule
 0 1
 C   0.4205  -1.6552  -0.2949
 H   0.5113  -1.4491  -1.3693
 O  -2.6743   0.0080   0.3121
 C  -0.6299  -1.2095   0.4031
 H  -0.7473  -1.4003   1.4769
 C  -1.6981  -0.4255  -0.2570
 H  -1.5427  -0.2518  -1.3530
 H   1.2220  -2.2369   0.1735
 $end

 ====================  Detailed SMD energy components  ====================
 (3)  G-ENP(liq) elect-nuc-pol free energy of system     -191.916357295 a.u.
 (4)  G-CDS(liq) cavity-dispersion-solvent structure            -0.7306 kcal/mol
 (6)  G-S(liq) free energy of system                     -191.917521529 a.u.
 ==========================================================================
 Summary of SMD free energies:
        G_CDS  =    -0.7306 kcal/mol (non-electrostatic energy)
        G(tot) =  -191.91752153 a.u. = G_ENP + G_CDS
 Total energy =  -191.91752153

 Total job time:  22.51s(wall), 530.49s(cpu)

        *************************************************************
        *                                                           *
        *  Thank you very much for using Q-Chem.  Have a nice day.  *
        *                                                           *
        *************************************************************
"""


# ===================================================================
# EDA pol_cat output — uses guess energy, multiple iterations
# ===================================================================

EDA_POL_OUTPUT = """\
Running on host compute03
 $molecule
 0 1
 C   0.0  0.0  0.0
 $end

Energy prior to optimization (guess energy) = -1814.000000000000
   15   -1814.1940740786      6.92e-09     00000 Convergence criterion met

    Total:               -2.432
 ----------------------------------

Energy prior to optimization (guess energy) = -1814.100000000000
   16   -1814.1949316028      4.81e-09     00000 Convergence criterion met

    Total:               -2.413
 ----------------------------------

Energy prior to optimization (guess energy) = -1814.157030967601
   16   -1814.1949987486      5.40e-09     00000 Convergence criterion met

    Total:               -2.414
 ----------------------------------

 STANDARD THERMODYNAMIC QUANTITIES AT   298.15 K  AND     1.00 ATM

   This Molecule has  0 Imaginary Frequencies
   Zero point vibrational energy:       40.500 kcal/mol

   Translational Entropy:        38.500  cal/mol.K
   Rotational Entropy:           24.500  cal/mol.K
   Vibrational Entropy:           6.500  cal/mol.K

   Total Enthalpy:               44.500 kcal/mol
   Total Entropy:                70.500  cal/mol.K

   QRRHO-Total Enthalpy:         44.400 kcal/mol
   QRRHO-Total Entropy:          70.400  cal/mol.K

 Total job time:  500.00s(wall), 12000.00s(cpu)

        *************************************************************
        *                                                           *
        *  Thank you very much for using Q-Chem.  Have a nice day.  *
        *                                                           *
        *************************************************************
"""


# ===================================================================
# EDA frz_cat output — uses convergence energy
# ===================================================================

EDA_FRZ_OUTPUT = """\
Running on host compute03
 $molecule
 0 1
 C   0.0  0.0  0.0
 $end

    5   -1814.1200000000      1.00e-07     00000 Convergence criterion met

    Total:               -2.100
 ----------------------------------

   10   -1814.1288377459      3.50e-09     00000 Convergence criterion met

    Total:               -2.200
 ----------------------------------

 STANDARD THERMODYNAMIC QUANTITIES AT   298.15 K  AND     1.00 ATM

   This Molecule has  0 Imaginary Frequencies
   Zero point vibrational energy:       39.500 kcal/mol

   Translational Entropy:        37.500  cal/mol.K
   Rotational Entropy:           23.500  cal/mol.K
   Vibrational Entropy:           5.500  cal/mol.K

   Total Enthalpy:               43.500 kcal/mol
   Total Entropy:                69.500  cal/mol.K

   QRRHO-Total Enthalpy:         43.400 kcal/mol
   QRRHO-Total Entropy:          69.400  cal/mol.K

 Total job time:  400.00s(wall), 9600.00s(cpu)

        *************************************************************
        *                                                           *
        *  Thank you very much for using Q-Chem.  Have a nice day.  *
        *                                                           *
        *************************************************************
"""


# ===================================================================
# EDA full_cat SP output — convergence + BSSE + CDS
# ===================================================================

EDA_FULL_SP_OUTPUT = """\
Running on host compute04
 $molecule
 0 1
 C   0.0  0.0  0.0
 $end

    Total:               -2.411
 ----------------------------------

    5   -1814.9100674026      3.76e-07     ortho_decomp 00000 Convergence criterion met
   21   -1815.1356189593      6.50e-09     00000 Convergence criterion met
   15   -1815.1481418253      1.92e-09     00000 Convergence criterion met

   Evaluating the BSSE with fragment SCF in the supersystem basis
   BSSE (kJ/mol) = 0.3295

 Total job time:  800.00s(wall), 19200.00s(cpu)

        *************************************************************
        *                                                           *
        *  Thank you very much for using Q-Chem.  Have a nice day.  *
        *                                                           *
        *************************************************************
"""


# ===================================================================
# Crash / status variants
# ===================================================================

CRASH_SCF_OUTPUT = """\
Running on host compute01

SCF failed to converge
"""

CRASH_FATAL_OUTPUT = """\
Running on host compute01

Q-Chem fatal error occurred in some module
"""

RUNNING_OUTPUT = """\
Running on host compute01
Starting calculation...
"""

CANCELLED_ERR = "CANCELLED AT 2024-01-01T12:00:00"

QCHEM_ERR = "Error in Q-Chem run"


# ===================================================================
# YAML config — minimal realistic
# ===================================================================

SAMPLE_CONFIG_YAML = """\
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
  - name: lip
  - name: bf3

reactants:
  - name: prop2enal
    include: true
  - name: buta13diene
    include: false

products:
  - name: cyclohex3ene1carbaldehyde
    include: true
"""
