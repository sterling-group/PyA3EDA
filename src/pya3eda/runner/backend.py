"""Execution backends: *where* a generated script runs (local bash vs SLURM).

The :class:`ExecutionBackend` Protocol decouples submission/polling from *what*
runs (the :mod:`~pya3eda.runner.engine` run block) and from the orchestrator,
so a new scheduler (PBS, cloud, …) is a new backend with no executor changes
(OCP/DIP). Two impls ship:

* :class:`LocalBackend` — runs the script via ``bash`` in the background
  (``Popen``), so many jobs run at once under the core budget; polled via
  ``Popen.poll``. Job IDs are synthetic ``local-N``.
* :class:`SlurmBackend` — ``sbatch`` the script, poll with ``squeue``. Each
  submission is *acknowledgement-gated*: the next ``sbatch`` only fires once the
  controller lists the previous job (see :meth:`SlurmBackend._confirm_queued`),
  so a run is paced by SLURM's real responsiveness instead of a guessed sleep.

``sbatch_available()`` is the single SLURM-vs-local switch used by the ``auto``
selection. Tests patch ``subprocess``/``Popen`` to avoid a live cluster.
"""

from __future__ import annotations

import functools
import getpass
import itertools
import logging
import os
import re
import shutil
import subprocess
import time
from enum import Enum, auto
from pathlib import Path
from typing import IO, Protocol

from pya3eda.errors import BackendError

log = logging.getLogger(__name__)

_JOB_ID_RE = re.compile(r"\b(\d+)\b")
_LOCAL_PREFIX = "local-"
_INVALID_JOB_RE = re.compile(r"invalid job id", re.IGNORECASE)


class _QueueState(Enum):
    """What ``squeue`` reports about one job id."""

    PRESENT = auto()  # controller lists it (pending or running) → acknowledged
    ABSENT = auto()  # controller answered but does not list it → already terminal
    UNAVAILABLE = auto()  # squeue itself failed → no information, retry


class JobSubmissionError(BackendError):
    """Raised when a backend fails to submit a job."""


@functools.lru_cache(maxsize=1)
def _current_user() -> str:
    """Username for ``squeue -u`` (numeric UID fallback in passwd-less envs)."""
    try:
        return getpass.getuser()
    except (KeyError, OSError):
        return str(os.getuid())


def sbatch_available(*, sbatch_cmd: str = "sbatch") -> bool:
    """Return True when ``sbatch`` is on ``PATH`` (i.e. a real SLURM host)."""
    return shutil.which(sbatch_cmd) is not None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class ExecutionBackend(Protocol):
    """Submits a generated script and reports completion."""

    name: str

    def available(self) -> bool:
        """Whether this backend can run in the current environment."""
        ...

    def submit(self, script_path: Path) -> str:
        """Submit *script_path*; return a job ID. Raise :class:`JobSubmissionError` on failure.

        Implementations may accept extra optional keywords (e.g. ``LocalBackend``
        takes ``log_path``); callers using this Protocol only pass *script_path*.
        """
        ...

    def is_finished(self, job_id: str) -> bool:
        """Return True once *job_id* is no longer running."""
        ...


# ---------------------------------------------------------------------------
# Local backend
# ---------------------------------------------------------------------------


class LocalBackend:
    """Run scripts via ``bash`` in the background; poll the child process."""

    name = "local"

    def __init__(self) -> None:
        """Initialise the background-process registry and id counter."""
        self._procs: dict[str, tuple[subprocess.Popen[bytes], IO[bytes]]] = {}
        self._counter = itertools.count(1)

    def available(self) -> bool:
        """Local execution is always possible."""
        return True

    def submit(self, script_path: Path, *, log_path: Path | None = None) -> str:
        """Launch ``bash script_path`` in the background; return a ``local-N`` id.

        The script's ``#SBATCH`` directives are inert to bash, so SLURM's
        stdout/stderr redirection does not fire; we send both streams to
        *log_path* (defaulting to ``<script>.err``) so on-disk artifacts match
        the SLURM run. A non-zero exit is surfaced via status parsing later, not
        raised here.
        """
        script_path = Path(script_path)
        log_path = Path(log_path) if log_path is not None else script_path.with_suffix(".err")
        handle = log_path.open("wb")
        try:
            proc = subprocess.Popen(
                ["bash", str(script_path)],
                stdout=handle,
                stderr=subprocess.STDOUT,
                cwd=script_path.parent,
            )
        except Exception:
            handle.close()
            raise
        job_id = f"{_LOCAL_PREFIX}{next(self._counter)}"
        self._procs[job_id] = (proc, handle)
        log.info("launched %s locally as %s (pid %s)", script_path, job_id, proc.pid)
        return job_id

    def is_finished(self, job_id: str) -> bool:
        """Poll the background job; close its log handle and reap it when done."""
        entry = self._procs.get(job_id)
        if entry is None:
            return True
        proc, handle = entry
        if proc.poll() is None:
            return False
        handle.close()
        self._procs.pop(job_id, None)
        if proc.returncode != 0:
            log.warning("local job %s exited %d", job_id, proc.returncode)
        return True


