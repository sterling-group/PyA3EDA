"""Tests for pya3eda.extractor — data extraction, profile assembly, barrier decomposition.

All tests are self-contained using synthetic Q-Chem output files
written to a temp directory tree that mirrors the expected layout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pya3eda.config import (
    load_config,
)
from pya3eda.extractor.barriers import (
    _barrier,
    _compute_for_catalyst,
    _should_use_preTS,
)
from pya3eda.extractor.stages import (
    _argmin,
    _build_one,
    _build_stage_best,
    _g_ni_for_stage,
    _normalize,
    _sum_energies,
)
from pya3eda.ids import (
    CalcID,
    DeltaDeltaData,
    ExtractedData,
    NiStageRef,
    ProfileData,
    ProfileID,
    ProfileSpec,
    StageAlt,
    StageData,
    StageSpec,
)
from pya3eda.registry import CalcRegistry
from pya3eda.utils import standard_state_correction
from tests.synthetic_outputs import (
    EDA_FRZ_OUTPUT,
    EDA_FULL_SP_OUTPUT,
    EDA_POL_OUTPUT,
    OPT_OUTPUT,
    SAMPLE_CONFIG_YAML,
    SP_OUTPUT,
    TS_OUTPUT,
)

# ===================================================================
# StageData / ProfileID class-level vocabulary
# ===================================================================


class TestStageDataClassVocabulary:
    def test_unit(self) -> None:
        assert StageData.UNIT == "kcal/mol"

    def test_energy_types(self) -> None:
        etypes = StageData.energy_types()
        assert "E" in etypes
        assert "G" in etypes
        # G_ni is not an energy type — NI is a trace
        assert "G_ni" not in etypes
        # name and calc_type are string fields, not float
        assert "name" not in etypes


class TestProfileIDTraceOrder:
    def test_trace_order_has_five_entries(self) -> None:
        assert len(ProfileID.TRACE_ORDER) == 5

    def test_trace_order_types(self) -> None:
        for _ct, label in ProfileID.TRACE_ORDER:
            assert isinstance(label, str)

    def test_method_label_opt(self) -> None:
        assert ProfileID.method_label("wB97X-V_def2-SVP_smd", None) == "wB97X-V_def2-SVP_smd"

    def test_method_label_sp(self) -> None:
        result = ProfileID.method_label("wB97X-V_def2-SVP_smd", "wB97M-V_def2-TZVPPD_smd_sp")
        assert result == "wB97M-V_def2-TZVPPD_smd_sp_wB97X-V_def2-SVP_smd_opt"


# ===================================================================
# Helpers — build a synthetic file tree for extraction
# ===================================================================

MK = "wB97X-V_def2-SVP_smd"
SP_SUB = "wB97M-V_def2-TZVPPD_smd_sp"


def _write_output(base: Path, rel: str, content: str) -> None:
    """Write content to base/rel, creating directories as needed."""
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _populate_tree(base: Path) -> None:
    """Create a minimal directory tree with synthetic Q-Chem outputs."""
    mk = MK
    sp = SP_SUB

    # Uncatalyzed: reactants
    _write_output(base, f"{mk}/no_cat/reactants/prop2enal/prop2enal_opt.out", OPT_OUTPUT)
    _write_output(base, f"{mk}/no_cat/reactants/prop2enal/{sp}/prop2enal_sp.out", SP_OUTPUT)

    # Uncatalyzed: ts
    _write_output(base, f"{mk}/no_cat/ts/tscomplex_opt.out", TS_OUTPUT)
    _write_output(base, f"{mk}/no_cat/ts/{sp}/tscomplex_sp.out", SP_OUTPUT)

    # Uncatalyzed: products
    _write_output(
        base,
        f"{mk}/no_cat/products/cyclohex3ene1carbaldehyde/cyclohex3ene1carbaldehyde_opt.out",
        OPT_OUTPUT,
    )
    _write_output(
        base,
        f"{mk}/no_cat/products/cyclohex3ene1carbaldehyde/{sp}/cyclohex3ene1carbaldehyde_sp.out",
        SP_OUTPUT,
    )

    # Catalyzed: lip catalyst only
    _write_output(base, f"{mk}/lip/cat/lip_opt.out", OPT_OUTPUT)
    _write_output(base, f"{mk}/lip/cat/{sp}/lip_sp.out", SP_OUTPUT)

    # lip preTS — 3 calc types
    for ct in ("full_cat", "pol_cat", "frz_cat"):
        _write_output(
            base,
            f"{mk}/lip/preTS/lip-prop2enal/{ct}/preTS_lip-prop2enal_{ct}_opt.out",
            EDA_POL_OUTPUT if ct == "pol_cat" else EDA_FRZ_OUTPUT,
        )
        _write_output(
            base,
            f"{mk}/lip/preTS/lip-prop2enal/{ct}/{sp}/preTS_lip-prop2enal_{ct}_sp.out",
            EDA_FULL_SP_OUTPUT
            if ct == "full_cat"
            else EDA_POL_OUTPUT
            if ct == "pol_cat"
            else EDA_FRZ_OUTPUT,
        )

    # lip ts — 3 calc types
    for ct in ("full_cat", "pol_cat", "frz_cat"):
        _write_output(
            base,
            f"{mk}/lip/ts/{ct}/lip-tscomplex_{ct}_opt.out",
            EDA_POL_OUTPUT if ct == "pol_cat" else EDA_FRZ_OUTPUT,
        )
        _write_output(
            base,
            f"{mk}/lip/ts/{ct}/{sp}/lip-tscomplex_{ct}_sp.out",
            EDA_FULL_SP_OUTPUT
            if ct == "full_cat"
            else EDA_POL_OUTPUT
            if ct == "pol_cat"
            else EDA_FRZ_OUTPUT,
        )

    # lip postTS — 3 calc types
    for ct in ("full_cat", "pol_cat", "frz_cat"):
        _write_output(
            base,
            f"{mk}/lip/postTS/lip-cyclohex3ene1carbaldehyde/{ct}/postTS_lip-cyclohex3ene1carbaldehyde_{ct}_opt.out",
            EDA_POL_OUTPUT if ct == "pol_cat" else EDA_FRZ_OUTPUT,
        )
        _write_output(
            base,
            f"{mk}/lip/postTS/lip-cyclohex3ene1carbaldehyde/{ct}/{sp}/postTS_lip-cyclohex3ene1carbaldehyde_{ct}_sp.out",
            EDA_FULL_SP_OUTPUT
            if ct == "full_cat"
            else EDA_POL_OUTPUT
            if ct == "pol_cat"
            else EDA_FRZ_OUTPUT,
        )


@pytest.fixture(scope="module")
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("extract")
    _populate_tree(base)
    return base


@pytest.fixture(scope="module")
def registry(tree: Path) -> CalcRegistry:
    cfg_path = tree / "new.yaml"
    cfg_path.write_text(SAMPLE_CONFIG_YAML)
    cfg = load_config(cfg_path)
    return CalcRegistry(cfg, tree)


# ===================================================================
# _extract_opt / _extract_sp (via extract_all)
# ===================================================================


class TestExtractAll:
    """Integration tests for extract_all using synthetic data."""

    @pytest.fixture(scope="class")
    def extracted(self, registry: CalcRegistry) -> dict[CalcID, ExtractedData]:
        from pya3eda.extractor.data import extract_all

        return extract_all(registry, criteria="all")

    def test_extracts_some_data(self, extracted: dict) -> None:
        assert len(extracted) > 0

    def test_opt_prop2enal(self, extracted: dict) -> None:
        cid = CalcID(
            method_key=MK,
            catalyst=None,
            stage="reactants",
            species="prop2enal",
            mode="opt",
        )
        assert cid in extracted, "prop2enal OPT not extracted"
        data = extracted[cid]

        assert data.energy is not None
        # Final energy -191.709724458668 Ha x 627.5094740631 = kcal/mol
        from pya3eda.utils import convert_unit

        expected_kcal = convert_unit(-191.709724458668, "Ha", "kcal/mol")
        assert data.energy == pytest.approx(expected_kcal, rel=1e-6)

        # Thermo corrections (QRRHO preferred)
        assert data.h_corr == pytest.approx(42.119, abs=0.01)
        assert data.s_corr == pytest.approx(66.534e-3, abs=1e-4)
        assert data.s_trans == pytest.approx(37.991e-3, abs=1e-4)
        assert data.temperature == pytest.approx(298.15)
        assert data.zpve == pytest.approx(38.832, abs=0.01)
        assert data.imag_freq == 0

        # Derived: H = E + h_corr
        assert data.H is not None
        assert pytest.approx(data.energy + data.h_corr, rel=1e-9) == data.H

        # Derived: G = H - T*S + SSC (since solvent=smd)
        assert data.G is not None
        ssc = standard_state_correction(298.15, 1.0)
        expected_G = data.H - 298.15 * data.s_corr + ssc
        assert pytest.approx(expected_G, rel=1e-9) == data.G

    def test_opt_ts_has_one_imag(self, extracted: dict) -> None:
        cid = CalcID(method_key=MK, catalyst=None, stage="ts", species="tscomplex", mode="opt")
        assert cid in extracted, "TS not extracted"
        assert extracted[cid].imag_freq == 1

    def test_sp_prop2enal(self, extracted: dict) -> None:
        cid = CalcID(
            method_key=MK,
            catalyst=None,
            stage="reactants",
            species="prop2enal",
            mode="sp",
            sp_subfolder=SP_SUB,
        )
        assert cid in extracted, "prop2enal SP not extracted"
        data = extracted[cid]

        assert data.sp_energy is not None
        from pya3eda.utils import convert_unit

        expected_sp = convert_unit(-191.91752153, "Ha", "kcal/mol")
        assert data.sp_energy == pytest.approx(expected_sp, rel=1e-5)

        # Thermo comes from OPT
        assert data.h_corr is not None
        assert data.H is not None
        assert data.G is not None

    def test_xyz_text_present(self, extracted: dict) -> None:
        cid = CalcID(
            method_key=MK,
            catalyst=None,
            stage="reactants",
            species="prop2enal",
            mode="opt",
        )
        assert cid in extracted
        data = extracted[cid]
        assert data.xyz_text is not None
        lines = data.xyz_text.strip().splitlines()
        n_atoms = int(lines[0])
        assert n_atoms == 8
        assert len(lines) == n_atoms + 2


# ===================================================================
# build_profiles
# ===================================================================


class TestBuildProfiles:
    @pytest.fixture(scope="class")
    def extracted(self, registry: CalcRegistry) -> dict:
        from pya3eda.extractor.data import extract_all

        return extract_all(registry, criteria="all")

    @pytest.fixture(scope="class")
    def profiles(self, registry: CalcRegistry, extracted: dict) -> dict[ProfileID, ProfileData]:
        from pya3eda.extractor.stages import build_profiles

        return build_profiles(registry, extracted)

    def test_profiles_not_empty(self, profiles: dict) -> None:
        assert len(profiles) > 0

    def test_uncatalyzed_opt_profile(self, profiles: dict) -> None:
        pid = ProfileID(method_key=MK, catalyst=None, calc_type=None, mode="opt")
        assert pid in profiles, "Uncatalyzed OPT profile not built"
        pd = profiles[pid]
        assert len(pd.stages) == 3
        stage_names = [s.name for s in pd.stages]
        assert stage_names == ["reactants", "ts", "products"]
        for s in pd.stages:
            if s.E is not None:
                assert isinstance(s.E, float)

    def test_stage_data_has_all_energy_types(self, profiles: dict) -> None:
        """Every returned StageData should have the fields from energy_types."""
        for pd in profiles.values():
            for s in pd.stages:
                for etype in StageData.energy_types():
                    assert hasattr(s, etype)


# ===================================================================
# compute_delta_delta
# ===================================================================


class TestComputeDeltaDelta:
    @pytest.fixture(scope="class")
    def extracted(self, registry: CalcRegistry) -> dict:
        from pya3eda.extractor.data import extract_all

        return extract_all(registry, criteria="all")

    @pytest.fixture(scope="class")
    def profiles(self, registry: CalcRegistry, extracted: dict) -> dict:
        from pya3eda.extractor.stages import build_profiles

        return build_profiles(registry, extracted)

    @pytest.fixture(scope="class")
    def dd_results(self, profiles: dict, registry: CalcRegistry) -> list[DeltaDeltaData]:
        from pya3eda.extractor.barriers import compute_delta_delta

        return compute_delta_delta(profiles, registry.catalyst_order)

    def test_produces_results(self, dd_results: list) -> None:
        assert len(dd_results) > 0

    def test_has_e_and_g_types(self, dd_results: list) -> None:
        etypes = {d.energy_type for d in dd_results}
        assert "E" in etypes or "G" in etypes

    def test_dd_complete_equals_full_minus_uncat(self, dd_results: list) -> None:
        for dd in dd_results:
            if (
                dd.dd_complete is not None
                and dd.barrier_full is not None
                and dd.barrier_uncat is not None
            ):
                assert dd.dd_complete == pytest.approx(dd.barrier_full - dd.barrier_uncat, abs=1e-9)

    def test_dd_pol_equals_pol_minus_frz(self, dd_results: list) -> None:
        for dd in dd_results:
            if dd.dd_pol is not None and dd.barrier_pol is not None and dd.barrier_frz is not None:
                assert dd.dd_pol == pytest.approx(dd.barrier_pol - dd.barrier_frz, abs=1e-9)

    def test_dd_ct_equals_full_minus_pol(self, dd_results: list) -> None:
        for dd in dd_results:
            if dd.dd_ct is not None and dd.barrier_full is not None and dd.barrier_pol is not None:
                assert dd.dd_ct == pytest.approx(dd.barrier_full - dd.barrier_pol, abs=1e-9)

    def test_g_ni_has_dd_ni(self, dd_results: list) -> None:
        """G_ni entries should have dd_ni = barrier_ni - barrier_uncat."""
        gni_entries = [d for d in dd_results if d.energy_type == "G_ni"]
        for dd in gni_entries:
            if dd.dd_ni is not None and dd.barrier_ni is not None and dd.barrier_uncat is not None:
                assert dd.dd_ni == pytest.approx(dd.barrier_ni - dd.barrier_uncat, abs=1e-9)


# ===================================================================
# Unit tests — stages.py internals
# ===================================================================


def _ed(
    *,
    energy: float | None = None,
    sp_energy: float | None = None,
    G: float | None = None,
    H: float | None = None,
    h_corr: float | None = None,
    s_corr: float | None = None,
    s_trans: float | None = None,
    temperature: float | None = None,
    **kw,
) -> ExtractedData:
    """Minimal ExtractedData factory — calc_id is a filler."""
    cid = kw.pop("calc_id", CalcID(method_key="m", stage="r", species="x"))
    return ExtractedData(
        calc_id=cid,
        energy=energy,
        sp_energy=sp_energy,
        G=G,
        H=H,
        h_corr=h_corr,
        s_corr=s_corr,
        s_trans=s_trans,
        temperature=temperature,
        **kw,
    )


class TestSumEnergies:
    def test_missing_cid_returns_none(self) -> None:
        cid = CalcID(method_key="m", stage="r", species="x")
        result = _sum_energies((cid,), {})
        assert result == (None, None)

    def test_has_E_false(self) -> None:
        """When energy and sp_energy are both None, E comes back None."""
        cid = CalcID(method_key="m", stage="r", species="x")
        ed = _ed(calc_id=cid, energy=None, sp_energy=None, G=10.0)
        E, G = _sum_energies((cid,), {cid: ed})
        assert E is None
        assert pytest.approx(10.0) == G

    def test_has_G_false(self) -> None:
        cid = CalcID(method_key="m", stage="r", species="x")
        ed = _ed(calc_id=cid, energy=5.0, G=None)
        E, G = _sum_energies((cid,), {cid: ed})
        assert pytest.approx(5.0) == E
        assert G is None

    def test_sums_multiple(self) -> None:
        c1 = CalcID(method_key="m", stage="r", species="a")
        c2 = CalcID(method_key="m", stage="r", species="b")
        d1 = _ed(calc_id=c1, energy=1.0, G=10.0)
        d2 = _ed(calc_id=c2, energy=2.0, G=20.0)
        E, G = _sum_energies((c1, c2), {c1: d1, c2: d2})
        assert pytest.approx(3.0) == E
        assert pytest.approx(30.0) == G

    def test_sp_energy_fallback(self) -> None:
        """When energy=None, sp_energy is used for E."""
        cid = CalcID(method_key="m", stage="r", species="x")
        ed = _ed(calc_id=cid, energy=None, sp_energy=7.0, G=10.0)
        E, _G = _sum_energies((cid,), {cid: ed})
        assert pytest.approx(7.0) == E


class TestArgmin:
    def test_picks_smallest(self) -> None:
        assert _argmin([3.0, 1.0, 2.0]) == 1

    def test_all_none(self) -> None:
        assert _argmin([None, None]) == 0

    def test_single_value(self) -> None:
        assert _argmin([5.0]) == 0

    def test_none_mixed(self) -> None:
        assert _argmin([None, 2.0, None]) == 1


class TestNormalize:
    def _sd(self, name: str, E: float | None, G: float | None) -> StageData:
        return StageData(name=name, E=E, G=G)

    def test_ref_not_found(self) -> None:
        stages = [self._sd("reactants", 10.0, 20.0)]
        result = _normalize(stages, "nonexistent")
        assert result[0].rel("E") is None  # no normalization performed

    def test_normal_subtraction(self) -> None:
        stages = [
            self._sd("reactants", 10.0, 100.0),
            self._sd("ts", 15.0, 110.0),
        ]
        result = _normalize(stages, "reactants")
        assert result[0].rel("E") == pytest.approx(0.0)
        assert result[0].rel("G") == pytest.approx(0.0)
        assert result[1].rel("E") == pytest.approx(5.0)
        assert result[1].rel("G") == pytest.approx(10.0)

    def test_partial_rel_E_none(self) -> None:
        """NI profile: E=None → _rel has only G key."""
        stages = [
            self._sd("reactants", None, 100.0),
            self._sd("ts", None, 110.0),
        ]
        result = _normalize(stages, "reactants")
        assert result[0].rel("E") is None
        assert result[0].rel("G") == pytest.approx(0.0)
        assert result[1].rel("E") is None
        assert result[1].rel("G") == pytest.approx(10.0)


class TestGniForStage:
    """Unit tests for _g_ni_for_stage."""

    def _cid(self, sp: str) -> CalcID:
        return CalcID(method_key="m", stage="r", species=sp)

    def test_missing_ref_data(self) -> None:
        """ref_cid not in extracted → None."""
        ni = NiStageRef(
            ref_cids=(self._cid("missing"),),
            trans_cids=(self._cid("x"),),
        )
        assert _g_ni_for_stage(ni, {}) is None

    def test_missing_s_trans_on_ref(self) -> None:
        ref_cid = self._cid("ref")
        trans_cid = self._cid("trans")
        ni = NiStageRef(ref_cids=(ref_cid,), trans_cids=(trans_cid,))
        extracted = {
            ref_cid: _ed(calc_id=ref_cid, H=10.0, s_corr=0.05, s_trans=None, temperature=298.15),
            trans_cid: _ed(calc_id=trans_cid, s_trans=0.03),
        }
        assert _g_ni_for_stage(ni, extracted) is None

    def test_missing_trans_data(self) -> None:
        ref_cid = self._cid("ref")
        trans_cid = self._cid("trans")
        ni = NiStageRef(ref_cids=(ref_cid,), trans_cids=(trans_cid,))
        extracted = {
            ref_cid: _ed(calc_id=ref_cid, H=10.0, s_corr=0.05, s_trans=0.03, temperature=298.15),
            # trans_cid missing from extracted
        }
        assert _g_ni_for_stage(ni, extracted) is None

    def test_no_temperature(self) -> None:
        ref_cid = self._cid("ref")
        trans_cid = self._cid("trans")
        ni = NiStageRef(ref_cids=(ref_cid,), trans_cids=(trans_cid,))
        extracted = {
            ref_cid: _ed(calc_id=ref_cid, H=10.0, s_corr=0.05, s_trans=0.03, temperature=None),
            trans_cid: _ed(calc_id=trans_cid, s_trans=0.03),
        }
        assert _g_ni_for_stage(ni, extracted) is None

    def test_happy_path_no_ssc(self) -> None:
        """Complete data, apply_ssc=False → computed G_ni value."""
        from pya3eda import constants as C
        from pya3eda.utils import convert_unit

        ref_cid = self._cid("ref")
        trans_cid = self._cid("trans")
        ni = NiStageRef(
            ref_cids=(ref_cid,),
            trans_cids=(trans_cid,),
            apply_ssc_to_g_ni=False,
        )
        T = 298.15
        H = -100.0  # kcal/mol
        s_corr = 0.066  # kcal/(mol·K)
        s_trans = 0.038  # kcal/(mol·K)

        extracted = {
            ref_cid: _ed(calc_id=ref_cid, H=H, s_corr=s_corr, s_trans=s_trans, temperature=T),
            trans_cid: _ed(calc_id=trans_cid, s_trans=s_trans, temperature=T),
        }

        result = _g_ni_for_stage(ni, extracted)
        assert result is not None

        # Manual calculation
        h_trans = convert_unit(2.5 * C.MOLAR_GAS_CONSTANT * T, "J/mol", "kcal/mol")
        h_nontrans = H - h_trans
        s_nontrans = s_corr - s_trans
        s_trans_sum = s_trans  # one trans contributor
        g_ni_expected = h_nontrans + 1 * h_trans - T * (s_nontrans + s_trans_sum)
        assert result == pytest.approx(g_ni_expected, rel=1e-9)

    def test_happy_path_with_ssc(self) -> None:
        """apply_ssc=True → standard-state correction added."""

        ref_cid = self._cid("ref")
        trans_cid = self._cid("trans")
        ni = NiStageRef(
            ref_cids=(ref_cid,),
            trans_cids=(trans_cid,),
            apply_ssc_to_g_ni=True,
        )
        T = 298.15
        H = -100.0
        s_corr = 0.066
        s_trans = 0.038

        extracted = {
            ref_cid: _ed(calc_id=ref_cid, H=H, s_corr=s_corr, s_trans=s_trans, temperature=T),
            trans_cid: _ed(calc_id=trans_cid, s_trans=s_trans, temperature=T),
        }

        result = _g_ni_for_stage(ni, extracted)
        result_no_ssc = _g_ni_for_stage(
            NiStageRef(ref_cids=(ref_cid,), trans_cids=(trans_cid,), apply_ssc_to_g_ni=False),
            extracted,
        )
        ssc = standard_state_correction(T)
        assert result == pytest.approx(result_no_ssc + 1 * ssc, rel=1e-9)


class TestBuildStageBest:
    """Tests for _build_stage_best with alternatives."""

    def _make_specs(
        self,
    ) -> tuple[
        StageSpec,
        ProfileSpec,
        dict[CalcID, ExtractedData],
    ]:
        # Primary candidate: E=10, G=100
        c_prim = CalcID(method_key="m", stage="preTS", species="a", calc_type="full_cat")
        # Alternative: E=5, G=200  (better E, worse G)
        c_alt = CalcID(method_key="m", stage="preTS", species="b", calc_type="full_cat")

        alt = StageAlt(calc_ids=(c_alt,), label="alt-label")
        stage_spec = StageSpec(
            name="preTS",
            calc_ids=(c_prim,),
            label="prim-label",
            alternatives=(alt,),
        )
        pid = ProfileID(method_key="m", catalyst="cat", calc_type="full_cat")
        pspec = ProfileSpec(id=pid, stages=(stage_spec,), selection_leader=True)

        extracted = {
            c_prim: _ed(calc_id=c_prim, energy=10.0, G=100.0),
            c_alt: _ed(calc_id=c_alt, energy=5.0, G=200.0),
        }
        return stage_spec, pspec, extracted

    def test_leader_picks_best(self) -> None:
        stage_spec, pspec, extracted = self._make_specs()
        selections: dict = {}
        sd = _build_stage_best(stage_spec, pspec, extracted, selections)
        # Best E → candidate 1 (idx 1, E=5.0)
        assert pytest.approx(5.0) == sd.E
        # Best G → candidate 0 (idx 0, G=100.0)
        assert pytest.approx(100.0) == sd.G
        # Selection recorded
        assert len(selections) == 1

    def test_follower_reuses_selection(self) -> None:
        stage_spec, pspec, extracted = self._make_specs()
        selections: dict = {}
        # Leader run
        _build_stage_best(stage_spec, pspec, extracted, selections)

        # Follower: same key, but not selection_leader
        pid_fol = ProfileID(method_key="m", catalyst="cat", calc_type="frz_cat")
        pspec_fol = ProfileSpec(id=pid_fol, stages=(stage_spec,), selection_leader=False)
        sd_fol = _build_stage_best(stage_spec, pspec_fol, extracted, selections)
        # Should use same indices as leader
        assert pytest.approx(5.0) == sd_fol.E
        assert pytest.approx(100.0) == sd_fol.G

    def test_follower_missing_data_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Follower reusing a leader index with no data → None + warning (no fallback)."""
        import logging

        stage_spec, pspec, extracted = self._make_specs()
        selections: dict = {}
        _build_stage_best(stage_spec, pspec, extracted, selections)  # leader records

        pid_fol = ProfileID(method_key="m", catalyst="cat", calc_type="frz_cat")
        pspec_fol = ProfileSpec(id=pid_fol, stages=(stage_spec,), selection_leader=False)
        with caplog.at_level(logging.WARNING):
            sd_fol = _build_stage_best(stage_spec, pspec_fol, {}, selections)
        assert sd_fol.E is None
        assert sd_fol.G is None
        assert "left as None" in caplog.text

    def test_is_ni_overrides_G(self) -> None:
        """When is_ni=True and g_ni_ref is present, G is overridden."""
        c_prim = CalcID(method_key="m", stage="preTS", species="a", calc_type="full_cat")
        ref_cid = CalcID(method_key="m", stage="r", species="ref")
        trans_cid = CalcID(method_key="m", stage="r", species="trans")

        ni_ref = NiStageRef(
            ref_cids=(ref_cid,),
            trans_cids=(trans_cid,),
            apply_ssc_to_g_ni=False,
        )
        stage_spec = StageSpec(
            name="preTS",
            calc_ids=(c_prim,),
            label="lbl",
            ni_ref=ni_ref,
        )
        pid = ProfileID(method_key="m", catalyst="cat", calc_type="full_cat")
        pspec = ProfileSpec(id=pid, stages=(stage_spec,), selection_leader=True)

        extracted = {
            c_prim: _ed(calc_id=c_prim, energy=10.0, G=100.0),
            ref_cid: _ed(calc_id=ref_cid, H=-50.0, s_corr=0.06, s_trans=0.03, temperature=298.15),
            trans_cid: _ed(calc_id=trans_cid, s_trans=0.03, temperature=298.15),
        }
        sd = _build_stage_best(stage_spec, pspec, extracted, {}, is_ni=True)
        assert sd.E is None  # NI always sets E=None
        assert sd.G is not None
        assert sd.calc_type == "ni"


