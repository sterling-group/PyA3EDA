"""pya3eda — Python automation for Asymmetrically-constrained Adiabatic ALMO-EDA."""

from __future__ import annotations

__all__ = ["__version__"]


def __getattr__(name: str) -> str:
    """Resolve ``__version__`` lazily (PEP 562).

    The ``importlib.metadata`` import + lookup costs ~50 ms and is only needed
    when the version is actually read (``pya3eda --version``). Deferring it keeps
    that cost off every other command's import path.
    """
    if name == "__version__":
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("pya3eda")
        except PackageNotFoundError:
            return "0+unknown"
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
