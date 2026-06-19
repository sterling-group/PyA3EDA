"""
File Builder Module

This module centralizes the logic for constructing the directory structure and complete
Q-Chem input files based on a sanitized configuration and template files.
It produces a folder tree structured as described by the processed configuration.
It produces a folder tree structured as follows:

    {opt_method}_{opt_dispersion}_{opt_basis}_{opt_solvent}/
    ├── no_cat/
    │   ├── reactants/
    │   │   ├── {Reactant1}/
    │   │   │   ├── {Reactant1}_opt.in
    │   │   │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
    │   │   │         └── {Reactant1}_sp.in
    │   │   ├── {Reactant2}/
    │   │   │   ├── {Reactant2}_opt.in
    │   │   │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
    │   │   │         └── {Reactant2}_sp.in
    │   │   └── {Reactant1}-{Reactant2}/
    │   │         ├── {Reactant1}-{Reactant2}_opt.in
    │   │         └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
    │   │               └── {Reactant1}-{Reactant2}_sp.in
    │   ├── products/
    │   │   ├── {Product1}/
    │   │   │   ├── {Product1}_opt.in
    │   │   │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
    │   │   │         └── {Product1}_sp.in
    │   │   └── {Product2}/
    │   │         ├── {Product2}_opt.in
    │   │         └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
    │   │               └── {Product2}_sp.in
    │   └── ts/
    │         ├── tscomplex_opt.in
    │         └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
    │               └── tscomplex_sp.in
    └── {Catalyst}/
        ├── preTS/
        │   ├── {Catalyst}-{Reactant1}/
        │   │   ├── full_cat/
        │   │   │   ├── preTS_{Catalyst}-{Reactant1}_full_cat_opt.in
        │   │   │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │   │   │         └── preTS_{Catalyst}-{Reactant1}_full_cat_sp.in
        │   │   ├── pol_cat/
        │   │   │   ├── preTS_{Catalyst}-{Reactant1}_pol_cat_opt.in
        │   │   │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │   │   │         └── preTS_{Catalyst}-{Reactant1}_pol_cat_sp.in
        │   │   └── frz_cat/
        │   │       ├── preTS_{Catalyst}-{Reactant1}_frz_cat_opt.in
        │   │       └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │   │             └── preTS_{Catalyst}-{Reactant1}_frz_cat_sp.in
        │   └── {Catalyst}-{Reactant1}-{Reactant2}/
        │         ├── full_cat/
        │         │   ├── preTS_{Catalyst}-{Reactant1}-{Reactant2}_full_cat_opt.in
        │         │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │         │         └── preTS_{Catalyst}-{Reactant1}-{Reactant2}_full_cat_sp.in
        │         ├── pol_cat/
        │         │   ├── preTS_{Catalyst}-{Reactant1}-{Reactant2}_pol_cat_opt.in
        │         │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │         │         └── preTS_{Catalyst}-{Reactant1}-{Reactant2}_pol_cat_sp.in
        │         └── frz_cat/
        │               ├── preTS_{Catalyst}-{Reactant1}-{Reactant2}_frz_cat_opt.in
        │               └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │                     └── preTS_{Catalyst}-{Reactant1}-{Reactant2}_frz_cat_sp.in
        ├── postTS/
        │   └── {Catalyst}-{Product1}/
        │         ├── full_cat/
        │         │   ├── postTS_{Catalyst}-{Product1}_full_cat_opt.in
        │         │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │         │         └── postTS_{Catalyst}-{Product1}_full_cat_sp.in
        │         ├── pol_cat/
        │         │   ├── postTS_{Catalyst}-{Product1}_pol_cat_opt.in
        │         │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │         │         └── postTS_{Catalyst}-{Product1}_pol_cat_sp.in
        │         └── frz_cat/
        │               ├── postTS_{Catalyst}-{Product1}_frz_cat_opt.in
        │               └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │                     └── postTS_{Catalyst}-{Product1}_frz_cat_sp.in
        └── ts/
            ├── full_cat/
            │   ├── ts_{Catalyst}-tscomplex_full_opt.in
            │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
            │         └── ts_{Catalyst}-tscomplex_full_sp.in
            ├── pol_cat/
            │   ├── ts_{Catalyst}-tscomplex_pol_opt.in
            │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
            │         └── ts_{Catalyst}-tscomplex_pol_sp.in
            └── frz_cat/
                    ├── ts_{Catalyst}-tscomplex_frz_opt.in
                    └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
                        └── ts_{Catalyst}-tscomplex_frz_sp.in
The module uses molecule builder routines (both standard and fragmented)
to generate the Q-Chem input file content before writing them to disk.
"""

