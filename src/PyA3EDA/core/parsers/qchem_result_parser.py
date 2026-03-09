"""
Q-Chem Parser Module

Pure parsing functions that extract numerical data from Q-Chem output text content.
Each function focuses on a single parsing task without business logic or cross-file operations.
Returns raw parsed values that can be further processed by extraction logic.
"""
import re
from typing import Optional, Tuple, Dict, Any, Pattern, List

from PyA3EDA.core.utils.unit_converter import convert_unit


# Regex patterns for data extraction
PATTERNS = {
    # Energy patterns - separate for different contexts
    "final_energy": re.compile(r"Final energy is\s+([-+]?\d+\.\d+)(?:\s+([A-Za-z][A-Za-z0-9./\-]*))?\s*$", re.MULTILINE),
    "total_energy": re.compile(r"Total energy =\s+([-+]?\d+\.\d+)(?:\s+([A-Za-z][A-Za-z0-9./\-]*))?\s*$", re.MULTILINE),
    "optimization_status": re.compile(r"(OPTIMIZATION CONVERGED|TRANSITION STATE CONVERGED)"),
    "thermodynamics": re.compile(r"STANDARD THERMODYNAMIC QUANTITIES AT\s+([-+]?\d+\.\d+)\s*K\s+AND\s+([-+]?\d+\.\d+)\s*ATM"),
    "imaginary_frequencies": re.compile(r"This Molecule has\s+(\d+)\s+Imaginary Frequencies"),
    "zero_point_energy": re.compile(r"Zero point vibrational energy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)", re.MULTILINE),
    "qrrho_parameters": re.compile(r"Quasi-RRHO corrections using alpha\s*=\s*(\d+),\s*and omega\s*=\s*(\d+)\s*cm\^-1"),
    "qrrho_total_enthalpy": re.compile(r"QRRHO-Total Enthalpy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)", re.MULTILINE),
    "total_enthalpy_fallback": re.compile(r"Total Enthalpy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)", re.MULTILINE),
    "qrrho_total_entropy": re.compile(r"QRRHO-Total Entropy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)", re.MULTILINE),
    "total_entropy_fallback": re.compile(r"Total Entropy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)", re.MULTILINE),
    "translational_entropy": re.compile(r"Translational Entropy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)", re.MULTILINE),
    # SMD CDS energy patterns - capture values with units from detailed block
    "smd_g_enp": re.compile(r"\(3\)\s+G-ENP\(liq\) elect-nuc-pol free energy of system\s+([-+]?\d+\.\d+)\s+(a\.u\.)", re.MULTILINE),
    "smd_g_s": re.compile(r"\(6\)\s+G-S\(liq\) free energy of system\s+([-+]?\d+\.\d+)\s+(a\.u\.)", re.MULTILINE),
    "smd_cds_detail": re.compile(r"\(4\)\s+G-CDS\(liq\) cavity-dispersion-solvent structure\s+([-+]?\d+\.\d+)\s+(kcal/mol)", re.MULTILINE),
    "smd_cds_summary": re.compile(r"G_CDS\s+=\s+([-+]?\d+\.\d+)\s+(kcal/mol)", re.MULTILINE),
    "smd_cds_extended_print": re.compile(r"Total:\s+([-+]?\d+\.\d+)\s*\n\s*-+", re.MULTILINE),
    # EDA-specific patterns
    "eda_polarized_energy": re.compile(r"Energy prior to optimization \(guess energy\)\s*=\s*([-+]?\d+\.\d+)", re.MULTILINE),
    "eda_convergence_energy": re.compile(r"^\s*\d+\s+([-+]?\d+\.\d+)\s+[\d.e-]+\s+\d+\s+Convergence criterion met", re.MULTILINE),
    "bsse_energy": re.compile(r"BSSE \(kJ/mol\)\s*=\s*([-+]?\d+\.\d+)", re.MULTILINE)
}


