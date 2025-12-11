"""
Delta-Delta Energy Contribution Extractor.

Extracts barrier heights and delta-delta contributions (ΔΔE‡/ΔΔG‡) from 
energy profile data for Energy Decomposition Analysis.

The barrier is calculated as: TS_energy - min(Reactants_energy, preTS_energy)
Delta-delta contributions show how each EDA component affects the barrier relative
to the uncatalyzed reaction.

Example:
    delta_delta_data = extract_delta_delta_contributions(profiles_data, catalyst_order)
"""
import logging
from typing import Dict, List, Any, Optional

from PyA3EDA.core.constants import Constants


def _convert_to_energy_dict(profile_data: List[Dict[str, Any]], energy_type: str, unit: str) -> Dict[str, float]:
    """
    Convert profile data list to energy dictionary format for barrier calculations.
    
    Args:
        profile_data: List of stage dictionaries with Stage, Calc_Type, and energy columns
        energy_type: Either "E" or "G"
        unit: Energy unit string
        
    Returns:
        Dictionary mapping stage keys to energy values
    """
    energy_column = f"{energy_type} ({unit})"
    energy_dict = {}
    
    for stage in profile_data:
        stage_name = stage.get("Stage", "")
        calc_type = stage.get("Calc_Type")
        energy = stage.get(energy_column)
        
        if energy is None:
            continue
            
        # Build key based on stage and calc_type
        if calc_type and calc_type not in [None, "", "unknown"]:
            key = f"{stage_name}_{calc_type}"
        else:
            key = stage_name
            
        energy_dict[key] = energy
    
    return energy_dict


def _calculate_barrier(energy_dict: Dict[str, float], calc_type: Optional[str] = None) -> Optional[float]:
    """
    Calculate barrier by subtracting min(Reactants, preTS) energy from TS energy.
    
    For uncatalyzed: barrier = TS - Reactants
    For catalyzed (frz/pol/full): barrier = TS_{type} - min(Reactants, preTS_{type})
    
    Args:
        energy_dict: Dictionary mapping stage keys to energy values
        calc_type: None for uncatalyzed, or "frz_cat", "pol_cat", "full_cat"
        
    Returns:
        Barrier height in kcal/mol, or None if required keys are missing
    """
    # Find reactant energy
    reactant_energy = None
    for key in ["Reactants", "Reactant"]:
        if key in energy_dict:
            reactant_energy = energy_dict[key]
            break
    
    if reactant_energy is None:
        return None
    
    if calc_type is None or calc_type == "":
        # Uncatalyzed barrier: TS - Reactants
        ts_key = "TS"
        if ts_key not in energy_dict:
            return None
        return energy_dict[ts_key] - reactant_energy
    else:
        # Catalyzed barrier: TS_{type} - min(Reactants, preTS_{type})
        ts_key = f"TS_{calc_type}"
        preTSkey = f"preTS_{calc_type}"
        
        if ts_key not in energy_dict:
            return None
            
        # Use preTS if available, otherwise just use Reactants
        if preTSkey in energy_dict:
            baseline = min(reactant_energy, energy_dict[preTSkey])
        else:
            baseline = reactant_energy
            
        return energy_dict[ts_key] - baseline


def _calculate_delta_delta_contributions(
    barriers: Dict[str, Optional[float]]
) -> Optional[Dict[str, float]]:
    """
    Calculate ΔΔG‡ contributions from barriers.
    
    ΔΔG‡(frz) = frz_barrier - uncat_barrier
    ΔΔG‡(pol) = pol_barrier - frz_barrier  
    ΔΔG‡(ct) = full_barrier - pol_barrier
    ΔΔG‡(complete) = full_barrier - uncat_barrier
    
    If some barriers are missing, calculates what's possible and uses None for unavailable.
    
    Args:
        barriers: Dict with keys "uncat", "frz", "pol", "full" and barrier values
        
    Returns:
        Dict with keys "frz", "pol", "ct", "complete" and contribution values,
        or None if uncatalyzed barrier is missing (minimum requirement)
    """
    uncat = barriers.get("uncat")
    frz = barriers.get("frz")
    pol = barriers.get("pol")
    full = barriers.get("full")
    
    # Need at least uncatalyzed barrier as reference
    if uncat is None:
        return None
    
    # Need at least one catalyzed barrier to have meaningful data
    if frz is None and pol is None and full is None:
        return None
    
    contributions = {}
    
    # ΔΔG‡(frz) = frz_barrier - uncat_barrier
    if frz is not None:
        contributions["frz"] = frz - uncat
    else:
        contributions["frz"] = None
        
    # ΔΔG‡(pol) = pol_barrier - frz_barrier
    if pol is not None and frz is not None:
        contributions["pol"] = pol - frz
    else:
        contributions["pol"] = None
        
    # ΔΔG‡(ct) = full_barrier - pol_barrier
    if full is not None and pol is not None:
        contributions["ct"] = full - pol
    else:
        contributions["ct"] = None
        
    # ΔΔG‡(complete) = full_barrier - uncat_barrier (or highest available - uncat)
    if full is not None:
        contributions["complete"] = full - uncat
    else:
        contributions["complete"] = None
    
    return contributions