import logging
from itertools import combinations
from pathlib import Path

from PyA3EDA.core.builders import rem_builder
from PyA3EDA.core.builders.molecule_builder import (
    build_fragmented_molecule_section,
    build_standard_molecule_section,
)
from PyA3EDA.core.utils.file_utils import read_text, write_text


def get_molecule_section(
    molecule_processing_fn,
    species: str,
    template_prefix: str = "",
    catalyst: str = None,
    mode: str = "opt",
    opt_output_path: Path = None,
    system_dir: Path = None,
    calc_type: str = None,
) -> str:
    """
    Returns the molecule section of the input file.

    Args:
        molecule_processing_fn: Function to process the molecule section
        species: Species name
        template_prefix: Prefix for template filename (e.g., "ts_", "preTS_")
        catalyst: Catalyst name (optional)
        mode: Mode ("opt" or "sp")
        opt_output_path: Path to the optimization output file (for sp mode)
        system_dir: System directory to locate molecule templates
        calc_type: Calculation type for calc-type-specific templates (e.g., "frz_cat")

    Returns:
        Processed molecule section string
    """

    def load_xyz(identifier: str) -> str:
        """Load XYZ template, trying calc_type-specific version first."""
        templates_dir = system_dir / "templates" / "molecule"
        for suffix in [f"_{calc_type}", ""] if calc_type else [""]:
            path = templates_dir / f"{identifier}{suffix}.xyz"
            if path.exists() and (content := read_text(path)):
                return content
        # Only log error if no template found at all (after trying all suffixes)
        logging.error(f"Missing template: {templates_dir / f'{identifier}.xyz'}")
        return None

    # Load the main composite/species template
    template_name = f"{template_prefix}{species}"
    composite_xyz_text = load_xyz(template_name)
    if not composite_xyz_text:
        logging.error(f"Failed to load molecule template for {species}")
        return None

    # For SP mode, read the optimization output
    output_text = (
        read_text(opt_output_path)
        if mode == "sp" and opt_output_path and opt_output_path.exists()
        else None
    )

    # For fragmented molecule sections, load catalyst and substrate templates
    catalyst_xyz_text = substrate_xyz_text = substrate_id = None

    if molecule_processing_fn == build_fragmented_molecule_section and system_dir:
        parts = species.split("-")
        if len(parts) >= 2:
            cat_id = catalyst or parts[0]
            substrate_id = "-".join(parts[1:])
            catalyst_xyz_text = load_xyz(cat_id)
            substrate_xyz_text = load_xyz(substrate_id)

    # Use the appropriate molecule building function
    # Create unique identifier including calc_type for proper caching
    unique_id = f"{template_name}_{calc_type}" if calc_type else template_name

    if molecule_processing_fn == build_fragmented_molecule_section:
        return molecule_processing_fn(
            composite_xyz_text,
            unique_id,
            catalyst_xyz_text,
            substrate_xyz_text,
            catalyst,
            substrate_id,
            output_text,
        )
    else:
        return molecule_processing_fn(composite_xyz_text, unique_id, output_text)


def get_rem_section(
    system_dir: Path,
    calc: str,
    rem: dict,
    category: str,
    branch: str,
    mode: str,
    method: str,
    basis: str,
) -> str:
    """
    Returns the REM section. For sp mode, uses sp builder; for opt mode, uses the opt builder.

    For SP mode, sets special parameters:
    - eda2: Set to 0 for no_cat or cat branch, otherwise from rem dict
    - scfmi_freeze_ss: Set to 1 for frz_cat calculations, 0 otherwise
    - eda_bsse: Set to true only for full_cat calculations, false otherwise
    """
    if mode == "sp":
        eda2 = "0" if category == "no_cat" or branch == "cat" else rem.get("eda2", "0")
        scfmi_freeze_ss = "1" if calc == "frz_cat" else "0"
        eda_bsse = "true" if calc == "full_cat" else "false"

        return rem_builder.build_rem_section_for_sp(
            system_dir,
            method,
            basis,
            rem.get("dispersion", "false"),
            rem.get("solvent", "false"),
            eda2,
            scfmi_freeze_ss,
            eda_bsse,
        )
    else:
        jobtype = (
            "ts"
            if branch == "ts"
            else (
                "sp"
                if len(rem.get("molecule_section", "").splitlines()) - 1 == 1
                else "opt"
            )
        )
        return rem_builder.build_rem_section_for_opt(
            system_dir,
            calc,
            rem["method"],
            basis,
            rem.get("dispersion", "false"),
            rem.get("solvent", "false"),
            jobtype,
        )


