"""Tests for pya3eda.parser.qchem — pure Q-Chem output parsing.

Every test is self-contained using synthetic Q-Chem output snippets.
"""

from __future__ import annotations

import pytest

from pya3eda.parser.qchem import (
    EDAData,
    EnergyResult,
    SMDData,
    parse_cds_print,
    parse_eda_energies,
    parse_energy,
    parse_enthalpy,
    parse_entropy,
    parse_imaginary_freq,
    parse_opt_converged,
    parse_smd,
    parse_status,
    parse_thermo_conditions,
    parse_translational_entropy,
    parse_zpve,
)
from pya3eda.utils import convert_unit
from tests.synthetic_outputs import (
    EDA_FRZ_OUTPUT,
    EDA_FULL_SP_OUTPUT,
    EDA_POL_OUTPUT,
    OPT_OUTPUT,
    SP_OUTPUT,
    TS_OUTPUT,
)

# ===================================================================
# parse_energy
# ===================================================================


class TestParseEnergy:
    """Tests for parse_energy (Final energy / Total energy)."""

    def test_final_energy_from_opt(self) -> None:
        result = parse_energy(OPT_OUTPUT)
        assert result is not None
        assert isinstance(result, EnergyResult)
        assert result.value_ha == pytest.approx(-191.709724458668)
        assert result.value_kcal == pytest.approx(convert_unit(-191.709724458668, "Ha", "kcal/mol"))

    def test_total_energy_from_sp(self) -> None:
        result = parse_energy(SP_OUTPUT)
        assert result is not None
        assert result.value_ha == pytest.approx(-191.91752153)

    def test_returns_none_for_empty_text(self) -> None:
        assert parse_energy("") is None

    def test_returns_none_for_garbage_text(self) -> None:
        assert parse_energy("no energy data here\nfoo bar") is None

    def test_picks_last_total_energy(self) -> None:
        """The parser must pick the *last* Total energy line."""
        text = "Total energy =  -100.123456\nsome stuff\nTotal energy =  -200.654321\n"
        result = parse_energy(text)
        assert result is not None
        assert result.value_ha == pytest.approx(-200.654321)

    def test_prefers_final_energy_over_total(self) -> None:
        text = "Total energy =  -100.123456\nFinal energy is -300.111222\n"
        result = parse_energy(text)
        assert result is not None
        assert result.value_ha == pytest.approx(-300.111222)

    def test_opt_output_has_multiple_total_but_final_wins(self) -> None:
        """OPT_OUTPUT has 3 'Total energy' lines then 'Final energy is' — final wins."""
        result = parse_energy(OPT_OUTPUT)
        assert result is not None
        # Should NOT be any of the intermediate Total energies
        assert result.value_ha != pytest.approx(-191.50000000, abs=1e-6)
        assert result.value_ha != pytest.approx(-191.60000000, abs=1e-6)
        assert result.value_ha != pytest.approx(-191.70000000, abs=1e-6)
        # Should be the Final energy
        assert result.value_ha == pytest.approx(-191.709724458668)


# ===================================================================
# parse_thermo_conditions
# ===================================================================


class TestThermoConditions:
    def test_from_opt(self) -> None:
        result = parse_thermo_conditions(OPT_OUTPUT)
        assert result is not None
        assert result.temperature == pytest.approx(298.15)
        assert result.pressure == pytest.approx(1.0)

    def test_from_ts(self) -> None:
        result = parse_thermo_conditions(TS_OUTPUT)
        assert result is not None
        assert result.temperature == pytest.approx(298.15)

    def test_none_when_missing(self) -> None:
        assert parse_thermo_conditions("no thermo here") is None


# ===================================================================
# parse_imaginary_freq
# ===================================================================


class TestImaginaryFreq:
    def test_zero_for_minimum(self) -> None:
        assert parse_imaginary_freq(OPT_OUTPUT) == 0

    def test_one_for_ts(self) -> None:
        assert parse_imaginary_freq(TS_OUTPUT) == 1

    def test_none_when_missing(self) -> None:
        assert parse_imaginary_freq("no freq info") is None


