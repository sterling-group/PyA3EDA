"""
Data extraction module with method combo-based architecture.

This module provides clean separation of concerns for data extraction:
- Core extraction functions for OPT and SP data
- Method combo processing with immediate file separation
- Pipeline orchestration from extraction to export
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyA3EDA.core.builders.builder import iter_input_paths
from PyA3EDA.core.parsers.qchem_result_parser import (
    parse_bsse_energy,
    parse_eda_convergence_energy,
    parse_eda_polarized_energy,
    parse_energy,
    parse_enthalpy,
    parse_entropy,
    parse_imaginary_frequencies,
    parse_optimization_status,
    parse_qrrho_parameters,
    parse_smd_cds_raw_values,
    parse_thermodynamic_conditions,
    parse_zero_point_energy,
)
from PyA3EDA.core.status.status_checker import should_process_file
from PyA3EDA.core.utils.file_utils import read_text
from PyA3EDA.core.utils.unit_converter import convert_unit


# CORE EXTRACTION FUNCTIONS (pure)
def extract_opt_data(
    file_path: Path, metadata: Dict[str, Any], criteria: str = "SUCCESSFUL"
) -> Optional[Dict[str, Any]]:
    """
    Extract all data from OPT output file.

    Args:
        file_path: Path to OPT output file
        metadata: File metadata from builder
        criteria: Status criteria for file processing

    Returns:
        Dictionary with extracted OPT data or None if extraction fails
    """
    # Get corresponding input file for status checking
    input_path = file_path.with_suffix(".in")

    # Check if file should be processed (backward compatible without metadata)
    should_process, reason = should_process_file(input_path, criteria, metadata=None)
    if not should_process:
        logging.debug(f"Skipping file {reason}: {file_path}")
        return None

    # Read file content
    content = read_text(file_path)
    if not content:
        logging.warning(f"Failed to read file content: {file_path}")
        return None

    # Initialize result with metadata
    result = {**metadata}
    result["output_file_stem"] = file_path.stem

    # Extract thermodynamic data using existing function
    thermo_data = _extract_opt_thermodynamic_data(content)
    if thermo_data:
        result.update(thermo_data)
        return result
    else:
        logging.warning(f"Failed to parse OPT data from: {file_path}")
        return None


def extract_sp_data(
    file_path: Path,
    metadata: Dict[str, Any],
    criteria: str = "SUCCESSFUL",
    opt_content: str = None,
) -> Optional[Dict[str, Any]]:
    """
    Extract all data from SP output file.

    Args:
        file_path: Path to SP output file
        metadata: File metadata from builder
        opt_content: Optional OPT content for thermodynamic corrections
        criteria: Status criteria for file processing

    Returns:
        Dictionary with extracted SP data or None if extraction fails
    """
    # Get corresponding input file for status checking
    input_path = file_path.with_suffix(".in")

    # Check if file should be processed (backward compatible without metadata)
    should_process, reason = should_process_file(input_path, criteria, metadata=None)
    if not should_process:
        logging.debug(f"Skipping file {reason}: {file_path}")
        return None

    # Read file content
    sp_content = read_text(file_path)
    if not sp_content:
        logging.warning(f"Failed to read file content: {file_path}")
        return None

    # Initialize result with metadata
    result = {**metadata}

    # Extract SP thermodynamic data using existing function
    thermo_data = _extract_sp_thermodynamic_data(sp_content, metadata, opt_content)
    if thermo_data:
        result.update(thermo_data)

        # Apply thermodynamic corrections if OPT content available
        if opt_content:
            apply_thermodynamic_corrections(result, opt_content)

        return result
    else:
        logging.warning(f"Failed to parse SP data from: {file_path}")
        return None


def extract_xyz_data(
    file_path: Path, metadata: Dict[str, Any], criteria: str = "SUCCESSFUL"
) -> Optional[Dict[str, Any]]:
    """
    Extract XYZ coordinate data from output file.

    Args:
        file_path: Path to output file
        metadata: File metadata from builder
        criteria: Status criteria for file processing

    Returns:
        Dictionary with XYZ coordinate data or None if extraction fails
    """
    # Get corresponding input file for status checking
    input_path = file_path.with_suffix(".in")

    # Check if file should be processed (backward compatible without metadata)
    should_process, reason = should_process_file(input_path, criteria, metadata=None)
    if not should_process:
        logging.debug(f"Skipping XYZ extraction for {file_path.name}: {reason}")
        return None


def apply_thermodynamic_corrections(data: Dict[str, Any], opt_content: str) -> None:
    """
    Apply thermodynamic corrections from OPT content to SP data.

    Args:
        data: SP data dictionary to update
        opt_content: OPT file content for corrections
    """
    # Extract corrections from OPT content
    corrections = {}
    correction_parsers = [
        (parse_enthalpy, None),
        (parse_entropy, None),
        (parse_thermodynamic_conditions, None),
    ]

    for parser_func, _ in correction_parsers:
        parser_data = parser_func(opt_content)
        if parser_data:
            corrections.update(parser_data)

    # Apply corrections and calculate derived values
    if corrections:
        data.update(corrections)
        _calculate_derived_values(data)
        logging.debug(
            f"Applied thermodynamic corrections: H={data.get('H (kcal/mol)', 'N/A')}, G={data.get('G (kcal/mol)', 'N/A')}"
        )


# EXISTING PRIVATE HELPER FUNCTIONS (keep as-is for now)


def _extract_opt_thermodynamic_data(content: str) -> Dict[str, Any]:
    """
    Extract thermodynamic data from OPT files using pure parsing functions.

    Args:
        content: Q-Chem OPT output content

    Returns:
        Dictionary with extracted thermodynamic data
    """
    data = {}
    fallback_used = False

    # Define parsers with their fallback flag names
    parsers = [
        (parse_energy, "energy_fallback_used"),
        (parse_enthalpy, "enthalpy_fallback_used"),
        (parse_entropy, "entropy_fallback_used"),
        (parse_optimization_status, None),
        (parse_thermodynamic_conditions, None),
        (parse_qrrho_parameters, None),
        (parse_imaginary_frequencies, None),
        (parse_zero_point_energy, None),
    ]

    # Extract energy first (required)
    energy_data = parse_energy(content)
    if not energy_data:
        return {}  # Cannot proceed without energy

    # Process all parsers
    for parser_func, fallback_key in parsers:
        parser_data = parser_func(content)
        if parser_data:
            data.update(parser_data)
            if fallback_key and parser_data.get(fallback_key):
                fallback_used = True

    # Calculate derived values
    _calculate_derived_values(data)

    # Add fallback flag
    data["Fallback Used"] = "Yes" if fallback_used else "No"

    return data


def _extract_sp_thermodynamic_data(
    sp_content: str, metadata: Dict[str, Any], opt_content: str = None
) -> Dict[str, Any]:
    """
    Extract thermodynamic data from SP files using pure parsing functions.
    Now handles both regular SP and EDA SP calculations.

    Args:
        sp_content: Q-Chem SP output content
        metadata: Metadata for extraction decisions
        opt_content: Optional OPT content for CDS validation

    Returns:
        Dictionary with extracted SP thermodynamic data
    """
    data = {}

    # Check if this is an EDA calculation using metadata directly
    calc_type = metadata.get("Calc_Type", "")
    eda2 = metadata.get("eda2", "0")
    is_eda = calc_type in ["full_cat", "pol_cat", "frz_cat"] and eda2 != "0"

    # Add debug logging for transparency
    if calc_type in ["full_cat", "pol_cat", "frz_cat"]:
        logging.debug(
            f"EDA calc type detected: {calc_type}, eda2: {eda2}, is_eda: {is_eda}"
        )

    if is_eda:
        # Handle EDA-specific energy extraction - get type directly from calc_type
        eda_type = (
            "frz"
            if "frz" in calc_type
            else "pol"
            if "pol" in calc_type
            else "full"
            if "full" in calc_type
            else "unknown"
        )

        logging.debug(f"Processing EDA {eda_type} calculation for SP file")
        eda_data = _extract_eda_sp_energy(sp_content, eda_type, metadata)
        if eda_data:
            data.update(eda_data)
        else:
            logging.warning(f"Failed to extract EDA {eda_type} energy data")
            return {}  # Cannot proceed without EDA energy
    else:
        # Handle regular SP energy extraction
        logging.debug("Processing regular SP calculation")
        energy_data = parse_energy(sp_content)
        if not energy_data:
            logging.warning("Failed to extract energy from regular SP calculation")
            return {}  # Cannot proceed without energy

        # Set SP energy fields from parsed energy data
        first_energy_key = list(energy_data.keys())[0]
        energy_unit = first_energy_key.split("(")[1].split(")")[0]
        data[f"SP_E ({energy_unit})"] = energy_data[first_energy_key]
        data["SP_E (kcal/mol)"] = energy_data["E (kcal/mol)"]
        data["SP_Fallback Used"] = (
            "Yes" if energy_data.get("energy_fallback_used") else "No"
        )

        # Extract SMD CDS energy only if SMD solvation is used (metadata directly)
        if metadata.get("SP_Solvent", "gas").lower() != "gas":
            cds_data = _extract_smd_cds_energy(opt_content, sp_content)
            if cds_data:
                data.update(cds_data)
                # Apply CDS correction to final SP energy (like EDA calculations)
                cds_value_kcal = cds_data.get("G_CDS (kcal/mol)", 0.0)
                cds_value_ha = cds_data.get("G_CDS (Ha)", 0.0)
                data["SP_E (kcal/mol)"] += cds_value_kcal
                data[f"SP_E ({energy_unit})"] += cds_value_ha
                logging.debug(
                    f"Applied CDS correction: {cds_value_kcal:.4f} kcal/mol for regular SP"
                )

        logging.debug(
            f"Regular SP energy extraction successful: {data['SP_E (kcal/mol)']:.4f} kcal/mol"
        )

    return data


def _extract_eda_sp_energy(
    sp_content: str, eda_type: str, metadata: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Extract energy from EDA SP calculations based on the EDA type.

    Args:
        sp_content: SP file content
        eda_type: Type of EDA calculation (frz, pol, full)
        metadata: File metadata

    Returns:
        Dictionary with extracted EDA energy data or None if extraction fails
    """
    data = {}

    # Extract base energy based on EDA type
    base_energy_ha = None
    fallback_reason = None

    if eda_type in ["frz", "pol"]:
        polarized_data = parse_eda_polarized_energy(sp_content)
        if polarized_data:
            base_energy_ha = polarized_data["polarized_energy"]
            fallback_reason = f"polarized_energy_{eda_type}"
        else:
            logging.warning(
                f"Failed to extract polarized energy for EDA {eda_type} calculation"
            )
            fallback_reason = f"no_polarized_energy_{eda_type}"

    elif eda_type == "full":
        convergence_data = parse_eda_convergence_energy(sp_content)
        if convergence_data:
            base_energy_ha = convergence_data["convergence_energy"]
            fallback_reason = (
                "convergence_no_bsse_full"  # Will be updated if BSSE found
            )
        else:
            logging.warning(
                f"Failed to extract convergence energy for EDA {eda_type} calculation"
            )
            fallback_reason = "no_convergence_full"

    else:
        logging.warning(f"Unknown EDA type: {eda_type}. Expected: frz, pol, or full")
        fallback_reason = f"unknown_eda_type_{eda_type}"

    # Handle extraction failure - return None columns with consistent structure
    if base_energy_ha is None:
        return {
            "SP_E_base (Ha)": None,
            "SP_E_base (kcal/mol)": None,
            "SP_E (Ha)": None,
            "SP_E (kcal/mol)": None,
            "SP_Fallback Used": fallback_reason,
        }

    # Convert base energy and set columns
    base_energy_kcal = convert_unit(base_energy_ha, "Ha", "kcal/mol")
    data.update(
        {"SP_E_base (Ha)": base_energy_ha, "SP_E_base (kcal/mol)": base_energy_kcal}
    )

    # Initialize final energy (will accumulate corrections)
    final_energy_ha = base_energy_ha
    final_energy_kcal = base_energy_kcal

    # Apply CDS correction if SMD solvation is used (metadata directly)
    if metadata.get("SP_Solvent", "gas").lower() != "gas":
        cds_data = _extract_smd_cds_energy(None, sp_content)
        if cds_data:
            cds_value_kcal = cds_data.get("G_CDS (kcal/mol)", 0.0)
            cds_value_ha = cds_data.get("G_CDS (Ha)", 0.0)

            # Set CDS correction columns and update final energy
            data.update(
                {"SP_CDS (Ha)": cds_value_ha, "SP_CDS (kcal/mol)": cds_value_kcal}
            )

            final_energy_ha += cds_value_ha
            final_energy_kcal += cds_value_kcal
            logging.debug(
                f"Applied CDS correction: {cds_value_kcal:.4f} kcal/mol for EDA {eda_type}"
            )

    # Apply BSSE correction for full EDA calculations only
    if eda_type == "full":
        bsse_data = parse_bsse_energy(sp_content)
        if bsse_data:
            bsse_kj = bsse_data["bsse_energy"]
            bsse_value_kcal = convert_unit(bsse_kj, "kJ/mol", "kcal/mol")
            bsse_value_ha = convert_unit(bsse_kj, "kJ/mol", "Ha")

            # Set BSSE correction columns and update final energy
            data.update(
                {
                    "SP_BSSE (kJ/mol)": bsse_kj,
                    "SP_BSSE (kcal/mol)": bsse_value_kcal,
                    "SP_BSSE (Ha)": bsse_value_ha,
                }
            )

            final_energy_ha += bsse_value_ha
            final_energy_kcal += bsse_value_kcal
            fallback_reason = "convergence_bsse_full"
            logging.debug(
                f"Applied BSSE correction: {bsse_value_kcal:.4f} kcal/mol for EDA full"
            )

    # Set final energy columns and fallback reason
    data.update(
        {
            "SP_E (Ha)": final_energy_ha,
            "SP_E (kcal/mol)": final_energy_kcal,
            "SP_Fallback Used": fallback_reason,
        }
    )

    logging.debug(
        f"EDA {eda_type} energy extraction successful: base={base_energy_kcal:.4f}, final={final_energy_kcal:.4f} kcal/mol"
    )
    return data