def build_file_path(
    system_dir: Path,
    method: str,
    basis: str,
    dispersion: str,
    solvent: str,
    category: str,
    branch: str,
    species: str,
    calc_type: str,
    catalyst_name: str = "",
    mode: str = "opt",
    opt_params: dict = None,
) -> Path:
    """
    Constructs the full input file path using sanitized values.
    For opt mode, folder and file names are built using the provided values.
    For sp mode, the top folder comes from the opt values in opt_params and an extra subfolder is added.
    """
    if mode == "opt":
        top_method, top_basis, top_disp, top_solvent = (
            method,
            basis,
            dispersion,
            solvent,
        )
        suffix = "_opt.in"
    elif mode == "sp":
        if opt_params is None:
            raise ValueError("For sp mode, opt_params must be provided.")
        top_method = opt_params.get("method")
        top_basis = opt_params.get("basis")
        top_disp = opt_params.get("dispersion")
        top_solvent = opt_params.get("solvent")
        suffix = "_sp.in"

        # Create sp_folder name using the centralized function
        sp_folder_base = build_method_folder_name(method, basis, dispersion, solvent)
        sp_folder = f"{sp_folder_base}_sp"
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Create base folder name using the centralized function
    base_folder_name = build_method_folder_name(
        top_method, top_basis, top_disp, top_solvent
    )
    base_folder = system_dir / base_folder_name

    if category == "no_cat":
        if branch in ("reactants", "products"):
            if mode == "opt":
                relative = Path("no_cat") / branch / species / f"{species}{suffix}"
            else:
                relative = (
                    Path("no_cat") / branch / species / sp_folder / f"{species}{suffix}"
                )
        elif branch == "ts":
            if mode == "opt":
                relative = Path("no_cat") / "ts" / f"tscomplex{suffix}"
            else:
                relative = Path("no_cat") / "ts" / sp_folder / f"tscomplex{suffix}"
        else:
            raise ValueError(f"Unknown branch for no_cat: {branch}")
    elif category == "cat":
        if not catalyst_name:
            raise ValueError("For catalyst cases, catalyst_name must be provided.")

        if branch == "preTS":
            if mode == "opt":
                relative = (
                    Path(catalyst_name)
                    / "preTS"
                    / species
                    / calc_type
                    / f"preTS_{species}_{calc_type}{suffix}"
                )
            else:
                relative = (
                    Path(catalyst_name)
                    / "preTS"
                    / species
                    / calc_type
                    / sp_folder
                    / f"preTS_{species}_{calc_type}{suffix}"
                )
        elif branch == "postTS":
            if mode == "opt":
                relative = (
                    Path(catalyst_name)
                    / "postTS"
                    / species
                    / calc_type
                    / f"postTS_{species}_{calc_type}{suffix}"
                )
            else:
                relative = (
                    Path(catalyst_name)
                    / "postTS"
                    / species
                    / calc_type
                    / sp_folder
                    / f"postTS_{species}_{calc_type}{suffix}"
                )
        elif branch == "ts":
            if mode == "opt":
                relative = (
                    Path(catalyst_name)
                    / "ts"
                    / calc_type
                    / f"ts_{catalyst_name}-tscomplex_{calc_type}{suffix}"
                )
            else:
                relative = (
                    Path(catalyst_name)
                    / "ts"
                    / calc_type
                    / sp_folder
                    / f"ts_{catalyst_name}-tscomplex_{calc_type}{suffix}"
                )
        elif branch == "cat":
            if mode == "opt":
                relative = Path(catalyst_name) / "cat" / f"{catalyst_name}{suffix}"
            else:
                relative = (
                    Path(catalyst_name) / "cat" / sp_folder / f"{catalyst_name}{suffix}"
                )
        else:
            raise ValueError(f"Unknown branch for catalyst: {branch}")
    else:
        raise ValueError(f"Unknown category: {category}")

    full_path = base_folder / relative
    return full_path


