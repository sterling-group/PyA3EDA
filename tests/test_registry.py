"""Tests for pya3eda.registry — CalcRegistry enumeration.

All tests are self-contained using inline Config objects.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pya3eda.config import (
    CatalystConfig,
    Config,
    LevelConfig,
    SpeciesConfig,
    TheoryConfig,
    load_config,
)
from pya3eda.ids import CalcID, ProfileID
from pya3eda.registry import CalcRegistry, build_method_key
from tests.synthetic_outputs import SAMPLE_CONFIG_YAML

# ===================================================================
# build_method_key
# ===================================================================


class TestBuildMethodKey:
    def test_basic(self) -> None:
        tc = TheoryConfig(method="wB97X-V", basis="def2-SVP", solvent="smd")
        assert build_method_key(tc) == "wB97X-V_def2-SVP_smd"

    def test_with_dispersion(self) -> None:
        tc = TheoryConfig(method="B3LYP", basis="6-31G*", dispersion="D3")
        result = build_method_key(tc)
        assert result == "B3LYP_D3_6-31G-asterisk-"
        # dispersion comes between method and basis

    def test_no_solvent_no_dispersion(self) -> None:
        tc = TheoryConfig(method="HF", basis="STO-3G")
        assert build_method_key(tc) == "HF_STO-3G"


# ===================================================================
# CalcRegistry — synthetic config (from YAML)
# ===================================================================


class TestRegistrySyntheticConfig:
    @pytest.fixture
    def registry(self, tmp_path: Path) -> CalcRegistry:
        cfg_path = tmp_path / "new.yaml"
        cfg_path.write_text(SAMPLE_CONFIG_YAML)
        cfg = load_config(cfg_path)
        return CalcRegistry(cfg, tmp_path)

    def test_method_keys(self, registry: CalcRegistry) -> None:
        assert registry.method_keys == ["wB97X-V_def2-SVP_smd"]

    def test_catalyst_order(self, registry: CalcRegistry) -> None:
        assert registry.catalyst_order == ["lip", "bf3"]

    def test_all_calcs_not_empty(self, registry: CalcRegistry) -> None:
        assert len(registry.all_calcs) > 0

    def test_all_profiles_not_empty(self, registry: CalcRegistry) -> None:
        assert len(registry.all_profiles) > 0

    def test_uncatalyzed_reactants_present(self, registry: CalcRegistry) -> None:
        """Individual reactants should be enumerated."""
        mk = "wB97X-V_def2-SVP_smd"
        cid_prop = CalcID(
            method_key=mk,
            catalyst=None,
            stage="reactants",
            species="prop2enal",
            mode="opt",
        )
        assert cid_prop in {s.id for s in registry.all_calcs}

    def test_uncatalyzed_ts(self, registry: CalcRegistry) -> None:
        mk = "wB97X-V_def2-SVP_smd"
        cid = CalcID(method_key=mk, catalyst=None, stage="ts", species="tscomplex", mode="opt")
        spec = registry.get(cid)
        assert spec.method_name == "wB97X-V"

    def test_catalyzed_calcs_have_three_calc_types(self, registry: CalcRegistry) -> None:
        """Each catalyzed stage should have full_cat, pol_cat, frz_cat."""
        calc_types = set()
        for spec in registry.all_calcs:
            if spec.id.catalyst == "lip" and spec.id.stage == "preTS" and spec.id.mode == "opt":
                calc_types.add(spec.id.calc_type)
        assert calc_types == {"full_cat", "pol_cat", "frz_cat"}

    def test_sp_calcs_have_sp_subfolder(self, registry: CalcRegistry) -> None:
        sp_calcs = registry.by_mode("sp")
        assert len(sp_calcs) > 0
        for spec in sp_calcs:
            assert spec.id.sp_subfolder == "wB97M-V_def2-TZVPPD_smd_sp"

    def test_get_nonexistent_raises(self, registry: CalcRegistry) -> None:
        fake = CalcID(method_key="fake", stage="ts", species="x")
        with pytest.raises(KeyError):
            registry.get(fake)

    def test_profiles_include_uncatalyzed(self, registry: CalcRegistry) -> None:
        mk = "wB97X-V_def2-SVP_smd"
        pid = ProfileID(method_key=mk, catalyst=None, calc_type=None, mode="opt")
        pspec = registry.get_profile(pid)
        assert len(pspec.stages) == 3  # reactants, ts, products

    def test_profiles_include_catalyzed(self, registry: CalcRegistry) -> None:
        mk = "wB97X-V_def2-SVP_smd"
        pid = ProfileID(method_key=mk, catalyst="lip", calc_type="full_cat", mode="opt")
        pspec = registry.get_profile(pid)
        assert len(pspec.stages) == 5  # reactants, preTS, ts, postTS, products


# ===================================================================
# CalcRegistry — minimal synthetic config
# ===================================================================


class TestRegistryMinimal:
    @pytest.fixture
    def mini_registry(self, tmp_path: Path) -> CalcRegistry:
        cfg = Config(
            levels=[LevelConfig(opt=TheoryConfig(method="HF", basis="STO-3G"))],
            reactants=[SpeciesConfig(name="A"), SpeciesConfig(name="B")],
            products=[SpeciesConfig(name="C")],
            catalysts=[CatalystConfig(name="cat1")],
        )
        return CalcRegistry(cfg, tmp_path)

    def test_method_key(self, mini_registry: CalcRegistry) -> None:
        assert mini_registry.method_keys == ["HF_STO-3G"]

    def test_reactant_calcs(self, mini_registry: CalcRegistry) -> None:
        names = {
            s.id.species
            for s in mini_registry.all_calcs
            if s.id.stage == "reactants" and s.id.catalyst is None and s.id.mode == "opt"
        }
        # Individual reactants + reactant combinations (both include=True by default)
        assert "A" in names
        assert "B" in names
        assert "A-B" in names

    def test_catalyzed_preTS(self, mini_registry: CalcRegistry) -> None:
        pre_ts = [
            s
            for s in mini_registry.all_calcs
            if s.id.stage == "preTS" and s.id.catalyst == "cat1" and s.id.mode == "opt"
        ]
        # preTS combos: cat1-A, cat1-B, cat1-A-B, each with 3 calc_types
        species_set = {s.id.species for s in pre_ts}
        assert "cat1-A" in species_set
        assert "cat1-B" in species_set
        assert "cat1-A-B" in species_set
        assert len(pre_ts) == 9  # 3 species x 3 calc_types

    def test_uncatalyzed_profile_stages(self, mini_registry: CalcRegistry) -> None:
        pid = ProfileID(method_key="HF_STO-3G", catalyst=None, calc_type=None, mode="opt")
        pspec = mini_registry.get_profile(pid)
        stage_names = [s.name for s in pspec.stages]
        assert stage_names == ["reactants", "ts", "products"]

    def test_catalyzed_profile_stages(self, mini_registry: CalcRegistry) -> None:
        pid = ProfileID(method_key="HF_STO-3G", catalyst="cat1", calc_type="full_cat", mode="opt")
        pspec = mini_registry.get_profile(pid)
        stage_names = [s.name for s in pspec.stages]
        assert stage_names == ["reactants", "preTS", "ts", "postTS", "products"]

    def test_by_method(self, mini_registry: CalcRegistry) -> None:
        result = mini_registry.by_method("HF_STO-3G")
        assert len(result) > 0
        assert all(s.id.method_key == "HF_STO-3G" for s in result)

    def test_by_mode(self, mini_registry: CalcRegistry) -> None:
        opt_calcs = mini_registry.by_mode("opt")
        assert len(opt_calcs) > 0
        sp_calcs = mini_registry.by_mode("sp")
        assert len(sp_calcs) == 0  # no SP in this config


# ===================================================================
# Property accessors (L87, L91)
# ===================================================================


class TestRegistryProperties:
    def test_config_property(self, tmp_path: Path) -> None:
        cfg = Config(
            levels=[LevelConfig(opt=TheoryConfig(method="HF", basis="STO-3G"))],
            reactants=[SpeciesConfig(name="mol_a")],
            products=[SpeciesConfig(name="mol_p")],
        )
        reg = CalcRegistry(cfg, tmp_path)
        assert reg.config is cfg

    def test_base_dir_property(self, tmp_path: Path) -> None:
        cfg = Config(
            levels=[LevelConfig(opt=TheoryConfig(method="HF", basis="STO-3G"))],
            reactants=[SpeciesConfig(name="mol_a")],
            products=[SpeciesConfig(name="mol_p")],
        )
        reg = CalcRegistry(cfg, tmp_path)
        assert reg.base_dir == tmp_path

    def test_profiles_for_method(self, tmp_path: Path) -> None:
        cfg = Config(
            levels=[LevelConfig(opt=TheoryConfig(method="HF", basis="STO-3G"))],
            reactants=[SpeciesConfig(name="mol_a")],
            products=[SpeciesConfig(name="mol_p")],
        )
        reg = CalcRegistry(cfg, tmp_path)
        profiles = reg.profiles_for_method("HF_STO-3G")
        assert len(profiles) > 0
        assert all(p.id.method_key == "HF_STO-3G" for p in profiles)
        # Non-existent method
        assert reg.profiles_for_method("NONEXISTENT") == []


# ===================================================================
# postTS alternatives (L667-696) — requires >1 included product
# ===================================================================


class TestPostTSAlternatives:
    def test_multi_product_generates_alternatives(self, tmp_path: Path) -> None:
        """Catalyst + 2 included products + 1 free: postTS alternatives + free_p loop."""
        cfg = Config(
            levels=[LevelConfig(opt=TheoryConfig(method="HF", basis="STO-3G"))],
            reactants=[SpeciesConfig(name="r1")],
            products=[
                SpeciesConfig(name="p1"),
                SpeciesConfig(name="p2"),
                SpeciesConfig(name="p_free", include=False),
            ],
            catalysts=[CatalystConfig(name="cat1")],
        )
        reg = CalcRegistry(cfg, tmp_path)
        # Should have postTS calcs for both full combo and individual subsets
        post_ts = [c for c in reg.all_calcs if c.id.stage == "postTS" and c.id.catalyst == "cat1"]
        # At least the main postTS + alternatives
        assert len(post_ts) >= 2

        # The profile should have alternatives in its postTS stage
        profiles = reg.all_profiles
        catalyzed = [p for p in profiles if p.id.catalyst == "cat1"]
        assert len(catalyzed) > 0
        for pspec in catalyzed:
            post_stages = [s for s in pspec.stages if s.name == "postTS"]
            if post_stages:
                assert post_stages[0].alternatives is not None


# ===================================================================
# Duplicate CalcID detection (L310) — merged OPT levels
# ===================================================================


class TestDuplicateDetection:
    def test_duplicate_opt_levels_deduplicated(self, tmp_path: Path) -> None:
        """Two levels with same OPT theory → CalcIDs deduplicated."""
        same_opt = TheoryConfig(method="HF", basis="STO-3G")
        cfg = Config(
            levels=[
                LevelConfig(opt=same_opt),
                LevelConfig(opt=same_opt, sp=[TheoryConfig(method="MP2", basis="cc-pVDZ")]),
            ],
            reactants=[SpeciesConfig(name="mol_a")],
            products=[SpeciesConfig(name="mol_p")],
        )
        reg = CalcRegistry(cfg, tmp_path)
        # OPT calcs should only appear once despite two levels with same OPT
        opt_calcs = reg.by_mode("opt")
        cids = [c.id for c in opt_calcs]
        assert len(cids) == len(set(cids))


class TestMethodKeyDeduplication:
    def test_levels_differing_only_in_eda2_share_method_key(self, tmp_path: Path) -> None:
        """Two unmerged levels whose OPT differs only in eda2 dedupe to one method_key."""
        cfg = Config(
            levels=[
                LevelConfig(opt=TheoryConfig(method="HF", basis="STO-3G")),
                LevelConfig(opt=TheoryConfig(method="HF", basis="STO-3G", eda2=0)),
            ],
            reactants=[SpeciesConfig(name="r1")],
            products=[SpeciesConfig(name="p1")],
        )
        reg = CalcRegistry(cfg, tmp_path)
        assert reg.method_keys == ["HF_STO-3G"]
