"""XYZ template and Q-Chem output coordinate parsing."""

from __future__ import annotations

import re
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class XYZData(NamedTuple):
    """Parsed XYZ structure."""

    n_atoms: int
    charge: int
    multiplicity: int
    atoms: list[str]  # formatted "Element   x   y   z" lines


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_coord_line(element: str, x: float, y: float, z: float) -> str:
    """Format a single coordinate line for XYZ output."""
    return f"{element}   {x:14.10f}   {y:14.10f}   {z:14.10f}"


def format_xyz(data: XYZData) -> str:
    """Format a complete XYZ file string."""
    lines = [str(data.n_atoms), f"{data.charge} {data.multiplicity}"]
    lines.extend(data.atoms)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Template XYZ parsing
# ---------------------------------------------------------------------------


def parse_xyz(text: str) -> XYZData | None:
    """Parse an XYZ-format string (n_atoms / charge mult / atom lines).

    Returns ``None`` if the text is malformed.
    """
    lines = text.splitlines()
    if len(lines) < 3:
        return None
    try:
        n_atoms = int(lines[0].strip())
    except ValueError:
        return None

    parts = lines[1].split()
    if len(parts) < 2:
        return None
    try:
        charge = int(parts[0])
        multiplicity = int(parts[1])
    except ValueError:
        return None

    atoms = lines[2 : 2 + n_atoms]
    # Reject truncated files: a declared count larger than the available
    # coordinate lines would otherwise yield an XYZData whose header count
    # disagrees with its body (and a malformed $molecule block downstream).
    if len(atoms) != n_atoms:
        return None
    return XYZData(n_atoms=n_atoms, charge=charge, multiplicity=multiplicity, atoms=atoms)


# ---------------------------------------------------------------------------
# Q-Chem output coordinate extraction
# ---------------------------------------------------------------------------

_COORD_RE = re.compile(
    r"^\s*\d+\s+([A-Za-z]+)\s+"
    r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s+"
    r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s+"
    r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)",
    re.MULTILINE,
)

_MOLECULE_RE = re.compile(
    r"\$molecule\s*\n\s*([+-]?\d+)\s+(\d+)",
    re.MULTILINE,
)


def parse_output_xyz(text: str) -> XYZData | None:
    """Extract the last optimised geometry from a Q-Chem output.

    Looks for the final "Standard Nuclear Orientation" block and reads the
    coordinate table.  Charge/multiplicity are extracted from the ``$molecule``
    section.
    """
    # Charge / multiplicity
    mol_match = _MOLECULE_RE.search(text)
    charge = int(mol_match.group(1)) if mol_match else 0
    mult = int(mol_match.group(2)) if mol_match else 1

    # Last orientation block
    tag = "Standard Nuclear Orientation"
    positions = [m.start() for m in re.finditer(re.escape(tag), text)]
    if not positions:
        return None
    block = text[positions[-1] :]

    atoms: list[str] = []
    for line in block.splitlines():
        m = _COORD_RE.match(line)
        if m:
            atoms.append(
                format_coord_line(
                    m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))
                )
            )
        elif atoms:
            # The coordinate rows form one contiguous table; the first
            # non-matching line after it (the trailing separator) ends the
            # geometry. Stop here so a later coordinate-shaped table (normal
            # modes, a second orientation, …) cannot inflate the atom count.
            break

    if not atoms:
        return None
    return XYZData(n_atoms=len(atoms), charge=charge, multiplicity=mult, atoms=atoms)