def _extract_smd_cds_energy(
    opt_content: str = None, sp_content: str = None
) -> Optional[Dict[str, Any]]:
    """
    Extract and validate SMD CDS energy using cross-file validation.

    Args:
        opt_content: OPT file content for primary CDS calculation
        sp_content: SP file content for validation

    Returns:
        Dictionary with validated CDS energy or None
    """
    primary_value = None
    primary_source = None
    validation_info = {}

    # Extract raw SMD values from OPT content
    if opt_content:
        opt_raw_data = parse_smd_cds_raw_values(opt_content)
        if opt_raw_data:
            # Primary method: Calculate from G-S and G-ENP components
            if "g_s_final" in opt_raw_data and "g_enp_final" in opt_raw_data:
                g_s_final = opt_raw_data["g_s_final"]
                g_enp_final = opt_raw_data["g_enp_final"]
                cds_hartree = g_s_final - g_enp_final
                primary_value = convert_unit(cds_hartree, "Ha", "kcal/mol")
                primary_source = "opt_calculated_from_components"

                # Validation 1: Against OPT summary (4 decimal tolerance)
                if "cds_summary_final" in opt_raw_data:
                    summary_val = opt_raw_data["cds_summary_final"]
                    validation_info["opt_summary_match"] = (
                        abs(primary_value - summary_val) <= 0.0001
                    )
                    validation_info["opt_summary_diff"] = abs(
                        primary_value - summary_val
                    )
                    if not validation_info["opt_summary_match"]:
                        logging.warning(
                            f"CDS validation failed (OPT 4dp): hartree={primary_value:.4f}, opt_summary={summary_val:.4f} kcal/mol"
                        )

            # Fallback to OPT summary if components not available
            elif "cds_summary_final" in opt_raw_data:
                primary_value = opt_raw_data["cds_summary_final"]
                primary_source = "opt_summary_value"

    # Validation 2: Against SP file total (3 decimal tolerance)
    if sp_content and primary_value is not None:
        sp_raw_data = parse_smd_cds_raw_values(sp_content)
        if sp_raw_data and "cds_sp_total_final" in sp_raw_data:
            sp_val = sp_raw_data["cds_sp_total_final"]
            validation_info["sp_total_match"] = abs(primary_value - sp_val) <= 0.001
            validation_info["sp_total_diff"] = abs(primary_value - sp_val)
            if not validation_info["sp_total_match"]:
                logging.warning(
                    f"CDS validation failed (SP 3dp): hartree={primary_value:.3f}, sp_total={sp_val:.3f} kcal/mol"
                )

    if primary_value is None:
        return None

    # Return consolidated result with OPT-derived CDS for SP calculations
    result = {
        "G_CDS (Ha)": cds_hartree,
        "G_CDS (kcal/mol)": primary_value,
    }
    result.update(validation_info)
    return result


