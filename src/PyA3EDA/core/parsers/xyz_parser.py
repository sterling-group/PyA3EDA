from typing import Any, Dict, Optional

# Cache for parsed XYZ data keyed by identifier.
_xyz_cache: dict[str, Dict[str, Any]] = {}


def parse_xyz(xyz_text: str, identifier: str) -> Optional[Dict[str, Any]]:
    """
    Parse an XYZ file text and cache the result.

    Expects:
      - First line: total number of atoms (integer)
      - Second line: two numbers: charge and multiplicity
      - Subsequent lines: atom information (element and xyz coordinates)

    Returns a dictionary with keys:
      'n_atoms': int,
      'charge': int,
      'multiplicity': int,
      'atoms': list[str]  (atom lines)

    The result is cached using the provided identifier.
    """
    if identifier in _xyz_cache:
        return _xyz_cache[identifier]

    lines = xyz_text.splitlines()
    if len(lines) < 2:
        return None
    try:
        n_atoms = int(lines[0].rstrip())
    except Exception:
        return None
    parts = lines[1].split()
    if len(parts) < 2:
        return None
    try:
        charge = int(parts[0])
        multiplicity = int(parts[1])
    except Exception:
        return None
    # Use exactly the next n_atoms lines as the atoms
    atoms = lines[2 : 2 + n_atoms]
    result = {
        "n_atoms": n_atoms,
        "charge": charge,
        "multiplicity": multiplicity,
        "atoms": atoms,
    }
    _xyz_cache[identifier] = result
    return result
