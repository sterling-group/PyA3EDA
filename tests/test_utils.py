"""Tests for pya3eda.utils — unit conversion & thermodynamic corrections."""

from __future__ import annotations

import math

import pytest

from pya3eda import constants as C
from pya3eda.utils import convert_unit, read_text, standard_state_correction, write_text

# ===================================================================
# convert_unit
# ===================================================================


class TestConvertUnit:
    def test_hartree_to_kcal(self) -> None:
        result = convert_unit(1.0, "Ha", "kcal/mol")
        assert result == pytest.approx(C.HARTREE_TO_KCALMOL)

    def test_kcal_to_hartree(self) -> None:
        result = convert_unit(C.HARTREE_TO_KCALMOL, "kcal/mol", "Ha")
        assert result == pytest.approx(1.0, rel=1e-9)

    def test_hartree_to_kjmol(self) -> None:
        result = convert_unit(1.0, "Ha", "kJ/mol")
        assert result == pytest.approx(C.HARTREE_TO_KJMOL, rel=1e-9)

    def test_kjmol_to_kcal(self) -> None:
        result = convert_unit(4.184, "kJ/mol", "kcal/mol")
        assert result == pytest.approx(1.0, rel=1e-4)

    def test_cal_to_kcal(self) -> None:
        result = convert_unit(1000.0, "cal/mol.K", "kcal/mol.K")
        assert result == pytest.approx(1.0, rel=1e-9)

    def test_atm_to_pa(self) -> None:
        result = convert_unit(1.0, "atm", "Pa")
        assert result == pytest.approx(101325.0)

    def test_identity_same_units(self) -> None:
        assert convert_unit(42.0, "kcal/mol", "kcal/mol") == pytest.approx(42.0)

    def test_alias_au(self) -> None:
        result = convert_unit(1.0, "a.u.", "kcal/mol")
        assert result == pytest.approx(C.HARTREE_TO_KCALMOL)

    def test_case_insensitive(self) -> None:
        result = convert_unit(1.0, "HA", "kcal/mol")
        assert result == pytest.approx(C.HARTREE_TO_KCALMOL)

    def test_unknown_pair_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown unit conversion"):
            convert_unit(1.0, "furlongs", "smoots")


# ===================================================================
# standard_state_correction
# ===================================================================


class TestStandardStateCorrection:
    def test_298K_1atm(self) -> None:
        """At 298.15 K / 1 atm, SSC ≈ 1.89 kcal/mol."""
        ssc = standard_state_correction(298.15, 1.0)
        assert ssc == pytest.approx(1.89, abs=0.02)

    def test_increases_with_temperature(self) -> None:
        low = standard_state_correction(200.0)
        high = standard_state_correction(400.0)
        assert high > low

    def test_matches_manual_calculation(self) -> None:
        T = 298.15
        P_pa = 101325.0
        R = C.MOLAR_GAS_CONSTANT
        ratio = (R * T * C.M3_TO_L) / P_pa
        correction_j = R * T * math.log(ratio)
        expected_kcal = convert_unit(correction_j, "J/mol", "kcal/mol")
        assert standard_state_correction(T, 1.0) == pytest.approx(expected_kcal)


# ===================================================================
# read_text / write_text
# ===================================================================


class TestFileIO:
    def test_read_missing_returns_none(self, tmp_path) -> None:
        assert read_text(tmp_path / "does_not_exist.txt") is None

    def test_write_and_read_round_trip(self, tmp_path) -> None:
        path = tmp_path / "sub" / "test.txt"
        content = "hello, world\nsecond line\n"
        write_text(path, content)
        assert read_text(path) == content

    def test_write_creates_parent_dirs(self, tmp_path) -> None:
        path = tmp_path / "a" / "b" / "c" / "file.txt"
        write_text(path, "data")
        assert path.exists()
