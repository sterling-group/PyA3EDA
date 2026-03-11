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
        energy_type: "E", "G", or "G_no_trans"
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


def _calculate_barrier(energy_dict: Dict[str, float], calc_type: Optional[str] = None,
                       baseline_choices: Dict[str, str] = None) -> Optional[float]:
    """
    Calculate barrier by subtracting min(Reactants, preTS) energy from TS energy.
    
    For uncatalyzed: barrier = TS - Reactants
    For catalyzed (frz/pol/full): barrier = TS_{type} - min(Reactants, preTS_{type})
    
    Args:
        energy_dict: Dictionary mapping stage keys to energy values
        calc_type: None for uncatalyzed, or "frz_cat", "pol_cat", "full_cat"
        baseline_choices: Optional dict mapping calc_type to the baseline key chosen
            by another energy surface (e.g. G). When provided, the same baseline stage
            is used instead of re-evaluating min() on this surface's values.
        
    Returns:
        Tuple-like: barrier height in kcal/mol, or None if required keys are missing.
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

        # If baseline_choices provided, use the same baseline stage as the reference surface
        if baseline_choices and calc_type in baseline_choices:
            chosen_key = baseline_choices[calc_type]
            if chosen_key in energy_dict:
                baseline = energy_dict[chosen_key]
            else:
                baseline = reactant_energy
        else:
            # Default: pick min(Reactants, preTS) on this surface
            if preTSkey in energy_dict and energy_dict[preTSkey] < reactant_energy:
                baseline = energy_dict[preTSkey]
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


def _determine_baseline_choices(energy_dict: Dict[str, float]) -> Dict[str, str]:
    """
    Determine which baseline stage (Reactants vs preTS) is chosen for each calc_type.
    
    The decision is driven by the full_cat preTS: if preTS_full_cat is lower than
    Reactants, then ALL calc_types (frz, pol, full) use their respective preTS as
    baseline. This keeps the decomposition chain consistent so that the delta-delta
    subtractions (frz-uncat, pol-frz, full-pol) all use the same baseline type.
    
    Returns:
        Dict mapping calc_type to the key of the chosen baseline stage.
    """
    reactant_energy = None
    reactant_key = None
    for key in ["Reactants", "Reactant"]:
        if key in energy_dict:
            reactant_energy = energy_dict[key]
            reactant_key = key
            break

    if reactant_energy is None:
        return {}

    # Decision driven by full_cat preTS
    full_preTSkey = "preTS_full_cat"
    use_preTS = (full_preTSkey in energy_dict and energy_dict[full_preTSkey] < reactant_energy)

    choices = {}
    for calc_type in ["frz_cat", "pol_cat", "full_cat"]:
        preTSkey = f"preTS_{calc_type}"
        if use_preTS and preTSkey in energy_dict:
            choices[calc_type] = preTSkey
        else:
            choices[calc_type] = reactant_key
    return choices


def _calculate_barriers_and_contributions(
    profile_data: List[Dict[str, Any]], 
    energy_type: str, 
    unit: str,
    baseline_choices: Dict[str, str] = None
) -> Optional[Dict[str, Any]]:
    """
    Calculate barriers and contributions for a single energy type.
    
    Args:
        profile_data: Profile data list with stage energies
        energy_type: "E", "G", or "G_no_trans"
        unit: Energy unit string
        baseline_choices: Optional dict mapping calc_type to baseline key.
            Used by G_no_trans to reuse G's baseline choices.
        
    Returns:
        Dict with barriers, contributions, and baseline_choices
    """
    energy_dict = _convert_to_energy_dict(profile_data, energy_type, unit)
    if not energy_dict:
        return None

    # Determine baseline choices on this surface (used for E/G)
    # or use provided ones (for G_no_trans reusing G's choices)
    if baseline_choices is None:
        baseline_choices = _determine_baseline_choices(energy_dict)

    barriers = {
        "uncat": _calculate_barrier(energy_dict, None, baseline_choices),
        "frz": _calculate_barrier(energy_dict, "frz_cat", baseline_choices),
        "pol": _calculate_barrier(energy_dict, "pol_cat", baseline_choices),
        "full": _calculate_barrier(energy_dict, "full_cat", baseline_choices)
    }
    
    contributions = _calculate_delta_delta_contributions(barriers)
    if not contributions:
        return None
        
    return {"barriers": barriers, "contributions": contributions, "baseline_choices": baseline_choices}


def extract_catalyst_delta_delta(
    catalyst_profiles: Dict[str, Dict[str, List[Dict[str, Any]]]],
    energy_type: str,
    catalyst_order: List[str],
    g_baseline_choices: Dict[str, Dict[str, str]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Extract delta-delta contributions for all catalysts from profile data.
    
    Args:
        catalyst_profiles: Dict mapping catalyst names to profile data (with "E" and "G" keys)
        energy_type: "E", "G", or "G_no_trans"
        catalyst_order: List of catalyst names in desired order
        g_baseline_choices: For G_no_trans only: dict mapping catalyst name to baseline
            choices determined by G, so G_no_trans uses the same reference stages.
        
    Returns:
        Dict mapping catalyst names to their data containing:
        - "barriers": dict with uncat, frz, pol, full barrier values
        - "contributions": dict with frz, pol, ct, complete contribution values
        - "unit": energy unit string
    """
    results = {}
    
    for catalyst in catalyst_order:
        if catalyst not in catalyst_profiles:
            logging.debug(f"Catalyst {catalyst} not found in profiles - skipping")
            continue
        
        unit = catalyst_profiles[catalyst].get("unit", Constants.ENERGY_UNIT)
        profile_data = catalyst_profiles[catalyst].get("G" if energy_type == "G_no_trans" else energy_type, [])
        
        if not profile_data:
            logging.debug(f"No {energy_type} profile data for catalyst {catalyst}")
            continue
        
        # For G_no_trans, reuse baseline choices from G so both surfaces use the same reference
        baseline = None
        if energy_type == "G_no_trans" and g_baseline_choices and catalyst in g_baseline_choices:
            baseline = g_baseline_choices[catalyst]
        
        result = _calculate_barriers_and_contributions(profile_data, energy_type, unit, baseline)
        if result:
            result["unit"] = unit
            results[catalyst] = result
            logging.debug(f"Catalyst {catalyst} {energy_type} contributions: {result['contributions']}")
            
    return results


