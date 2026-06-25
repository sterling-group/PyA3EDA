"""Energy profile plots — reaction coordinate SVG diagrams."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("SVG")
import matplotlib.pyplot as plt

from pya3eda.ids import ProfileData, ProfileID, StageData
from pya3eda.registry import CalcRegistry
from pya3eda.vocab import CalcType, Surface

log = logging.getLogger(__name__)

# Colours per trace label (plot-specific, keyed by ProfileID.TRACE_ORDER labels)
_TRACE_COLORS: dict[str, str] = {
    "uncat": "black",
    "NI": "darkorange",
    "FRZ": "firebrick",
    "POL": "forestgreen",
    "FULL": "royalblue",
}

# Stage x-positions for 5-stage and 3-stage profiles
_X5 = [0, 2, 4, 6, 8]
_X3 = [0, 4, 8]
_BAR_WIDTH = 0.5

# Annotation offsets: (va, y_offset, x_offset)
_DEFAULT_OFFSETS: dict[str, tuple[str, float, float]] = {
    "firebrick": ("bottom", 0.1, 0.0),
    "black": ("bottom", 0.1, 0.0),
    "forestgreen": ("top", -0.5, 0.0),
    "royalblue": ("top", -0.5, 0.0),
    "darkorange": ("bottom", 0.1, 0.0),
}

_CUSTOM_OFFSETS: dict[tuple[str, str], tuple[str, float, float]] = {
    ("black", "TS"): ("bottom", 0.2, -0.6),
    ("forestgreen", "TS"): ("bottom", -1.5, 0.6),
    ("forestgreen", "pre-TS"): ("bottom", -1.5, 0.6),
    ("forestgreen", "post-TS"): ("bottom", -1.5, -0.7),
    ("firebrick", "post-TS"): ("bottom", 0.1, 0.1),
    ("black", "product"): ("bottom", 0.1, 0.05),
}

_STAGE_LABELS = {
    "reactants": "reactant",
    "preTS": "pre-TS",
    "ts": "TS",
    "postTS": "post-TS",
    "products": "product",
}

_SKIP_ENDPOINTS = frozenset({"reactant", "product"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plot_all_profiles(
    profiles: dict[ProfileID, ProfileData],
    registry: CalcRegistry,
    base_dir: Path,
) -> None:
    """Generate profile SVGs for every catalyst x method_key."""
    total = 0

    # Derive plot groupings from registry-known profile IDs
    # (method_key, mode, sp_subfolder) → set of catalysts
    groups: dict[tuple[str, str, str | None], set[str]] = {}
    for pspec in registry.all_profiles:
        pid = pspec.id
        key = (pid.method_key, pid.mode, pid.sp_subfolder)
        groups.setdefault(key, set())
        if pid.catalyst:
            groups[key].add(pid.catalyst)

    for (mk, mode, sp_sub), catalysts in sorted(groups.items()):
        plots_dir = base_dir / "results" / mk / "plots"

        # To always include NI on the G plot (no separate G_ni),
        # change the line below to: StageData.energy_types()
        # and remove the `if calc_type == CalcType.NI and not include_ni` guard
        # in _plot_catalyst.
        for etype in StageData.barrier_surfaces():
            uncat_pid = ProfileID(
                method_key=mk,
                catalyst=None,
                calc_type=None,
                mode=mode,
                sp_subfolder=sp_sub,
            )
            uncat_data = profiles.get(uncat_pid)

            for cat in sorted(catalysts):
                plotted = _plot_catalyst(
                    profiles,
                    uncat_data,
                    mk,
                    cat,
                    mode,
                    sp_sub,
                    etype,
                    plots_dir,
                )
                if plotted:
                    total += 1

    log.info("Generated %d profile plots", total)


def _plot_catalyst(
    profiles: dict[ProfileID, ProfileData],
    uncat_data: ProfileData | None,
    method_key: str,
    catalyst: str,
    mode: str,
    sp_subfolder: str | None,
    etype: str,
    plots_dir: Path,
) -> bool:
    """Plot one catalyst's profile (all calc_types + uncatalyzed), returns True if saved."""
    unit = StageData.UNIT
    # include_ni / surface: controls whether the NI trace appears.
    # To always include NI on G, remove these two lines and
    # the `if calc_type == CalcType.NI ...` guard below; use etype directly.
    include_ni = etype == Surface.G_NI
    surface = Surface.G if include_ni else etype

    # Gather normalized traces per calc_type
    traces: list[dict[str, Any]] = []
    for calc_type, label in ProfileID.TRACE_ORDER:
        if calc_type == CalcType.NI and not include_ni:
            continue
        is_uncat = calc_type is None
        pdata = (
            uncat_data
            if is_uncat
            else profiles.get(
                ProfileID(
                    method_key=method_key,
                    catalyst=catalyst,
                    calc_type=calc_type,
                    mode=mode,
                    sp_subfolder=sp_subfolder,
                )
            )
        )
        if pdata is None:
            continue
        trace_data = _rel_trace(pdata, surface)
        if trace_data is not None:
            color = _TRACE_COLORS.get(label, "gray")
            skip = frozenset() if is_uncat else _SKIP_ENDPOINTS
            traces.append(
                {
                    "stages": trace_data,
                    "color": color,
                    "label": label,
                    "skip_stages": skip,
                }
            )

    if not traces:
        return False

    fig, ax = plt.subplots(figsize=(14, 8))

    for t in traces:
        _draw_trace(ax, t["stages"], t["color"], t["skip_stages"])
        ax.plot([], [], color=t["color"], lw=4, label=t["label"])

    _style_axes(ax, etype, unit, traces)

    plots_dir.mkdir(parents=True, exist_ok=True)
    mlabel = ProfileID.method_label(method_key, sp_subfolder)
    fname = f"{mode}_profile_{etype}_{catalyst}_{mlabel}.svg"
    plt.savefig(plots_dir / fname, format="svg", transparent=False)
    log.info("Saved profile plot: %s", plots_dir / fname)
    plt.close(fig)
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rel_trace(
    pdata: ProfileData,
    etype: str,
) -> list[tuple[str, float]] | None:
    """Read pre-computed relative energies for plotting."""
    vals = [(s.name, v) for s in pdata.stages if (v := s.rel(etype)) is not None]
    return vals or None


