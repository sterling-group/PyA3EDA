"""Delta-delta barplot — grouped ΔΔ‡ contribution charts as SVG."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("SVG")
import matplotlib.colors as mc
import matplotlib.pyplot as plt

from pya3eda.ids import DeltaDeltaData, ProfileID, StageData
from pya3eda.registry import CalcRegistry

log = logging.getLogger(__name__)

# Colours keyed by contribution type
_BASE_COLORS: dict[str, str] = {
    "ni": "darkorange",
    "frz": "firebrick",
    "pol": "forestgreen",
    "ct": "royalblue",
    "complete": "black",
}

_CONTRIBUTION_TYPES = ["frz", "pol", "ct", "complete"]
_DISPLAY_LABELS = ["FRZ", "POL", "CT", "FULL"]

_NI_CONTRIBUTION_TYPES = ["ni", "frz", "pol", "ct", "complete"]
_NI_DISPLAY_LABELS = ["CONF", "FRZ", "POL", "CT", "FULL"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plot_delta_delta_barplots(
    delta_delta: list[DeltaDeltaData],
    registry: CalcRegistry,
    base_dir: Path,
) -> None:
    """Generate barplots for every method_key x energy_type."""
    catalyst_order = registry.catalyst_order
    if not catalyst_order:
        return

    total = 0
    for mk in registry.method_keys:
        mk_data = [dd for dd in delta_delta if dd.method_key == mk]
        if not mk_data:
            continue
        plots_dir = base_dir / "results" / mk / "plots"

        # Discover (mode, sp_subfolder) pairs from actual data
        mode_sps = sorted({(dd.mode, dd.sp_subfolder) for dd in mk_data})

        for mode, sp_sub in mode_sps:
            subset = [dd for dd in mk_data if dd.mode == mode and dd.sp_subfolder == sp_sub]

            for etype in sorted({dd.energy_type for dd in subset}):
                et_data = [dd for dd in subset if dd.energy_type == etype]

                ordered_cats = [
                    cat for cat in catalyst_order if any(dd.catalyst == cat for dd in et_data)
                ]
                if not ordered_cats:
                    continue

                cats_str = "_".join(ordered_cats)
                mlabel = ProfileID.method_label(mk, sp_sub)
                fname = f"{mode}_delta_delta_barplot_{etype}_{cats_str}_{mlabel}.svg"
                _plot_single(et_data, ordered_cats, etype, plots_dir / fname)
                total += 1

    log.info("Generated %d barplots", total)


# ---------------------------------------------------------------------------
# Single barplot
# ---------------------------------------------------------------------------


def _plot_single(
    data: list[DeltaDeltaData],
    ordered_cats: list[str],
    energy_type: str,
    output_path: Path,
) -> None:
    """Render and save a single grouped ΔΔ‡ barplot."""
    cat_lookup = {dd.catalyst: dd for dd in data}
    unit = StageData.UNIT

    ctypes = _NI_CONTRIBUTION_TYPES if energy_type == "G_ni" else _CONTRIBUTION_TYPES
    labels = _NI_DISPLAY_LABELS if energy_type == "G_ni" else _DISPLAY_LABELS

    n_groups = len(ctypes)
    n_cats = len(ordered_cats)

    values = np.zeros((n_groups, n_cats))
    has_val = np.zeros((n_groups, n_cats), dtype=bool)

    for i, cat in enumerate(ordered_cats):
        dd = cat_lookup.get(cat)
        if dd is None:
            continue
        for j, ctype in enumerate(ctypes):
            v = getattr(dd, f"dd_{ctype}", None)
            if v is not None:
                values[j, i] = v
                has_val[j, i] = True

    lightness = _catalyst_lightness(n_cats)

    bar_width = 0.15
    gap = 0.1
    group_w = n_cats * bar_width
    group_spacing = group_w + gap
    group_pos = np.arange(n_groups) * group_spacing

    fig_width = 4 + n_cats * 1.5
    fig, ax = plt.subplots(figsize=(fig_width, 6))

    # Compute dynamic annotation fontsize based on bar width in figure space
    x_range = n_groups * group_spacing + gap  # approximate data x-span
    bar_width_inches = (fig_width / x_range) * bar_width if x_range > 0 else 0.5
    bar_width_pts = bar_width_inches * 72  # convert to points
    annotation_fontsize = max(6, min(16, bar_width_pts * 0.42))

    for i, cat in enumerate(ordered_cats):
        colors = [_lighten(_BASE_COLORS[ct], lightness[i]) for ct in ctypes]
        offset = (i - (n_cats - 1) / 2) * bar_width
        xpos = group_pos + offset
        ax.bar(xpos, values[:, i], bar_width, label=cat, color=colors)

        for j in range(n_groups):
            if not has_val[j, i]:
                continue
            h = values[j, i]
            va = "bottom" if h >= 0 else "top"
            y_off = 3 if h >= 0 else -3
            ax.annotate(
                f"{h:.1f}",
                xy=(xpos[j], h),
                xytext=(0, y_off),
                textcoords="offset points",
                ha="center",
                va=va,
                fontsize=annotation_fontsize,
            )

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(bottom=False, left=False, top=False, labelbottom=False, labeltop=True)
    ax.set_xticks(group_pos)

    labels_obj = ax.set_xticklabels(labels, fontsize=24, fontweight="bold")
    color_list = [_BASE_COLORS[ct] for ct in ctypes]
    for lbl, clr in zip(labels_obj, color_list, strict=True):
        lbl.set_color(clr)

    ax.set_yticks([])

    xmin, xmax = ax.get_xlim()
    ymin_ax, ymax_ax = ax.get_ylim()
    ax.annotate(
        "",
        xy=(xmax, 0),
        xytext=(xmin, 0),
        arrowprops=dict(arrowstyle="->", color="k", lw=2.5),
        clip_on=False,
    )
    ax.annotate(
        "",
        xy=(xmin, ymax_ax),
        xytext=(xmin, ymin_ax),
        arrowprops=dict(arrowstyle="->", color="k", lw=2.5),
        clip_on=False,
    )

    display_e = "G" if energy_type.startswith("G") else energy_type
    ax.set_ylabel(
        rf"$\boldsymbol{{\Delta\Delta}}\boldsymbol{{{display_e}}}^{{\boldsymbol{{\ddagger}}}}\;\mathbf{{({unit})}}$",
        fontsize=20,
    )

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, format="svg", transparent=False)
    log.info("Saved barplot: %s", output_path)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------


def _lighten(color: str, amount: float) -> tuple[float, float, float]:
    """Lighten *color* by mixing towards white by *amount* (0-1)."""
    try:
        c = mc.cnames[color]
    except KeyError:
        c = color
    rgb = np.array(mc.to_rgb(c))
    return tuple((1 - amount) * rgb + amount * np.array([1.0, 1.0, 1.0]))


def _catalyst_lightness(n: int) -> list[float]:
    """Return lightness offsets for *n* catalysts (0.0 to 0.4)."""
    if n == 1:
        return [0.0]
    return [i * 0.4 / (n - 1) for i in range(n)]
