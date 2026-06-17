"""Job submission via pluggable backends."""

from __future__ import annotations

import logging
import time

from pya3eda.registry import CalcRegistry
from pya3eda.runner.backend import get_backend
from pya3eda.status.checker import should_process

log = logging.getLogger(__name__)

DEFAULT_DELAY = 5.2  # seconds between submissions


def run_all(
    registry: CalcRegistry,
    criteria: str,
    *,
    backend: str = "qqchem",
    extra_argv: list[str] | None = None,
) -> int:
    """Submit jobs for every calculation matching *criteria*.

    *backend* selects the submission backend (e.g. ``"qqchem"``).
    *extra_argv* are raw CLI tokens forwarded to the backend.

    Returns the number of jobs successfully submitted.
    """
    if not criteria:
        log.warning("No run criteria specified")
        return 0

    be = get_backend(backend)
    count = 0
    for spec in registry.all_calcs:
        if not spec.input_path.exists():
            continue
        if not should_process(spec, criteria):
            continue
        log.info("Submitting: %s", spec.input_path)
        if be.submit(spec.input_path, extra_argv=extra_argv):
            log.info("Submitted: %s", spec.input_path)
            count += 1
            time.sleep(DEFAULT_DELAY)

    log.info("Total jobs submitted: %d", count)
    return count