# ===================================================================
# parse_zpve
# ===================================================================


class TestZPVE:
    def test_from_opt(self) -> None:
        result = parse_zpve(OPT_OUTPUT)
        assert result is not None
        assert result == pytest.approx(38.832, abs=0.001)

    def test_from_ts(self) -> None:
        result = parse_zpve(TS_OUTPUT)
        assert result is not None
        assert result == pytest.approx(98.200, abs=0.001)

    def test_none_when_missing(self) -> None:
        assert parse_zpve("") is None


# ===================================================================
# parse_enthalpy
# ===================================================================


class TestEnthalpy:
    def test_prefers_qrrho(self) -> None:
        """QRRHO-Total Enthalpy (42.119) should be preferred over Total (42.162)."""
        result = parse_enthalpy(OPT_OUTPUT)
        assert result is not None
        assert result == pytest.approx(42.119, abs=0.001)

    def test_falls_back_to_total(self) -> None:
        text = "  Total Enthalpy:               42.162 kcal/mol\n"
        result = parse_enthalpy(text)
        assert result is not None
        assert result == pytest.approx(42.162, abs=0.001)

    def test_none_when_missing(self) -> None:
        assert parse_enthalpy("no enthalpy") is None

    def test_ts_qrrho_value(self) -> None:
        result = parse_enthalpy(TS_OUTPUT)
        assert result is not None
        assert result == pytest.approx(103.200, abs=0.001)


# ===================================================================
# parse_entropy
# ===================================================================


class TestEntropy:
    def test_prefers_qrrho(self) -> None:
        """QRRHO-Total Entropy (66.534 cal/mol.K → 0.066534 kcal/mol.K)."""
        result = parse_entropy(OPT_OUTPUT)
        assert result is not None
        assert result == pytest.approx(66.534e-3, abs=1e-5)

    def test_none_when_missing(self) -> None:
        assert parse_entropy("") is None

    def test_ts_entropy_value(self) -> None:
        result = parse_entropy(TS_OUTPUT)
        assert result is not None
        assert result == pytest.approx(79.800e-3, abs=1e-5)


# ===================================================================
# parse_translational_entropy
# ===================================================================


class TestTranslationalEntropy:
    def test_from_opt(self) -> None:
        result = parse_translational_entropy(OPT_OUTPUT)
        assert result is not None
        assert result == pytest.approx(37.991e-3, abs=1e-5)

    def test_none_when_missing(self) -> None:
        assert parse_translational_entropy("nothing") is None


# ===================================================================
# parse_opt_converged
# ===================================================================


class TestOptConverged:
    def test_converged_opt(self) -> None:
        assert parse_opt_converged(OPT_OUTPUT) is True

    def test_converged_ts(self) -> None:
        assert parse_opt_converged(TS_OUTPUT) is True

    def test_not_converged(self) -> None:
        assert parse_opt_converged("no convergence here") is False


# ===================================================================
# parse_smd
# ===================================================================


class TestParseSMD:
    def test_sp_with_smd(self) -> None:
        result = parse_smd(SP_OUTPUT)
        assert result is not None
        assert isinstance(result, SMDData)
        assert result.g_enp_ha == pytest.approx(-191.916357295)
        assert result.g_s_ha == pytest.approx(-191.917521529)
        assert result.cds_kcal == pytest.approx(-0.7306, abs=1e-4)

    def test_none_when_missing(self) -> None:
        assert parse_smd("regular output without smd") is None


# ===================================================================
# parse_eda_energies
# ===================================================================