def build_and_write_input_file(
    system_dir: Path,
    sanitized: dict,
    original: dict,
    category: str,
    branch: str,
    species: str,
    calc_type: str,
    template_base_path: Path,
    template_prefix: str,
    molecule_proc_fn,
    catalyst_name: str = "",
    mode: str = "opt",
    overwrite: str = None,
    sp_strategy: str = "smart",
) -> None:
    """
    Builds the file path (using sanitized values), creates the file content, and writes it to disk.
    In sp mode the opt_params for file naming are taken from the sanitized version.

    Args:
        system_dir: Base system directory
        sanitized: Dictionary with sanitized naming values
        original: Dictionary with original values
        category: Category (no_cat or cat)
        branch: Branch (reactants, products, ts, etc.)
        species: Species name
        calc_type: Calculation type
        template_base_path: Path to base template file
        template_prefix: Prefix for template filename (e.g., "ts_", "preTS_")
        molecule_proc_fn: Function to process molecule section
        catalyst_name: Catalyst name (optional)
        mode: Mode (opt or sp)
        overwrite: Overwrite criteria (None, "all", "CRASH", "terminated", etc.)
        sp_strategy: Strategy for SP file generation ("always", "smart", "never")
    """
    # SP file generation handling
    opt_output_path = None
    if mode == "sp":
        # Skip SP file generation based on strategy
        if sp_strategy == "never":
            return

        opt_params = {
            "method": sanitized["opt_method"],
            "basis": sanitized["opt_basis"],
            "dispersion": sanitized["opt_dispersion"],
            "solvent": sanitized["opt_solvent"],
        }

        opt_input_path = build_file_path(
            system_dir,
            opt_params["method"],
            opt_params["basis"],
            opt_params["dispersion"],
            opt_params["solvent"],
            category,
            branch,
            species,
            calc_type,
            catalyst_name,
            mode="opt",
        )

        opt_output_path = opt_input_path.with_suffix(".out")
    else:
        opt_params = None

    # Build file path
    file_path = build_file_path(
        system_dir,
        sanitized["method"],
        sanitized["basis"],
        sanitized["dispersion"],
        sanitized["solvent"],
        category,
        branch,
        species,
        calc_type,
        catalyst_name,
        mode,
        opt_params,
    )

    from PyA3EDA.core.status.status_checker import should_process_file

    # Check SP strategy after building SP file path so we can log the correct file
    if mode == "sp" and sp_strategy == "smart":
        # Create minimal metadata for validation (only need Branch for TS validation)
        opt_metadata = {"Mode": "opt", "Branch": branch}
        # Check if OPT file should be processed as "SUCCESSFUL" (includes validation)
        should_generate, reason = should_process_file(
            opt_input_path, "SUCCESSFUL", opt_metadata
        )

        if not should_generate:
            logging.info(
                f"Skipping SP file ({reason}): {file_path.relative_to(system_dir)}"
            )
            return

    # Check if file exists and determine if we should overwrite
    if file_path.exists():
        # Check if we should overwrite based on the provided criteria
        should_write, reason = should_process_file(file_path, overwrite)
        if not should_write:
            logging.info(
                f"Skipping file ({reason}): {file_path.relative_to(system_dir)}"
            )
            return
        logging.info(
            f"Overwriting file ({reason}): {file_path.relative_to(system_dir)}"
        )

    # Load base template
    base_template = read_text(template_base_path)
    if not base_template:
        logging.error(f"Failed to read template: {template_base_path}")
        return

    # Add geom opt section for opt mode
    if mode == "opt":
        geom_file = system_dir / "templates" / "rem" / "geom_opt.rem"
        geom_content = read_text(geom_file)
        if geom_content:
            base_template += "\n\n" + geom_content
        else:
            logging.warning(f"Geometry optimization template not found: {geom_file}")

    # Add solvent REM section if solvent is specified
    if sanitized["solvent"] and sanitized["solvent"].lower() != "false":
        solvent_name = sanitized["solvent"]
        solvent_file = system_dir / "templates" / "rem" / f"solvent_{solvent_name}.rem"
        if solvent_file.exists():
            solvent_content = read_text(solvent_file)
            if solvent_content:
                base_template += "\n\n" + solvent_content
        else:
            logging.warning(f"Solvent file not found: {solvent_file}")

    # Generate molecule section
    try:
        # Get molecule section through the unified interface
        molecule_section = get_molecule_section(
            molecule_processing_fn=molecule_proc_fn,
            species=species,
            template_prefix=template_prefix,
            catalyst=catalyst_name,
            mode=mode,
            opt_output_path=opt_output_path,
            system_dir=system_dir,
            calc_type=calc_type,
        )

        if not molecule_section:
            logging.error(f"Failed to generate molecule section for {species}")
            return
    except Exception as e:
        logging.error(f"Error generating molecule section for {species}: {str(e)}")
        return

    # Store molecule section in original values
    original["molecule_section"] = molecule_section

    # Prepare REM values
    rem_vals = {
        "method": original["method"],
        "basis": original["basis"],
        "dispersion": original.get("dispersion", "false"),
        "solvent": original.get("solvent", "false"),
        "molecule_section": molecule_section,
    }

    # Add EDA2 parameter for SP mode
    if mode == "sp":
        rem_vals["eda2"] = original.get("eda2", "0")

    # Get REM section
    rem_section = get_rem_section(
        system_dir,
        calc_type,
        rem_vals,
        category,
        branch,
        mode,
        rem_vals["method"],
        rem_vals["basis"],
    )

    # Format final content
    content = base_template.format(
        molecule_section=molecule_section.rstrip(), rem_section=rem_section.rstrip()
    )

    if not content.rstrip():
        logging.error(
            f"Empty content generated for {file_path}. Skipping file creation."
        )
        return

    # Write the file
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if write_text(file_path, content):
        logging.info(f"Input file written to {file_path.relative_to(system_dir)}")
    else:
        logging.error(f"Failed to write input file to {file_path}")


