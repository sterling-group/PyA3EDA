"""
XYZ Format Utilities

Centralized formatting functions for XYZ coordinate data.
"""


def format_xyz_coordinate_line(element: str, x: float, y: float, z: float) -> str:
    """
    Format a single coordinate line for XYZ output.

    Args:
        element: Element symbol
        x, y, z: Coordinate values

    Returns:
        Formatted coordinate line string
    """
    return f"{element}   {x:14.10f}   {y:14.10f}   {z:14.10f}"


def format_xyz_content(
    n_atoms: int, charge: int, multiplicity: int, atoms: list[str]
) -> str:
    """
    Format complete XYZ file content.

    Args:
        n_atoms: Number of atoms
        charge: Molecular charge
        multiplicity: Spin multiplicity
        atoms: List of formatted atom lines

    Returns:
        Complete XYZ file content string
    """
    if not atoms:
        return ""

    content_lines = [str(n_atoms), f"{charge} {multiplicity}"]
    content_lines.extend(atoms)

    return "\n".join(content_lines) + "\n"
