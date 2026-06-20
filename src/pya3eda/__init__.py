"""pya3eda — Python automation for Asymmetrically-constrained Adiabatic ALMO-EDA."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pya3eda")
except PackageNotFoundError:  # pragma: no cover - only when run from a source tree
    __version__ = "0+unknown"

__all__ = ["__version__"]