class TestBuildOne:
    """Test _build_one integrating _sum_energies + _normalize."""

    def test_ni_profile_has_no_E(self) -> None:
        """NI profile sets E=None on all stages."""
        c_r = CalcID(method_key="m", stage="reactants", species="x", calc_type="full_cat")
        c_ts = CalcID(method_key="m", stage="ts", species="y", calc_type="full_cat")

        stages = (
            StageSpec(name="reactants", calc_ids=(c_r,), label="r"),
            StageSpec(name="ts", calc_ids=(c_ts,), label="ts"),
        )
        pid = ProfileID(method_key="m", catalyst="cat", calc_type="full_cat")
        pspec = ProfileSpec(id=pid, stages=stages, selection_leader=True, ref_stage="reactants")

        extracted = {
            c_r: _ed(calc_id=c_r, energy=10.0, G=100.0),
            c_ts: _ed(calc_id=c_ts, energy=20.0, G=110.0),
        }

        pd = _build_one(pspec, extracted, {}, is_ni=True)
        assert pd is not None
        assert pd.profile_id.calc_type == "ni"
        for s in pd.stages:
            assert s.E is None
            assert s.calc_type == "ni"

    def test_ni_profile_with_ni_ref(self) -> None:
        """NI profile uses ni_ref for G on complex stages."""
        c_r = CalcID(method_key="m", stage="reactants", species="x", calc_type="full_cat")
        c_ts = CalcID(method_key="m", stage="ts", species="y", calc_type="full_cat")
        ref_cid = CalcID(method_key="m", stage="r", species="ref")
        trans_cid = CalcID(method_key="m", stage="r", species="trans")

        ni_ref = NiStageRef(
            ref_cids=(ref_cid,),
            trans_cids=(trans_cid,),
            apply_ssc_to_g_ni=False,
        )
        stages = (
            StageSpec(name="reactants", calc_ids=(c_r,), label="r"),
            StageSpec(name="ts", calc_ids=(c_ts,), label="ts", ni_ref=ni_ref),
        )
        pid = ProfileID(method_key="m", catalyst="cat", calc_type="full_cat")
        pspec = ProfileSpec(id=pid, stages=stages, selection_leader=True, ref_stage="reactants")

        extracted = {
            c_r: _ed(calc_id=c_r, energy=10.0, G=100.0),
            c_ts: _ed(calc_id=c_ts, energy=20.0, G=110.0),
            ref_cid: _ed(calc_id=ref_cid, H=-50.0, s_corr=0.06, s_trans=0.03, temperature=298.15),
            trans_cid: _ed(calc_id=trans_cid, s_trans=0.03, temperature=298.15),
        }

        pd = _build_one(pspec, extracted, {}, is_ni=True)
        assert pd is not None
        ts_stage = next(s for s in pd.stages if s.name == "ts")
        # G should come from _g_ni_for_stage, not from the normal sum
        assert ts_stage.G != 110.0  # not the raw value

    def test_regular_profile(self) -> None:
        """Non-NI profile preserves E and G."""
        c_r = CalcID(method_key="m", stage="reactants", species="x")
        c_ts = CalcID(method_key="m", stage="ts", species="y")
        stages = (
            StageSpec(name="reactants", calc_ids=(c_r,), label="r"),
            StageSpec(name="ts", calc_ids=(c_ts,), label="ts"),
        )
        pid = ProfileID(method_key="m", calc_type=None)
        pspec = ProfileSpec(id=pid, stages=stages, ref_stage="reactants")

        extracted = {
            c_r: _ed(calc_id=c_r, energy=10.0, G=100.0),
            c_ts: _ed(calc_id=c_ts, energy=20.0, G=110.0),
        }

        pd = _build_one(pspec, extracted, {})
        assert pd is not None
        ts_stage = next(s for s in pd.stages if s.name == "ts")
        assert pytest.approx(20.0) == ts_stage.E
        assert pytest.approx(110.0) == ts_stage.G
        assert ts_stage.rel("E") == pytest.approx(10.0)
        assert ts_stage.rel("G") == pytest.approx(10.0)

    def test_build_one_with_alternatives(self) -> None:
        """_build_one delegates to _build_stage_best when alternatives exist."""
        c_r = CalcID(method_key="m", stage="reactants", species="x", calc_type="full_cat")
        c_ts_a = CalcID(method_key="m", stage="ts", species="a", calc_type="full_cat")
        c_ts_b = CalcID(method_key="m", stage="ts", species="b", calc_type="full_cat")

        alt = StageAlt(calc_ids=(c_ts_b,), label="alt")
        stages = (
            StageSpec(name="reactants", calc_ids=(c_r,), label="r"),
            StageSpec(name="ts", calc_ids=(c_ts_a,), label="ts", alternatives=(alt,)),
        )
        pid = ProfileID(method_key="m", catalyst="cat", calc_type="full_cat")
        pspec = ProfileSpec(id=pid, stages=stages, selection_leader=True, ref_stage="reactants")

        extracted = {
            c_r: _ed(calc_id=c_r, energy=10.0, G=100.0),
            c_ts_a: _ed(calc_id=c_ts_a, energy=20.0, G=110.0),
            c_ts_b: _ed(calc_id=c_ts_b, energy=15.0, G=115.0),
        }

        pd = _build_one(pspec, extracted, {})
        assert pd is not None
        ts_stage = next(s for s in pd.stages if s.name == "ts")
        # Best E = 15.0 (alt), Best G = 110.0 (primary)
        assert pytest.approx(15.0) == ts_stage.E
        assert pytest.approx(110.0) == ts_stage.G


