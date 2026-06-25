"""Exception hierarchy for pya3eda.

Every exception inherits from :class:`PyA3EDAError` and carries a non-zero
``exit_code`` so the CLI can catch one type and translate the failure mode into a
deterministic process exit code (see ``cli.main``). Assign the next free integer
when adding a class.

============  ============================================
Exit code     Meaning
============  ============================================
``1``         :class:`PyA3EDAError` — generic / catch-all
``2``         :class:`ConfigError` — YAML config missing or invalid
``3``         :class:`TemplateNotFoundError` — template / input file missing
``4``         :class:`IncompleteDataError` — derived value missing a required input
``5``         :class:`BackendError` — execution backend unknown or refused a job
``6``         :class:`RunOptionError` — invalid run / job options
``7``         :class:`ThrottleTimeoutError` — wait deadline expired
``8``         :class:`~pya3eda.runner.clusters.ClusterConfigError` — cluster config missing/invalid
============  ============================================
"""

from __future__ import annotations


class PyA3EDAError(Exception):
    """Base class for every pya3eda-raised exception."""

    exit_code: int = 1


class ConfigError(PyA3EDAError):
    """The YAML config is missing, malformed, or fails validation."""

    exit_code = 2


class TemplateNotFoundError(PyA3EDAError):
    """A required template or input file does not exist."""

    exit_code = 3


class IncompleteDataError(PyA3EDAError):
    """A derived value could not be computed because a required input was missing.

    Raised instead of silently collapsing a partial computation to ``None`` — a
    free energy assembled from a present electronic energy but a *missing* thermal
    correction "is not true", so the gap must fail loudly. Caught and aggregated
    per extraction run so one error lists every gap at once.
    """

    exit_code = 4

    @classmethod
    def combine(cls, messages: list[str]) -> IncompleteDataError:
        """Build one error from many per-calculation messages."""
        body = "\n  - ".join(messages)
        return cls(f"Incomplete data for {len(messages)} computation(s):\n  - {body}")


class BackendError(PyA3EDAError):
    """An execution backend is unknown or refused a job."""

    exit_code = 5


class RunOptionError(PyA3EDAError):
    """Invalid run / job options (parallelism, version, qcsetup, core budget, …)."""

    exit_code = 6


class ThrottleTimeoutError(PyA3EDAError):
    """A throttled wait exceeded its configured deadline."""

    exit_code = 7