def _calculate_derived_values(data: Dict[str, Any]) -> None:
    """
    Calculate derived thermodynamic values (H and G) in place.
    Uses the final extracted energy: SP_E for SP calculations, E for OPT calculations.

    Args:
        data: Dictionary containing parsed data to modify
    """
    # Determine base energy key based on calculation type
    # For SP calculations: use SP_E (kcal/mol) which includes all corrections (CDS, BSSE)
    # For OPT calculations: use E (kcal/mol) which is the base extracted energy
    if "SP_E (kcal/mol)" in data:
        base_energy_key = "SP_E (kcal/mol)"
    else:
        base_energy_key = "E (kcal/mol)"

    # Calculate H (kcal/mol)
    if base_energy_key in data and "Total Enthalpy Corr. (kcal/mol)" in data:
        data["H (kcal/mol)"] = (
            data[base_energy_key] + data["Total Enthalpy Corr. (kcal/mol)"]
        )

    # Calculate G (kcal/mol)
    if all(
        key in data
        for key in [
            "H (kcal/mol)",
            "Temperature (K)",
            "Total Entropy Corr. (kcal/mol.K)",
        ]
    ):
        data["G (kcal/mol)"] = (
            data["H (kcal/mol)"]
            - data["Temperature (K)"] * data["Total Entropy Corr. (kcal/mol.K)"]
        )


