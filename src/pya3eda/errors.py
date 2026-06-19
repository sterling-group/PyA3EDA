"""Domain exceptions for pya3eda."""

from __future__ import annotations


class IncompleteDataError(ValueError):
    """A derived value could not be computed because a required input was missing.

    Raised instead of silently collapsing a partial computation to ``None`` — a
    free energy assembled from a present electronic energy but a *missing* thermal
    correction (or similar) "is not true", so the gap must fail loudly rather than
    propagate a wrong or absent number. Caught and aggregated per extraction run so
    one error lists every gap at once.
    """

    @classmethod
    def combine(cls, messages: list[str]) -> IncompleteDataError:
        """Build one error from many per-calculation messages."""
        body = "\n  - ".join(messages)
        return cls(f"Incomplete data for {len(messages)} computation(s):\n  - {body}")