def _draw_trace(
    ax: plt.Axes,
    stages: list[tuple[str, float]],
    color: str,
    skip_stages: frozenset[str] = frozenset(),
) -> None:
    """Draw horizontal bars + dashed connectors for one trace."""
    if not stages:
        return

    n = len(stages)
    x_starts = _X5[:n] if n == 5 else _X3[:n] if n == 3 else list(range(0, 2 * n, 2))
    x_centers = [x + _BAR_WIDTH / 2 for x in x_starts]

    for i, (sname, E) in enumerate(stages):
        label = _STAGE_LABELS.get(sname, sname)
        if label.lower() in skip_stages:
            continue

        ax.plot(
            [x_starts[i], x_starts[i] + _BAR_WIDTH],
            [E, E],
            lw=4,
            color=color,
            solid_capstyle="round",
        )

        key = (color, label)
        if key in _CUSTOM_OFFSETS:
            va, y_off, x_off = _CUSTOM_OFFSETS[key]
        else:
            va, y_off, x_off = _DEFAULT_OFFSETS.get(color, ("bottom", 0.1, 0.0))
        ax.text(
            x_centers[i] + x_off,
            E + y_off,
            f"{E:.1f}",
            color=color,
            weight="normal",
            ha="center",
            va=va,
            fontsize=24,
        )

    for i in range(len(stages) - 1):
        x_end = x_starts[i] + _BAR_WIDTH
        x_next = x_starts[i + 1]
        ax.plot(
            [x_end, x_next],
            [stages[i][1], stages[i + 1][1]],
            linestyle="--",
            color=color,
            lw=2,
            solid_capstyle="round",
        )


def _style_axes(
    ax: plt.Axes,
    etype: str,
    unit: str,
    traces: list[dict[str, Any]],
) -> None:
    """Apply axis labels, ticks, limits, and arrows to a profile plot."""
    ax.tick_params(bottom=False, left=False)
    ax.set_xticks([0.25, 2.25, 4.25, 6.25, 8.25])
    ax.set_xticklabels(
        ["reactants", "pre-TS", "TS", "post-TS", "product"],
        fontsize=12,
        fontweight="bold",
    )
    ax.set_yticks([])
    ax.set_xlim(-1, 10)

    display = "G" if etype.startswith("G") else etype
    ax.set_xlabel("reaction coordinate", fontsize=20, fontweight="bold")
    ax.set_ylabel(
        rf"$\boldsymbol{{\Delta}}\boldsymbol{{{display}}}\;\mathbf{{({unit})}}$",
        fontsize=20,
    )

    # Collect all energies for y-limits
    all_vals: list[float] = []
    for t in traces:
        all_vals.extend(v for _, v in t["stages"])
    if all_vals:
        ymin, ymax = min(all_vals), max(all_vals)
        ypad = abs(ymax - ymin) * 0.07
        ax.set_ylim(ymin - ypad - 1, ymax + ypad + 1)

    for spine in ax.spines.values():
        spine.set_visible(False)

    xmin, xmax = ax.get_xlim()
    ymin_lim, ymax_lim = ax.get_ylim()
    ax.annotate(
        "",
        xy=(xmax, ymin_lim),
        xytext=(xmin, ymin_lim),
        arrowprops={"arrowstyle": "->", "color": "k", "lw": 2.5},
        clip_on=False,
    )
    ax.annotate(
        "",
        xy=(xmin, ymax_lim),
        xytext=(xmin, ymin_lim),
        arrowprops={"arrowstyle": "->", "color": "k", "lw": 2.5},
        clip_on=False,
    )

    plt.tight_layout()
