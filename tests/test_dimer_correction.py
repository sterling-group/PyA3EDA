"""Tests for scripts/dimer_correction.py — the dissociation-correction math.

The script lives in ``scripts/`` (not the package), so it is imported by path.
It is not part of the coverage gate; these tests pin the correction arithmetic.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import dimer_correction

from pya3eda.ids import CalcID, DeltaDeltaData, ExtractedData
from tests.synthetic_outputs import OPT_OUTPUT


def _cat_cid(mode: str = "opt", sp: str | None = None) -> CalcID:
    return CalcID(
        method_key="m", catalyst="bf3", stage="cat", species="bf3", mode=mode, sp_subfolder=sp
    )


def _registry() -> MagicMock:
    reg = MagicMock()
    reg.get.return_value = MagicMock(solvent="false")
    return reg


def _dd(energy_type: str, **kw: object) -> DeltaDeltaData:
    return DeltaDeltaData(method_key="m", catalyst="bf3", energy_type=energy_type, **kw)


class TestCorrectDeltaDelta:
    def test_e_correction(self) -> None:
        cid = _cat_cid()
        extracted = {cid: ExtractedData(calc_id=cid, energy=-100.0)}
        dd = _dd("E", dd_complete=-10.0, barrier_full=40.0)
        e_dimer, _ = dimer_correction.extract_opt_energies(OPT_OUTPUT, "false")
        out = dimer_correction.correct_delta_delta(
            [dd], _registry(), extracted, catalyst="bf3", opt_text=OPT_OUTPUT, sp_text=None
        )
        corr = 2.0 * (-100.0) - e_dimer
        assert out[0].dd_dissoc == corr
        assert out[0].dd_complete == -10.0 + corr  # FULL grows by the correction
        assert out[0].barrier_full == 40.0 + corr

    def test_g_correction_uses_g_values(self) -> None:
        cid = _cat_cid()
        extracted = {cid: ExtractedData(calc_id=cid, energy=-100.0, G=-90.0)}
        dd = _dd("G", dd_complete=-8.0, barrier_full=30.0)
        _, g_dimer = dimer_correction.extract_opt_energies(OPT_OUTPUT, "false")
        out = dimer_correction.correct_delta_delta(
            [dd], _registry(), extracted, catalyst="bf3", opt_text=OPT_OUTPUT, sp_text=None
        )
        assert out[0].dd_dissoc == 2.0 * (-90.0) - g_dimer

    def test_non_target_catalyst_unchanged(self) -> None:
        dd = DeltaDeltaData(method_key="m", catalyst="other", energy_type="E", dd_complete=-5.0)
        out = dimer_correction.correct_delta_delta(
            [dd], _registry(), {}, catalyst="bf3", opt_text=OPT_OUTPUT, sp_text=None
        )
        assert out[0].dd_dissoc is None

    def test_missing_catalyst_data_skipped(self) -> None:
        dd = _dd("E", dd_complete=-5.0)
        out = dimer_correction.correct_delta_delta(
            [dd], _registry(), {}, catalyst="bf3", opt_text=OPT_OUTPUT, sp_text=None
        )
        assert out[0].dd_dissoc is None

    def test_sp_row_without_dimer_sp_skipped(self) -> None:
        cid = _cat_cid(mode="sp", sp="x")
        extracted = {cid: ExtractedData(calc_id=cid, sp_energy=-100.0, G=-90.0)}
        dd = _dd("E", mode="sp", sp_subfolder="x", dd_complete=-5.0)
        out = dimer_correction.correct_delta_delta(
            [dd], _registry(), extracted, catalyst="bf3", opt_text=OPT_OUTPUT, sp_text=None
        )
        assert out[0].dd_dissoc is None  # no dimer SP → (None, None) → uncorrected