def extract_with_pattern(content: str, primary_pattern: Pattern, fallback_pattern: Pattern = None, 
                        field_mapping: Dict[str, str] = None, default_unit: str = None) -> Tuple[Any, bool]:
    """
    Universal pattern extraction function that handles all parsing scenarios.
    Always uses findall() and takes the last match for consistency.
    
    Args:
        content: Text content to search
        primary_pattern: Primary regex pattern to try first
        fallback_pattern: Optional fallback regex pattern if primary fails
        field_mapping: Optional dictionary mapping group indices to field names
        default_unit: Default unit if pattern doesn't capture unit
        
    Returns:
        Tuple of (result, fallback_used) where result format depends on parameters:
        - Single value: float
        - Value with unit: (float, str)  
        - Multiple fields: Dict[str, Any]
        - Nothing found: None
    """
    fallback_used = False
    
    # Try primary pattern first
    matches = primary_pattern.findall(content)
    
    # Try fallback pattern if primary failed and fallback provided
    if not matches and fallback_pattern:
        matches = fallback_pattern.findall(content)
        fallback_used = True
    
    if not matches:
        return None, fallback_used
    
    # Get the last match (most recent/final occurrence)
    last_match = matches[-1]
    
    # Handle field mapping (for multi-group patterns)
    if field_mapping:
        result = {}
        if isinstance(last_match, tuple):
            for group_idx, field_name in field_mapping.items():
                if group_idx <= len(last_match):
                    value = last_match[group_idx - 1]  # findall is 0-indexed, field_mapping is 1-indexed
                    try:
                        if '.' in str(value):
                            result[field_name] = float(value)
                        else:
                            result[field_name] = int(value)
                    except (ValueError, TypeError):
                        result[field_name] = value
        else:
            # Single value with field mapping
            if 1 in field_mapping:
                try:
                    result[field_mapping[1]] = float(last_match) if '.' in str(last_match) else int(last_match)
                except (ValueError, TypeError):
                    result[field_mapping[1]] = last_match
        return result, fallback_used
    
    # Handle value with unit (tuple result)
    if isinstance(last_match, tuple):
        value = float(last_match[0])
        unit = last_match[1] if len(last_match) > 1 and last_match[1] else default_unit
        return (value, unit), fallback_used
    
    # Handle single value
    return float(last_match), fallback_used


# PURE PARSING FUNCTIONS - Each function parses one specific data type


def parse_final_energy(content: str, prefix: str = "E") -> Optional[Dict[str, Any]]:
    """Parse final energy from OPT calculations (Final energy is pattern)."""
    result, _ = extract_with_pattern(content, PATTERNS["final_energy"], default_unit="Ha")
    
    if result is not None:
        energy_value, energy_unit = result
        return {
            f"{prefix} ({energy_unit})": energy_value,
            f"{prefix} (kcal/mol)": convert_unit(energy_value, energy_unit, "kcal/mol")
        }
    return None


def parse_total_energy(content: str, prefix: str = "E") -> Optional[Dict[str, Any]]:
    """Parse total energy from SP calculations (Total energy = pattern)."""
    result, _ = extract_with_pattern(content, PATTERNS["total_energy"], default_unit="Ha")
    
    if result is not None:
        energy_value, energy_unit = result
        return {
            f"{prefix} ({energy_unit})": energy_value,
            f"{prefix} (kcal/mol)": convert_unit(energy_value, energy_unit, "kcal/mol")
        }
    return None


def parse_energy(content: str, prefix: str = "E") -> Optional[Dict[str, Any]]:
    """Parse energy with fallback - tries final energy first, then total energy."""
    result, fallback_used = extract_with_pattern(
        content, PATTERNS["final_energy"], PATTERNS["total_energy"], default_unit="Ha")
    
    if result is not None:
        energy_value, energy_unit = result
        return {
            f"{prefix} ({energy_unit})": energy_value,
            f"{prefix} (kcal/mol)": convert_unit(energy_value, energy_unit, "kcal/mol"),
            "energy_fallback_used": fallback_used
        }
    return None


