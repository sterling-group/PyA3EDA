"""CPU-core budget throttler for batch job submission.

A run submits many jobs, but a host (or a politeness cap on a cluster) has a
fixed core budget. The throttler tracks each active job's core demand and
blocks new submissions until the budget allows. Polling delegates to a
caller-supplied ``is_finished`` callable (DIP) so it works for both local
processes and SLURM job IDs, and so tests can inject a fake.

Ported from ChemRefine's two-resource throttler, reduced to the single CPU
budget pya3eda needs (Q-Chem has no GPU path).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

log = logging.getLogger(__name__)

IsFinishedFn = Callable[[str], bool]


class ThrottleTimeoutError(RuntimeError):
    """Raised when the core budget does not free up within a deadline."""


class Throttler:
    """Track active jobs against a CPU-core budget."""

    def __init__(self, *, max_cores: int, poll_interval: float = 10.0) -> None:
        """Create a throttler with a ``max_cores`` budget and poll cadence."""
        if max_cores < 1:
            raise ValueError(f"max_cores must be >= 1; got {max_cores}")
        self.max_cores = max_cores
        self.poll_interval = poll_interval
        self._active: dict[str, int] = {}  # job_id -> cores

    @property
    def cores_in_use(self) -> int:
        """Sum of the core demand of all currently active jobs."""
        return sum(self._active.values())

    @property
    def active_jobs(self) -> tuple[str, ...]:
        """Snapshot of active job IDs."""
        return tuple(self._active)

    def register(self, job_id: str, cores: int) -> None:
        """Mark a newly-submitted job as active, charging ``cores``."""
        if cores < 1:
            raise ValueError(f"cores must be >= 1; got {cores}")
        self._active[job_id] = cores

    def wait_for_room(
        self,
        cores_needed: int,
        *,
        is_finished: IsFinishedFn,
        max_wait_seconds: float | None = None,
    ) -> None:
        """Block until ``cores_needed`` cores can be allocated.

        Reaps finished jobs each iteration via ``is_finished``; sleeps
        ``poll_interval`` between checks. Raises :class:`ThrottleTimeoutError`
        if ``max_wait_seconds`` elapses first.
        """
        if cores_needed > self.max_cores:
            raise ValueError(
                f"requested {cores_needed} cores exceeds the total budget {self.max_cores}"
            )
        deadline = time.monotonic() + max_wait_seconds if max_wait_seconds is not None else None
        while True:
            self._reap(is_finished)
            if self.cores_in_use + cores_needed <= self.max_cores:
                return
            if deadline is not None and time.monotonic() >= deadline:
                raise ThrottleTimeoutError(
                    f"timed out after {max_wait_seconds}s waiting for {cores_needed} cores"
                )
            log.debug(
                "waiting on budget: %d+%d/%d", self.cores_in_use, cores_needed, self.max_cores
            )
            time.sleep(self.poll_interval)

    def wait_all(
        self,
        *,
        is_finished: IsFinishedFn,
        max_wait_seconds: float | None = None,
    ) -> None:
        """Block until every active job has finished."""
        deadline = time.monotonic() + max_wait_seconds if max_wait_seconds is not None else None
        while self._active:
            self._reap(is_finished)
            if not self._active:
                return
            if deadline is not None and time.monotonic() >= deadline:
                raise ThrottleTimeoutError(
                    f"timed out after {max_wait_seconds}s waiting for all jobs to finish"
                )
            time.sleep(self.poll_interval)

    def _reap(self, is_finished: IsFinishedFn) -> None:
        """Drop every active job that ``is_finished`` reports done."""
        for jid in list(self._active):
            if is_finished(jid):
                cores = self._active.pop(jid)
                log.info("job %s finished, freed %d cores", jid, cores)
