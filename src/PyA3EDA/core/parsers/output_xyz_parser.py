import re
from typing import Any, Dict, Optional

from PyA3EDA.core.utils.xyz_format_utils import format_xyz_coordinate_line


def parse_qchem_output_xyz(out_text: str, identifier: str) -> Optional[Dict[str, Any]]:
    """
    Parses a Q-Chem output file text to extract the final atomic coordinates from the output.

    It finds the last occurrence of the "Standard Nuclear Orientation" block and extracts
    coordinate lines. Each coordinate line is expected to start with an index, an element symbol,
    and three floating point numbers.

    Also extracts charge and multiplicity from the molecular input section.

    Returns a dictionary with:
      'n_atoms': int,
      'atoms': list[str] (each formatted as "Element   x   y   z"),
      'Charge': int,
      'Multiplicity': int
    """
    # Extract charge and multiplicity from the molecular input section
    charge, multiplicity = _extract_charge_multiplicity(out_text)

    # Locate the last occurrence of the orientation block.
    orient_tag = "Standard Nuclear Orientation"
    orient_positions = [m.start() for m in re.finditer(re.escape(orient_tag), out_text)]
    if not orient_positions:
        return None
    last_orient_index = orient_positions[-1]
    orientation_block = out_text[last_orient_index:]

    # Use a robust regex to match coordinate lines in the orientation block.
    coord_line_re = re.compile(
        r"^\s*\d+\s+([A-Za-z]+)\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)[ \t]+"
        r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)[ \t]+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)",
        re.MULTILINE,
    )
    atoms = []
    for line in orientation_block.splitlines():
        match = coord_line_re.match(line)
        if match:
            element = match.group(1)
            x = float(match.group(2))
            y = float(match.group(3))
            z = float(match.group(4))
            atoms.append(format_xyz_coordinate_line(element, x, y, z))

    if not atoms:
        return None

    return {
        "n_atoms": len(atoms),
        "atoms": atoms,
        "Charge": charge,
        "Multiplicity": multiplicity,
    }


def _extract_charge_multiplicity(out_text: str) -> tuple[int, int]:
    """
    Extract charge and multiplicity from Q-Chem output file.

    Looks for the $molecule section in the "User input:" block.
    The format is:
    $molecule
    charge multiplicity
    [coordinates or fragments]
    $end

    For fragmented molecules, takes the first charge/multiplicity line.
    Returns (0, 1) if not found.
    """
    # Look for the $molecule section in the output
    molecule_pattern = r"\$molecule\s*\n\s*([+-]?\d+)\s+(\d+)"
    match = re.search(molecule_pattern, out_text, re.MULTILINE)

    if match:
        charge = int(match.group(1))
        multiplicity = int(match.group(2))
        return charge, multiplicity

    # Return defaults if not found
    return 0, 1
