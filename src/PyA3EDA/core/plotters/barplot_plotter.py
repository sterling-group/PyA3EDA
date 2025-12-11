"""
Delta-Delta Barplot Plotter for Energy Decomposition Analysis.

Generates matplotlib barplots showing ΔΔG‡ contributions
(frozen, polarization, charge transfer) from pre-extracted delta-delta data.

Example:
    plot_delta_delta_barplots(delta_delta_data, base_dir, catalyst_order)
"""
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
import numpy as np
import matplotlib
matplotlib.use('SVG')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.colors as mc


# Base colors for contribution types (keys match extractor output)
BASE_COLORS = {
    "frz": "firebrick",
    "pol": "forestgreen",
    "ct": "royalblue",
    "complete": "black"
}

# Contribution types to plot (lowercase for data lookup)
CONTRIBUTION_TYPES = ["frz", "pol", "ct", "complete"]

# Display labels (uppercase for plot)
DISPLAY_LABELS = ["FRZ", "POL", "CT", "FULL"]


def _lighten_color(color: str, amount: float = 0.0) -> Tuple[float, float, float]:
    """
    Lighten a color by mixing with white. Returns pure RGB (no alpha).
    
    Args:
        color: Color name or hex code
        amount: 0.0 = original color, 1.0 = white
        
    Returns:
        RGB tuple (values 0-1)
    """
    try:
        c = mc.cnames[color]
    except KeyError:
        c = color
    rgb = np.array(mc.to_rgb(c))
    # Linear interpolation toward white
    lightened = (1 - amount) * rgb + amount * np.array([1.0, 1.0, 1.0])
    return tuple(lightened)


def _get_catalyst_colors(n_catalysts: int) -> List[float]:
    """
    Generate lightness amounts for each catalyst.
    First catalyst gets full color, subsequent ones get progressively lighter.
    
    Args:
        n_catalysts: Number of catalysts
        
    Returns:
        List of lightness amounts (0.0 to ~0.5)
    """
    if n_catalysts == 1:
        return [0.0]
    # Spread from 0.0 to 0.4 (don't go too light)
    return [i * 0.4 / (n_catalysts - 1) for i in range(n_catalysts)]


def _plot_single_barplot(
    delta_delta_data: Dict[str, Dict[str, Any]],
    catalyst_order: List[str],
    energy_type: str,
    output_path: Path
) -> None:
    """
    Generate and save a single delta-delta barplot with color variants per catalyst.
    
    Args:
        delta_delta_data: Dict mapping catalyst names to their data with "contributions" key
        catalyst_order: List of catalyst names in desired plot order
        energy_type: "E" or "G" for axis labeling
        output_path: Full path where to save the plot
    """
    # Filter to catalysts that have data, preserving order
    ordered_cats = [cat for cat in catalyst_order if cat in delta_delta_data]
    
    if not ordered_cats:
        logging.warning("No catalysts with contribution data - skipping barplot")
        return
    
    # Extract unit from first catalyst's data (all should have same unit)
    unit = delta_delta_data[ordered_cats[0]].get("unit", "kcal/mol")
    
    n_groups = len(CONTRIBUTION_TYPES)
    n_cats = len(ordered_cats)
    
    # Build data array [n_groups, n_cats] - None values become 0.0
    data = np.zeros((n_groups, n_cats))
    has_value = np.zeros((n_groups, n_cats), dtype=bool)  # Track which have real values
    for j, ctype in enumerate(CONTRIBUTION_TYPES):
        for i, cat in enumerate(ordered_cats):
            contributions = delta_delta_data[cat].get("contributions", {})
            val = contributions.get(ctype)
            if val is not None:
                data[j, i] = val
                has_value[j, i] = True
    
    # Get lightness amounts for each catalyst
    lightness_amounts = _get_catalyst_colors(n_cats)
    
    # Plot setup - fixed bar width and gap, figure adapts to n_cats
    bar_width = 0.15  # Fixed width per bar
    gap_between_groups = 0.1  # Fixed gap between groups
    group_width = n_cats * bar_width  # Total width of bars in one group
    group_spacing = group_width + gap_between_groups  # Center-to-center distance
    group_positions = np.arange(n_groups) * group_spacing
    
    # Figure width scales with number of catalysts
    fig_width = 4 + n_cats * 1.5  # Base width + extra per catalyst
    fig, ax = plt.subplots(figsize=(fig_width, 6))
    
    # Plot bars for each catalyst with progressively lighter colors
    for i, cat in enumerate(ordered_cats):
        lightness = lightness_amounts[i]
        colors = [_lighten_color(BASE_COLORS[ctype], lightness) for ctype in CONTRIBUTION_TYPES]
        offset = (i - (n_cats - 1) / 2) * bar_width
        x_positions = group_positions + offset
        ax.bar(x_positions, data[:, i], bar_width, label=cat, color=colors)
        
        # Annotate bars (only if value exists, not None)
        for j in range(n_groups):
            if not has_value[j, i]:
                continue  # Skip annotation for missing data
            height = data[j, i]
            if height >= 0:
                va = 'bottom'
                offset_text = 3
            else:
                va = 'top'
                offset_text = -3
            ax.annotate(f"{height:.1f}",
                        xy=(x_positions[j], height),
                        xytext=(0, offset_text),
                        textcoords="offset points",
                        ha="center", va=va, fontsize=16)
    
    # Style axes
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(bottom=False, left=False, top=False, labelbottom=False, labeltop=True)
    ax.set_xticks(group_positions)
    
    # Set xticklabels with matching colors (use display labels)
    xticklabels = ax.set_xticklabels(DISPLAY_LABELS, fontsize=24, fontweight="bold")
    base_color_list = [BASE_COLORS[ctype] for ctype in CONTRIBUTION_TYPES]
    for label, color in zip(xticklabels, base_color_list):
        label.set_color(color)
    
    ax.set_yticks([])
    
    # Add arrowed axes
    xmin, xmax = ax.get_xlim()
    ymin_ax, ymax_ax = ax.get_ylim()
    ax.annotate("", xy=(xmax, 0), xytext=(xmin, 0),
                arrowprops=dict(arrowstyle="->", color="k", lw=2.5),
                clip_on=False)
    ax.annotate("", xy=(xmin, ymax_ax), xytext=(xmin, ymin_ax),
                arrowprops=dict(arrowstyle="->", color="k", lw=2.5),
                clip_on=False)
    
    # Labels
    ax.set_ylabel(rf"$\Delta\Delta {energy_type}^\ddagger$ ({unit})", fontsize=20, fontweight="bold")
    
    # Legend for catalysts (using gray shades matching their lightness)
    if n_cats > 1:
        from matplotlib.patches import Patch
        legend_colors = [_lighten_color("gray", lightness_amounts[i]) for i in range(n_cats)]
        legend_handles = [Patch(facecolor=legend_colors[i], edgecolor='black', label=cat) 
                          for i, cat in enumerate(ordered_cats)]
        # ax.legend(handles=legend_handles, loc='best', fontsize=10)
    
    plt.tight_layout()
    
    # Save plot - true vector PDF (no transparency)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, format="svg", transparent=True)
    logging.info(f"Saved delta-delta barplot: {output_path}")
    plt.close(fig)


