"""
Status Checker Module

Provides functions for checking the status of Q-Chem calculations,
grouping results by method_basis (first folder of the relative path),
and printing formatted reports with intermediate group summaries and an overall summary.
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple

from PyA3EDA.core.builders.builder import iter_input_paths
from PyA3EDA.core.constants import Constants
from PyA3EDA.core.parsers.qchem_result_parser import (
    parse_imaginary_frequencies,
    parse_optimization_status,
)
from PyA3EDA.core.parsers.qchem_status_parser import parse_qchem_status
from PyA3EDA.core.utils.file_utils import read_text

# Create a separate logger for summary that uses a simple formatter.
summary_logger = logging.getLogger("summary_logger")
if not summary_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    summary_logger.addHandler(handler)
    summary_logger.propagate = False


def get_status_for_file(input_file: Path, metadata: dict = None) -> Tuple[str, str]:
    """
    Reads the output and error files corresponding to the input_file and determines the status.
    If metadata is provided for successful OPT calculations, adds validation and convergence info.

    Args:
        input_file: Path to the input file
        metadata: Optional metadata for enhanced OPT validation

    Returns:
        Tuple[str, str]: (status, details) with optional OPT validation info
    """
    output_file = input_file.with_suffix(".out")
    error_file = input_file.with_suffix(".err")
    content = read_text(output_file) if output_file.exists() else ""
    err_content = read_text(error_file) if error_file.exists() else ""

    # Check if job is still running based on submission file
    input_stem = input_file.stem
    # Pattern 1: filename.in_jobid.taskid
    submission_pattern1 = f"{input_stem}.in_[0-9]*.[0-9]*"
    # Pattern 2: .filename.in.jobid.qcin.taskid
    submission_pattern2 = f".{input_stem}.in.[0-9]*.qcin.[0-9]*"

    submission_exists = bool(list(input_file.parent.glob(submission_pattern1))) or bool(
        list(input_file.parent.glob(submission_pattern2))
    )

    # Get base status first
    status, details = parse_qchem_status(content, err_content, submission_exists)

    # Enhanced validation for successful OPT calculations only
    if (
        status.lower() == "successful"
        and metadata
        and metadata.get("Mode") == "opt"
        and content
    ):
        # Check optimization status and imaginary frequencies
        opt_status = parse_optimization_status(content)
        imag_freq_parsed = parse_imaginary_frequencies(content)

        # Skip enhanced validation if no patterns found
        if opt_status is None and imag_freq_parsed is None:
            return status, details

        # Get convergence type
        convergence_type = "unknown"
        opt_status_text = opt_status.get("Optimization Status", "")
        if "TRANSITION STATE CONVERGED" in opt_status_text:
            convergence_type = "ts"
        elif "OPTIMIZATION CONVERGED" in opt_status_text:
            convergence_type = "opt"

        # Get imaginary frequency count directly as int
        imag_freq = int(imag_freq_parsed.get("Imaginary Frequencies", 0))

        # Simple validation logic
        branch = metadata.get("Branch", "").lower()
        ts_expected = branch == "ts"

        # Check if validation fails
        validation_failed = False
        if ts_expected:
            # TS branch: should have 1 imaginary frequency AND convergence type should match
            if convergence_type != "ts" or imag_freq != 1:
                validation_failed = True
        else:
            # Non-TS branch: should have 0 imaginary frequencies AND should not be TS convergence
            if convergence_type == "ts" or imag_freq > 0:
                validation_failed = True

        # Return appropriate status
        if validation_failed:
            return (
                "VALIDATION",
                f"Conv: {convergence_type}, Imag: {imag_freq if imag_freq is not None else 'unknown'}",
            )
        else:
            return status, details

    return status, details


def should_process_file(
    input_file: Path, criteria: str, metadata: dict = None
) -> Tuple[bool, str]:
    """
    Determine if a file should be processed based on criteria.
    Enhanced with OPT info display.

    Args:
        input_file: Path to the input file
        criteria: Criteria for processing ("all", "nofile", or status name)
        metadata: Optional metadata containing calculation details

    Returns:
        Tuple[bool, str]: (should_process, reason)
    """
    if not input_file.exists():
        return False, "File doesn't exist"

    if criteria is None:
        return False, "No criteria specified"

    if criteria.lower() == "all":
        return True, "Process all"

    if criteria.lower() == "nofile":
        output_file = input_file.with_suffix(".out")
        if not output_file.exists():
            return True, "Output file doesn't exist"
        return False, "Output file exists"

    # Use enhanced status checking if metadata is available
    status, details = get_status_for_file(input_file, metadata)

    if status.lower() == criteria.lower():
        return True, f"Status match: {status}"

    return False, f"Status mismatch: {status} ≠ {criteria}"


def group_paths_by_method_basis(path_items: List) -> Dict[str, List]:
    """
    Groups paths by method combination with proper dispersion formatting.
    Uses metadata when available for accurate grouping, falls back to path-based grouping.
    """
    # Dispersion formatting map
    disp_map = {
        "empirical_grimme": "D2",
        "empirical_chg": "CHG",
        "empirical_grimme3": "D3(0)",
        "d3_zero": "D3(0)",
        "d3_bj": "D3(BJ)",
        "d3_cso": "D3(CSO)",
        "d3_zerom": "D3M(0)",
        "d3_bjm": "D3M(BJ)",
        "d3_op": "D3(op)",
        "d3": "D3",
        "d4": "D4",
    }

    # Handle both old (just paths) and new (path with metadata) formats
    if path_items and hasattr(path_items[0], "path"):
        # New format with metadata - use metadata for proper grouping
        # Create reverse map for unsanitizing
        reverse_map = {s: o for o, s in Constants.ESCAPE_MAP.items()}

        groups = {}
        for item in path_items:
            metadata = item.metadata

            # Get components from metadata (sanitized) and unsanitize them
            method = metadata.get("Method", "unknown")
            basis = metadata.get("Basis", "")
            dispersion = metadata.get("Dispersion", "")
            solvent = metadata.get("Solvent", "")

            # Unsanitize the values
            for s, o in reverse_map.items():
                method = method.replace(s, o)
                basis = basis.replace(s, o)
                dispersion = dispersion.replace(s, o)
                solvent = solvent.replace(s, o)

            # Start building the key with method
            key_parts = [method]

            # Add dispersion if it exists and is not "false" or "none"
            if dispersion and dispersion.lower() not in ["false", "none", ""]:
                disp_formatted = disp_map.get(dispersion.lower(), dispersion)
                key_parts[0] = f"{method}-{disp_formatted}"

            # Add basis if it exists
            if basis:
                key_parts.append(basis)

            # Add solvent if it exists and is not "none" or empty
            if solvent and solvent.lower() not in ["none", ""]:
                key_parts.append(f"({solvent})")

            # Join all parts
            if len(key_parts) == 1:
                key = key_parts[0]
            elif len(key_parts) == 2:
                key = "/".join(key_parts)
            else:
                # Method-Disp/Basis(Solvent) or Method/Basis(Solvent)
                key = f"{key_parts[0]}/{key_parts[1]}{key_parts[2]}"

            groups.setdefault(key, []).append(item)
        return groups


def print_group_status(
    group_key: str, path_items: List, system_dir: Path
) -> Dict[str, int]:
    """
    Checks statuses for paths in this group, prints a formatted report including the calculation mode
    (OPT or SP), and returns a summary dictionary of status counts for the group.
    Enhanced to show OPT convergence info when available.
    """
    # Handle both old (just paths) and new (path with metadata) formats
    if path_items and hasattr(path_items[0], "path"):
        # New format with metadata
        paths = [item.path for item in path_items]
        metadata_list = [item.metadata for item in path_items]
    else:
        # Old format without metadata
        paths = path_items
        metadata_list = [None] * len(paths)

    header_text = "Input File (rel)"
    max_path_length = max(
        max(
            len(str(path.relative_to(system_dir).parent / path.stem)) for path in paths
        ),
        len(header_text),
    )
    # Format string with fixed widths for each column.
    format_str = f"{{:<{max_path_length}}} | {{:<6}} | {{:<10}} | {{}}"
    group_counts: Dict[str, int] = {}

    boundary_line = "-" * 60
    summary_logger.info(f"\n{boundary_line}")
    summary_logger.info(f"{' ' * 8}GROUP: {group_key}")
    summary_logger.info(boundary_line)
    summary_logger.info(format_str.format(header_text, "Mode", "Status", "Details"))
    summary_logger.info(boundary_line)

    for path, metadata in zip(paths, metadata_list):
        relative_path = path.relative_to(system_dir).parent / path.stem
        mode = "SP" if path.stem.endswith("_sp") else "OPT"
        if path.exists():
            # Use status checking with metadata for enhanced validation
            status, details = get_status_for_file(path, metadata)
        else:
            status, details = "absent", "Input file not found"
        group_counts[status] = group_counts.get(status, 0) + 1
        # Use summary_logger to ensure uniform formatting.
        summary_logger.info(
            format_str.format(str(relative_path), mode, status, details)
        )

    summary_logger.info(f"\n{' ' * 4}Summary for {group_key}:")
    for s, count in group_counts.items():
        summary_logger.info(f"    {s} : {count}")
    return group_counts


def check_all_statuses(config_manager, system_dir: Path) -> None:
    """
    Iterates over expected input paths (grouped by method_basis), checks their statuses on the fly,
    prints a formatted report for each group along with an intermediate summary, and finally prints
    an overall status summary. Enhanced to show OPT convergence info when available.

    Args:
        config_manager: ConfigManager instance or raw config dict
        system_dir: Base system directory
    """
    logging.info("Status checking started:")
    # Use metadata for enhanced status reporting
    path_items = list(
        iter_input_paths(config_manager, system_dir, include_metadata=True)
    )
    if not path_items:
        logging.info("No input paths available for status checking.")
        return

    groups = group_paths_by_method_basis(path_items)
    overall_counts: Dict[str, int] = {}

    for group_key, group_items in groups.items():
        group_counts = print_group_status(group_key, group_items, system_dir)
        for s, count in group_counts.items():
            overall_counts[s] = overall_counts.get(s, 0) + count

    # Print overall summary with a boundary block.
    boundary_line = "=" * 60
    summary_logger.info(f"\n{boundary_line}")
    summary_logger.info(f"{' ' * 8}OVERALL STATUS SUMMARY")
    summary_logger.info(boundary_line)
    for s, count in overall_counts.items():
        summary_logger.info(f"    {s} : {count}")
    summary_logger.info(boundary_line)
    logging.info("Status checking finished.")
