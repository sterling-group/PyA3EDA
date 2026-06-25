"""Tests for pya3eda.ids — data model identity and hashing."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pya3eda.ids import CalcID, ExtractedData, ProfileID, StageData


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


class TestStageData:
    def test_rel_private_attr_survives_model_copy(self) -> None:
        """Guard the relative-energy mechanism: ``StageData._rel`` is a Pydantic
        PrivateAttr that ``extractor.stages._normalize`` populates via
        ``model_copy(update={"_rel": ...})``. If a Pydantic upgrade ever stops
        applying ``update`` to a private attribute, every relative energy would
        silently become ``None`` (empty profile CSVs/plots) — this fails loudly
        instead.
        """
        stage = StageData(name="ts", E=5.0, G=3.0)
        assert stage.rel("E") is None  # nothing normalised yet

        normalised = stage.model_copy(update={"_rel": {"E": 2.5, "G": 1.5}})
        assert normalised.rel("E") == 2.5
        assert normalised.rel("G") == 1.5
        assert stage.rel("E") is None  # original (frozen) untouched


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