def plot_delta_delta_barplots(
    delta_delta_data: Dict[str, Dict[str, Any]], 
    base_dir: Path,
    catalyst_order: List[str]
) -> None:
    """
    Generate delta-delta barplots for all method combinations and energy types.
    
    Creates one barplot per method combo per energy type, with all catalysts
    grouped together. Output naming: delta_delta_barplot_{method_combo}_{E|G}.pdf
    
    Args:
        delta_delta_data: Dictionary with pre-extracted delta-delta data for all combos
                         Structure: {combo_name: {data_key: {energy_type: {catalyst: data}}}}
        base_dir: Base directory where results are stored
        catalyst_order: List of catalyst names in desired order from config
        
    Creates plots in: base_dir/results/{method_combo}/plots/
    """
    if not delta_delta_data:
        logging.warning("No delta-delta data provided for barplot generation")
        return
    
    if not catalyst_order:
        logging.warning("No catalyst order provided - cannot generate barplots")
        return
    
    total_plots = 0
    
    for combo_name, combo_data in delta_delta_data.items():
        plots_dir = base_dir / "results" / combo_name / "plots"
        
        for data_key in ["opt_data", "sp_data"]:
            energy_type_data = combo_data.get(data_key, {})
            if not energy_type_data:
                continue
            
            calc_mode = "opt" if data_key == "opt_data" else "sp"
            
            for energy_type in ["E", "G"]:
                catalyst_data = energy_type_data.get(energy_type, {})
                if not catalyst_data:
                    continue
                
                try:
                    # Get catalysts that have data, in order
                    plotted_cats = [cat for cat in catalyst_order if cat in catalyst_data]
                    if not plotted_cats:
                        continue
                    
                    # Generate filename with catalyst names
                    cats_str = "_".join(plotted_cats)
                    plot_filename = f"delta_delta_barplot_{calc_mode}_{combo_name}_{cats_str}_{energy_type}.svg"
                    
                    plot_path = plots_dir / plot_filename
                    
                    # Generate and save plot
                    _plot_single_barplot(catalyst_data, catalyst_order, energy_type, plot_path)
                    total_plots += 1
                    
                except Exception as e:
                    logging.error(f"Failed to generate barplot for {combo_name} {energy_type}: {e}")
                    continue
    
    logging.info(f"Barplot generation completed: {total_plots} plots created")