def get_combinations(species_list, min_length=2):
    """
    Generates dash-joined combination strings from a list of species.
    Uses each species' opt value so that file naming is consistent.
    """
    for r in range(min_length, len(species_list) + 1):
        for combo in combinations(species_list, r):
            yield "-".join(spec["name"]["opt"] for spec in combo)


def build_method_folder_name(
    method: str, basis: str, dispersion: str, solvent: str
) -> str:
    """
    Build a method folder name by filtering out 'false' values.
    Used consistently for both OPT and SP folder naming.
    """
    folder_parts = [method]

    # Only include dispersion if not false
    if dispersion and dispersion.lower() != "false":
        folder_parts.append(dispersion)

    # Always include basis set
    folder_parts.append(basis)

    # Only include solvent if not false
    if solvent and solvent.lower() != "false":
        folder_parts.append(solvent)

    # Join parts with underscores
    return "_".join(folder_parts)


def create_file_metadata(
    method: dict,
    basis_set: dict,
    mode: str,
    category: str,
    branch: str,
    species: str,
    calc_type: str,
    catalyst: str,
    file_path: Path,
    config_manager=None,
) -> dict:
    """
    Create comprehensive, standardized metadata for calculation files.

    Args:
        method: Method configuration dict
        basis_set: Basis set configuration dict
        mode: Calculation mode ("opt" or "sp")
        category: Calculation category ("no_cat" or "cat")
        branch: Calculation branch ("reactants", "products", "ts", etc.)
        species: Species name for this calculation
        calc_type: Calculation type ("full_cat", "pol_cat", "frz_cat", etc.)
        catalyst: Catalyst name (empty string if none)
        file_path: Path to the calculation file
        config_manager: Optional config manager for component lists

    Returns:
        Comprehensive metadata dictionary with all available information
    """
    # Core identification metadata
    core_metadata = {
        "Species": species,
        "Category": category,
        "Branch": branch,
        "Calc_Type": calc_type,
        "Catalyst": catalyst,
        "Mode": mode,
        "Path": str(file_path),
    }

    # Method and computational parameters
    computational_metadata = _get_computational_metadata(method, basis_set, mode)

    # Additional method parameters
    additional_metadata = {
        "eda2": method.get("eda2", "0")  # EDA2 parameter for analysis
    }

    # Component information from config manager
    component_metadata = {}
    if config_manager:
        component_metadata = _get_reaction_components(config_manager, species, catalyst)

    # Combine all metadata
    return {
        **core_metadata,
        **computational_metadata,
        **additional_metadata,
        **component_metadata,
    }