# ===================================================================
# Unit tests — barriers.py internals
# ===================================================================


def _sd(name: str, E: float | None = None, G: float | None = None) -> StageData:
    return StageData(name=name, E=E, G=G)


def _stages_dict(*stages: StageData) -> dict[str, StageData]:
    return {s.name: s for s in stages}


class TestShouldUsePreTS:
    def test_returns_true_when_preTS_below_reactants(self) -> None:
        stages = _stages_dict(
            _sd("reactants", G=100.0),
            _sd("preTS", G=80.0),
            _sd("ts", G=150.0),
        )
        assert _should_use_preTS(stages, "G") is True

    def test_returns_false_when_preTS_above_reactants(self) -> None:
        stages = _stages_dict(
            _sd("reactants", G=80.0),
            _sd("preTS", G=100.0),
            _sd("ts", G=150.0),
        )
        assert _should_use_preTS(stages, "G") is False

    def test_returns_false_when_reactants_missing(self) -> None:
        stages = _stages_dict(_sd("preTS", G=80.0), _sd("ts", G=150.0))
        assert _should_use_preTS(stages, "G") is False

    def test_returns_false_when_preTS_missing(self) -> None:
        stages = _stages_dict(_sd("reactants", G=100.0), _sd("ts", G=150.0))
        assert _should_use_preTS(stages, "G") is False

    def test_returns_false_when_values_none(self) -> None:
        stages = _stages_dict(
            _sd("reactants", G=None),
            _sd("preTS", G=100.0),
        )
        assert _should_use_preTS(stages, "G") is False


