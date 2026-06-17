"""Tests for qqchem.slurm — SLURM script generation and submission."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qqchem.slurm import generate_slurm_script, submit_job


def _kwargs(tmp_path: Path, **overrides: object) -> dict:
    """Build a complete generate_slurm_script kwargs dict with sane defaults."""
    base: dict = dict(
        input_path=tmp_path / "job.in",
        job_name="job",
        output_file="job.out",
        error_file="job.err",
        partition="normal",
        cpus=1,
        qchem_processors=1,
        mem_per_cpu=2000,
        walltime="1-00:00:00",
        parallel_type="openmp",
        module_load_commands=["module load qchem/6.2.1"],
        environment_vars=[],
        qcsetup_file="",
        mpi_support=True,
        mpi_modules=[],
        scratch=None,
        scratch_base_dir="/scratch/$USER",
        nodename=None,
        exclude_nodes=None,
        save=False,
        save_all=False,
        save_scratch=False,
        force=False,
        cluster_name="testcluster",
    )
    base.update(overrides)
    return base


def _generate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **overrides: object) -> str:
    """Generate a script in an isolated cwd and return its text."""
    monkeypatch.chdir(tmp_path)
    name = generate_slurm_script(**_kwargs(tmp_path, **overrides))
    return (tmp_path / name).read_text()


# ===================================================================
# Scratch cleanup safety (B3 regression)
# ===================================================================


class TestScratchCleanupGuard:
    def test_default_scratch_sets_scrname_and_cleans_subdir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = _generate(tmp_path, monkeypatch, scratch=None)
        assert "export scrname=q${SLURM_JOB_ID}" in text
        # rm -rf must be guarded by a non-empty scrname check
        assert 'if [ -n "$scrname" ]; then' in text
        assert 'rm -rf "$QCSCRATCH/$scrname"' in text

    def test_no_unguarded_rm_rf(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Every `rm -rf` of the scratch dir must be preceded by the guard.
        text = _generate(tmp_path, monkeypatch, scratch=None)
        for m in re.finditer(r'rm -rf "\$QCSCRATCH/\$scrname"', text):
            preceding = text[: m.start()]
            assert preceding.rstrip().endswith('if [ -n "$scrname" ]; then')

    def test_custom_scratch_does_not_wipe_scratch_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # With a user-supplied --scratch, $scrname is never set, so the guard
        # makes cleanup a no-op (it must NOT rm -rf the whole custom dir).
        text = _generate(tmp_path, monkeypatch, scratch="/custom/scratch")
        assert "export QCSCRATCH=/custom/scratch" in text
        assert "export scrname=" not in text
        assert 'if [ -n "$scrname" ]; then' in text  # rm still guarded

    def test_save_scratch_skips_cleanup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = _generate(tmp_path, monkeypatch, save_scratch=True)
        assert "Not deleting scratch directory" in text
        assert "rm -rf" not in text

    def test_save_copy_guarded_on_scrname(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = _generate(tmp_path, monkeypatch, save=True)
        assert 'if [ -n "$scrname" ] && [ -d "$QCSCRATCH/$scrname" ]; then' in text


# ===================================================================
# SBATCH directives
# ===================================================================


class TestSbatchDirectives:
    def test_output_and_error_both_go_to_err_file_intentional(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Intentional by design: Q-Chem writes the .out file itself via the
        # `qchem ... output_file` command; SLURM's own stdout/stderr go to .err.
        text = _generate(tmp_path, monkeypatch, output_file="job.out", error_file="job.err")
        assert "#SBATCH --output=job.err" in text
        assert "#SBATCH --error=job.err" in text
        # The output_file is still used for the qchem command itself.
        assert "job.out" in text.split("# Run Q-Chem job")[1]

    def test_resources_written(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        text = _generate(tmp_path, monkeypatch, cpus=4, mem_per_cpu=3000, partition="big")
        assert "#SBATCH --cpus-per-task=4" in text
        assert "#SBATCH --mem-per-cpu=3000" in text
        assert "#SBATCH --partition=big" in text
        assert "export OMP_NUM_THREADS=4" in text

    def test_node_and_exclude(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        text = _generate(tmp_path, monkeypatch, nodename="node01", exclude_nodes="node02")
        assert "#SBATCH --nodelist=node01" in text
        assert "#SBATCH --exclude=node02" in text


class TestScriptBody:
    def test_environment_vars_written(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = _generate(tmp_path, monkeypatch, environment_vars=["export FOO=bar"])
        assert "export FOO=bar" in text

    def test_qcsetup_sourced(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        text = _generate(tmp_path, monkeypatch, qcsetup_file="/opt/qcsetup")
        assert "source /opt/qcsetup" in text

    def test_save_all_adds_save_flag(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        text = _generate(tmp_path, monkeypatch, save_all=True)
        assert "qchem -save " in text


class TestOpenMPI:
    def test_openmpi_emits_mpi_flags(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        text = _generate(
            tmp_path,
            monkeypatch,
            parallel_type="openmpi",
            qchem_processors=4,
            cpus=2,
            mpi_support=True,
            mpi_modules=["openmpi4/4.1.6"],
        )
        assert "-mpi -np 4 -nt 2" in text
        assert "module load openmpi4/4.1.6" in text

    def test_openmpi_without_support_exits_unless_forced(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            generate_slurm_script(
                **_kwargs(
                    tmp_path,
                    parallel_type="openmpi",
                    qchem_processors=2,
                    mpi_support=False,
                    force=False,
                )
            )

    def test_openmpi_without_support_proceeds_with_force(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = _generate(
            tmp_path,
            monkeypatch,
            parallel_type="openmpi",
            qchem_processors=2,
            mpi_support=False,
            force=True,
        )
        assert "-mpi -np 2" in text


# ===================================================================
# submit_job
# ===================================================================


class TestSubmitJob:
    def test_dryrun_does_not_submit(self, capsys: pytest.CaptureFixture) -> None:
        with patch("qqchem.slurm.subprocess.run") as run:
            submit_job("job.slurm", dryrun=True)
        run.assert_not_called()
        assert "Dry run" in capsys.readouterr().out

    def test_submit_parses_job_id_and_removes_script(self, tmp_path: Path) -> None:
        script = tmp_path / "job.slurm"
        script.write_text("#!/bin/bash\n")
        mock_result = MagicMock()
        mock_result.stdout = "Submitted batch job 123456\n"
        with patch("qqchem.slurm.subprocess.run", return_value=mock_result):
            submit_job(str(script), dryrun=False, save_slurm=False)
        assert not script.exists()  # removed when save_slurm is False

    def test_submit_keeps_script_when_requested(self, tmp_path: Path) -> None:
        script = tmp_path / "job.slurm"
        script.write_text("#!/bin/bash\n")
        mock_result = MagicMock()
        mock_result.stdout = "Submitted batch job 99\n"
        with patch("qqchem.slurm.subprocess.run", return_value=mock_result):
            submit_job(str(script), dryrun=False, save_slurm=True)
        assert script.exists()

    def test_submit_no_script_file_to_remove(self, tmp_path: Path) -> None:
        """save_slurm=False but the script is already gone → no unlink, no error."""
        missing = tmp_path / "gone.slurm"
        mock_result = MagicMock()
        mock_result.stdout = "Submitted batch job 7\n"
        with patch("qqchem.slurm.subprocess.run", return_value=mock_result):
            submit_job(str(missing), dryrun=False, save_slurm=False)
        assert not missing.exists()

    def test_submit_exits_when_no_job_id(self, tmp_path: Path) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "garbage output\n"
        with (
            patch("qqchem.slurm.subprocess.run", return_value=mock_result),
            pytest.raises(SystemExit),
        ):
            submit_job("job.slurm", dryrun=False)
