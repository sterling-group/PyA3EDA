"""
Data extraction module with clean separation of concerns.

This module provides pure extraction functions:
- extract_all_data: Discovers and extracts all data, returns structured results

Clean separation of concerns:
- Extractor: Handles discovery and extraction only
- Exporter: Handles file writing and directory organization  
- Workflow: Orchestrates extraction and export

Single source of truth via iter_input_paths()
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from PyA3EDA.core.utils.file_utils import read_text
from PyA3EDA.core.parsers.qchem_result_parser import (
    parse_energy, parse_final_energy, parse_total_energy, parse_enthalpy, parse_entropy, 
    parse_translational_entropy, parse_optimization_status, parse_thermodynamic_conditions, 
    parse_qrrho_parameters, parse_imaginary_frequencies, parse_zero_point_energy, 
    parse_smd_detail_block, parse_smd_cds_extended_print, parse_eda_polarized_energy, 
    parse_eda_convergence_energy, parse_bsse_energy
)
from PyA3EDA.core.parsers.output_xyz_parser import parse_qchem_output_xyz
from PyA3EDA.core.status.status_checker import should_process_file
from PyA3EDA.core.utils.unit_converter import convert_unit
from PyA3EDA.core.utils.thermodynamics import calculate_standard_state_correction
from PyA3EDA.core.builders.builder import iter_input_paths


# CORE EXTRACTION FUNCTIONS (pure)

def _extract_base_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Extract base metadata fields common to all extraction types."""
    return {
        "Species": metadata.get("Species", "unknown"),
        "Category": metadata.get("Category", "unknown"),
        "Branch": metadata.get("Branch", "unknown"),
        "Calc_Type": metadata.get("Calc_Type", "unknown"),
        "Catalyst": metadata.get("Catalyst", ""),
        "Mode": metadata.get("Mode", "unknown"),
        "eda2": metadata.get("eda2", "unknown"),
        # Component information for profile extraction
        "reactants": metadata.get("reactants", []),
        "products": metadata.get("products", []),
        "catalysts": metadata.get("catalysts", []),
        "all_reactants": metadata.get("all_reactants", []),
        "all_products": metadata.get("all_products", []),
        "all_catalysts": metadata.get("all_catalysts", [])
    }


def _extract_opt_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Extract OPT-specific metadata fields."""
    base_metadata = _extract_base_metadata(metadata)
    base_metadata.update({
        "Method": metadata.get("Method", "unknown"),
        "Method_Combo": metadata.get("Method_Combo", "unknown"),
        "Basis": metadata.get("Basis", "unknown"),
        "Dispersion": metadata.get("Dispersion", "unknown"),
        "Solvent": metadata.get("Solvent", "unknown")
    })
    return base_metadata


def _extract_sp_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Extract SP-specific metadata fields."""
    base_metadata = _extract_base_metadata(metadata)
    base_metadata.update({
        # Base method info for folder structure
        "Method_Combo": metadata.get("Method_Combo", "unknown"),
        # SP-specific method info
        "SP_Method": metadata.get("SP_Method", "unknown"),
        "SP_Method_Combo": metadata.get("SP_Method_Combo", "unknown"),
        "SP_Basis": metadata.get("SP_Basis", "unknown"),
        "SP_Dispersion": metadata.get("SP_Dispersion", "unknown"),
        "SP_Solvent": metadata.get("SP_Solvent", "unknown")
    })
    return base_metadata


def extract_opt_data(file_path: Path, metadata: Dict[str, Any], criteria: str = "SUCCESSFUL") -> Optional[Dict[str, Any]]:
    """
    Extract all data from OPT output file.
    
    Args:
        file_path: Path to OPT output file
        metadata: File metadata from builder
        criteria: Status criteria for file processing
        
    Returns:
        Dictionary with extracted OPT data or None if extraction fails
    """
    # Check if file should be processed with enhanced OPT validation
    should_process, reason = should_process_file(file_path, criteria, metadata)
    if not should_process:
        logging.debug(f"Skipping file {reason}: {file_path}")
        return None
        
    # Read file content
    content = read_text(file_path)
    if not content:
        logging.warning(f"Could not read content from: {file_path}")
        return None
    
    # Extract thermodynamic data (includes metadata and H/G calculation)
    data = extract_opt_thermodynamic_data(content, metadata)
    if not data:
        logging.warning(f"Failed to extract thermodynamic data from: {file_path}")
        return None
    
    return data