def _get_computational_metadata(method: dict, basis_set: dict, mode: str) -> dict:
    """Extract computational method metadata with method combos."""
    if mode == "opt":
        method_combo = build_method_folder_name(
            method["name"]["opt"],
            basis_set["opt"],
            method["dispersion"]["opt"],
            method["solvent"]["opt"],
        )

        return {
            "Method": method["name"]["opt"],
            "Method_Combo": method_combo,
            "Basis": basis_set["opt"],
            "Dispersion": method["dispersion"]["opt"],
            "Solvent": method["solvent"]["opt"],
        }

    else:  # sp mode
        # Base method combo for folder structure
        base_method_combo = build_method_folder_name(
            method["name"]["opt"],
            basis_set["opt"],
            method["dispersion"]["opt"],
            method["solvent"]["opt"],
        )

        # SP method combo for SP calculations
        sp_method_combo = build_method_folder_name(
            method["name"]["sp"],
            basis_set["sp"],
            method["dispersion"]["sp"],
            method["solvent"]["sp"],
        )

        return {
            "Method": method["name"]["opt"],  # Base method for folder structure
            "Method_Combo": base_method_combo,  # Base method combo
            "SP_Method": method["name"]["sp"],  # SP-specific method
            "SP_Method_Combo": sp_method_combo,  # SP-specific method combo
            "Basis": basis_set["opt"],  # Base basis for folder structure
            "SP_Basis": basis_set["sp"],  # SP-specific basis
            "Dispersion": method["dispersion"]["opt"],  # Base dispersion
            "SP_Dispersion": method["dispersion"]["sp"],  # SP-specific dispersion
            "Solvent": method["solvent"]["opt"],  # Base solvent
            "SP_Solvent": method["solvent"]["sp"],  # SP-specific solvent
        }


def _get_reaction_components(config_manager, species: str, catalyst: str) -> dict:
    """Extract comprehensive reaction component metadata from config manager."""
    config = config_manager.get_builder_config()

    # Get complete reaction components
    all_reactants = [r["name"]["opt"] for r in config.get("reactants", [])]
    all_products = [p["name"]["opt"] for p in config.get("products", [])]
    all_catalysts = [c["name"]["opt"] for c in config.get("catalysts", [])]

    # Filter to components present in this specific calculation
    present_reactants = [r for r in all_reactants if r in species]
    present_products = [p for p in all_products if p in species]
    present_catalysts = [c for c in all_catalysts if c in species or c == catalyst]

    return {
        # Components present in this specific calculation
        "reactants": present_reactants,
        "products": present_products,
        "catalysts": present_catalysts,
        # Complete reaction information (for profile extraction)
        "all_reactants": all_reactants,
        "all_products": all_products,
        "all_catalysts": all_catalysts,
    }


