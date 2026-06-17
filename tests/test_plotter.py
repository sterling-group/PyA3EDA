"""Tests for pya3eda.plotter — profile SVG and delta-delta barplot generation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import matplotlib
import pytest

from pya3eda.ids import (
    DeltaDeltaData,
    ProfileData,
    ProfileID,
    ProfileSpec,
    StageData,
    StageSpec,
)

matplotlib.use("SVG")


# ── Helpers ──────────────────────────────────────────────────────────

MK = "wb97x"


def _sd(
    name: str,
    *,
    E: float | None = None,
    G: float | None = None,
    calc_type: str | None = None,
    label: str = "",
    _rel: dict[str, float] | None = None,
) -> StageData:
    sd = StageData(name=name, E=E, G=G, calc_type=calc_type, species_label=label)
    if _rel:
        sd = sd.model_copy(update={"_rel": _rel})
    return sd


def _pid(
    calc_type: str | None = None,
    catalyst: str | None = None,
    mode: str = "opt",
    sp_sub: str | None = None,
) -> ProfileID:
    return ProfileID(
        method_key=MK,
        calc_type=calc_type,
        catalyst=catalyst,
        mode=mode,
        sp_subfolder=sp_sub,
    )


def _dd(catalyst: str, etype: str, **kw) -> DeltaDeltaData:
    return DeltaDeltaData(method_key=MK, catalyst=catalyst, energy_type=etype, **kw)


def _pspec(
    calc_type: str | None, catalyst: str | None, leader: bool = False
) -> ProfileSpec:
    """Minimal ProfileSpec for registry.all_profiles."""
    pid = _pid(calc_type=calc_type, catalyst=catalyst)
    stage = StageSpec(name="reactants", calc_ids=(), label="r")
    return ProfileSpec(id=pid, stages=(stage,), selection_leader=leader)


# ===================================================================
# profile.py
# ===================================================================

from pya3eda.plotter.profile import (
    _draw_trace,
    _plot_catalyst,
    _rel_trace,
    _style_axes,
    plot_all_profiles,
)


class TestRelTrace:
    def test_returns_values(self) -> None:
        stages = (
            _sd("reactants", _rel={"G": 0.0}),
            _sd("ts", _rel={"G": 10.0}),
        )
        pd = ProfileData(profile_id=_pid(), stages=stages)
        result = _rel_trace(pd, "G")
        assert result is not None
        assert len(result) == 2
        assert result[0] == ("reactants", 0.0)
        assert result[1] == ("ts", 10.0)

    def test_all_none(self) -> None:
        stages = (
            _sd("reactants"),
            _sd("ts"),
        )
        pd = ProfileData(profile_id=_pid(), stages=stages)
        assert _rel_trace(pd, "G") is None


class TestDrawTrace:
    def test_3_stage(self) -> None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        stages = [("reactants", 0.0), ("ts", 10.0), ("products", -5.0)]
        _draw_trace(ax, stages, "black")
        # 3 bars + 2 connectors + 3 annotations → no error
        plt.close(fig)

    def test_5_stage(self) -> None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        stages = [
            ("reactants", 0.0),
            ("preTS", -2.0),
            ("ts", 10.0),
            ("postTS", -1.0),
            ("products", -5.0),
        ]
        _draw_trace(ax, stages, "royalblue")
        plt.close(fig)

    def test_skip_endpoints(self) -> None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        stages = [
            ("reactants", 0.0),
            ("preTS", -2.0),
            ("ts", 10.0),
            ("postTS", -1.0),
            ("products", -5.0),
        ]
        _draw_trace(
            ax, stages, "firebrick", skip_stages=frozenset({"reactant", "product"})
        )
        plt.close(fig)

    def test_empty(self) -> None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        _draw_trace(ax, [], "black")
        plt.close(fig)

    def test_custom_offsets(self) -> None:
        """Hit _CUSTOM_OFFSETS by drawing with known (color, label) combos."""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        stages = [("reactants", 0.0), ("ts", 10.0), ("products", -5.0)]
        # black + TS triggers _CUSTOM_OFFSETS[("black", "TS")]
        _draw_trace(ax, stages, "black")
        # forestgreen touches other custom offsets
        stages5 = [
            ("reactants", 0.0),
            ("preTS", -2.0),
            ("ts", 10.0),
            ("postTS", -1.0),
            ("products", -5.0),
        ]
        _draw_trace(ax, stages5, "forestgreen")
        plt.close(fig)


class TestStyleAxes:
    def test_g_ni_display(self) -> None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        traces = [{"stages": [("reactants", 0.0), ("ts", 10.0)]}]
        _style_axes(ax, "G_ni", "kcal/mol", traces)
        ylabel = ax.get_ylabel()
        # G_ni should use display="G" (starts with G)
        assert "G" in ylabel
        plt.close(fig)

    def test_e_display(self) -> None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        traces = [{"stages": [("reactants", 0.0), ("ts", 5.0)]}]
        _style_axes(ax, "E", "kcal/mol", traces)
        ylabel = ax.get_ylabel()
        assert "E" in ylabel
        plt.close(fig)


class TestPlotCatalyst:
    def _make_profiles(self) -> dict[ProfileID, ProfileData]:
        uncat_stages = (
            _sd("reactants", _rel={"E": 0.0, "G": 0.0}),
            _sd("ts", _rel={"E": 10.0, "G": 12.0}),
            _sd("products", _rel={"E": -5.0, "G": -3.0}),
        )
        full_stages = (
            _sd("reactants", calc_type="full_cat", _rel={"E": 0.0, "G": 0.0}),
            _sd("preTS", calc_type="full_cat", _rel={"E": -2.0, "G": -1.0}),
            _sd("ts", calc_type="full_cat", _rel={"E": 8.0, "G": 9.0}),
            _sd("postTS", calc_type="full_cat", _rel={"E": -3.0, "G": -2.0}),
            _sd("products", calc_type="full_cat", _rel={"E": -6.0, "G": -4.0}),
        )
        ni_stages = (
            _sd("reactants", calc_type="ni", _rel={"G": 0.0}),
            _sd("preTS", calc_type="ni", _rel={"G": -0.5}),
            _sd("ts", calc_type="ni", _rel={"G": 11.0}),
            _sd("postTS", calc_type="ni", _rel={"G": -1.5}),
            _sd("products", calc_type="ni", _rel={"G": -3.5}),
        )

        uncat_pid = _pid(calc_type=None, catalyst=None)
        full_pid = _pid(calc_type="full_cat", catalyst="cat")
        ni_pid = _pid(calc_type="ni", catalyst="cat")

        return {
            uncat_pid: ProfileData(profile_id=uncat_pid, stages=uncat_stages),
            full_pid: ProfileData(profile_id=full_pid, stages=full_stages),
            ni_pid: ProfileData(profile_id=ni_pid, stages=ni_stages),
        }

    def test_no_traces(self, tmp_path: Path) -> None:
        result = _plot_catalyst({}, None, MK, "cat", "opt", None, "G", tmp_path)
        assert result is False

    def test_ni_skipped_on_E(self, tmp_path: Path) -> None:
        profiles = self._make_profiles()
        uncat_data = profiles[_pid(calc_type=None, catalyst=None)]
        result = _plot_catalyst(
            profiles,
            uncat_data,
            MK,
            "cat",
            "opt",
            None,
            "E",
            tmp_path,
        )
        assert result is True
        svgs = list(tmp_path.glob("*.svg"))
        assert len(svgs) == 1

    def test_ni_included_on_G_ni(self, tmp_path: Path) -> None:
        profiles = self._make_profiles()
        uncat_data = profiles[_pid(calc_type=None, catalyst=None)]
        result = _plot_catalyst(
            profiles,
            uncat_data,
            MK,
            "cat",
            "opt",
            None,
            "G_ni",
            tmp_path,
        )
        assert result is True


class TestPlotAllProfiles:
    def test_creates_svgs(self, tmp_path: Path) -> None:
        """Integration: plot_all_profiles generates SVG files."""
        uncat_stages = (
            _sd("reactants", _rel={"E": 0.0, "G": 0.0}),
            _sd("ts", _rel={"E": 10.0, "G": 12.0}),
            _sd("products", _rel={"E": -5.0, "G": -3.0}),
        )
        full_stages = (
            _sd("reactants", calc_type="full_cat", _rel={"E": 0.0, "G": 0.0}),
            _sd("preTS", calc_type="full_cat", _rel={"E": -2.0, "G": -1.0}),
            _sd("ts", calc_type="full_cat", _rel={"E": 8.0, "G": 9.0}),
            _sd("postTS", calc_type="full_cat", _rel={"E": -3.0, "G": -2.0}),
            _sd("products", calc_type="full_cat", _rel={"E": -6.0, "G": -4.0}),
        )

        uncat_pid = _pid(calc_type=None, catalyst=None)
        full_pid = _pid(calc_type="full_cat", catalyst="cat")

        profiles = {
            uncat_pid: ProfileData(profile_id=uncat_pid, stages=uncat_stages),
            full_pid: ProfileData(profile_id=full_pid, stages=full_stages),
        }

        # Mock registry.all_profiles
        registry = MagicMock()
        registry.all_profiles = [
            _pspec(None, None),
            _pspec("full_cat", "cat", leader=True),
        ]

        plot_all_profiles(profiles, registry, tmp_path)

        svgs = list((tmp_path / "results" / MK / "plots").rglob("*.svg"))
        # E, G, G_ni × 1 catalyst = 3 (or 2 if G_ni skipped due to no NI trace)
        assert len(svgs) >= 2


# ===================================================================
# contributions.py
# ===================================================================

from pya3eda.plotter.contributions import (
    _catalyst_lightness,
    _lighten,
    _plot_single,
    plot_delta_delta_barplots,
)


class TestCatalystLightness:
    def test_single(self) -> None:
        assert _catalyst_lightness(1) == [0.0]

    def test_three(self) -> None:
        result = _catalyst_lightness(3)
        assert len(result) == 3
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(0.2)
        assert result[2] == pytest.approx(0.4)


class TestLighten:
    def test_no_lightening(self) -> None:
        r, g, b = _lighten("firebrick", 0.0)
        # Original firebrick colour preserved
        import matplotlib.colors as mc

        expected = mc.to_rgb("firebrick")
        assert r == pytest.approx(expected[0])
        assert g == pytest.approx(expected[1])
        assert b == pytest.approx(expected[2])

    def test_full_lightening(self) -> None:
        r, g, b = _lighten("black", 1.0)
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(1.0)
        assert b == pytest.approx(1.0)

    def test_hex_color(self) -> None:
        """Hex colour triggers the KeyError → fallback path."""
        r, g, b = _lighten("#ff0000", 0.0)
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(0.0)
        assert b == pytest.approx(0.0)


class TestPlotSingle:
    def test_e_g_4bar(self, tmp_path: Path) -> None:
        data = [
            _dd("cat1", "E", dd_frz=-1.0, dd_pol=-2.0, dd_ct=-3.0, dd_complete=-6.0)
        ]
        out = tmp_path / "test.svg"
        _plot_single(data, ["cat1"], "E", out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_g_ni_5bar(self, tmp_path: Path) -> None:
        data = [
            _dd(
                "cat1",
                "G_ni",
                dd_ni=-0.5,
                dd_frz=-1.0,
                dd_pol=-2.0,
                dd_ct=-3.0,
                dd_complete=-6.5,
            )
        ]
        out = tmp_path / "test_gni.svg"
        _plot_single(data, ["cat1"], "G_ni", out)
        assert out.exists()

    def test_multi_catalyst(self, tmp_path: Path) -> None:
        data = [
            _dd("cat1", "G", dd_frz=-1.0, dd_pol=-2.0, dd_ct=-3.0, dd_complete=-6.0),
            _dd("cat2", "G", dd_frz=-0.5, dd_pol=-1.0, dd_ct=-1.5, dd_complete=-3.0),
        ]
        out = tmp_path / "multi.svg"
        _plot_single(data, ["cat1", "cat2"], "G", out)
        assert out.exists()

    def test_missing_cat_in_data(self, tmp_path: Path) -> None:
        """ordered_cats includes a catalyst with no data → has_val stays False."""
        data = [
            _dd("cat1", "G", dd_frz=-1.0, dd_pol=-2.0, dd_ct=-3.0, dd_complete=-6.0)
        ]
        out = tmp_path / "missing.svg"
        _plot_single(data, ["cat1", "cat_missing"], "G", out)
        assert out.exists()


class TestPlotDeltaDeltaBarplots:
    def test_creates_svgs(self, tmp_path: Path) -> None:
        dd_list = [
            _dd("cat1", "E", dd_frz=-1.0, dd_pol=-2.0, dd_ct=-3.0, dd_complete=-6.0),
            _dd("cat1", "G", dd_frz=-1.0, dd_pol=-2.0, dd_ct=-3.0, dd_complete=-6.0),
            _dd(
                "cat1",
                "G_ni",
                dd_ni=-0.5,
                dd_frz=-1.0,
                dd_pol=-2.0,
                dd_ct=-3.0,
                dd_complete=-6.5,
            ),
        ]
        registry = MagicMock()
        registry.catalyst_order = ["cat1"]
        registry.method_keys = [MK]

        plot_delta_delta_barplots(dd_list, registry, tmp_path)
        svgs = list((tmp_path / "results" / MK / "plots").rglob("*.svg"))
        assert len(svgs) == 3

    def test_empty_catalyst_order(self, tmp_path: Path) -> None:
        registry = MagicMock()
        registry.catalyst_order = []
        registry.method_keys = [MK]
        dd_list = [_dd("cat1", "E")]
        plot_delta_delta_barplots(dd_list, registry, tmp_path)
        svgs = list(tmp_path.rglob("*.svg"))
        assert len(svgs) == 0

    def test_no_data_for_mk(self, tmp_path: Path) -> None:
        registry = MagicMock()
        registry.catalyst_order = ["cat1"]
        registry.method_keys = ["other_mk"]
        dd_list = [_dd("cat1", "E")]
        plot_delta_delta_barplots(dd_list, registry, tmp_path)
        svgs = list(tmp_path.rglob("*.svg"))
        assert len(svgs) == 0

    def test_catalyst_order_mismatch(self, tmp_path: Path) -> None:
        """catalyst_order has no match for actual data catalysts → no plots."""
        registry = MagicMock()
        registry.catalyst_order = ["nonexistent_cat"]
        registry.method_keys = [MK]
        dd_list = [_dd("cat1", "E", dd_frz=-1.0)]
        plot_delta_delta_barplots(dd_list, registry, tmp_path)
        svgs = list(tmp_path.rglob("*.svg"))
        assert len(svgs) == 0