def extract_catalyst_delta_delta(
    catalyst_profiles: Dict[str, Dict[str, List[Dict[str, Any]]]],
    energy_type: str,
    catalyst_order: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Extract delta-delta contributions for all catalysts from profile data.
    
    Args:
        catalyst_profiles: Dict mapping catalyst names to profile data (with "E" and "G" keys)
        energy_type: "E" or "G"
        catalyst_order: List of catalyst names in desired order
        
    Returns:
        Dict mapping catalyst names to their data containing:
        - "barriers": dict with uncat, frz, pol, full barrier values
        - "contributions": dict with frz, pol, ct, complete contribution values
    """
    results = {}
    
    for catalyst in catalyst_order:
        if catalyst not in catalyst_profiles:
            logging.debug(f"Catalyst {catalyst} not found in profiles - skipping")
            continue
        
        # Get unit from catalyst data (set at extraction time)
        unit = catalyst_profiles[catalyst].get("unit", Constants.ENERGY_UNIT)
        
        profile_data = catalyst_profiles[catalyst].get(energy_type, [])
        if not profile_data:
            logging.debug(f"No {energy_type} profile data for catalyst {catalyst}")
            continue
            
        # Convert to energy dict
        energy_dict = _convert_to_energy_dict(profile_data, energy_type, unit)
        if not energy_dict:
            continue
            
        # Calculate all barriers
        barriers = {
            "uncat": _calculate_barrier(energy_dict, None),
            "frz": _calculate_barrier(energy_dict, "frz_cat"),
            "pol": _calculate_barrier(energy_dict, "pol_cat"),
            "full": _calculate_barrier(energy_dict, "full_cat")
        }
        
        # Calculate contributions
        contributions = _calculate_delta_delta_contributions(barriers)
        
        if contributions:
            results[catalyst] = {
                "barriers": barriers,
                "contributions": contributions,
                "unit": unit
            }
            logging.debug(f"Catalyst {catalyst} contributions: {contributions}")
            
    return results


def extract_all_delta_delta(
    processed_data: Dict[str, Dict[str, Any]],
    catalyst_order: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Extract delta-delta contributions for all method combos and energy types.
    
    Args:
        processed_data: Dictionary with processed data including profiles
        catalyst_order: List of catalyst names in desired order from config
        
    Returns:
        Dictionary with structure:
        {
            "method_combo_name": {
                "opt_data": {
                    "E": {catalyst: {"barriers": {...}, "contributions": {...}}, ...},
                    "G": {catalyst: {"barriers": {...}, "contributions": {...}}, ...}
                },
                "sp_data": {...}
            }
        }
    """
    if not processed_data:
        logging.warning("No processed data provided for delta-delta extraction")
        return {}
    
    if not catalyst_order:
        logging.warning("No catalyst order provided - cannot extract delta-delta")
        return {}
    
    all_delta_delta = {}
    
    for combo_name, combo_data in processed_data.items():
        profiles_data = combo_data.get("profiles", {})
        if not profiles_data:
            continue
            
        combo_delta_delta = {}
        
        # Process each data type (opt/sp)
        for data_key in ["opt_data", "sp_data"]:
            catalyst_profiles = profiles_data.get(data_key, {})
            if not catalyst_profiles:
                continue
            
            data_delta_delta = {}
            
            # Process each energy type (E and G)
            for energy_type in ["E", "G"]:
                delta_delta = extract_catalyst_delta_delta(
                    catalyst_profiles,
                    energy_type,
                    catalyst_order
                )
                if delta_delta:
                    data_delta_delta[energy_type] = delta_delta
            
            if data_delta_delta:
                combo_delta_delta[data_key] = data_delta_delta
        
        if combo_delta_delta:
            all_delta_delta[combo_name] = combo_delta_delta
    
    return all_delta_delta