def process_input_files(
    config_manager,
    system_dir: Path,
    mode: str = "generate",
    overwrite: str = None,
    sp_strategy: str = "smart",
):
    """
    Process input files based on mode - either generate them or yield their paths.

    Args:
        config_manager: ConfigManager instance with processed configuration
        system_dir: Base system directory
        mode: "generate" to create files, "yield" to yield paths
        overwrite: Overwrite criteria (None, "all", "CRASH", "terminated", etc.)
        sp_strategy: Strategy for SP file generation ("always", "smart", "never")
    """
    if mode not in ("generate", "yield"):
        raise ValueError(f"Invalid mode: {mode}. Must be 'generate' or 'yield'")

    templates_dir = system_dir / "templates"
    base_template_path = templates_dir / "base_template.in"
    processed_config = (
        config_manager.get_builder_config()
        if hasattr(config_manager, "get_builder_config")
        else config_manager
    )

    # Keep track of OPT files already processed to avoid duplicates
    processed_opt_files = set()

    # Helper function to handle both path generation and file writing
    def process_file(
        method,
        bs,
        file_mode,
        category,
        branch,
        species,
        calc_type="",
        catalyst_name="",
        template_prefix="",
        molecule_fn=None,
    ):
        """Process a single input file - either yield its path or build and write it."""
        nonlocal processed_opt_files

        if file_mode == "sp" and not (
            method["name"].get("sp_enabled", False) and bs.get("sp_enabled", False)
        ):
            return

        # Build file path
        if file_mode == "opt":
            file_path = build_file_path(
                system_dir,
                method["name"]["opt"],
                bs["opt"],
                method["dispersion"]["opt"],
                method["solvent"]["opt"],
                category,
                branch,
                species,
                calc_type,
                catalyst_name,
                mode=file_mode,
            )

            # Check for duplicates
            opt_key = (
                method["name"]["opt"],
                bs["opt"],
                method["dispersion"]["opt"],
                method["solvent"]["opt"],
                category,
                branch,
                species,
                calc_type,
                catalyst_name,
            )

            if opt_key in processed_opt_files:
                return None
            processed_opt_files.add(opt_key)
        else:  # sp
            file_path = build_file_path(
                system_dir,
                method["name"]["sp"],
                bs["sp"],
                method["dispersion"]["sp"],
                method["solvent"]["sp"],
                category,
                branch,
                species,
                calc_type,
                catalyst_name,
                mode=file_mode,
                opt_params={
                    "method": method["name"]["opt"],
                    "basis": bs["opt"],
                    "dispersion": method["dispersion"]["opt"],
                    "solvent": method["solvent"]["opt"],
                },
            )

        # Create metadata
        metadata = create_file_metadata(
            method,
            bs,
            file_mode,
            category,
            branch,
            species,
            calc_type,
            catalyst_name,
            file_path,
            config_manager,
        )

        # For yield mode, return path with metadata
        if mode == "yield":
            from types import SimpleNamespace

            return SimpleNamespace(path=file_path, metadata=metadata)

        # For generate mode, build and write the file
        sanitized, original = config_manager.get_common_values(method, bs, file_mode)

        build_and_write_input_file(
            system_dir=system_dir,
            sanitized=sanitized,
            original=original,
            category=category,
            branch=branch,
            species=species,
            calc_type=calc_type,
            template_base_path=base_template_path,
            template_prefix=template_prefix,
            molecule_proc_fn=molecule_fn,
            catalyst_name=catalyst_name,
            mode=file_mode,
            overwrite=overwrite,
            sp_strategy=sp_strategy,
        )

        # Return None for consistency (calling code will filter these)
        return None

    # Group methods by OPT configuration
    opt_groups = {}
    for method in processed_config.get("methods", []):
        for bs in method.get("basis_sets", []):
            opt_key = (
                method["name"]["opt"],
                method["dispersion"]["opt"],
                bs["opt"],
                method["solvent"]["opt"],
            )

            if opt_key not in opt_groups:
                opt_groups[opt_key] = {
                    "opt_method": method,
                    "opt_bs": bs,
                    "sp_configs": [],
                }

            if method["name"].get("sp_enabled", False) and bs.get("sp_enabled", False):
                opt_groups[opt_key]["sp_configs"].append({"method": method, "bs": bs})

    # Helper to process OPT file followed by all corresponding SP files for a species
    def process_opt_and_sp_for_species(
        category,
        branch,
        species,
        calc_type="",
        catalyst_name="",
        template_prefix="",
        molecule_fn=None,
    ):
        """Helper to process OPT file followed by all corresponding SP files for a species."""
        for opt_key, group in opt_groups.items():
            # Process OPT first
            result = process_file(
                group["opt_method"],
                group["opt_bs"],
                "opt",
                category,
                branch,
                species,
                calc_type,
                catalyst_name,
                template_prefix,
                molecule_fn,
            )
            if mode == "yield" and result:
                yield result

            # Then process all SP files for this OPT
            for sp_config in group["sp_configs"]:
                result = process_file(
                    sp_config["method"],
                    sp_config["bs"],
                    "sp",
                    category,
                    branch,
                    species,
                    calc_type,
                    catalyst_name,
                    template_prefix,
                    molecule_fn,
                )
                if mode == "yield" and result:
                    yield result

    # Process each species type with OPT-first-then-SP order
    for category, branch, species_list, species_fn in [
        (
            "no_cat",
            "reactants",
            processed_config.get("reactants", []),
            lambda r: r["name"]["opt"],
        ),
        (
            "no_cat",
            "products",
            processed_config.get("products", []),
            lambda p: p["name"]["opt"],
        ),
        ("no_cat", "ts", [{"name": {"opt": "tscomplex"}}], lambda t: t["name"]["opt"]),
    ]:
        for species_data in species_list:
            species = species_fn(species_data)
            yield from process_opt_and_sp_for_species(
                category, branch, species, molecule_fn=build_standard_molecule_section
            )

    # Process reactant combinations
    reactants_incl = [
        r for r in processed_config.get("reactants", []) if r.get("include", True)
    ]
    if len(reactants_incl) > 1:
        for combo in get_combinations(reactants_incl, min_length=2):
            yield from process_opt_and_sp_for_species(
                "no_cat",
                "reactants",
                combo,
                molecule_fn=build_standard_molecule_section,
            )

    # # Process product combinations (commented out - uncomment if needed for completeness)
    # products_incl = [p for p in processed_config.get("products", []) if p.get("include", True)]
    # if len(products_incl) > 1:
    #     for combo in get_combinations(products_incl, min_length=2):
    #         yield from process_opt_and_sp_for_species(
    #             "no_cat", "products", combo, molecule_fn=build_standard_molecule_section
    #         )

    # Process catalysts
    for catalyst in processed_config.get("catalysts", []):
        cat_name = catalyst["name"]["opt"]

        # Catalyst itself
        yield from process_opt_and_sp_for_species(
            "cat",
            "cat",
            cat_name,
            catalyst_name=cat_name,
            molecule_fn=build_standard_molecule_section,
        )

        # preTS: catalyst with reactants
        for combo in get_combinations(reactants_incl, min_length=1):
            species_combo = f"{cat_name}-{combo}"
            for calc_type in ("full_cat", "pol_cat", "frz_cat"):
                yield from process_opt_and_sp_for_species(
                    "cat",
                    "preTS",
                    species_combo,
                    calc_type=calc_type,
                    catalyst_name=cat_name,
                    template_prefix="preTS_",
                    molecule_fn=build_fragmented_molecule_section,
                )

        # postTS: catalyst with products
        products_incl = [
            p for p in processed_config.get("products", []) if p.get("include", True)
        ]
        for combo in get_combinations(products_incl, min_length=1):
            species_combo = f"{cat_name}-{combo}"
            for calc_type in ("full_cat", "pol_cat", "frz_cat"):
                yield from process_opt_and_sp_for_species(
                    "cat",
                    "postTS",
                    species_combo,
                    calc_type=calc_type,
                    catalyst_name=cat_name,
                    template_prefix="postTS_",
                    molecule_fn=build_fragmented_molecule_section,
                )

        # TS: Catalyst TS
        for calc_type in ("full_cat", "pol_cat", "frz_cat"):
            yield from process_opt_and_sp_for_species(
                "cat",
                "ts",
                f"ts_{cat_name}-tscomplex",
                calc_type=calc_type,
                catalyst_name=cat_name,
                molecule_fn=build_fragmented_molecule_section,
            )

    if mode == "generate":
        logging.info("Input file generation completed.")


def generate_all_inputs(
    config_manager, system_dir: Path, overwrite: str = None, sp_strategy: str = "smart"
) -> None:
    """Generate all Q-Chem input files using the unified config from config_manager."""
    list(
        process_input_files(
            config_manager, system_dir, "generate", overwrite, sp_strategy
        )
    )


def iter_input_paths(config, system_dir: Path, include_metadata: bool = False):
    """
    Iterate through all input file paths, optionally with metadata.

    This function serves as the single source of truth for file discovery across
    the PyA3EDA system, used by status checker, data extractor, and executor.

    Args:
        config: ConfigManager instance with processed configuration
        system_dir: Base system directory
        include_metadata: Whether to include metadata with paths

    Yields:
        Path objects (if include_metadata=False) or SimpleNamespace objects
        with 'path' and 'metadata' attributes (if include_metadata=True)
    """
    # Use the existing process_input_files function in yield mode
    for result in process_input_files(config, system_dir, mode="yield"):
        if result:
            if include_metadata:
                yield result  # Return the full object with path and metadata
            else:
                yield result.path  # Extract just the path
