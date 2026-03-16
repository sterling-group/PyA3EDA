"""
Energy Profile Extractor for Quantum Chemistry Calculations.

Functional approach for processing quantum chemistry calculation data to construct 
reaction energy profiles for both catalyzed and uncatalyzed pathways.

Example:
     profiles = extract_profiles(calculation_data)
     all_profiles = process_all_profiles(extracted_data)
"""
import logging
from typing import Dict, List, Any, Optional


def _get_components(raw_data: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Extract reaction components from calculation metadata."""
    if not raw_data:
        return {"all_reactants": [], "all_products": [], "all_catalysts": []}
    
    # Get first entry's component data (all entries should have same reaction setup)
    first_entry = raw_data[0]
    return {
        "all_reactants": first_entry.get("all_reactants", []),
        "all_products": first_entry.get("all_products", []),  
        "all_catalysts": first_entry.get("all_catalysts", [])
    }


def _build_energy_lookup(raw_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Build energy lookup table with support for calculation-specific keys.
    
    Supports both OPT data (E and G) and SP-only data (E only).
    For SP-only data, G will be None and those profiles will be skipped during filtering.
    """
    energy_lookup = {}
    
    for data in raw_data:
        species = data.get("Species", "")
        if not species:
            continue
        
        # Get energy values
        e_val = data.get("E (kcal/mol)") or data.get("SP_E (kcal/mol)")
        g_val = data.get("G (kcal/mol)")  # May be None for SP-only data
        g_trans_val = data.get("G_trans (kcal/mol)")  # Translational Gibbs contribution
        
        # Require at least E value (G is optional for SP-only calculations)
        if e_val is not None:
            calc_type = data.get("Calc_Type", "")
            
            entry = {"E": e_val, "G": g_val, "G_trans": g_trans_val}
            
            # Create calc_type-specific key if calc_type exists
            if calc_type and calc_type != "unknown":
                energy_lookup[f"{species}_{calc_type}"] = entry.copy()
            
            # Always create base species key
            energy_lookup[species] = entry
    
    return energy_lookup


def _get_energy(species: str, energy_lookup: Dict[str, Dict[str, float]], calc_type: str = None) -> Optional[Dict[str, float]]:
    """Get energy for species, trying calc_type-specific key first if provided."""
    if calc_type:
        calc_type_key = f"{species}_{calc_type}"
        if calc_type_key in energy_lookup:
            return energy_lookup[calc_type_key]
    
    return energy_lookup.get(species)


def _find_entries(raw_data: List[Dict[str, Any]], branch: str = None, category: str = None, catalyst: str = None) -> List[Dict[str, Any]]:
    """Find calculation entries matching specified metadata criteria."""
    matches = []
    for entry in raw_data:
        if branch and entry.get("Branch") != branch:
            continue
        if category and entry.get("Category") != category:
            continue
        if catalyst and entry.get("Catalyst") != catalyst:
            continue
        matches.append(entry)
    return matches


def _create_stage(stage_name: str, species_list: List[str], energy_lookup: Dict[str, Dict[str, float]], calc_types: List[str] = None) -> Optional[Dict[str, Any]]:
    """
    Create an energy profile stage by combining species energies.
    
    Args:
        stage_name (str): Name identifier for the profile stage.
        species_list (List[str]): List of species identifiers to combine.
        energy_lookup (Dict): Lookup table for species energies.
        calc_types (List[str], optional): List of calculation types corresponding to each species.
            
    Returns:
        Optional[Dict[str, Any]]: Dictionary containing stage data or None if energies unavailable.
    """
    if not species_list:
        return None
    
    total_e = 0.0
    total_g = 0.0
    total_g_trans = 0.0
    has_g_data = True  # Track if all species have G values
    has_g_trans_data = True  # Track if all species have G_trans values
    calc_types = calc_types or [None] * len(species_list)
    
    # Sum energies for all species
    for species, calc_type in zip(species_list, calc_types):
        energy = _get_energy(species, energy_lookup, calc_type)
        if not energy:
            return None
        
        total_e += energy["E"]
        
        # Handle G being None for SP-only data
        if energy["G"] is None:
            has_g_data = False
        else:
            total_g += energy["G"]
        
        # Handle G_trans
        if energy.get("G_trans") is None:
            has_g_trans_data = False
        else:
            total_g_trans += energy["G_trans"]
    
    # Get primary calc_type with sanity check
    non_empty_calc_types = [ct for ct in calc_types if ct]
    if len(set(non_empty_calc_types)) > 1:
        logging.warning(f"Mixed calc_types in '{stage_name}': {set(non_empty_calc_types)}")
    primary_calc_type = non_empty_calc_types[0] if non_empty_calc_types else None
    
    # Simple source description
    if len(species_list) == 1 and calc_types[0]:
        source = f"Direct ({calc_types[0]})"
    elif len(species_list) == 1:
        source = "Direct"
    else:
        source = "Addition"
    
    result = {
        "Stage": stage_name,
        "Calc_Type": primary_calc_type,
        "Species": " + ".join(species_list),
        "E (kcal/mol)": total_e,
        "G (kcal/mol)": total_g if has_g_data else None,  # None if no G data available
        "Source": source
    }
    
    # Add G_trans if available
    if has_g_trans_data:
        result["G_trans (kcal/mol)"] = total_g_trans
    
    return result


def _generate_stages(stage_type: str, catalyst: str, raw_data: List[Dict[str, Any]], components: Dict[str, List[str]], energy_lookup: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
    """Universal stage generator for all stage types using configuration-driven approach."""
    
    # Stage type configurations
    stage_configurations = {
        "reactants": {
            "branch": "reactants", "category": "no_cat", "stage_name": "Reactants",
            "needs_missing_components": True, "needs_catalyst": True, "components_key": "all_reactants"
        },
        "products": {
            "branch": "products", "category": "no_cat", "stage_name": "Products", 
            "needs_missing_components": True, "needs_catalyst": True, "components_key": "all_products"
        },
        "preTS": {
            "branch": "preTS", "category": "cat", "stage_name": "preTS",
            "needs_missing_components": True, "needs_calc_type": True, "components_key": "all_reactants"
        },
        "postTS": {
            "branch": "postTS", "category": "cat", "stage_name": "postTS",
            "needs_missing_components": True, "needs_calc_type": True, "components_key": "all_products"
        },
        "ts_cat": {
            "branch": "ts", "category": "cat", "stage_name": "TS",
            "needs_calc_type": True, "catalyst_present": True
        },
        "ts_nocat": {
            "branch": "ts", "category": "no_cat", "stage_name": "TS",
            "needs_catalyst": True
        }
    }
    
    stage_config = stage_configurations.get(stage_type)
    if not stage_config:
        return []
        
    # Find entries based on configuration
    entries = _find_entries(
        raw_data,
        branch=stage_config["branch"], 
        category=stage_config["category"],
        catalyst=catalyst if stage_config["category"] == "cat" else None
    )
    
    if not entries:
        return []
        
    stages = []
    seen_combinations = set() if stage_config["category"] == "no_cat" else None
    
    for entry in entries:
        calc_type = entry.get("Calc_Type", "")
        
        # Build stage name - keep stage separate from calc_type
        stage_name = stage_config["stage_name"]  # Just use base stage name
        
        # Build species list based on configuration
        species_list = [entry["Species"]]
        calc_types = [calc_type] if calc_type else [None]
        
        # Add missing components if needed
        if stage_config.get("needs_missing_components") and stage_config.get("components_key"):
            components_list = components[stage_config["components_key"]]
            present_components = entry.get(stage_config["components_key"].replace("all_", ""), [])
            missing_components = [c for c in components_list if c not in present_components]
            
            if missing_components:
                species_list.extend(missing_components)
                calc_types.extend([None] * len(missing_components))
        
        # Add catalyst if needed (and not already present)
        if stage_config.get("needs_catalyst") and not stage_config.get("catalyst_present"):
            species_list.append(catalyst)
            calc_types.append(None)
        
        # Handle duplicates for no_cat
        if seen_combinations is not None:
            species_set = frozenset(species_list)
            if species_set in seen_combinations:
                continue
            seen_combinations.add(species_set)
        
        # Create stage
        stage = _create_stage(stage_name, species_list, energy_lookup, calc_types)
        if stage:
            stages.append(stage)
            
    return stages


def _generate_catalyst_profile(catalyst: str, raw_data: List[Dict[str, Any]], components: Dict[str, List[str]], energy_lookup: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
    """Generate a complete profile for a single catalyst using unified stage generation."""
    profile = []
    
    # Add stages in order: reactants -> preTS -> TS -> postTS -> products
    profile.extend(_generate_stages("reactants", catalyst, raw_data, components, energy_lookup))
    profile.extend(_generate_stages("preTS", catalyst, raw_data, components, energy_lookup))
    profile.extend(_generate_stages("ts_cat", catalyst, raw_data, components, energy_lookup))
    profile.extend(_generate_stages("ts_nocat", catalyst, raw_data, components, energy_lookup))
    profile.extend(_generate_stages("postTS", catalyst, raw_data, components, energy_lookup))
    profile.extend(_generate_stages("products", catalyst, raw_data, components, energy_lookup))

    # Add derived trans-reference stage at preTS based on full preTS and reactants.
    # This is used for the translational delta-delta formulation.
    react_stage = next(
        (s for s in profile if s.get("Stage") == "Reactants" and not s.get("Calc_Type") and s.get("G_trans (kcal/mol)") is not None),
        None,
    )
    prets_full_stage = next(
        (s for s in profile if s.get("Stage") == "preTS" and s.get("Calc_Type") == "full_cat" and s.get("G_trans (kcal/mol)") is not None),
        None,
    )
    if react_stage and prets_full_stage:
        profile.append({
            "Stage": "preTS",
            "Calc_Type": "trans_cat",
            # Keep species aligned with full_cat stage so filtering can retain this row.
            "Species": prets_full_stage.get("Species", ""),
            "E (kcal/mol)": None,
            "G (kcal/mol)": None,
            "G_trans (kcal/mol)": prets_full_stage["G_trans (kcal/mol)"] - react_stage["G_trans (kcal/mol)"],
            "Source": "Derived",
        })
    
    return profile


def _filter_profile(profile: List[Dict[str, Any]], energy_type: str) -> List[Dict[str, Any]]:
    """Smart filtering: Group by stage, find min full_cat, keep same species for pol/frz_cat.
    
    For SP-only data without G values, returns empty list when filtering by G.
    """
    energy_key = f"{energy_type} (kcal/mol)"
    
    # Check if any stage has the required energy type (skip G filtering for SP-only data)
    has_energy_data = any(stage.get(energy_key) is not None for stage in profile)
    if not has_energy_data:
        logging.info(f"Skipping {energy_type} profile filtering - no {energy_type} data available (SP-only data)")
        return []
    
    stage_groups = {}
    
    # Group by stage name (e.g., "Reactants", "preTS", "TS", etc.)
    for stage in profile:
        stage_name = stage.get("Stage", "")
        if stage_name not in stage_groups:
            stage_groups[stage_name] = []
        stage_groups[stage_name].append(stage)
    
    filtered = []
    for stage_name, stages in stage_groups.items():
        # Subgroup stages: those with calc_types vs those without
        calc_type_stages = [s for s in stages if s.get("Calc_Type") and s.get("Calc_Type") not in [None, "", "unknown"]]
        no_calc_type_stages = [s for s in stages if not s.get("Calc_Type") or s.get("Calc_Type") in [None, "", "unknown"]]
        
        # Handle calc_type subgroup: smart filtering via full_cat
        if calc_type_stages:
            full_cat_stages = [s for s in calc_type_stages if s.get("Calc_Type") == "full_cat"]
            if full_cat_stages:
                # Find min full_cat, keep same species for pol/frz_cat  
                min_full_cat = min(full_cat_stages, key=lambda x: x.get(energy_key, float('inf')))
                min_species = min_full_cat.get("Species", "")
                
                filtered.append(min_full_cat)
                for calc_type in ["pol_cat", "frz_cat", "trans_cat"]:
                    matching_stages = [
                        s for s in calc_type_stages 
                        if s.get("Calc_Type") == calc_type and s.get("Species") == min_species
                    ]
                    if matching_stages:
                        filtered.append(matching_stages[0])
            else:
                # Has calc_types but no full_cat: find lowest energy stage, then keep all calc_types for that species
                min_stage = min(calc_type_stages, key=lambda x: x.get(energy_key, float('inf')))
                min_species = min_stage.get("Species", "")
                
                # Keep all calc_types that match the minimum species
                for stage in calc_type_stages:
                    if stage.get("Species") == min_species:
                        filtered.append(stage)
        
        # Handle no-calc_type subgroup: simple minimum energy
        if no_calc_type_stages:
            min_no_calc = min(no_calc_type_stages, key=lambda x: x.get(energy_key, float('inf')))
            filtered.append(min_no_calc)
    
    return sorted(filtered, key=lambda s: profile.index(s))  # Keep original order


def extract_profiles(raw_data_list: List[Dict[str, Any]], filter_duplicates: bool = False) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Extract energy profiles for all catalyst pathways.
    
    Args:
        raw_data_list: List of calculation data dictionaries
        filter_duplicates: Whether to apply smart filtering
        
    Returns:
        Dictionary mapping catalyst names to their profile data
    """
    if not raw_data_list:
        return {}
    
    # Build lookup structures
    components = _get_components(raw_data_list)
    energy_lookup = _build_energy_lookup(raw_data_list)
    
    profiles = {}
    for catalyst in components["all_catalysts"]:
        raw_profile = _generate_catalyst_profile(catalyst, raw_data_list, components, energy_lookup)
        if raw_profile:  # Only include non-empty profiles
            catalyst_profiles = {"raw": raw_profile}
            
            if filter_duplicates:
                catalyst_profiles["E"] = _filter_profile(raw_profile, "E")
                catalyst_profiles["G"] = _filter_profile(raw_profile, "G")
                catalyst_profiles["G_trans"] = _filter_profile(raw_profile, "G_trans")
            
            profiles[catalyst] = catalyst_profiles
    
    return profiles


def process_all_profiles(raw_data: Dict[str, Dict[str, List[Dict[str, Any]]]]) -> Dict[str, Dict[str, Any]]:
    """
    Process all raw extracted data into profiles for all method combos.
    
    Args:
        raw_data: Dictionary mapping method combo names to their extracted data
        
    Returns:
        Dictionary with raw data + processed profiles for each combo
    """
    if not raw_data:
        return {}
    
    processed_data = {}
    for combo_name, combo_data in raw_data.items():
        processed_data[combo_name] = {
            **combo_data,  # Keep all original data
            "profiles": {}  # Add profiles
        }
        
        # Process profiles for each data type (opt/sp)
        for data_key in ["opt_data", "sp_data"]:
            if combo_data.get(data_key):
                calc_type = "OPT" if data_key == "opt_data" else "SP"
                logging.info(f"Generating profiles for {calc_type} data in {combo_name}")
                profiles = extract_profiles(combo_data[data_key], filter_duplicates=True)
                if profiles:
                    logging.info(f"  Generated profiles for {len(profiles)} catalysts: {list(profiles.keys())}")
                else:
                    logging.warning(f"  No profiles generated for {calc_type} data (check if catalyst metadata exists)")
                processed_data[combo_name]["profiles"][data_key] = profiles
    
    return processed_data