class TestBarrier:
    def test_none_stages(self) -> None:
        assert _barrier(None, "G", use_preTS=False) is None

    def test_missing_ts(self) -> None:
        stages = _stages_dict(_sd("reactants", G=100.0))
        assert _barrier(stages, "G", use_preTS=False) is None

    def test_ts_value_none(self) -> None:
        stages = _stages_dict(
            _sd("reactants", G=100.0),
            _sd("ts", G=None),
        )
        assert _barrier(stages, "G", use_preTS=False) is None

    def test_normal_barrier(self) -> None:
        stages = _stages_dict(
            _sd("reactants", G=100.0),
            _sd("ts", G=150.0),
        )
        assert _barrier(stages, "G", use_preTS=False) == pytest.approx(50.0)

    def test_use_preTS_true(self) -> None:
        stages = _stages_dict(
            _sd("reactants", G=100.0),
            _sd("preTS", G=80.0),
            _sd("ts", G=150.0),
        )
        assert _barrier(stages, "G", use_preTS=True) == pytest.approx(70.0)

    def test_use_preTS_missing_falls_through(self) -> None:
        """use_preTS=True but no preTS stage → falls through to reactants."""
        stages = _stages_dict(
            _sd("reactants", G=100.0),
            _sd("ts", G=150.0),
        )
        assert _barrier(stages, "G", use_preTS=True) == pytest.approx(50.0)

    def test_use_preTS_value_none_falls_through(self) -> None:
        """use_preTS=True but preTS.G=None → falls through to reactants."""
        stages = _stages_dict(
            _sd("reactants", G=100.0),
            _sd("preTS", G=None),
            _sd("ts", G=150.0),
        )
        assert _barrier(stages, "G", use_preTS=True) == pytest.approx(50.0)

    def test_reactants_missing(self) -> None:
        stages = _stages_dict(_sd("ts", G=150.0))
        assert _barrier(stages, "G", use_preTS=False) is None

    def test_reactants_value_none(self) -> None:
        stages = _stages_dict(
            _sd("reactants", G=None),
            _sd("ts", G=150.0),
        )
        assert _barrier(stages, "G", use_preTS=False) is None

    def test_E_surface(self) -> None:
        stages = _stages_dict(
            _sd("reactants", E=50.0),
            _sd("ts", E=80.0),
        )
        assert _barrier(stages, "E", use_preTS=False) == pytest.approx(30.0)