def parse_enthalpy(content: str) -> Optional[Dict[str, Any]]:
    """Parse enthalpy correction from Q-Chem output content."""
    result, fallback_used = extract_with_pattern(
        content, PATTERNS["qrrho_total_enthalpy"], PATTERNS["total_enthalpy_fallback"])
    
    if result is not None:
        enthalpy_value, enthalpy_unit = result
        return {
            "Total Enthalpy Corr. (kcal/mol)": convert_unit(enthalpy_value, enthalpy_unit, "kcal/mol"),
            "enthalpy_fallback_used": fallback_used
        }
    return None


def parse_entropy(content: str) -> Optional[Dict[str, Any]]:
    """Parse entropy correction from Q-Chem output content."""
    result, fallback_used = extract_with_pattern(
        content, PATTERNS["qrrho_total_entropy"], PATTERNS["total_entropy_fallback"])
    
    if result is not None:
        entropy_value, entropy_unit = result
        return {
            "Total Entropy Corr. (kcal/mol.K)": convert_unit(entropy_value, entropy_unit, "kcal/mol.K"),
            "entropy_fallback_used": fallback_used
        }
    return None


def parse_translational_entropy(content: str) -> Optional[Dict[str, Any]]:
    """Parse translational entropy from Q-Chem output content."""
    result, _ = extract_with_pattern(content, PATTERNS["translational_entropy"])
    
    if result is not None:
        entropy_value, entropy_unit = result
        return {
            "S_trans (kcal/mol.K)": convert_unit(entropy_value, entropy_unit, "kcal/mol.K")
        }
    return None


def parse_optimization_status(content: str) -> Optional[Dict[str, Any]]:
    """Parse optimization status from Q-Chem output content."""
    result, _ = extract_with_pattern(content, PATTERNS["optimization_status"], field_mapping={1: "status"})
    return {"Optimization Status": result["status"]} if result else None


def parse_thermodynamic_conditions(content: str) -> Optional[Dict[str, Any]]:
    """Parse temperature and pressure from Q-Chem output content."""
    result, _ = extract_with_pattern(content, PATTERNS["thermodynamics"], field_mapping={1: "temperature", 2: "pressure"})
    return {"Temperature (K)": result["temperature"], "Pressure (atm)": result["pressure"]} if result else None


def parse_qrrho_parameters(content: str) -> Optional[Dict[str, Any]]:
    """Parse QRRHO parameters from Q-Chem output content."""
    result, _ = extract_with_pattern(content, PATTERNS["qrrho_parameters"], field_mapping={1: "alpha", 2: "omega"})
    return {"Alpha": result["alpha"], "Omega (cm^-1)": result["omega"]} if result else None


def parse_imaginary_frequencies(content: str) -> Optional[Dict[str, Any]]:
    """Parse imaginary frequencies count from Q-Chem output content."""
    result, _ = extract_with_pattern(content, PATTERNS["imaginary_frequencies"], field_mapping={1: "count"})
    return {"Imaginary Frequencies": result["count"]} if result else None


def parse_zero_point_energy(content: str) -> Optional[Dict[str, Any]]:
    """Parse zero point energy from Q-Chem output content."""
    result, _ = extract_with_pattern(content, PATTERNS["zero_point_energy"], default_unit="kcal/mol")
    
    if result is not None:
        zpe_value, zpe_unit = result
        return {f"Zero Point Energy ({zpe_unit})": zpe_value}
    return None


