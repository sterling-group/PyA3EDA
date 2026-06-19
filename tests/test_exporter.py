"""Tests for pya3eda.exporter.results — CSV and XYZ export."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pya3eda.exporter.results import (
    _export_delta_delta,
    _export_profiles,
    _export_raw,
    _export_raw_profiles,
    _export_xyz,
    _write_csv,
    export_all,
)
from pya3eda.ids import (
    CalcID,
    DeltaDeltaData,
    ExtractedData,
    ProfileData,
    ProfileID,
    StageData,
)

MK = "wb97x"


# ── Helpers ──────────────────────────────────────────────────────────


def _cid(
    stage: str = "reactants",
    mode: str = "opt",
    calc_type: str | None = None,
    sp_sub: str | None = None,
    catalyst: str | None = None,
    species: str = "mol",
) -> CalcID:
    return CalcID(
        method_key=MK,
        catalyst=catalyst,
        stage=stage,
        species=species,
        calc_type=calc_type,
        mode=mode,
        sp_subfolder=sp_sub,
    )


def _ed(cid: CalcID, **kw) -> ExtractedData:
    return ExtractedData(calc_id=cid, **kw)


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


# ── _write_csv ───────────────────────────────────────────────────────


class TestWriteCsv:
    def test_empty_rows(self, tmp_path: Path) -> None:
        assert _write_csv([], tmp_path / "empty.csv") == 0
        assert not (tmp_path / "empty.csv").exists()

    def test_success(self, tmp_path: Path) -> None:
        rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        assert _write_csv(rows, tmp_path / "out.csv") == 1
        content = (tmp_path / "out.csv").read_text()
        assert "a,b" in content
        assert "1,2" in content


# ── _export_raw ──────────────────────────────────────────────────────


class TestExportRaw:
    def test_opt_and_sp(self, tmp_path: Path) -> None:
        c_opt = _cid(mode="opt")
        c_sp = _cid(mode="sp", sp_sub="sp1")
        extracted = {
            c_opt: _ed(c_opt, energy=-100.0),
            c_sp: _ed(c_sp, sp_energy=-101.0),
        }
        count = _export_raw(extracted, MK, tmp_path)
        assert count == 2
        assert (tmp_path / f"opt_{MK}.csv").exists()
        assert (tmp_path / f"sp_{MK}.csv").exists()

    def test_method_key_filter(self, tmp_path: Path) -> None:
        c = _cid()
        extracted = {c: _ed(c, energy=-100.0)}
        count = _export_raw(extracted, "other_key", tmp_path)
        assert count == 0

    def test_only_opt(self, tmp_path: Path) -> None:
        c = _cid(mode="opt")
        extracted = {c: _ed(c, energy=-100.0)}
        count = _export_raw(extracted, MK, tmp_path)
        assert count == 1
        assert (tmp_path / f"opt_{MK}.csv").exists()
        assert not (tmp_path / f"sp_{MK}.csv").exists()


# ── _export_raw_profiles ────────────────────────────────────────────


class TestExportRawProfiles:
    def test_exports_profile_csv(self, tmp_path: Path) -> None:
        pid = _pid(catalyst="cat", calc_type="full_cat")
        stages = (
            _sd("reactants", E=10.0, G=100.0, calc_type="full_cat"),
            _sd("ts", E=20.0, G=110.0, calc_type="full_cat"),
        )
        profiles = {pid: ProfileData(profile_id=pid, stages=stages)}
        count = _export_raw_profiles(profiles, MK, tmp_path)
        assert count == 1
        csvs = list(tmp_path.glob("*.csv"))
        assert len(csvs) == 1
        content = csvs[0].read_text()
        assert "E (kcal/mol)" in content
        assert "G (kcal/mol)" in content
        assert "rel_E" in content

    def test_filters_method_key(self, tmp_path: Path) -> None:
        pid = _pid(calc_type="full_cat")
        profiles = {pid: ProfileData(profile_id=pid, stages=())}
        count = _export_raw_profiles(profiles, "other_key", tmp_path)
        assert count == 0

    def test_empty_stages_writes_nothing(self, tmp_path: Path) -> None:
        """A matching profile with no stages yields no rows → nothing written."""
        pid = _pid()
        profiles = {pid: ProfileData(profile_id=pid, stages=())}
        assert _export_raw_profiles(profiles, MK, tmp_path) == 0


# ── _export_profiles ────────────────────────────────────────────────


class TestExportProfiles:
    def _make_profiles(self) -> dict[ProfileID, ProfileData]:
        """Build uncat + full_cat + frz_cat profiles for catalyst 'cat'."""
        uncat_pid = _pid(calc_type=None, catalyst=None)
        full_pid = _pid(calc_type="full_cat", catalyst="cat")
        frz_pid = _pid(calc_type="frz_cat", catalyst="cat")

        uncat_stages = (
            _sd("reactants", label="r", _rel={"E": 0.0, "G": 0.0}),
            _sd("ts", label="t", _rel={"E": 10.0, "G": 12.0}),
            _sd("products", label="p", _rel={"E": -5.0, "G": -3.0}),
        )
        full_stages = (
            _sd("reactants", calc_type="full_cat", label="r", _rel={"E": 0.0, "G": 0.0}),
            _sd("preTS", calc_type="full_cat", label="pre", _rel={"E": -2.0, "G": -1.0}),
            _sd("ts", calc_type="full_cat", label="t", _rel={"E": 8.0, "G": 9.0}),
            _sd(
                "postTS",
                calc_type="full_cat",
                label="post",
                _rel={"E": -3.0, "G": -2.0},
            ),
            _sd("products", calc_type="full_cat", label="p", _rel={"E": -6.0, "G": -4.0}),
        )
        frz_stages = (
            _sd("reactants", calc_type="frz_cat", label="r", _rel={"E": 0.0, "G": 0.0}),
            _sd("preTS", calc_type="frz_cat", label="pre", _rel={"E": -1.0, "G": -0.5}),
            _sd("ts", calc_type="frz_cat", label="t", _rel={"E": 9.0, "G": 10.0}),
            _sd("postTS", calc_type="frz_cat", label="post", _rel={"E": -2.0, "G": -1.5}),
            _sd("products", calc_type="frz_cat", label="p", _rel={"E": -5.0, "G": -3.5}),
        )

        return {
            uncat_pid: ProfileData(profile_id=uncat_pid, stages=uncat_stages),
            full_pid: ProfileData(profile_id=full_pid, stages=full_stages),
            frz_pid: ProfileData(profile_id=frz_pid, stages=frz_stages),
        }

    def test_stage_major_ordering(self, tmp_path: Path) -> None:
        profiles = self._make_profiles()
        # Add a profile from different method_key (should be skipped)
        other_pid = ProfileID(method_key="other", calc_type=None)
        profiles[other_pid] = ProfileData(profile_id=other_pid, stages=())
        count = _export_profiles(profiles, MK, tmp_path)
        assert count == 1

        csv = next(iter(tmp_path.glob("*.csv")))
        import pandas as pd

        df = pd.read_csv(csv)

        # Endpoints (reactants/products) only for uncat
        traces = df["Trace"].tolist()
        stages = df["Stage"].tolist()

        # First rows are reactants — only uncat
        r_traces = [t for t, s in zip(traces, stages, strict=True) if s == "reactants"]
        assert r_traces == ["uncat"]

        # Products — only uncat
        p_traces = [t for t, s in zip(traces, stages, strict=True) if s == "products"]
        assert p_traces == ["uncat"]

        # preTS: FULL and FRZ but NOT uncat
        pre_traces = [t for t, s in zip(traces, stages, strict=True) if s == "preTS"]
        assert "uncat" not in pre_traces
        assert "FULL" in pre_traces
        assert "FRZ" in pre_traces

    def test_endpoint_dedup(self, tmp_path: Path) -> None:
        """Catalytic traces skip reactants and products rows."""
        profiles = self._make_profiles()
        _export_profiles(profiles, MK, tmp_path)
        csv = next(iter(tmp_path.glob("*.csv")))
        import pandas as pd

        df = pd.read_csv(csv)

        for _, row in df.iterrows():
            if row["Stage"] in ("reactants", "products"):
                assert row["Trace"] == "uncat"

    def test_empty_available(self, tmp_path: Path) -> None:
        """No profiles for this method_key → 0 files."""
        count = _export_profiles({}, MK, tmp_path)
        assert count == 0

    def test_available_but_no_rows(self, tmp_path: Path) -> None:
        """A catalyzed trace with no stages is available but yields no rows → not written."""
        pid = _pid(calc_type="full_cat", catalyst="cat1")
        profiles = {pid: ProfileData(profile_id=pid, stages=())}
        assert _export_profiles(profiles, MK, tmp_path) == 0

    def test_catalyst_with_no_matching_profiles(self, tmp_path: Path) -> None:
        """A catalyst appears in one mode but not another → empty available → skip."""
        # Create a profile that registers cat2 in catalysts and (opt, None) in mode_sps,
        # but cat2 has no matching trace profiles for any calc_type in TRACE_ORDER.
        pid_cat2 = ProfileID(method_key=MK, catalyst="cat2", calc_type="custom_type", mode="opt")
        stages = (_sd("reactants", label="r", _rel={"E": 0.0}),)
        profiles = {pid_cat2: ProfileData(profile_id=pid_cat2, stages=stages)}
        count = _export_profiles(profiles, MK, tmp_path)
        assert count == 0


# ── _export_delta_delta ─────────────────────────────────────────────


class TestExportDeltaDelta:
    def test_e_g_rows(self, tmp_path: Path) -> None:
        dd_list = [
            _dd("cat1", "E", barrier_uncat=50.0, barrier_full=40.0, dd_complete=-10.0),
            _dd("cat1", "G", barrier_uncat=55.0, barrier_full=45.0, dd_complete=-10.0),
        ]
        count = _export_delta_delta(dd_list, MK, tmp_path)
        assert count == 2
        # Check E file has no barrier_ni column
        e_csv = next(iter(tmp_path.glob("*_E_*.csv")))
        content = e_csv.read_text()
        assert "Barrier_ni" not in content

    def test_g_ni_rows(self, tmp_path: Path) -> None:
        dd_list = [
            _dd(
                "cat1",
                "G_ni",
                barrier_uncat=55.0,
                barrier_ni=52.0,
                barrier_full=45.0,
                dd_ni=-3.0,
                dd_complete=-10.0,
            ),
        ]
        count = _export_delta_delta(dd_list, MK, tmp_path)
        assert count == 1
        csv = next(iter(tmp_path.glob("*.csv")))
        content = csv.read_text()
        assert "Barrier_ni" in content
        assert "DD_G_ni_ni" in content

    def test_empty(self, tmp_path: Path) -> None:
        count = _export_delta_delta([], MK, tmp_path)
        assert count == 0

    def test_dissoc_column(self, tmp_path: Path) -> None:
        dd_list = [
            _dd(
                "cat1", "E", barrier_uncat=50.0, barrier_full=42.0, dd_complete=-8.0, dd_dissoc=2.0
            ),
        ]
        _export_delta_delta(dd_list, MK, tmp_path)
        content = next(iter(tmp_path.glob("*_E_*.csv"))).read_text()
        assert "DD_E_dissoc" in content

    def test_method_key_filter(self, tmp_path: Path) -> None:
        dd_list = [_dd("cat1", "E", barrier_uncat=50.0)]
        count = _export_delta_delta(dd_list, "other", tmp_path)
        assert count == 0


# ── _export_xyz ─────────────────────────────────────────────────────


class TestExportXyz:
    def test_writes_xyz(self, tmp_path: Path) -> None:
        c = _cid(species="water")
        extracted = {c: _ed(c, xyz_text="3\nwater\nO 0 0 0\nH 1 0 0\nH 0 1 0\n")}
        count = _export_xyz(extracted, MK, tmp_path)
        assert count == 1
        assert (tmp_path / "water.xyz").exists()

    def test_skips_none_xyz(self, tmp_path: Path) -> None:
        c = _cid()
        extracted = {c: _ed(c, xyz_text=None)}
        count = _export_xyz(extracted, MK, tmp_path)
        assert count == 0

    def test_calc_type_in_filename(self, tmp_path: Path) -> None:
        xyz = "3\nwater\nO 0 0 0\nH 1 0 0\nH 0 1 0\n"
        c_frz = _cid(species="water", calc_type="frz_cat")
        c_pol = _cid(species="water", calc_type="pol_cat")
        extracted = {
            c_frz: _ed(c_frz, xyz_text=xyz),
            c_pol: _ed(c_pol, xyz_text=xyz),
        }
        count = _export_xyz(extracted, MK, tmp_path)
        assert count == 2
        assert (tmp_path / "water_frz_cat.xyz").exists()
        assert (tmp_path / "water_pol_cat.xyz").exists()

    def test_method_key_filter(self, tmp_path: Path) -> None:
        c = _cid(species="water")
        extracted = {c: _ed(c, xyz_text="3\nwater\nO 0 0 0\nH 1 0 0\nH 0 1 0\n")}
        count = _export_xyz(extracted, "other", tmp_path)
        assert count == 0

    @pytest.mark.parametrize(
        "stage, species, calc_type, catalyst, expected_name",
        [
            ("preTS", "lip-mol", "full_cat", "lip", "preTS_lip-mol_full_cat.xyz"),
            ("postTS", "lip-mol", "frz_cat", "lip", "postTS_lip-mol_frz_cat.xyz"),
            ("ts", "lip-tscomplex", "full_cat", "lip", "ts_lip-tscomplex_full_cat.xyz"),
            ("ts", "tscomplex", None, None, "tscomplex.xyz"),
        ],
    )
    def test_stage_prefix_in_filename(
        self, tmp_path, stage, species, calc_type, catalyst, expected_name
    ) -> None:
        xyz = "3\nwater\nO 0 0 0\nH 1 0 0\nH 0 1 0\n"
        c = _cid(stage=stage, species=species, calc_type=calc_type, catalyst=catalyst)
        extracted = {c: _ed(c, xyz_text=xyz)}
        count = _export_xyz(extracted, MK, tmp_path)
        assert count == 1
        assert (tmp_path / expected_name).exists()


# ── export_all ──────────────────────────────────────────────────────


class TestExportAll:
    def test_integration(self, tmp_path: Path) -> None:
        """export_all calls all sub-exporters; verify files created."""
        registry = MagicMock()
        registry.method_keys = [MK]

        c = _cid(species="water")
        extracted = {c: _ed(c, energy=-100.0, xyz_text="1\nH\nH 0 0 0\n")}

        pid = _pid(calc_type=None, catalyst=None)
        stages = (_sd("reactants", E=0.0, G=0.0, _rel={"E": 0.0, "G": 0.0}),)
        profiles = {pid: ProfileData(profile_id=pid, stages=stages)}

        dd_list: list[DeltaDeltaData] = []

        export_all(registry, extracted, profiles, dd_list, tmp_path)

        results_dir = tmp_path / "results" / MK
        assert results_dir.exists()
        # At least raw data + xyz should be written
        all_files = list(results_dir.rglob("*.*"))
        assert len(all_files) >= 2
