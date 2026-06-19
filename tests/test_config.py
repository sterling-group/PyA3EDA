"""Tests for pya3eda.config — YAML loading and validation.

All tests are self-contained using synthetic YAML config.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pya3eda.config import (
    Config,
    LevelConfig,
    SpeciesConfig,
    TheoryConfig,
    load_config,
)
from pya3eda.errors import ConfigError
from tests.synthetic_outputs import SAMPLE_CONFIG_YAML

# ===================================================================
# TheoryConfig
# ===================================================================


class TestTheoryConfig:
    def test_basic_creation(self) -> None:
        tc = TheoryConfig(method="wB97X-V", basis="def2-SVP")
        assert tc.method == "wB97X-V"
        assert tc.basis == "def2-SVP"
        assert tc.dispersion is None
        assert tc.solvent is None
        assert tc.eda2 is None

    def test_eda2_validation(self) -> None:
        TheoryConfig(method="m", basis="b", eda2=0)
        TheoryConfig(method="m", basis="b", eda2=1)
        TheoryConfig(method="m", basis="b", eda2=2)

    def test_eda2_invalid_value(self) -> None:
        with pytest.raises(ValueError, match="eda2 must be 0, 1, or 2"):
            TheoryConfig(method="m", basis="b", eda2=3)

    def test_frozen(self) -> None:
        tc = TheoryConfig(method="m", basis="b")
        with pytest.raises(ValidationError):  # frozen model
            tc.method = "other"

    def test_dispersion_bool_false(self) -> None:
        """YAML bare ``false`` (parsed as bool) is coerced to string."""
        tc = TheoryConfig(method="m", basis="b", dispersion=False)
        assert tc.dispersion == "false"
        assert isinstance(tc.dispersion, str)

    def test_dispersion_bool_true(self) -> None:
        tc = TheoryConfig(method="m", basis="b", dispersion=True)
        assert tc.dispersion == "true"

    def test_solvent_bool_false(self) -> None:
        tc = TheoryConfig(method="m", basis="b", solvent=False)
        assert tc.solvent == "false"
        assert isinstance(tc.solvent, str)

    def test_dispersion_string_passthrough(self) -> None:
        tc = TheoryConfig(method="m", basis="b", dispersion="d3bj")
        assert tc.dispersion == "d3bj"

    def test_dispersion_none_unchanged(self) -> None:
        tc = TheoryConfig(method="m", basis="b", dispersion=None)
        assert tc.dispersion is None


# ===================================================================
# Config
# ===================================================================


class TestConfig:
    def test_minimal_valid(self) -> None:
        cfg = Config(
            levels=[LevelConfig(opt=TheoryConfig(method="hf", basis="sto-3g"))],
            reactants=[SpeciesConfig(name="A")],
            products=[SpeciesConfig(name="B")],
        )
        assert len(cfg.levels) == 1
        assert cfg.catalysts == []

    def test_at_least_one_level(self) -> None:
        with pytest.raises(ValueError, match="At least one level"):
            Config(
                levels=[],
                reactants=[SpeciesConfig(name="A")],
                products=[SpeciesConfig(name="B")],
            )

    def test_at_least_one_reactant(self) -> None:
        with pytest.raises(ValueError, match="At least one reactant"):
            Config(
                levels=[LevelConfig(opt=TheoryConfig(method="hf", basis="b"))],
                reactants=[],
                products=[SpeciesConfig(name="B")],
            )

    def test_at_least_one_product(self) -> None:
        with pytest.raises(ValueError, match="At least one product"):
            Config(
                levels=[LevelConfig(opt=TheoryConfig(method="hf", basis="b"))],
                reactants=[SpeciesConfig(name="A")],
                products=[],
            )

    def test_merge_duplicate_opts(self) -> None:
        """Two levels with the same OPT should merge their SP lists."""
        opt = TheoryConfig(method="hf", basis="sto-3g")
        sp1 = TheoryConfig(method="mp2", basis="cc-pVDZ")
        sp2 = TheoryConfig(method="b3lyp", basis="6-31G*")

        cfg = Config(
            levels=[
                LevelConfig(opt=opt, sp=[sp1]),
                LevelConfig(opt=opt, sp=[sp2]),
            ],
            reactants=[SpeciesConfig(name="A")],
            products=[SpeciesConfig(name="B")],
        )
        assert len(cfg.levels) == 1
        assert len(cfg.levels[0].sp) == 2
        assert sp1 in cfg.levels[0].sp
        assert sp2 in cfg.levels[0].sp

    def test_duplicate_sp_rejected(self) -> None:
        opt = TheoryConfig(method="hf", basis="sto-3g")
        sp = TheoryConfig(method="mp2", basis="cc-pVDZ")

        with pytest.raises(ValueError, match="Duplicate SP"):
            Config(
                levels=[
                    LevelConfig(opt=opt, sp=[sp]),
                    LevelConfig(opt=opt, sp=[sp]),
                ],
                reactants=[SpeciesConfig(name="A")],
                products=[SpeciesConfig(name="B")],
            )


# ===================================================================
# load_config
# ===================================================================


class TestLoadConfig:
    def test_load_synthetic_config(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "new.yaml"
        cfg_path.write_text(SAMPLE_CONFIG_YAML)
        cfg = load_config(cfg_path)
        assert len(cfg.levels) == 1
        assert cfg.levels[0].opt.method == "wB97X-V"
        assert cfg.levels[0].opt.basis == "def2-SVP"
        assert cfg.levels[0].opt.solvent == "smd"
        assert len(cfg.levels[0].sp) == 1
        assert cfg.levels[0].sp[0].method == "wB97M-V"
        assert cfg.levels[0].sp[0].eda2 == 1
        assert len(cfg.catalysts) == 2
        assert [c.name for c in cfg.catalysts] == ["lip", "bf3"]
        assert len(cfg.reactants) == 2
        assert cfg.reactants[0].name == "prop2enal"
        assert cfg.reactants[0].include is True
        assert cfg.reactants[1].name == "buta13diene"
        assert cfg.reactants[1].include is False
        assert len(cfg.products) == 1
        assert cfg.products[0].name == "cyclohex3ene1carbaldehyde"

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("- just a list\n")
        with pytest.raises(ConfigError, match="YAML mapping"):
            load_config(bad_file)

    def test_schema_violation_wrapped(self, tmp_path: Path) -> None:
        """A Pydantic validation failure surfaces as ConfigError."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("levels: []\nreactants: []\nproducts: []\n")
        with pytest.raises(ConfigError, match="Invalid configuration"):
            load_config(bad_file)
