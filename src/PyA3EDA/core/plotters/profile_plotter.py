"""
Energy Profile Plotter for Quantum Chemistry Calculations.

Functional approach for generating matplotlib plots from processed energy profile data.
Adapted from standalone plotting script to work directly with processed data structures.

Example:
     plot_all_profiles(processed_data, base_dir)
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import matplotlib
matplotlib.use('SVG')  # Non-interactive backend
import matplotlib.pyplot as plt

from PyA3EDA.core.constants import Constants


def _convert_to_energy_dict(profile_data: List[Dict[str, Any]], energy_type: str, unit: str) -> Dict[str, float]:
    """
    Convert profile data list to energy dictionary format expected by plotting functions.
    
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


def _normalize_energies(energy_dict: Dict[str, float]) -> Dict[str, float]:
    """
    Normalize energies relative to reactants (sets reactants to 0).
    
    Args:
        energy_dict: Dictionary mapping stage keys to absolute energies
        
    Returns:
        Dictionary with normalized energies
    """
    # Find reactant energy
    reactant_key = None
    for key in ["Reactants", "Reactant"]:
        if key in energy_dict:
            reactant_key = key
            break
            
    if reactant_key is None:
        logging.warning("No reactant stage found for normalization")
        return energy_dict
        
    reactant_energy = energy_dict[reactant_key]
    
    # Normalize all energies
    normalized = {}
    for key, energy in energy_dict.items():
        normalized[key] = energy - reactant_energy
        
    return normalized


