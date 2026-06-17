"""Q-Chem input file parsing and modification."""

from __future__ import annotations

import re
from pathlib import Path


def read_input_file(input_path: Path) -> list[str]:
    """Read a Q-Chem input file and return its lines."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file '{input_path}' does not exist.")
    return input_path.read_text().splitlines(keepends=True)


def parse_mem_total(lines: list[str]) -> list[int]:
    """Return all ``mem_total`` values found in ``$rem`` blocks."""
    text = "".join(lines)
    values: list[int] = []
    for block in re.findall(r"\$rem(.*?)\$end", text, re.DOTALL | re.IGNORECASE):
        values.extend(int(v) for v in re.findall(r"\bmem_total\s*=?\s*(\d+)", block, re.IGNORECASE))
    return values


def adjust_mem_total(lines: list[str], mem_total_value: int) -> tuple[list[str], bool]:
    """Set ``mem_total`` in every ``$rem`` block, adding it if absent.

    Returns the (possibly modified) lines and whether any change was made.
    """
    text = "".join(lines)
    original = text

    def _adjust(match: re.Match) -> str:
        """Replace or insert ``mem_total`` within a single ``$rem`` block."""
        block = match.group(0)
        if re.search(r"\bmem_total\s*=?\s*\d+", block, re.IGNORECASE):
            return re.sub(
                r"(\bmem_total\s*=?\s*)(\d+)",
                rf"\g<1>{mem_total_value}",
                block,
                flags=re.IGNORECASE,
            )
        return block.replace("$rem", f"$rem\n   mem_total {mem_total_value}", 1)

    adjusted = re.sub(r"\$rem(.*?)\$end", _adjust, text, flags=re.DOTALL | re.IGNORECASE)
    return adjusted.splitlines(keepends=True), adjusted != original