class TestParseEDAEnergies:
    def test_pol_cat_uses_last_guess_energy(self) -> None:
        """pol_cat picks the last 'Energy prior to optimization (guess energy)' line."""
        result = parse_eda_energies(EDA_POL_OUTPUT, "pol_cat")
        assert result is not None
        assert isinstance(result, EDAData)
        # Last guess energy (3rd of 3 entries)
        assert result.sp_energy_ha == pytest.approx(-1814.157030967601)
        assert result.bsse_kcal is None

    def test_pol_cat_does_not_pick_first_guess(self) -> None:
        """Explicitly verify earlier entries are ignored."""
        result = parse_eda_energies(EDA_POL_OUTPUT, "pol_cat")
        assert result is not None
        assert result.sp_energy_ha != pytest.approx(-1814.000000000000, abs=1e-6)
        assert result.sp_energy_ha != pytest.approx(-1814.100000000000, abs=1e-6)

    def test_pol_cat_extracts_cds(self) -> None:
        """CDS is the LAST 'Total:' table — the full-system value, which follows
        any per-fragment CDS tables; taking the first would pick a fragment's CDS."""
        result = parse_eda_energies(EDA_POL_OUTPUT, "pol_cat")
        assert result is not None
        assert result.cds_kcal == pytest.approx(-2.414, abs=0.001)

    def test_frz_cat_uses_last_convergence(self) -> None:
        """frz_cat picks the last convergence energy line."""
        result = parse_eda_energies(EDA_FRZ_OUTPUT, "frz_cat")
        assert result is not None
        # Second (last) convergence energy
        assert result.sp_energy_ha == pytest.approx(-1814.1288377459)
        assert result.bsse_kcal is None

    def test_full_cat_sp_uses_last_convergence(self) -> None:
        result = parse_eda_energies(EDA_FULL_SP_OUTPUT, "full_cat")
        assert result is not None
        # Last convergence energy in the file
        assert result.sp_energy_ha == pytest.approx(-1815.1481418253)

    def test_full_cat_sp_has_bsse(self) -> None:
        result = parse_eda_energies(EDA_FULL_SP_OUTPUT, "full_cat")
        assert result is not None
        assert result.bsse_kcal is not None
        assert result.bsse_kcal == pytest.approx(
            convert_unit(0.3295, "kJ/mol", "kcal/mol"), abs=1e-4
        )

    def test_full_cat_sp_has_cds(self) -> None:
        result = parse_eda_energies(EDA_FULL_SP_OUTPUT, "full_cat")
        assert result is not None
        assert result.cds_kcal == pytest.approx(-2.411, abs=0.001)

    def test_pol_cat_returns_none_for_empty(self) -> None:
        assert parse_eda_energies("", "pol_cat") is None

    def test_full_cat_returns_none_for_empty(self) -> None:
        assert parse_eda_energies("", "full_cat") is None

    def test_full_cat_without_bsse_or_cds(self) -> None:
        """full_cat with a convergence energy but no BSSE / SMD-CDS lines."""
        text = "   10   -1814.1288377459      3.50e-09     00000 Convergence criterion met\n"
        result = parse_eda_energies(text, "full_cat")
        assert result is not None
        assert result.bsse_kcal is None
        assert result.cds_kcal is None


class TestParseCdsPrint:
    def test_last_table_is_full_system(self) -> None:
        """With multiple CDS tables (per-fragment then full-system), the last wins."""
        assert parse_cds_print(EDA_POL_OUTPUT) == pytest.approx(-2.414, abs=1e-4)

    def test_none_when_absent(self) -> None:
        assert parse_cds_print("no CDS extended-print table here") is None


# ===================================================================
# parse_status
# ===================================================================