def _define_profiles(energy_dict: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Build the 4 standard profiles (FRZ, POL, FULL, uncatalyzed) from energy dictionary.
    
    Args:
        energy_dict: Dictionary mapping stage keys to normalized energies
        
    Returns:
        List of profile definitions for plotting
    """
    # Determine reactant and product keys
    reactant_key = "Reactants" if "Reactants" in energy_dict else "Reactant"
    product_key = "Products" if "Products" in energy_dict else "Product"
    
    if reactant_key not in energy_dict:
        raise KeyError(f"Reactant stage not found. Available keys: {list(energy_dict.keys())}")
    if product_key not in energy_dict:
        raise KeyError(f"Product stage not found. Available keys: {list(energy_dict.keys())}")
    
    # Define the 4 standard profiles
    profile_frz = [
        {"label": "reactant", "key": reactant_key},
        {"label": "pre-TS",   "key": "preTS_frz_cat"},
        {"label": "TS",       "key": "TS_frz_cat"},
        {"label": "post-TS",  "key": "postTS_frz_cat"},
        {"label": "product",  "key": product_key},
    ]
    
    profile_pol = [
        {"label": "reactant", "key": reactant_key},
        {"label": "pre-TS",   "key": "preTS_pol_cat"},
        {"label": "TS",       "key": "TS_pol_cat"},
        {"label": "post-TS",  "key": "postTS_pol_cat"},
        {"label": "product",  "key": product_key},
    ]
    
    profile_full = [
        {"label": "reactant", "key": reactant_key},
        {"label": "pre-TS",   "key": "preTS_full_cat"},
        {"label": "TS",       "key": "TS_full_cat"},
        {"label": "post-TS",  "key": "postTS_full_cat"},
        {"label": "product",  "key": product_key},
    ]
    
    profile_uncat = [
        {"label": "reactant", "key": reactant_key},
        {"label": "TS",       "key": "TS"},
        {"label": "product",  "key": product_key},
    ]
    
    profiles = [
        {"name": "FRZ",         "profile": profile_frz,   "color": "firebrick",   "annotate_rp": False},
        {"name": "POL",         "profile": profile_pol,   "color": "forestgreen", "annotate_rp": False},
        {"name": "FULL",        "profile": profile_full,  "color": "royalblue",   "annotate_rp": False},
        {"name": "uncatalyzed", "profile": profile_uncat, "color": "black",       "annotate_rp": True},
    ]
    
    # Filter out profiles where required stages are missing
    valid_profiles = []
    for prof in profiles:
        missing_keys = [stage["key"] for stage in prof["profile"] if stage["key"] not in energy_dict]
        if not missing_keys:
            valid_profiles.append(prof)
        else:
            logging.info(f"Skipping {prof['name']} profile - missing stages: {missing_keys}")
    
    # If no profiles are valid, log available keys for debugging
    if not valid_profiles:
        logging.info(f"No complete profiles can be plotted. Available energy keys: {sorted(energy_dict.keys())}")
    
    return valid_profiles


def _plot_single_profile(ax, profile: List[Dict[str, str]], energy_dict: Dict[str, float], color: str, annotate_rp: bool):
    """
    Plot a single energy profile on the given axes.
    
    Args:
        ax: Matplotlib axes object
        profile: List of stage dictionaries with 'label' and 'key'
        energy_dict: Dictionary mapping keys to energies
        color: Color for this profile
        annotate_rp: Whether to annotate reactant/product energies
    """
    bar_linewidth = 4
    dash_linewidth = 2
    
    n_stages = len(profile)
    if n_stages == 5:
        x_starts = [0, 2, 4, 6, 8]
    elif n_stages == 3:
        x_starts = [0, 4, 8]
    else:
        raise ValueError("Profile must have either 3 or 5 stages.")

    bar_width = 0.5
    x_centers = [x + bar_width/2 for x in x_starts]

    # Get energies for this profile
    energies = [energy_dict[stage['key']] for stage in profile]

    # Annotation offsets by (color, stage_label) for fine-grained control
    # Format: (color, stage_label): (va, y_offset, x_offset)
    # Default offsets by color
    DEFAULT_OFFSETS = {
        'firebrick':    ('bottom', 0.1, 0.0),
        'black':        ('bottom', 0.1, 0.0),
        'forestgreen':  ('top', -0.5, 0.0),
        'royalblue':    ('top', -0.5, 0.0),
    }
    
    # Custom overrides: (color, stage_label) -> (va, y_offset, x_offset)
    # Customize these for specific stage/color combinations
    CUSTOM_OFFSETS = {
        # Example: move black TS annotation to the left
        ('black', 'TS'):        ('bottom', 0.2, -0.6),
        # Example: move green TS annotation to the right
        ('forestgreen', 'TS'):  ('bottom', -1.5, 0.6),
        ('forestgreen', 'pre-TS'):  ('bottom', -1.5, 0.6),
        ('forestgreen', 'post-TS'):  ('bottom', -1.5, -0.7),
        ('firebrick', 'post-TS'):  ('bottom', 0.1, 0.1),
        ('black', 'product'):  ('bottom', 0.1, 0.05),

    }

    # Draw horizontal bars and annotations
    for i, (x, E) in enumerate(zip(x_starts, energies)):
        stage_label = profile[i]['label']
        
        # Skip Reactant/Product bars for profiles that don't annotate them
        # (only uncatalyzed/black draws bars at these positions)
        if (stage_label.lower() in ['reactant', 'product']) and (not annotate_rp):
            continue
        
        ax.plot([x, x + bar_width], [E, E], lw=bar_linewidth, color=color, solid_capstyle='round')
        
        # Get offset: check custom first, then default
        key = (color, stage_label)
        if key in CUSTOM_OFFSETS:
            va, y_offset, x_offset = CUSTOM_OFFSETS[key]
        else:
            va, y_offset, x_offset = DEFAULT_OFFSETS.get(color, ('bottom', 0.5, 0))
        
        ax.text(x_centers[i] + x_offset, E + y_offset, f"{E:.1f}",
                color=color, weight="normal", ha="center", va=va, fontsize=24)

    # Draw dashed connections
    for i in range(len(x_starts) - 1):
        x_end = x_starts[i] + bar_width
        x_next = x_starts[i+1]
        E_current = energies[i]
        E_next = energies[i+1]
        ax.plot([x_end, x_next], [E_current, E_next],
                linestyle="--", color=color, lw=dash_linewidth, solid_capstyle='round')


def _plot_energy_profiles(energy_dict: Dict[str, float], catalyst_name: str, energy_type: str, output_path: Path, unit: str = "kcal/mol"):
    """
    Generate and save a complete energy profile plot.
    
    Args:
        energy_dict: Normalized energy dictionary
        catalyst_name: Name of catalyst for the plot
        energy_type: "E" or "G" for energy type
        output_path: Full path where to save the plot
        unit: Energy unit for axis label
    """
    profiles = _define_profiles(energy_dict)
    
    if not profiles:
        logging.warning(f"No valid profiles found for {catalyst_name} - skipping plot")
        return
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plot each profile
    for prof in profiles:
        _plot_single_profile(ax, prof["profile"], energy_dict, prof["color"], prof["annotate_rp"])
        ax.plot([], [], color=prof["color"], lw=4, label=prof["name"])

    # Configure axes
    ax.tick_params(bottom=False, left=False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlim(-1, 10)


    # Set common x-axis ticks and labels.
    xtick_positions = [0.25, 2.25, 4.25, 6.25, 8.25]
    xtick_labels = ["reactants", "pre-TS", "TS", "post-TS", "product"]
    ax.set_xticks(xtick_positions)
    ax.set_xticklabels(xtick_labels, fontsize=12, fontweight="bold")
    ax.set_xlabel("reaction coordinate", fontsize=20, fontweight="bold")
    ax.set_ylabel(rf"$\Delta$ {energy_type} ({unit})", fontsize=20, fontweight="bold")
    # ax.set_title(f"Reaction Profiles for {catalyst_name}", fontsize=14)
    # ax.legend()
    # ax.grid(True, linestyle="--", alpha=0.5)


    # Set y-limits with padding
    all_energies = []
    for prof in profiles:
        for stage in prof["profile"]:
            all_energies.append(energy_dict[stage['key']])
    
    ymin, ymax = min(all_energies), max(all_energies)
    ypad = abs(ymax - ymin) * 0.07
    ax.set_ylim(ymin - ypad - 1, ymax + ypad + 1)

    # Clean axes and add arrows
    for spine in ax.spines.values():
        spine.set_visible(False)

    xmin, xmax = ax.get_xlim()
    ymin_lim, ymax_lim = ax.get_ylim()
    
    # Add coordinate system arrows
    ax.annotate("", xy=(xmax, ymin_lim), xytext=(xmin, ymin_lim),
                arrowprops=dict(arrowstyle="->", color="k", lw=2.5), clip_on=False)
    ax.annotate("", xy=(xmin, ymax_lim), xytext=(xmin, ymin_lim),
                arrowprops=dict(arrowstyle="->", color="k", lw=2.5), clip_on=False)

    plt.tight_layout()
    
    # Save plot
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, format="svg", transparent=False, dpi=300)
    logging.info(f"Saved energy profile plot: {output_path}")
    plt.close(fig)


def plot_all_profiles(processed_data: Dict[str, Dict[str, Any]], base_dir: Path):
    """
    Generate energy profile plots for all catalysts and method combinations.
    
    Args:
        processed_data: Dictionary with processed data including profiles
        base_dir: Base directory where results are stored
        
    Creates plots in: base_dir/results/{method_combo}/plots/
    """
    if not processed_data:
        logging.warning("No processed data provided for plotting")
        return
    
    total_plots = 0
    
    for combo_name, combo_data in processed_data.items():
        try:
            profiles_data = combo_data.get("profiles", {})
            if not profiles_data:
                logging.info(f"No profiles found for {combo_name} - skipping plots")
                continue
            
            # Create plots directory
            plots_dir = base_dir / "results" / combo_name / "plots"
            
            # Process each data type (opt/sp)
            for data_key in ["opt_data", "sp_data"]:
                catalyst_profiles = profiles_data.get(data_key, {})
                if not catalyst_profiles:
                    continue
                
                # Determine calculation mode
                calc_mode = "opt" if data_key == "opt_data" else "sp"
                
                # Process each catalyst
                for catalyst, catalyst_data in catalyst_profiles.items():
                    # Get unit from data (set at extraction time)
                    unit = catalyst_data.get("unit", Constants.ENERGY_UNIT)
                    
                    # Process each energy type (E and G)
                    for energy_type in ["E", "G"]:
                        profile_data = catalyst_data.get(energy_type, [])
                        if not profile_data:
                            continue
                        
                        try:
                            # Convert to energy dictionary format
                            energy_dict = _convert_to_energy_dict(profile_data, energy_type, unit)
                            if not energy_dict:
                                continue
                            
                            # Normalize energies
                            normalized_dict = _normalize_energies(energy_dict)
                            
                            # Generate plot filename (matching CSV naming convention)
                            plot_filename = f"{calc_mode}_profile_{energy_type}_{combo_name}_{catalyst}.svg"
                            plot_path = plots_dir / plot_filename
                            
                            # Generate and save plot
                            _plot_energy_profiles(normalized_dict, catalyst, energy_type, plot_path, unit)
                            total_plots += 1
                            
                        except Exception as e:
                            logging.error(f"Failed to plot {calc_mode} {energy_type} profile for {catalyst} in {combo_name}: {e}")
                            continue
                
        except Exception as e:
            logging.error(f"Failed to process plots for method combo {combo_name}: {e}")
            continue
    
    logging.info(f"Plot generation completed: {total_plots} plots created")