# METHOD COMBO PROCESSING
def extract_method_combo_data(
    config_manager,
    method_combo_name: str,
    system_dir: Path,
    criteria: str = "SUCCESSFUL",
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract data from all files in a method combo, organized by file type.
    Uses iter_input_paths as single source of truth for file discovery.

    Args:
        config_manager: ConfigManager instance
        method_combo_name: Name of method combo
        system_dir: System directory containing method combo folders
        criteria: Status criteria for file selection

    Returns:
        Dictionary with keys "opt_data", "sp_data", "xyz_data" containing respective data lists
    """
    result = {"opt_data": [], "sp_data": [], "xyz_data": []}

    logging.info(f"Processing method combo: {method_combo_name}")

    # Get all input files using iter_input_paths (single source of truth)
    input_files = []
    try:
        for file_info in iter_input_paths(
            config_manager, system_dir, include_metadata=True
        ):
            if (
                file_info
                and hasattr(file_info, "metadata")
                and hasattr(file_info, "path")
            ):
                # Filter files that belong to this method combo
                if file_info.metadata.get("Method_Combo") == method_combo_name:
                    input_files.append((file_info.path, file_info.metadata))
    except Exception as e:
        logging.error(
            f"Failed to get input files for method combo {method_combo_name}: {e}"
        )
        return result

    if not input_files:
        logging.warning(f"No input files found for method combo: {method_combo_name}")
        return result

    # Process files by type
    opt_files = [
        (path, meta) for path, meta in input_files if meta.get("Mode") == "opt"
    ]
    sp_files = [(path, meta) for path, meta in input_files if meta.get("Mode") == "sp"]

    # Extract OPT data first (needed for SP corrections)
    opt_content_cache = {}
    for input_path, metadata in opt_files:
        output_path = input_path.with_suffix(".out")

        # Use consistent status checking (backward compatible without metadata)
        should_process, reason = should_process_file(
            input_path, criteria, metadata=None
        )
        if not should_process:
            logging.debug(f"Skipping OPT file {reason}: {input_path}")
            continue

        opt_data = extract_opt_data(output_path, metadata, criteria)
        if opt_data:
            # Add CSV-ready data (coordinates are NOT included here)
            result["opt_data"].append(opt_data)

            # Cache OPT content for SP corrections
            opt_content = read_text(output_path)
            if opt_content:
                opt_content_cache[metadata.get("Species", "unknown")] = opt_content

        # Extract XYZ data separately (completely separate from CSV data)
        xyz_data = extract_xyz_data(output_path, metadata, criteria)
        if xyz_data:
            result["xyz_data"].append(xyz_data)

    # Extract SP data with OPT corrections
    for input_path, metadata in sp_files:
        output_path = input_path.with_suffix(".out")

        # Use consistent status checking (backward compatible without metadata)
        should_process, reason = should_process_file(
            input_path, criteria, metadata=None
        )
        if not should_process:
            logging.debug(f"Skipping SP file {reason}: {input_path}")
            continue

        # Get corresponding OPT content for corrections
        species = metadata.get("Species", "unknown")
        opt_content = opt_content_cache.get(species)

        sp_data = extract_sp_data(output_path, metadata, criteria, opt_content)
        if sp_data:
            # Add CSV-ready data (coordinates are NOT included here)
            result["sp_data"].append(sp_data)

    logging.info(
        f"Extracted from {method_combo_name}: {len(result['opt_data'])} OPT, {len(result['sp_data'])} SP, {len(result['xyz_data'])} XYZ"
    )
    return result


def extract_and_export_method_combo(
    config_manager,
    method_combo_name: str,
    system_dir: Path,
    output_dir: Path,
    criteria: str = "SUCCESSFUL",
) -> Dict[str, Any]:
    """
    Extract data from method combo and immediately export to separate files.

    Args:
        config_manager: ConfigManager instance (not processed config)
        method_combo_name: Name of method combo (e.g., "m06_6311gd_gas")
        system_dir: System directory containing method combo folders
        output_dir: Output directory for export files
        criteria: Status criteria for file selection

    Returns:
        Export results summary
    """
    # Extract data organized by type
    combo_data = extract_method_combo_data(
        config_manager, method_combo_name, system_dir, criteria
    )

    if not any(combo_data.values()):
        logging.warning(f"No data extracted for method combo: {method_combo_name}")
        return {}

    # Import exporter functions
    from PyA3EDA.core.exporters.data_exporter import write_csv_data, write_xyz_files

    # Create structured output directories based on user specification:
    # results/raw/{method_combo_name}/
    # results/raw/{method_combo_name}/xyz_files/
    method_combo_dir = output_dir / "raw" / method_combo_name
    xyz_dir = method_combo_dir / "xyz_files"

    export_results = {}

    # Export OPT data to method combo directory
    if combo_data["opt_data"]:
        opt_file_path = method_combo_dir / f"opt_{method_combo_name}.csv"
        if write_csv_data(combo_data["opt_data"], opt_file_path, "OPT"):
            export_results["opt_csv"] = opt_file_path

    # Export SP data to method combo directory
    if combo_data["sp_data"]:
        sp_file_path = method_combo_dir / f"sp_{method_combo_name}.csv"
        if write_csv_data(combo_data["sp_data"], sp_file_path, "SP"):
            export_results["sp_csv"] = sp_file_path

    # Export XYZ data to xyz_files subdirectory within method combo directory
    if combo_data["xyz_data"]:
        xyz_results = write_xyz_files(combo_data["xyz_data"], xyz_dir)
        if xyz_results:
            export_results["xyz_files"] = xyz_results

    logging.info(
        f"Exported method combo {method_combo_name}: {len(export_results)} file types"
    )
    return export_results


def extract_and_export_all_combos(
    config_manager, system_dir: Path, output_dir: Path, criteria: str = "SUCCESSFUL"
) -> Dict[str, Any]:
    """
    Extract and export data for all method combos using iter_input_paths as single source of truth.

    Args:
        config_manager: ConfigManager instance (not processed config)
        system_dir: System directory containing method combo folders
        output_dir: Output directory for all exports
        criteria: Status criteria for file selection

    Returns:
        Combined export results for all method combos
    """
    all_results = {}

    # Get all method combos from iter_input_paths (single source of truth)
    method_combos = {}
    try:
        for file_info in iter_input_paths(
            config_manager, system_dir, include_metadata=True
        ):
            if file_info and hasattr(file_info, "metadata"):
                method_combo = file_info.metadata.get("Method_Combo")
                if method_combo:
                    if method_combo not in method_combos:
                        method_combos[method_combo] = []
                    method_combos[method_combo].append(
                        (file_info.path, file_info.metadata)
                    )
    except Exception as e:
        logging.error(f"Failed to discover method combos: {e}")
        return all_results

    if not method_combos:
        logging.warning(f"No method combos found in: {system_dir}")
        return all_results

    logging.info(
        f"Found {len(method_combos)} method combos: {sorted(method_combos.keys())}"
    )

    # Process each method combo
    for combo_name in sorted(method_combos.keys()):
        try:
            combo_results = extract_and_export_method_combo(
                config_manager, combo_name, system_dir, output_dir, criteria
            )
            if combo_results:
                all_results[combo_name] = combo_results
        except Exception as e:
            logging.error(f"Failed to process method combo {combo_name}: {e}")
            continue

    # Summary statistics
    total_combos = len(all_results)
    total_files = sum(len(results) for results in all_results.values())

    logging.info(
        f"Completed extraction and export: {total_combos} method combos, {total_files} total files"
    )
    return all_results
