"""Tests for pya3eda.ids — data model identity and hashing."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pya3eda.ids import CalcID, ExtractedData, ProfileID


class TestCalcID:
    def test_frozen_hashable(self) -> None:
        cid = CalcID(method_key="mk", stage="ts", species="mol")
        assert hash(cid) is not None
        d = {cid: "value"}
        assert d[cid] == "value"

    def test_equality(self) -> None:
        a = CalcID(method_key="mk", stage="ts", species="mol")
        b = CalcID(method_key="mk", stage="ts", species="mol")
        assert a == b

    def test_inequality(self) -> None:
        a = CalcID(method_key="mk", stage="ts", species="mol")
        b = CalcID(method_key="mk", stage="ts", species="other")
        assert a != b

    def test_defaults(self) -> None:
        cid = CalcID(method_key="mk", stage="r", species="s")
        assert cid.catalyst is None
        assert cid.calc_type is None
        assert cid.mode == "opt"
        assert cid.sp_subfolder is None

    def test_frozen(self) -> None:
        cid = CalcID(method_key="mk", stage="r", species="s")
        with pytest.raises(ValidationError):
            cid.species = "new"


class TestProfileID:
    def test_frozen_hashable(self) -> None:
        pid = ProfileID(method_key="mk")
        assert hash(pid) is not None

    def test_defaults(self) -> None:
        pid = ProfileID(method_key="mk")
        assert pid.catalyst is None
        assert pid.calc_type is None
        assert pid.mode == "opt"
        assert pid.sp_subfolder is None


class TestExtractedData:
    def test_mutable(self) -> None:
        """ExtractedData is not frozen — can be mutated."""
        cid = CalcID(method_key="mk", stage="r", species="s")
        data = ExtractedData(calc_id=cid)
        data.energy = 42.0
        assert data.energy == 42.0

    def test_defaults_none(self) -> None:
        cid = CalcID(method_key="mk", stage="r", species="s")
        data = ExtractedData(calc_id=cid)
        assert data.energy is None
        assert data.H is None
        assert data.G is None
        assert data.sp_energy is None
        assert data.xyz_text is None