def extract_sp_data(file_path: Path, metadata: Dict[str, Any], criteria: str = "SUCCESSFUL", opt_content: str = None) -> Optional[Dict[str, Any]]:
    """
    Extract all data from SP output file with OPT corrections.
    
    Args:
        file_path: Path to SP output file
        metadata: File metadata from builder
        criteria: Status criteria for file processing
        opt_content: OPT file content for thermodynamic corrections
        
    Returns:
        Dictionary with extracted SP data or None if extraction fails
    """
    # Check if file should be processed
    should_process, reason = should_process_file(file_path, criteria, metadata)
    if not should_process:
        logging.debug(f"Skipping file {reason}: {file_path}")
        return None
        
    # Read file content
    content = read_text(file_path)
    if not content:
        logging.warning(f"Could not read content from: {file_path}")
        return None
    
    # Extract SP thermodynamic data (includes metadata and H/G calculation)
    data = extract_sp_thermodynamic_data(content, metadata, opt_content)
    if not data:
        logging.warning(f"Failed to extract SP data from: {file_path}")
        return None
    
    return data


def extract_xyz_data(file_path: Path, metadata: Dict[str, Any], criteria: str = "SUCCESSFUL") -> Optional[Dict[str, Any]]:
    """
    Extract coordinate data from output file for XYZ export.
    
    Args:
        file_path: Path to output file
        metadata: File metadata from builder
        criteria: Status criteria for file processing
        
    Returns:
        Dictionary with coordinate data or None if extraction fails
    """
    # Check if file should be processed
    should_process, reason = should_process_file(file_path, criteria, metadata)
    if not should_process:
        logging.debug(f"Skipping XYZ extraction for {file_path.name}: {reason}")
        return None
    
    # Read file content
    content = read_text(file_path)
    if not content:
        logging.warning(f"Could not read content from: {file_path}")
        return None
        
    # Use the species identifier from metadata for XYZ parsing
    identifier = metadata.get("Species", file_path.stem)
    xyz_data = parse_qchem_output_xyz(content, identifier)
    
    if xyz_data:
        return {
            "coordinates": xyz_data,
            "Species": metadata.get("Species", "unknown"),
            "output_file_stem": file_path.stem,
            "data_type": metadata.get("Mode", "unknown")
        }
    else:
        logging.warning(f"Failed to parse XYZ coordinates from: {file_path}")
        return None