class TestComputeForCatalyst:
    """Test _compute_for_catalyst with constructed profile dicts."""

    def _profile(self, calc_type: str, stages: tuple[StageData, ...]) -> ProfileData:
        pid = ProfileID(method_key="m", catalyst="cat", calc_type=calc_type)
        return ProfileData(profile_id=pid, stages=stages)

    def test_g_ni_row_produced(self) -> None:
        """full_cat + ni + nocat → G_ni DeltaDeltaData row produced."""
        r, ts, p = 100.0, 150.0, 90.0

        full = self._profile(
            "full_cat",
            (
                _sd("reactants", G=r),
                _sd("ts", G=ts),
                _sd("products", G=p),
            ),
        )
        nocat = self._profile(
            "nocat",
            (
                _sd("reactants", G=r + 5),
                _sd("ts", G=ts + 10),
                _sd("products", G=p),
            ),
        )
        ni = self._profile(
            "ni",
            (
                _sd("reactants", G=r + 3),
                _sd("ts", G=ts + 7),
                _sd("products", G=p),
            ),
        )

        profiles = {pd.profile_id: pd for pd in (full, nocat, ni)}
        results = _compute_for_catalyst("m", "cat", "opt", None, profiles)

        gni = [d for d in results if d.energy_type == "G_ni"]
        assert len(gni) == 1
        assert gni[0].barrier_ni is not None
        assert gni[0].dd_ni is not None

    def test_g_ni_skipped_when_ni_missing(self) -> None:
        """Without NI profile, G_ni row is skipped."""
        full = self._profile(
            "full_cat",
            (
                _sd("reactants", G=100.0),
                _sd("ts", G=150.0),
            ),
        )
        nocat = self._profile(
            "nocat",
            (
                _sd("reactants", G=105.0),
                _sd("ts", G=160.0),
            ),
        )
        profiles = {pd.profile_id: pd for pd in (full, nocat)}
        results = _compute_for_catalyst("m", "cat", "opt", None, profiles)

        gni = [d for d in results if d.energy_type == "G_ni"]
        assert len(gni) == 0
        # But E and G rows should still exist
        eg = [d for d in results if d.energy_type in ("E", "G")]
        assert len(eg) > 0

    def test_use_preTS_affects_all_calc_types(self) -> None:
        """When preTS < reactants on full_cat, all barriers use preTS baseline."""
        full = self._profile(
            "full_cat",
            (
                _sd("reactants", G=100.0),
                _sd("preTS", G=80.0),
                _sd("ts", G=150.0),
                _sd("postTS", G=90.0),
                _sd("products", G=85.0),
            ),
        )
        frz = self._profile(
            "frz_cat",
            (
                _sd("reactants", G=102.0),
                _sd("preTS", G=82.0),
                _sd("ts", G=155.0),
                _sd("postTS", G=92.0),
                _sd("products", G=87.0),
            ),
        )
        nocat = self._profile(
            "nocat",
            (
                _sd("reactants", G=105.0),
                _sd("ts", G=160.0),
                _sd("products", G=88.0),
            ),
        )

        profiles = {pd.profile_id: pd for pd in (full, frz, nocat)}
        results = _compute_for_catalyst("m", "cat", "opt", None, profiles)

        g_rows = [d for d in results if d.energy_type == "G"]
        assert len(g_rows) == 1
        dd = g_rows[0]
        # full barrier = ts - preTS = 150 - 80 = 70
        assert dd.barrier_full == pytest.approx(70.0)
        # frz barrier = 155 - 82 = 73
        assert dd.barrier_frz == pytest.approx(73.0)