def parse_smd_detail_block(content: str) -> Optional[Dict[str, Any]]:
    """
    Parse SMD detailed energy components from Q-Chem output (OPT and regular SP files).
    Extracts G-ENP, G-S, and detailed G-CDS values from the detailed SMD block with units.
    """
    result = {}
    
    # Extract G-ENP with unit (a.u.) - consistent with other parsers
    g_enp_result, _ = extract_with_pattern(content, PATTERNS["smd_g_enp"], default_unit="Ha")
    if g_enp_result is not None:
        if isinstance(g_enp_result, tuple):
            g_enp_value, g_enp_unit = g_enp_result
            # Convert a.u. to Ha for consistency
            g_enp_unit = "Ha" if g_enp_unit == "a.u." else g_enp_unit
        else:
            g_enp_value, g_enp_unit = g_enp_result, "Ha"
        result["g_enp_final"] = g_enp_value
    
    # Extract G-S with unit (a.u.) - consistent with other parsers
    g_s_result, _ = extract_with_pattern(content, PATTERNS["smd_g_s"], default_unit="Ha")
    if g_s_result is not None:
        if isinstance(g_s_result, tuple):
            g_s_value, g_s_unit = g_s_result
            # Convert a.u. to Ha for consistency
            g_s_unit = "Ha" if g_s_unit == "a.u." else g_s_unit
        else:
            g_s_value, g_s_unit = g_s_result, "Ha"
        result["g_s_final"] = g_s_value
        
    # Extract detailed CDS with unit (kcal/mol) - consistent with other parsers
    cds_detail_result, _ = extract_with_pattern(content, PATTERNS["smd_cds_detail"], default_unit="kcal/mol")
    if cds_detail_result is not None:
        if isinstance(cds_detail_result, tuple):
            cds_detail_value, cds_detail_unit = cds_detail_result
        else:
            cds_detail_value, cds_detail_unit = cds_detail_result, "kcal/mol"
        result["cds_detail_final"] = cds_detail_value
    
    return result if result else None


def parse_smd_cds_extended_print(content: str) -> Optional[float]:
    """
    Parse CDS value from extended print pattern (uses "Total:" pattern).
    This is used in EDA calc_type calculations for CDS validation.
    Returns the CDS value in kcal/mol.
    """
    cds_value, _ = extract_with_pattern(content, PATTERNS["smd_cds_extended_print"])
    return cds_value if cds_value is not None else None


def parse_eda_polarized_energy(content: str, prefix: str = "SP_E") -> Optional[Dict[str, Any]]:
    """Parse polarized energy from EDA SP calculations (pol types)."""
    result, _ = extract_with_pattern(content, PATTERNS["eda_polarized_energy"], default_unit="Ha")
    
    if result is not None:
        # Assume it's a single float value in Hartree
        energy_value = result if isinstance(result, (int, float)) else result[0]
        return {
            f"{prefix} (Ha)": energy_value,
            f"{prefix} (kcal/mol)": convert_unit(energy_value, "Ha", "kcal/mol")
        }
    return None


def parse_eda_convergence_energy(content: str, prefix: str = "SP_E") -> Optional[Dict[str, Any]]:
    """Parse full energy from EDA SP calculations (frz/full type)."""
    result, _ = extract_with_pattern(content, PATTERNS["eda_convergence_energy"], default_unit="Ha")
    
    if result is not None:
        # Assume it's a single float value in Hartree
        energy_value = result if isinstance(result, (int, float)) else result[0]
        return {
            f"{prefix} (Ha)": energy_value,
            f"{prefix} (kcal/mol)": convert_unit(energy_value, "Ha", "kcal/mol")
        }
    return None


def parse_bsse_energy(content: str) -> Optional[Dict[str, Any]]:
    """Parse BSSE energy from EDA SP calculations (full type correction)."""
    result, _ = extract_with_pattern(content, PATTERNS["bsse_energy"], default_unit="kJ/mol")

    if result is not None:
        # Assume it's a single float value in kJ/mol
        energy_value = result if isinstance(result, (int, float)) else result[0]
        return {
            "bsse_energy (kJ/mol)": energy_value,
            "bsse_energy (kcal/mol)": convert_unit(energy_value, "kJ/mol", "kcal/mol")
        }
    return None