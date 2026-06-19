"""Tests for pya3eda.runner.backend (sbatch_available, Local/Slurm backends, factory)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pya3eda.runner import backend
from pya3eda.runner.backend import (
    JobSubmissionError,
    LocalBackend,
    SlurmBackend,
    _current_user,
    get_backend,
    sbatch_available,
)


def _wait(be: LocalBackend, job_id: str, timeout: float = 5.0) -> None:
    """Block until a local job is finished (test helper)."""
    deadline = time.monotonic() + timeout
    while not be.is_finished(job_id):
        if time.monotonic() > deadline:
            raise AssertionError("local job did not finish in time")
        time.sleep(0.01)


def _write_script(path: Path, body: str) -> Path:
    path.write_text(f"#!/bin/bash\n{body}\n", encoding="utf-8")
    return path


# ===================================================================
# sbatch_available / factory
# ===================================================================


class TestSbatchAvailable:
    def test_true_when_present(self) -> None:
        with patch("pya3eda.runner.backend.shutil.which", return_value="/usr/bin/sbatch"):
            assert sbatch_available() is True

    def test_false_when_absent(self) -> None:
        with patch("pya3eda.runner.backend.shutil.which", return_value=None):
            assert sbatch_available() is False


class TestGetBackend:
    def test_auto_local(self) -> None:
        with patch("pya3eda.runner.backend.sbatch_available", return_value=False):
            assert isinstance(get_backend("auto"), LocalBackend)

    def test_auto_slurm(self) -> None:
        with patch("pya3eda.runner.backend.sbatch_available", return_value=True):
            assert isinstance(get_backend("auto"), SlurmBackend)

    def test_explicit(self) -> None:
        assert isinstance(get_backend("local"), LocalBackend)
        assert isinstance(get_backend("slurm"), SlurmBackend)

    def test_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend("nope")


# ===================================================================
# _current_user
# ===================================================================


class TestCurrentUser:
    def test_returns_username(self) -> None:
        _current_user.cache_clear()
        assert isinstance(_current_user(), str)

    def test_uid_fallback(self) -> None:
        _current_user.cache_clear()
        with (
            patch("pya3eda.runner.backend.getpass.getuser", side_effect=OSError),
            patch("pya3eda.runner.backend.os.getuid", return_value=4242),
        ):
            assert _current_user() == "4242"
        _current_user.cache_clear()


# ===================================================================
# LocalBackend
# ===================================================================


class TestLocalBackend:
    def test_available(self) -> None:
        assert LocalBackend().available() is True

    def test_submit_and_finish(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path / "job.slurm", "echo hello")
        be = LocalBackend()
        job_id = be.submit(script)
        assert job_id.startswith("local-")
        _wait(be, job_id)
        assert "hello" in (tmp_path / "job.err").read_text()

    def test_is_finished_unknown_job(self) -> None:
        assert LocalBackend().is_finished("local-999") is True

    def test_nonzero_exit_still_finishes(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path / "job.slurm", "exit 3")
        be = LocalBackend()
        job_id = be.submit(script)
        _wait(be, job_id)  # finishes (logs a warning) despite the non-zero exit

    def test_custom_log_path(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path / "job.slurm", "echo logged")
        log = tmp_path / "custom.log"
        be = LocalBackend()
        job_id = be.submit(script, log_path=log)
        _wait(be, job_id)
        assert "logged" in log.read_text()

    def test_popen_failure_closes_handle(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path / "job.slurm", "echo x")
        be = LocalBackend()
        with (
            patch("pya3eda.runner.backend.subprocess.Popen", side_effect=OSError("boom")),
            pytest.raises(OSError, match="boom"),
        ):
            be.submit(script)


# ===================================================================
# SlurmBackend
# ===================================================================


class TestSlurmBackend:
    def test_available(self) -> None:
        with patch("pya3eda.runner.backend.sbatch_available", return_value=True):
            assert SlurmBackend().available() is True

    def test_submit_success(self, tmp_path: Path) -> None:
        script = tmp_path / "job.slurm"
        script.write_text("#!/bin/bash\n")
        result = MagicMock(stdout="Submitted batch job 12345\n")
        with patch("pya3eda.runner.backend.subprocess.run", return_value=result) as run:
            job_id = SlurmBackend().submit(script)
        assert job_id == "12345"
        assert run.call_args.kwargs["cwd"] == script.parent

    def test_submit_sbatch_error(self, tmp_path: Path) -> None:
        script = tmp_path / "job.slurm"
        script.write_text("#!/bin/bash\n")
        with (
            patch(
                "pya3eda.runner.backend.subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "sbatch"),
            ),
            pytest.raises(JobSubmissionError, match="sbatch failed"),
        ):
            SlurmBackend().submit(script)

    def test_submit_unparseable_output(self, tmp_path: Path) -> None:
        script = tmp_path / "job.slurm"
        script.write_text("#!/bin/bash\n")
        result = MagicMock(stdout="no number here\n")
        with (
            patch("pya3eda.runner.backend.subprocess.run", return_value=result),
            pytest.raises(JobSubmissionError, match="could not parse job ID"),
        ):
            SlurmBackend().submit(script)

    def test_is_finished_true_when_absent(self) -> None:
        result = MagicMock(stdout="JOBID\n99999\n")
        with patch("pya3eda.runner.backend.subprocess.run", return_value=result):
            assert SlurmBackend().is_finished("12345") is True

    def test_is_finished_false_when_running(self) -> None:
        result = MagicMock(stdout="JOBID\n12345\n")
        with patch("pya3eda.runner.backend.subprocess.run", return_value=result):
            assert SlurmBackend().is_finished("12345") is False

    def test_is_finished_false_for_array_task(self) -> None:
        result = MagicMock(stdout="JOBID\n12345_0\n")
        with patch("pya3eda.runner.backend.subprocess.run", return_value=result):
            assert SlurmBackend().is_finished("12345") is False

    def test_is_finished_empty_queue(self) -> None:
        result = MagicMock(stdout="")
        with patch("pya3eda.runner.backend.subprocess.run", return_value=result):
            assert SlurmBackend().is_finished("12345") is True

    def test_is_finished_squeue_error_retries(self) -> None:
        with patch(
            "pya3eda.runner.backend.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "squeue"),
        ):
            assert SlurmBackend().is_finished("12345") is False


def test_backends_registry() -> None:
    assert set(backend.BACKENDS) == {"local", "slurm"}