def extract_opt_thermodynamic_data(content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Extract thermodynamic data from OPT calculation."""
    data = {}

    # Basic energy extraction - parse_energy returns a dictionary with default prefix (keeps "E")
    energy_data = parse_energy(content)
    if energy_data:
        data.update(energy_data)
    else:
        return {}  # Cannot proceed without energy
    
    # Thermodynamic data
    if enthalpy_data := parse_enthalpy(content):
        data.update(enthalpy_data)
    
    if entropy_data := parse_entropy(content):
        data.update(entropy_data)
    
    if s_trans_data := parse_translational_entropy(content):
        data.update(s_trans_data)
    
    if thermo_data := parse_thermodynamic_conditions(content):
        data.update(thermo_data)
    
    if qrrho_data := parse_qrrho_parameters(content):
        data.update(qrrho_data)
    
    if zpe_data := parse_zero_point_energy(content):
        data.update(zpe_data)
    
    if imag_freq := parse_imaginary_frequencies(content):
        data.update(imag_freq)
    
    if opt_status := parse_optimization_status(content):
        data.update(opt_status)
    
    # Calculate H and G with metadata context (need Solvent key)
    data.update(metadata)
    calculate_enthalpy_and_gibbs(data, mode="opt")

    return data


def extract_sp_thermodynamic_data(sp_content: str, metadata: Dict[str, Any], opt_content: str = None) -> Dict[str, Any]:
    """Extract thermodynamic data from SP calculation based on calc_type presence."""
    data = {}
    
    # Determine extraction strategy based on calc_type presence
    calc_type = metadata.get("Calc_Type", "").strip()
    
    if not calc_type:
        # No calc_type = Regular SP calculation
        data = _extract_regular_sp(sp_content, opt_content)
    else:
        # Has calc_type = EDA calculation
        data = _extract_eda_sp(sp_content, calc_type.lower(), metadata, opt_content)
    
    if not data:
        return {}
    
    # Apply thermodynamic corrections from OPT file
    if opt_content:
        apply_thermodynamic_corrections(data, opt_content)
    
    # Calculate H and G with metadata context (need SP_Solvent key)
    data.update(metadata)
    calculate_enthalpy_and_gibbs(data, mode="sp")
    
    return data


def extract_smd_detail_block_data(content: str) -> Dict[str, Any]:
    """
    Extract SMD data from detailed SMD summary block (OPT and regular SP files).
    Returns G_S, G_ENP, and G_CDS values in both Hartree and kcal/mol.
    """
    data = {}
    
    # Parse SMD detail block using the parser
    smd_data = parse_smd_detail_block(content)
    if not smd_data:
        return data
    
    # Extract G_S and G_ENP components (both in Hartree from parser)
    if "g_s_final" in smd_data and "g_enp_final" in smd_data and "cds_detail_final" in smd_data:
        g_s_ha = smd_data["g_s_final"]
        g_enp_ha = smd_data["g_enp_final"]
        g_cds_ha = g_s_ha - g_enp_ha  # Calculate CDS difference
        g_cds_detail_kcal = smd_data["cds_detail_final"]
        
        data.update({
            "G_S (Ha)": g_s_ha,
            "G_S (kcal/mol)": convert_unit(g_s_ha, "Ha", "kcal/mol"),
            "G_ENP (Ha)": g_enp_ha,
            "G_ENP (kcal/mol)": convert_unit(g_enp_ha, "Ha", "kcal/mol"),
            "G_CDS (Ha)": g_cds_ha,
            "G_CDS (kcal/mol)": g_cds_detail_kcal
        })
    
    return data


def extract_cds_extended_print(sp_content: str) -> Dict[str, Any]:
    """
    Extract CDS value from extended print pattern (EDA calc_type calculations).
    Returns CDS data in both Hartree and kcal/mol without validation.
    """
    data = {}
    
    # Extract CDS from SP extended print pattern
    sp_cds_kcal = parse_smd_cds_extended_print(sp_content)
    if sp_cds_kcal is None:
        logging.warning("Failed to extract CDS from SP extended print. Use print=2 in smx block.")
        return {}
    
    # Convert to Hartree and prepare data
    sp_cds_ha = convert_unit(sp_cds_kcal, "kcal/mol", "Ha")
    
    data.update({
        "G_CDS (Ha)": sp_cds_ha,
        "G_CDS (kcal/mol)": sp_cds_kcal
    })
    
    return data


def validate_cds_against_opt(sp_cds_kcal: float, opt_content: str) -> Dict[str, Any]:
    """
    Validate SP CDS value against OPT detail block data.
    Pure validation function - receives CDS value and validates against OPT.
    Returns validation flags and reference data.
    """
    validation_data = {}
    
    # Parse OPT detail block for validation reference (use parser, not extractor)
    opt_detail_data = parse_smd_detail_block(opt_content)
    if not opt_detail_data:
        logging.warning("Cannot validate CDS - failed to parse OPT detail block")
        return {}
    
    # Calculate OPT CDS from components or use summary value
    opt_cds_kcal = None
    if "g_s_final" in opt_detail_data and "g_enp_final" in opt_detail_data:
        # Calculate from components (most accurate)
        g_s_ha = opt_detail_data["g_s_final"]
        g_enp_ha = opt_detail_data["g_enp_final"]
        g_cds_ha = g_s_ha - g_enp_ha
        opt_cds_kcal = convert_unit(g_cds_ha, "Ha", "kcal/mol")
    elif "cds_summary_final" in opt_detail_data:
        # Fallback to summary value
        opt_cds_kcal = opt_detail_data["cds_summary_final"]
    
    if opt_cds_kcal is None:
        logging.warning("Cannot validate CDS - OPT CDS value not available")
        return {}
    
    # Perform validation with tolerance check
    cds_diff = abs(sp_cds_kcal - opt_cds_kcal)
    tolerance = 0.001  # kcal/mol
    is_valid = cds_diff <= tolerance
    
    # Prepare validation results
    validation_data.update({
        "CDS_Validation_Pass": is_valid,
        "CDS_SP_vs_OPT_Diff": cds_diff,
        "CDS_OPT_Reference": opt_cds_kcal,
        "CDS_Validation_Performed": True
    })
    
    if not is_valid:
        logging.warning(f"CDS validation failed: SP={sp_cds_kcal:.6f}, OPT={opt_cds_kcal:.6f}, diff={cds_diff:.6f}")
    else:
        logging.debug(f"CDS validation passed: SP={sp_cds_kcal:.6f}, OPT={opt_cds_kcal:.6f}, diff={cds_diff:.6f}")
    
    return validation_data


def _extract_regular_sp(sp_content: str, opt_content: str = None) -> Dict[str, Any]:
    """Extract energy from regular SP calculation (eda2 = 0)."""
    data = {}
    
    # Extract total energy with SP prefix
    energy_data = parse_total_energy(sp_content, prefix="SP_E")
    if not energy_data:
        logging.warning("Failed to extract total energy from regular SP calculation")
        return {}
    
    data.update(energy_data)  # Will contain "SP_E (Ha)" and "SP_E (kcal/mol)"
    
    # Extract SMD detail block
    if smd_data := extract_smd_detail_block_data(sp_content):
        data.update(smd_data)
    
    return data


def _extract_eda_sp(sp_content: str, calc_type: str, metadata: Dict[str, Any], opt_content: str = None) -> Dict[str, Any]:
    """Extract energy from EDA SP calculation based on calc_type with direct CDS validation."""
    data = {}
    
    # Determine EDA type and extract base energy
    if calc_type == "pol_cat":
        base_energy_ha = parse_eda_polarized_energy(sp_content)
    elif calc_type in ["frz_cat", "full_cat"]:
        base_energy_ha = parse_eda_convergence_energy(sp_content)
    else:
        logging.warning(f"Unknown EDA calc_type: {calc_type}")
        return {}
    
    if base_energy_ha is None:
        logging.warning(f"Failed to extract base energy for EDA {calc_type}")
        return {}
    
    # Start with base energy
    final_energy_ha = base_energy_ha["SP_E (Ha)"]
    final_energy_kcal = convert_unit(final_energy_ha, "Ha", "kcal/mol")

    # Apply SMD CDS correction if solvent is used - simplified validation logic
    sp_solvent = metadata.get("SP_Solvent", "gas").lower()
    if sp_solvent == "smd":
        # Extract CDS data
        cds_data = extract_cds_extended_print(sp_content)
        if cds_data:
            # Extract values for local use
            sp_cds_kcal = cds_data["G_CDS (kcal/mol)"]
            sp_cds_ha = cds_data["G_CDS (Ha)"]
            # Add CDS data to results
            data.update(cds_data)
            
            # Only validate if OPT also uses SMD
            opt_solvent = metadata.get("Solvent", "gas").lower()
            if opt_content is not None and opt_solvent == "smd":
                validation_data = validate_cds_against_opt(sp_cds_kcal, opt_content)
                data.update(validation_data)
            
            # Apply CDS correction to final energy
            final_energy_ha += sp_cds_ha
            final_energy_kcal += sp_cds_kcal

    # Apply BSSE correction for full_cat
    if calc_type == "full_cat":
        bsse_data = parse_bsse_energy(sp_content)
        if bsse_data:
            bsse_kj = bsse_data["bsse_energy (kJ/mol)"]
            bsse_ha = convert_unit(bsse_kj, "kJ/mol", "Ha")
            bsse_kcal = convert_unit(bsse_kj, "kJ/mol", "kcal/mol")
            
            data.update({
                "SP_BSSE (kJ/mol)": bsse_kj,
                "SP_BSSE (kcal/mol)": bsse_kcal,
                "SP_BSSE (Ha)": bsse_ha
            })
            final_energy_ha += bsse_ha
            final_energy_kcal += bsse_kcal
    
    # Set final SP energy
    data.update({
        "SP_E (Ha)": final_energy_ha,
        "SP_E (kcal/mol)": final_energy_kcal
    })
    
    return data


def apply_thermodynamic_corrections(data: Dict[str, Any], opt_content: str) -> None:
    """Apply thermodynamic corrections from OPT file to SP data."""
    if enthalpy_data := parse_enthalpy(opt_content):
        data.update(enthalpy_data)
    
    if entropy_data := parse_entropy(opt_content):
        data.update(entropy_data)
    
    if s_trans_data := parse_translational_entropy(opt_content):
        data.update(s_trans_data)
    
    if thermo_data := parse_thermodynamic_conditions(opt_content):
        data.update(thermo_data)
    
    if qrrho_data := parse_qrrho_parameters(opt_content):
        data.update(qrrho_data)
    
    if zpe_data := parse_zero_point_energy(opt_content):
        data.update(zpe_data)


def calculate_enthalpy_and_gibbs(data: Dict[str, Any], mode: str) -> None:
    """Calculate H and G with optional solvent correction.
    
    Args:
        data: Dictionary with energy and thermodynamic corrections.
        mode: "sp" or "opt" (determines which keys to use).
    """
    base_energy_key = f"{'SP_' if mode == 'sp' else ''}E (kcal/mol)"
    
    # Calculate H = E + H_corr
    if base_energy_key in data and "Total Enthalpy Corr. (kcal/mol)" in data:
        data["H (kcal/mol)"] = data[base_energy_key] + data["Total Enthalpy Corr. (kcal/mol)"]
        logging.debug(f"{mode.upper()}: Calculated H = {data['H (kcal/mol)']:.6f} kcal/mol")
    else:
        logging.debug(f"{mode.upper()}: Skipping H calculation - missing energy or enthalpy correction")

    # Calculate G = H - T*S_corr
    required_keys = ["H (kcal/mol)", "Temperature (K)", "Total Entropy Corr. (kcal/mol.K)"]
    if not all(k in data for k in required_keys):
        missing_keys = [k for k in required_keys if k not in data]
        logging.debug(f"{mode.upper()}: Skipping G calculation - missing keys: {missing_keys}")
        return
    
    temperature = data["Temperature (K)"]
    g_gas = data["H (kcal/mol)"] - temperature * data["Total Entropy Corr. (kcal/mol.K)"]
    data["G(gas) (kcal/mol)"] = g_gas
    data["G (kcal/mol)"] = g_gas
    logging.debug(f"{mode.upper()}: Calculated G(gas) = {g_gas:.6f} kcal/mol at T={temperature} K")
    
    # Calculate G_no_trans = G + T*S_trans (G without translational entropy contribution)
    # This is used for separating translational entropy in EDA analysis
    if "S_trans (kcal/mol.K)" in data:
        s_trans = data["S_trans (kcal/mol.K)"]
        g_no_trans = g_gas + temperature * s_trans  # Adding back T*S_trans
        data["G_no_trans (kcal/mol)"] = g_no_trans
        logging.debug(f"{mode.upper()}: Calculated G_no_trans = {g_no_trans:.6f} kcal/mol")
    
    # Apply solvent correction if any solvent model is used (not gas phase)
    solvent_key = f"{'SP_' if mode == 'sp' else ''}Solvent"
    solvent = data.get(solvent_key, "gas").lower()
    if solvent != "gas" and all(k in data for k in ["Temperature (K)", "Pressure (atm)"]):
        pressure = data["Pressure (atm)"]
        correction = calculate_standard_state_correction(temperature, pressure)
        g_solvent = g_gas + correction
        data["G(1M) (kcal/mol)"] = g_solvent
        data["Standard State Corr. (kcal/mol)"] = correction
        data["G (kcal/mol)"] = g_solvent
        logging.debug(f"{mode.upper()}: Applied standard state correction for {solvent}: "
                      f"dG = {correction:.6f} kcal/mol (T={temperature} K, P={pressure} atm)")
        logging.debug(f"{mode.upper()}: G(gas) = {g_gas:.6f} kcal/mol,\n G(1M) = {g_solvent:.6f} kcal/mol")
        
        # Also apply correction to G_no_trans
        if "G_no_trans (kcal/mol)" in data:
            data["G_no_trans (kcal/mol)"] = data["G_no_trans (kcal/mol)"] #+ correction
            # logging.debug(f"{mode.upper()}: Applied standard state correction to G_no_trans for {solvent}")
            logging.debug(f"{mode.upper()}: G_no_trans = {data['G_no_trans (kcal/mol)']:.6f} kcal/mol")
    elif solvent != "gas":
        logging.debug(f"{mode.upper()}: Skipping standard state correction for {solvent} - missing temperature or pressure")
    else:
        logging.debug(f"{mode.upper()}: Gas phase calculation - no standard state correction applied")


# MAIN EXTRACTION FUNCTION

def extract_all_data(config_manager, system_dir: Path, criteria: str = "SUCCESSFUL") -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Extract data for all method combos and return extracted data.
    Pure extraction function - does not handle export.
    
    Returns:
        Dictionary mapping method combo names to their extracted data
    """
    all_extracted_data = {}
    
    # Discover all method combos and organize files by combo
    combo_files = {}
    try:
        for file_info in iter_input_paths(config_manager, system_dir, include_metadata=True):
            if file_info and hasattr(file_info, 'metadata'):
                method_combo = file_info.metadata.get("Method_Combo")
                if method_combo:
                    if method_combo not in combo_files:
                        combo_files[method_combo] = []
                    combo_files[method_combo].append((file_info.path, file_info.metadata))
    except Exception as e:
        logging.error(f"Failed to discover method combos: {e}")
        return
        
    if not combo_files:
        logging.warning(f"No method combos found in: {system_dir}")
        return
        
    logging.info(f"Found {len(combo_files)} method combos: {sorted(combo_files.keys())}")
    
    # Process each method combo
    for combo_name, input_files in combo_files.items():
        logging.info(f"Processing method combo: {combo_name}")
        
        # Separate files by type
        opt_files = [(path, meta) for path, meta in input_files if meta.get("Mode") == "opt"]
        sp_files = [(path, meta) for path, meta in input_files if meta.get("Mode") == "sp"]
        
        # Data containers
        opt_data = []
        sp_data = []
        xyz_data = []
        opt_content_cache = {}
        
        # Extract OPT data first (needed for SP corrections)
        for input_path, metadata in opt_files:
            output_path = input_path.with_suffix(".out")
            
            # Check if file should be processed with enhanced OPT validation
            should_process, reason = should_process_file(input_path, criteria, metadata)
            if not should_process:
                logging.debug(f"Skipping OPT file {reason}: {input_path}")
                continue
            
            # Extract OPT data
            opt_result = extract_opt_data(output_path, metadata, criteria)
            if opt_result:
                opt_data.append(opt_result)
                
                # Cache OPT content for SP corrections with enhanced key
                opt_content = read_text(output_path)
                if opt_content:
                    # Create comprehensive cache key: Species|Branch|Calc_Type
                    cache_key = f"{metadata.get('Species', 'unknown')}|{metadata.get('Branch', 'unknown')}|{metadata.get('Calc_Type', 'unknown')}"
                    opt_content_cache[cache_key] = opt_content
                    logging.debug(f"Caching OPT with key: {cache_key}")
                    
            # Extract XYZ data separately
            xyz_result = extract_xyz_data(output_path, metadata, criteria)
            if xyz_result:
                xyz_data.append(xyz_result)
        
        # Extract SP data with OPT corrections
        for input_path, metadata in sp_files:
            output_path = input_path.with_suffix(".out")
            
            # Check if file should be processed
            should_process, reason = should_process_file(input_path, criteria, metadata)
            if not should_process:
                logging.debug(f"Skipping SP file {reason}: {input_path}")
                continue
            
            # Get corresponding OPT content for corrections using enhanced key
            # Create matching cache key: Species|Branch|Calc_Type
            cache_key = f"{metadata.get('Species', 'unknown')}|{metadata.get('Branch', 'unknown')}|{metadata.get('Calc_Type', 'unknown')}"
            opt_content = opt_content_cache.get(cache_key)
            
            logging.debug(f"SP file looking for OPT key: {cache_key}")
            if not opt_content:
                logging.warning(f"No matching OPT found for SP {cache_key}")
                logging.debug(f"Available OPT keys in cache: {list(opt_content_cache.keys())}")
            else:
                logging.debug(f"Found matching OPT for SP {cache_key}")
            
            sp_result = extract_sp_data(output_path, metadata, criteria, opt_content)
            if sp_result:
                sp_data.append(sp_result)

        # Store results for this combo
        combo_data = {
            "opt_data": opt_data,
            "sp_data": sp_data,
            "xyz_data": xyz_data
        }
        
        if any(combo_data.values()):
            all_extracted_data[combo_name] = combo_data
            logging.info(f"Extracted from {combo_name}: {len(opt_data)} OPT, {len(sp_data)} SP, {len(xyz_data)} XYZ")
    
    # Return extracted data for external export handling
    if all_extracted_data:
        total_combos = len(all_extracted_data)
        total_files = sum(
            len(combo_data["opt_data"]) + len(combo_data["sp_data"]) + len(combo_data["xyz_data"])
            for combo_data in all_extracted_data.values()
        )
        logging.info(f"Extraction completed: {total_combos} method combos, {total_files} total files")
        return all_extracted_data
    else:
        logging.warning("No data extracted")
        return {}