# ---------------------------------------------------------------------------
# SLURM backend
# ---------------------------------------------------------------------------


class SlurmBackend:
    """Submit scripts with ``sbatch``; poll completion with ``squeue``."""

    name = "slurm"

    def __init__(
        self,
        *,
        sbatch_cmd: str = "sbatch",
        squeue_cmd: str = "squeue",
        appear_grace_polls: int = 3,
        squeue_failure_timeout: float = 300.0,
        confirm_submission: bool = True,
        confirm_timeout: float = 60.0,
        confirm_poll_interval: float = 0.25,
        confirm_max_interval: float = 5.0,
    ) -> None:
        """Configure the ``sbatch`` / ``squeue`` commands (overridable for tests).

        *appear_grace_polls* guards the submit→poll race: a job just ``sbatch``-ed
        may not show up in ``squeue`` for a poll or two (scheduler latency). A
        submitted-but-never-yet-observed job is treated as still running for up to
        this many polls so it is not declared finished before it even starts.

        *squeue_failure_timeout* bounds the transient-vs-fatal split: a ``squeue``
        error is retried (treated as "not finished") only while failures stay
        within this many seconds of the first one. Continuous failure past the
        window raises :class:`BackendError` rather than letting a waited run hang
        forever — a transient blip on a busy cluster resets the window on the next
        success, but a genuinely broken ``squeue`` fails loud.

        *confirm_submission* gates each submission on SLURM acknowledging the
        previous job (see :meth:`_confirm_queued`); *confirm_timeout* bounds that
        wait, and *confirm_poll_interval* / *confirm_max_interval* are the first
        and largest back-off steps between acknowledgement polls.
        """
        self.sbatch_cmd = sbatch_cmd
        self.squeue_cmd = squeue_cmd
        self._appear_grace_polls = appear_grace_polls
        self._squeue_failure_timeout = squeue_failure_timeout
        self._first_squeue_failure: float | None = None  # monotonic time of first failure
        self._seen: set[str] = set()  # job ids observed in squeue at least once
        self._awaiting: dict[str, int] = {}  # submitted, not yet seen → polls elapsed
        self._confirm_submission = confirm_submission
        self._confirm_timeout = confirm_timeout
        self._confirm_poll_interval = confirm_poll_interval
        self._confirm_max_interval = confirm_max_interval

    def available(self) -> bool:
        """Whether ``sbatch`` is on ``PATH``."""
        return sbatch_available(sbatch_cmd=self.sbatch_cmd)

    def submit(self, script_path: Path) -> str:
        """``sbatch`` the script, wait for SLURM to acknowledge it, return the job ID.

        The acknowledgement wait (:meth:`_confirm_queued`) is what keeps a run from
        firing every ``sbatch`` back-to-back at a controller that may be struggling.
        """
        try:
            result = subprocess.run(
                [self.sbatch_cmd, str(script_path)],
                capture_output=True,
                text=True,
                check=True,
                cwd=Path(script_path).parent,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise JobSubmissionError(f"sbatch failed for {script_path}: {exc}") from exc
        m = _JOB_ID_RE.search(result.stdout)
        if not m:
            raise JobSubmissionError(
                f"could not parse job ID from sbatch output: {result.stdout!r}"
            )
        job_id = m.group(1)
        self._awaiting[job_id] = 0  # track until first observed in squeue (race guard)
        log.info("submitted %s as job %s", script_path, job_id)
        self._confirm_queued(job_id)
        return job_id

    def _confirm_queued(self, job_id: str) -> None:
        """Block until SLURM acknowledges *job_id* before the caller submits the next.

        ``sbatch`` returning an ID means slurmctld accepted the job, but on a
        loaded controller it can be seconds before the job is actually visible in
        the queue — and that is exactly when firing the next ``sbatch`` immediately
        makes things worse. A fixed sleep cannot express that: short enough to be
        cheap when the controller is healthy is too short when it is not. So poll
        ``squeue -j`` with a backing-off interval instead — a responsive controller
        confirms on the first query with no sleep at all, a lagging one is waited
        out for precisely as long as it lags.

        Never fatal: the job *is* already queued, so this gate is pacing, not
        correctness. If the wait times out, or ``squeue`` is unusable, it is
        disabled for the rest of the run (warned once) rather than charging the
        same penalty to every remaining submission.
        """
        deadline = time.monotonic() + self._confirm_timeout
        interval = self._confirm_poll_interval
        while self._confirm_submission:
            state = self._queue_state(job_id)
            if not self._confirm_submission:
                return  # squeue itself turned out to be unusable → stop polling
            if state is _QueueState.PRESENT:
                # Acknowledged: also settles the submit→poll race outright, so
                # is_finished needs no appearance grace for this job.
                self._seen.add(job_id)
                self._awaiting.pop(job_id, None)
                log.debug("job %s acknowledged by SLURM", job_id)
                return
            if state is _QueueState.ABSENT:
                # Controller answered and does not list it → already terminal (a
                # very short job) or a queue it cannot report on. Nothing to wait
                # for; leave the appearance grace to is_finished either way.
                log.debug("job %s not listed by squeue after submit; not waiting", job_id)
                return
            if time.monotonic() >= deadline:
                self._disable_confirm(
                    f"squeue did not acknowledge job {job_id} within {self._confirm_timeout:.0f}s"
                )
                return
            time.sleep(interval)
            interval = min(interval * 2, self._confirm_max_interval)

    def _queue_state(self, job_id: str) -> _QueueState:
        """Ask ``squeue`` about a single job id (cheaper than listing the whole queue)."""
        try:
            result = subprocess.run(
                [self.squeue_cmd, "-h", "-j", job_id, "-o", "%i"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            # "Invalid job id" is an answer, not an outage: the controller knows
            # nothing about the job, so it has already left the queue.
            if _INVALID_JOB_RE.search(exc.stderr or ""):
                return _QueueState.ABSENT
            return _QueueState.UNAVAILABLE
        except FileNotFoundError:
            self._disable_confirm(f"{self.squeue_cmd} not found")
            return _QueueState.UNAVAILABLE
        ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if any(i == job_id or i.startswith(f"{job_id}_") for i in ids):
            return _QueueState.PRESENT
        return _QueueState.ABSENT

    def _disable_confirm(self, reason: str) -> None:
        """Turn the acknowledgement gate off for the rest of the run, warning once."""
        if self._confirm_submission:
            self._confirm_submission = False
            log.warning("%s; submitting without acknowledgement gating from here on", reason)

    def is_finished(self, job_id: str) -> bool:
        """Return True once *job_id* is no longer running.

        A job is "finished" only after it has been *observed* in ``squeue`` and
        then disappeared — which, for jobs acknowledged at submit time, is already
        the case before the first poll. A submitted-but-never-yet-seen job is held
        as running for ``appear_grace_polls`` polls to absorb scheduler latency, so the
        throttler/pipeline does not free its cores (or build its SPs) before the
        job has even started. Jobs this backend never submitted fall back to the
        plain "absent ⇒ finished" rule.
        """
        try:
            result = subprocess.run(
                [self.squeue_cmd, "-u", _current_user(), "-o", "%i"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            # squeue is often transient on busy clusters → retry (not-finished), but
            # escalate if it has failed continuously past the timeout so a waited
            # run fails loud instead of hanging forever.
            now = time.monotonic()
            if self._first_squeue_failure is None:
                self._first_squeue_failure = now
            elif now - self._first_squeue_failure > self._squeue_failure_timeout:
                raise BackendError(
                    f"squeue has failed continuously for over "
                    f"{self._squeue_failure_timeout:.0f}s; cannot determine job completion"
                ) from None
            return False
        self._first_squeue_failure = None  # squeue responded → reset the failure window
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        running = lines[1:] if lines else []  # drop the "JOBID" header
        present = any(line == job_id or line.startswith(f"{job_id}_") for line in running)

        if present:
            self._seen.add(job_id)
            self._awaiting.pop(job_id, None)
            return False
        if job_id in self._seen:
            return True  # ran and is now gone → genuinely finished
        if job_id in self._awaiting:
            self._awaiting[job_id] += 1
            if self._awaiting[job_id] >= self._appear_grace_polls:
                self._awaiting.pop(job_id, None)
                return True  # never appeared within grace → assume done / failed to enqueue
            return False  # still within the appearance grace window
        return True  # not a job we submitted → absent means finished


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

BACKENDS: dict[str, type[ExecutionBackend]] = {
    "local": LocalBackend,
    "slurm": SlurmBackend,
}


def get_backend(name: str = "auto") -> ExecutionBackend:
    """Return an execution backend by name.

    ``"auto"`` (default) selects :class:`SlurmBackend` when ``sbatch`` is on
    ``PATH``, else :class:`LocalBackend`. Raise :class:`BackendError` for unknown names.
    """
    if name == "auto":
        return SlurmBackend() if sbatch_available() else LocalBackend()
    cls = BACKENDS.get(name)
    if cls is None:
        available = ", ".join(["auto", *sorted(BACKENDS)])
        raise BackendError(f"Unknown backend '{name}'. Available: {available}")
    return cls()