# ===================================================================
# extractor/data.py — edge cases (L77, L145, L200, L206)
# ===================================================================


class TestExtractOneEdgeCases:
    """Unit tests for _extract_one edge cases."""

    def test_non_successful_status_skipped(self, tmp_path: Path) -> None:
        """criteria != 'all' and non-SUCCESSFUL status → None."""
        from unittest.mock import patch

        from pya3eda.extractor.data import _extract_one

        cid = CalcID(method_key="m", stage="reactants", species="mol", mode="opt")
        spec = type(
            "Spec",
            (),
            {
                "id": cid,
                "output_path": tmp_path / "mol.out",
                "input_path": tmp_path / "mol.in",
            },
        )()
        (tmp_path / "mol.in").touch()
        with patch("pya3eda.extractor.data.get_status", return_value=("CRASH", "err")):
            result = _extract_one(spec, "SUCCESSFUL", {})
        assert result is None

    def test_empty_output_content(self, tmp_path: Path) -> None:
        """Output file exists but is empty → None."""
        from unittest.mock import patch

        from pya3eda.extractor.data import _extract_one
        from pya3eda.status.checker import Status

        cid = CalcID(method_key="m", stage="reactants", species="mol", mode="sp")
        spec = type(
            "Spec",
            (),
            {
                "id": cid,
                "output_path": tmp_path / "mol.out",
                "input_path": tmp_path / "mol.in",
            },
        )()
        (tmp_path / "mol.in").touch()
        (tmp_path / "mol.out").touch()  # empty file
        with patch("pya3eda.extractor.data.get_status", return_value=(Status.SUCCESSFUL, "ok")):
            result = _extract_one(spec, "all", {})
        assert result is None

    def test_sp_no_energy_returns_none(self, tmp_path: Path) -> None:
        """SP output without parseable energy → None."""
        from unittest.mock import patch

        from pya3eda.extractor.data import _extract_one
        from pya3eda.status.checker import Status

        cid = CalcID(method_key="m", stage="reactants", species="mol", mode="sp")
        spec = type(
            "Spec",
            (),
            {
                "id": cid,
                "output_path": tmp_path / "mol.out",
                "input_path": tmp_path / "mol.in",
                "solvent": "false",
                "is_fragmented": False,
            },
        )()
        (tmp_path / "mol.in").touch()
        (tmp_path / "mol.out").write_text("some output without energy")
        with patch("pya3eda.extractor.data.get_status", return_value=(Status.SUCCESSFUL, "ok")):
            result = _extract_one(spec, "all", {})
        assert result is None

    def test_eda_sp_no_eda_data_returns_none(self, tmp_path: Path) -> None:
        """EDA SP output without parseable EDA energies → None."""
        from unittest.mock import patch

        from pya3eda.extractor.data import _extract_one
        from pya3eda.status.checker import Status

        cid = CalcID(method_key="m", stage="ts", species="mol", mode="sp", calc_type="full_cat")
        spec = type(
            "Spec",
            (),
            {
                "id": cid,
                "output_path": tmp_path / "mol.out",
                "input_path": tmp_path / "mol.in",
                "solvent": "false",
                "is_fragmented": True,
            },
        )()
        (tmp_path / "mol.in").touch()
        (tmp_path / "mol.out").write_text("some output without EDA data")
        with patch("pya3eda.extractor.data.get_status", return_value=(Status.SUCCESSFUL, "ok")):
            result = _extract_one(spec, "all", {})
        assert result is None

    def test_sp_without_opt_thermo_fails_loud(self, tmp_path: Path) -> None:
        """SP with a parseable energy but no OPT thermo → loud IncompleteDataError."""
        from unittest.mock import patch

        from pya3eda.errors import IncompleteDataError
        from pya3eda.extractor.data import _extract_one
        from pya3eda.status.checker import Status

        cid = CalcID(method_key="m", stage="reactants", species="mol", mode="sp")
        spec = type(
            "Spec",
            (),
            {
                "id": cid,
                "output_path": tmp_path / "mol.out",
                "input_path": tmp_path / "mol.in",
                "solvent": "false",
                "is_fragmented": False,
            },
        )()
        (tmp_path / "mol.in").touch()
        (tmp_path / "mol.out").write_text("Final energy is -100.5 Ha\n")
        with (
            patch("pya3eda.extractor.data.get_status", return_value=(Status.SUCCESSFUL, "ok")),
            pytest.raises(IncompleteDataError, match="OPT thermo"),
        ):
            _extract_one(spec, "all", {})  # empty opt_cache

    def test_extract_all_aggregates_incomplete_errors(self, tmp_path: Path) -> None:
        """An OPT that parsed an energy but no thermo makes extract_all fail loud."""
        from unittest.mock import MagicMock, patch

        from pya3eda.errors import IncompleteDataError
        from pya3eda.extractor.data import extract_all
        from pya3eda.status.checker import Status

        cid = CalcID(method_key="m", stage="reactants", species="mol", mode="opt")
        out = tmp_path / "mol.out"
        out.write_text("Total energy = -100.500000\n")  # parses as energy; no thermo
        spec = type(
            "Spec",
            (),
            {
                "id": cid,
                "output_path": out,
                "input_path": tmp_path / "mol.in",
                "solvent": "false",
                "is_fragmented": False,
            },
        )()
        reg = MagicMock(all_calcs=[spec])
        with (
            patch("pya3eda.extractor.data.get_status", return_value=(Status.SUCCESSFUL, "ok")),
            pytest.raises(IncompleteDataError, match="Incomplete data for 1 computation"),
        ):
            extract_all(reg, criteria="all")


