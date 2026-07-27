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


class Fragment(NamedTuple):
    """One fragment of a fragmented ``$molecule`` block — size and state, no coordinates."""

    charge: int
    multiplicity: int
    n_atoms: int


class MoleculeLayout(NamedTuple):
    """How a fragmented ``$molecule`` block divides its atoms between fragments."""

    charge: int
    multiplicity: int
    fragments: list[Fragment]


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

_MOLECULE_BLOCK_RE = re.compile(r"\$molecule\s*\n(.*?)\$end", re.DOTALL | re.IGNORECASE)

_CHARGE_MULT_RE = re.compile(r"^\s*([+-]?\d+)\s+(\d+)\s*$")

# "Element x y z", tolerating a ghost-atom "@" prefix and isotope digits.
_XYZ_ATOM_RE = re.compile(
    r"^\s*@?[A-Za-z]{1,3}\d*" + r"".join([r"\s+[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"] * 3) + r"\s*$"
)


def parse_output_fragments(text: str) -> MoleculeLayout | None:
    """Read the fragment layout from the ``$molecule`` block echoed in a Q-Chem output.

    Returns the total charge/multiplicity plus one :class:`Fragment` per ``---``-separated
    block — sizes and charge states only, deliberately **never coordinates**.  Optimised
    coordinates come from the last ``Standard Nuclear Orientation`` block instead (see
    :func:`parse_output_xyz`); the echoed block holds the *starting* geometry, and only its
    fragmentation — invariant across an optimisation — is of interest here.

    ``None`` means "no usable layout, fall back to templates": no ``$molecule`` block, no
    ``---`` separators (an unfragmented or z-matrix molecule, or ``$molecule read``), or a
    fragment header that is not ``charge multiplicity``.

    Anchored to the *first* block on purpose: an optimisation echoes its input near the top,
    then may print a trailing ``Z-matrix Print:`` ``$molecule`` in internal coordinates that
    carries no fragment structure at all.
    """
    m = _MOLECULE_BLOCK_RE.search(text)
    if m is None:
        return None

    # Split the block on its "---" fragment separators.
    segments: list[list[str]] = [[]]
    for line in m.group(1).splitlines():
        if line.strip() == "---":
            segments.append([])
        else:
            segments[-1].append(line)

    if len(segments) < 2:
        return None  # no separators → not a fragmented molecule

    total_lines = [ln for ln in segments[0] if ln.strip()]
    if not total_lines:
        return None
    total = _CHARGE_MULT_RE.match(total_lines[0])
    if total is None:
        return None

    fragments: list[Fragment] = []
    for segment in segments[1:]:
        lines = [ln for ln in segment if ln.strip()]
        if not lines:
            return None
        head = _CHARGE_MULT_RE.match(lines[0])
        if head is None:
            return None
        fragments.append(
            Fragment(
                charge=int(head.group(1)),
                multiplicity=int(head.group(2)),
                n_atoms=sum(1 for ln in lines[1:] if _XYZ_ATOM_RE.match(ln)),
            )
        )

    return MoleculeLayout(
        charge=int(total.group(1)),
        multiplicity=int(total.group(2)),
        fragments=fragments,
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