def extract_trans_contributions(
    g_data: Dict[str, Dict[str, Any]],
    g_no_trans_data: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, float]]:
    """
    Calculate translational entropy contributions per EDA term.
    
    trans_bar = contribution(G) - contribution(G_no_trans)
    
    Args:
        g_data: Delta-delta data for full G
        g_no_trans_data: Delta-delta data for G_no_trans
        
    Returns:
        Dict mapping catalyst to trans contributions {trans_frz, trans_pol, trans_ct, trans_complete}
    """
    trans_contributions = {}
    
    for catalyst in g_data:
        if catalyst not in g_no_trans_data:
            continue
            
        g_contrib = g_data[catalyst].get("contributions", {})
        no_trans_contrib = g_no_trans_data[catalyst].get("contributions", {})
        
        trans = {}
        for bar_type in ["frz", "pol", "ct", "complete"]:
            g_val = g_contrib.get(bar_type)
            no_trans_val = no_trans_contrib.get(bar_type)
            if g_val is not None and no_trans_val is not None:
                trans[f"trans_{bar_type}"] = g_val - no_trans_val
        
        if trans:
            trans_contributions[catalyst] = trans
            
    return trans_contributions


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
            
            # Extract E contributions
            e_data = extract_catalyst_delta_delta(catalyst_profiles, "E", catalyst_order)
            if e_data:
                data_delta_delta["E"] = e_data
            
            # Extract G contributions (full G with all entropy)
            g_data = extract_catalyst_delta_delta(catalyst_profiles, "G", catalyst_order)
            if g_data:
                data_delta_delta["G"] = g_data
            
            # Extract G_no_trans contributions using G's baseline choices
            # so both surfaces measure barriers from the same reference stage
            g_baselines = {cat: cat_data["baseline_choices"] 
                          for cat, cat_data in g_data.items() 
                          if "baseline_choices" in cat_data} if g_data else {}
            g_no_trans_data = extract_catalyst_delta_delta(
                catalyst_profiles, "G_no_trans", catalyst_order, g_baselines)
            if g_no_trans_data:
                data_delta_delta["G_no_trans"] = g_no_trans_data
                
                # Calculate trans contributions (G - G_no_trans per bar)
                if g_data:
                    trans_data = extract_trans_contributions(g_data, g_no_trans_data)
                    if trans_data:
                        data_delta_delta["G_trans"] = trans_data
            
            if data_delta_delta:
                combo_delta_delta[data_key] = data_delta_delta
        
        if combo_delta_delta:
            all_delta_delta[combo_name] = combo_delta_delta
    
    return all_delta_delta