class TestParseStatus:
    def test_successful(self) -> None:
        status, detail = parse_status(OPT_OUTPUT)
        assert status == "SUCCESSFUL"
        assert "00:03:00" in detail  # 180.20s wall → 00:03:00

    def test_empty_output(self) -> None:
        status, _detail = parse_status("")
        assert status == "nofile"

    def test_crash_on_fatal_error(self) -> None:
        text = "Q-Chem fatal error occurred in some module\n"
        status, _ = parse_status(text)
        assert status == "CRASH"

    def test_crash_on_scf_failure(self) -> None:
        status, detail = parse_status("SCF failed to converge\n")
        assert status == "CRASH"
        assert "SCF" in detail

    def test_running_without_thank_you(self) -> None:
        text = "Running on host abc\nSome calculation output\n"
        status, _ = parse_status(text)
        assert status == "running"

    def test_running_then_crash_is_crash_not_running(self) -> None:
        """A job that printed 'Running on' then died with a marker → CRASH, not a
        forever-'running' that the NOFILE filter would never resubmit."""
        status, detail = parse_status("Running on host abc\nSCF failed to converge\n")
        assert status == "CRASH"
        assert "SCF" in detail

    def test_running_then_killed_is_terminated(self) -> None:
        """'Running on' plus a kill marker → terminated, not running."""
        status, _ = parse_status("Running on host abc\nProcess killed by signal\n")
        assert status == "terminated"

    def test_cancelled(self) -> None:
        status, _ = parse_status("", "CANCELLED AT 2024-01-01")
        assert status == "terminated"

    def test_error_in_stderr(self) -> None:
        status, _ = parse_status("some output", "Error in Q-Chem run")
        assert status == "CRASH"

    def test_submission_sentinel(self) -> None:
        status, _ = parse_status("", "", submission_exists=True)
        assert status == "running"

    def test_sp_output_successful(self) -> None:
        status, detail = parse_status(SP_OUTPUT)
        assert status == "SUCCESSFUL"
        assert "00:00:22" in detail  # 22.51s wall

    def test_ts_output_successful(self) -> None:
        status, detail = parse_status(TS_OUTPUT)
        assert status == "SUCCESSFUL"
        assert "01:00:00" in detail  # 3600.50s wall

    def test_killed_in_output_terminated(self) -> None:
        """'killed' keyword in output → terminated."""
        status, _ = parse_status("Some output killed process\n")
        assert status == "terminated"

    def test_empty_whitespace_output(self) -> None:
        """Whitespace-only output → empty status."""
        status, _ = parse_status("   \n  \n")
        assert status == "empty"

    def test_crash_detail_known_tag(self) -> None:
        """_crash_detail returns known failure message for SGeom Failed."""
        status, detail = parse_status("Q-Chem fatal error occurred\nSGeom Failed\n")
        assert status == "CRASH"
        assert "Geometry optimization" in detail

    def test_crash_detail_error_occurred(self) -> None:
        """_crash_detail extracts message after 'error occurred'."""
        text = "Error in Q-Chem run"
        err = text
        out = "error occurred in module\n  Something specific happened here.\n\n"
        status, detail = parse_status(out, err)
        assert status == "CRASH"
        assert "Something specific happened here" in detail

    def test_crash_detail_empty_text(self) -> None:
        """_crash_detail with empty output → generic message."""
        status, detail = parse_status("", "Error in Q-Chem run")
        assert status == "CRASH"
        assert "Q-Chem execution crashed" in detail

    def test_crash_detail_unknown(self) -> None:
        """_crash_detail with non-empty text but no known patterns → Unknown failure."""
        status, detail = parse_status("some random text", "Aborted")
        assert status == "CRASH"
        assert "Unknown failure" in detail

    def test_crash_detail_error_occurred_no_match(self) -> None:
        """'error occurred' present but no trailing detail line → Unknown failure."""
        status, detail = parse_status("Q-Chem fatal error occurred")
        assert status == "CRASH"
        assert detail == "Unknown failure"

    def test_wall_time_no_match(self) -> None:
        """Successful output without 'Total job time' → 'unknown' time."""
        text = "Running on host\nThank you very much for using Q-Chem.\n"
        status, detail = parse_status(text)
        assert status == "SUCCESSFUL"
        assert "unknown" in detail

    def test_wall_time_no_wall_pattern(self) -> None:
        """Total job time present but no (wall) pattern → raw time string."""
        text = (
            "Running on host\nThank you very much for using Q-Chem.\n"
            "Total job time: 5 minutes 30 seconds\n"
        )
        status, detail = parse_status(text)
        assert status == "SUCCESSFUL"
        assert "5 minutes 30 seconds" in detail