class TestParseSpEnergyBranches:
    def test_eda_without_cds(self) -> None:
        """EDA SP output with no SMD-CDS line skips the CDS correction."""
        from pya3eda.extractor.data import _parse_sp_energy

        content = "   10   -1814.1288377459      3.50e-09     00000 Convergence criterion met\n"
        spec = type("S", (), {"id": type("I", (), {"calc_type": "frz_cat"})()})()
        assert _parse_sp_energy(content, spec) is not None


class TestDeriveHG:
    """Fail-loud derivation of H/G from a present electronic energy."""

    _CID = CalcID(method_key="m", stage="reactants", species="mol", mode="opt")

    def test_gas_phase_skips_ssc(self) -> None:
        """Gas-phase H/G omit the standard-state correction."""
        from pya3eda.extractor.data import _derive_hg

        H, G = _derive_hg(self._CID, 10.0, 2.0, 0.01, 298.0, None, "false")
        assert pytest.approx(12.0) == H
        assert pytest.approx(12.0 - 298.0 * 0.01) == G

    def test_solvent_adds_ssc(self) -> None:
        """Solvent phase with a pressure adds the standard-state correction."""
        from pya3eda.extractor.data import _derive_hg
        from pya3eda.utils import standard_state_correction

        _H, G = _derive_hg(self._CID, 10.0, 2.0, 0.01, 298.0, 1.0, "smd")
        assert pytest.approx(12.0 - 298.0 * 0.01 + standard_state_correction(298.0, 1.0)) == G

    def test_missing_thermo_raises(self) -> None:
        """Energy present but h_corr/temperature missing → loud error naming them."""
        from pya3eda.errors import IncompleteDataError
        from pya3eda.extractor.data import _derive_hg

        with pytest.raises(IncompleteDataError, match=r"h_corr.*temperature"):
            _derive_hg(self._CID, 10.0, None, 0.01, None, None, "false")

    def test_solvent_missing_pressure_raises(self) -> None:
        """Solvent phase without a pressure → loud error (SSC cannot be applied)."""
        from pya3eda.errors import IncompleteDataError
        from pya3eda.extractor.data import _derive_hg

        with pytest.raises(IncompleteDataError, match="pressure"):
            _derive_hg(self._CID, 10.0, 2.0, 0.01, 298.0, None, "smd")


class TestComputeForCatalystBranches:
    def test_missing_full_cat_uses_no_pretts_baseline(self) -> None:
        """A catalyst with no full_cat profile falls back to use_preTS=False."""
        from pya3eda.extractor.barriers import _compute_for_catalyst

        result = _compute_for_catalyst("m", "cat", "opt", None, {})
        assert isinstance(result, list)
