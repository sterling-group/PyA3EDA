"""Tests for the integrated dimer dissociation (DISS) correction.

Covers the ``dimer: true`` config flag, the ``dimer``-stage registry enumeration
and on-disk path, and ``apply_dimer_corrections`` (correction maths, multi-catalyst
selection, skip-when-not-run, and fail-loud on ran-but-incomplete data).
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pya3eda.config import CatalystConfig, load_config
from pya3eda.errors import IncompleteDataError
from pya3eda.extractor.dimer import apply_dimer_corrections
from pya3eda.ids import CalcID, DeltaDeltaData, ExtractedData
from pya3eda.registry import CalcRegistry
from tests.synthetic_outputs import SAMPLE_CONFIG_YAML

# ===================================================================
# Config + registry
# ===================================================================


def test_catalyst_dimer_defaults_false() -> None:
    assert CatalystConfig(name="bf3").dimer is False
    assert CatalystConfig(name="bf3", dimer=True).dimer is True


def _registry(tmp_path: Path) -> CalcRegistry:
    """Registry from the sample config with ``lip`` marked ``dimer: true``."""
    yaml = SAMPLE_CONFIG_YAML.replace("  - name: lip\n", "  - name: lip\n    dimer: true\n")
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml)
    return CalcRegistry(load_config(cfg), tmp_path)


def test_registry_dimer_catalysts(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    assert reg.dimer_catalysts == {"lip"}  # bf3 not flagged


def test_registry_enumerates_dimer_calc_and_path(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    mk = "wB97X-V_def2-SVP_smd"
    opt = CalcID(method_key=mk, catalyst="lip", stage="dimer", species="lip-dimer", mode="opt")
    spec = reg.get(opt)
    assert spec.input_path.as_posix().endswith("lip/dimer/lip-dimer_opt.in")

    # SP lives in the method sub-folder, next to cat/
    sp = CalcID(
        method_key=mk,
        catalyst="lip",
        stage="dimer",
        species="lip-dimer",
        mode="sp",
        sp_subfolder="wB97M-V_def2-TZVPPD_smd_sp",
    )
    sp_spec = reg.get(sp)
    assert sp_spec.input_path.as_posix().endswith(
        "lip/dimer/wB97M-V_def2-TZVPPD_smd_sp/lip-dimer_sp.in"
    )


def test_registry_no_dimer_when_unflagged(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(SAMPLE_CONFIG_YAML)  # neither catalyst flagged
    reg = CalcRegistry(load_config(cfg), tmp_path)
    assert reg.dimer_catalysts == set()
    assert not any(c.id.stage == "dimer" for c in reg.all_calcs)


# ===================================================================
# apply_dimer_corrections
# ===================================================================


def _dd(energy_type: str = "E", *, mode: str = "opt", **kw: object) -> DeltaDeltaData:
    return DeltaDeltaData(method_key="m", catalyst="lip", energy_type=energy_type, mode=mode, **kw)


def _cid(stage: str, species: str, *, mode: str = "opt") -> CalcID:
    return CalcID(method_key="m", catalyst="lip", stage=stage, species=species, mode=mode)


def _reg(dimers: set[str]) -> MagicMock:
    return MagicMock(dimer_catalysts=dimers)


def test_no_dimer_catalysts_is_passthrough() -> None:
    dd = [_dd(dd_complete=-10.0)]
    assert apply_dimer_corrections(dd, _reg(set()), {}) is dd


def test_non_dimer_catalyst_unchanged() -> None:
    dd = DeltaDeltaData(method_key="m", catalyst="bf3", energy_type="E", dd_complete=-5.0)
    out = apply_dimer_corrections([dd], _reg({"lip"}), {})
    assert out[0].dd_dissoc is None


def test_e_correction_uses_electronic_energy() -> None:
    extracted = {
        _cid("cat", "lip"): ExtractedData(calc_id=_cid("cat", "lip"), energy=-100.0),
        _cid("dimer", "lip-dimer"): ExtractedData(
            calc_id=_cid("dimer", "lip-dimer"), energy=-210.0
        ),
    }
    dd = _dd("E", dd_complete=-10.0, barrier_full=40.0)
    out = apply_dimer_corrections([dd], _reg({"lip"}), extracted)
    corr = 2.0 * (-100.0) - (-210.0)  # +10
    assert out[0].dd_dissoc == pytest.approx(corr)
    assert out[0].dd_complete == pytest.approx(-10.0 + corr)
    assert out[0].barrier_full == pytest.approx(40.0 + corr)


def test_e_correction_falls_back_to_sp_energy() -> None:
    extracted = {
        _cid("cat", "lip"): ExtractedData(calc_id=_cid("cat", "lip"), sp_energy=-100.0),
        _cid("dimer", "lip-dimer"): ExtractedData(
            calc_id=_cid("dimer", "lip-dimer"), sp_energy=-210.0
        ),
    }
    out = apply_dimer_corrections([_dd("E", dd_complete=-1.0)], _reg({"lip"}), extracted)
    assert out[0].dd_dissoc == pytest.approx(2.0 * -100.0 - -210.0)


def test_g_correction_uses_free_energy() -> None:
    extracted = {
        _cid("cat", "lip"): ExtractedData(calc_id=_cid("cat", "lip"), energy=-100.0, G=-90.0),
        _cid("dimer", "lip-dimer"): ExtractedData(
            calc_id=_cid("dimer", "lip-dimer"), energy=-210.0, G=-185.0
        ),
    }
    out = apply_dimer_corrections([_dd("G", dd_complete=-8.0)], _reg({"lip"}), extracted)
    assert out[0].dd_dissoc == pytest.approx(2.0 * -90.0 - -185.0)


def test_correction_without_barrier_full_leaves_it_none() -> None:
    extracted = {
        _cid("cat", "lip"): ExtractedData(calc_id=_cid("cat", "lip"), energy=-100.0),
        _cid("dimer", "lip-dimer"): ExtractedData(
            calc_id=_cid("dimer", "lip-dimer"), energy=-210.0
        ),
    }
    out = apply_dimer_corrections([_dd("E", dd_complete=-1.0)], _reg({"lip"}), extracted)
    assert out[0].dd_dissoc is not None
    assert out[0].barrier_full is None


def test_multi_catalyst_only_dimer_one_corrected() -> None:
    extracted = {
        _cid("cat", "lip"): ExtractedData(calc_id=_cid("cat", "lip"), energy=-100.0),
        _cid("dimer", "lip-dimer"): ExtractedData(
            calc_id=_cid("dimer", "lip-dimer"), energy=-210.0
        ),
    }
    lip = _dd("E", dd_complete=-10.0)
    bf3 = DeltaDeltaData(method_key="m", catalyst="bf3", energy_type="E", dd_complete=-5.0)
    out = apply_dimer_corrections([lip, bf3], _reg({"lip"}), extracted)
    assert out[0].dd_dissoc is not None
    assert out[1].dd_dissoc is None


def test_monomer_not_extracted_skips(caplog: pytest.LogCaptureFixture) -> None:
    extracted = {
        _cid("dimer", "lip-dimer"): ExtractedData(
            calc_id=_cid("dimer", "lip-dimer"), energy=-210.0
        ),
    }
    with caplog.at_level(logging.WARNING):
        out = apply_dimer_corrections([_dd("E", dd_complete=-1.0)], _reg({"lip"}), extracted)
    assert out[0].dd_dissoc is None
    assert "monomer data not extracted" in caplog.text


def test_dimer_not_extracted_skips(caplog: pytest.LogCaptureFixture) -> None:
    extracted = {_cid("cat", "lip"): ExtractedData(calc_id=_cid("cat", "lip"), energy=-100.0)}
    with caplog.at_level(logging.WARNING):
        out = apply_dimer_corrections([_dd("E", dd_complete=-1.0)], _reg({"lip"}), extracted)
    assert out[0].dd_dissoc is None
    assert "dimer data not extracted" in caplog.text


def test_dd_complete_none_skips() -> None:
    extracted = {
        _cid("cat", "lip"): ExtractedData(calc_id=_cid("cat", "lip"), energy=-100.0),
        _cid("dimer", "lip-dimer"): ExtractedData(
            calc_id=_cid("dimer", "lip-dimer"), energy=-210.0
        ),
    }
    out = apply_dimer_corrections([_dd("E", dd_complete=None)], _reg({"lip"}), extracted)
    assert out[0].dd_dissoc is None


def test_monomer_ran_but_incomplete_fails_loud() -> None:
    extracted = {
        _cid("cat", "lip"): ExtractedData(calc_id=_cid("cat", "lip")),  # ran, no energy/G
        _cid("dimer", "lip-dimer"): ExtractedData(
            calc_id=_cid("dimer", "lip-dimer"), energy=-210.0
        ),
    }
    with pytest.raises(IncompleteDataError, match="monomer ran but has no E"):
        apply_dimer_corrections([_dd("E", dd_complete=-1.0)], _reg({"lip"}), extracted)


def test_dimer_ran_but_incomplete_fails_loud() -> None:
    extracted = {
        _cid("cat", "lip"): ExtractedData(calc_id=_cid("cat", "lip"), energy=-100.0, G=-90.0),
        _cid("dimer", "lip-dimer"): ExtractedData(
            calc_id=_cid("dimer", "lip-dimer"), energy=-210.0
        ),  # has E but no G
    }
    with pytest.raises(IncompleteDataError, match="dimer ran but has no G"):
        apply_dimer_corrections([_dd("G", dd_complete=-1.0)], _reg({"lip"}), extracted)


def test_incomplete_data_error_combine() -> None:
    err = IncompleteDataError.combine(["a missing x", "b missing y"])
    assert "2 computation(s)" in str(err)
    assert "a missing x" in str(err) and "b missing y" in str(err)
