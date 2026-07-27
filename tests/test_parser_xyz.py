"""Tests for pya3eda.parser.xyz — XYZ parsing and formatting.

All tests are self-contained using synthetic Q-Chem output snippets.
"""

from __future__ import annotations

from pya3eda.parser.xyz import (
    XYZData,
    format_coord_line,
    format_xyz,
    parse_output_fragments,
    parse_output_xyz,
    parse_xyz,
)
from tests.synthetic_outputs import FRAGMENTED_OPT_OUTPUT, OPT_OUTPUT, TS_OUTPUT

# ===================================================================
# parse_xyz
# ===================================================================


class TestParseXYZ:
    def test_simple_water(self) -> None:
        text = "3\n0 1\nO   0.0  0.0  0.0\nH   0.0  0.757  0.587\nH   0.0  -0.757  0.587\n"
        result = parse_xyz(text)
        assert result is not None
        assert result.n_atoms == 3
        assert result.charge == 0
        assert result.multiplicity == 1
        assert len(result.atoms) == 3
        assert result.atoms[0].startswith("O")

    def test_returns_none_for_too_short(self) -> None:
        assert parse_xyz("3\n") is None
        assert parse_xyz("") is None

    def test_returns_none_for_bad_atom_count(self) -> None:
        assert parse_xyz("abc\n0 1\nH 0 0 0\n") is None

    def test_returns_none_for_bad_charge_mult(self) -> None:
        assert parse_xyz("1\nbad\nH 0 0 0\n") is None

    def test_respects_atom_count(self) -> None:
        text = "1\n0 1\nH   0.0  0.0  0.0\nO   1.0  1.0  1.0\n"
        result = parse_xyz(text)
        assert result is not None
        assert result.n_atoms == 1
        assert len(result.atoms) == 1

    def test_returns_none_for_truncated_atoms(self) -> None:
        # Declares 3 atoms but only 2 coordinate lines are present.
        text = "3\n0 1\nO   0.0  0.0  0.0\nH   0.0  0.757  0.587\n"
        assert parse_xyz(text) is None


# ===================================================================
# format_coord_line
# ===================================================================


class TestFormatCoordLine:
    def test_basic_formatting(self) -> None:
        line = format_coord_line("C", 1.234, -5.678, 0.0)
        assert "C" in line
        assert "1.2340000000" in line
        assert "-5.6780000000" in line

    def test_precision(self) -> None:
        line = format_coord_line("H", 0.123456789012, 0.0, 0.0)
        # Should have 10 decimal places
        assert "0.1234567890" in line


# ===================================================================
# format_xyz
# ===================================================================


class TestFormatXYZ:
    def test_round_trip(self) -> None:
        data = XYZData(
            n_atoms=2,
            charge=0,
            multiplicity=1,
            atoms=[
                "H   0.0000000000   0.0000000000   0.0000000000",
                "H   0.0000000000   0.0000000000   0.7400000000",
            ],
        )
        text = format_xyz(data)
        lines = text.strip().splitlines()
        assert lines[0] == "2"
        assert lines[1] == "0 1"
        assert len(lines) == 4


# ===================================================================
# parse_output_xyz
# ===================================================================


class TestParseOutputXYZ:
    def test_opt_output_extracts_coords(self) -> None:
        """Synthetic OPT output should yield the final geometry (8 atoms)."""
        result = parse_output_xyz(OPT_OUTPUT)
        assert result is not None
        assert result.n_atoms == 8
        assert len(result.atoms) == 8

    def test_picks_last_orientation_block(self) -> None:
        """OPT_OUTPUT has two Standard Nuclear Orientation blocks — picks the last."""
        result = parse_output_xyz(OPT_OUTPUT)
        assert result is not None
        # Last block has specific coords (0.4205...) not dummy (0.0/1.0)
        assert "0.4205497061" in result.atoms[0]

    def test_ts_output_extracts_coords(self) -> None:
        result = parse_output_xyz(TS_OUTPUT)
        assert result is not None
        assert result.n_atoms == 1
        # Last block has coords (1.0, 2.0, 3.0)
        assert "1.0000000000" in result.atoms[0]

    def test_returns_none_for_no_orientation_block(self) -> None:
        assert parse_output_xyz("no coordinate data") is None

    def test_extracts_last_orientation_inline(self) -> None:
        """Should pick the last Standard Nuclear Orientation block."""
        block = """
 $molecule
 0 1
 $end

 Standard Nuclear Orientation (Angstroms)
    I     Atom           X            Y            Z
 ----------------------------------------------------------------
    1      H       0.0000000    0.0000000    0.0000000
 ----------------------------------------------------------------

 Standard Nuclear Orientation (Angstroms)
    I     Atom           X            Y            Z
 ----------------------------------------------------------------
    1      H       1.0000000    2.0000000    3.0000000
 ----------------------------------------------------------------
"""
        result = parse_output_xyz(block)
        assert result is not None
        assert result.n_atoms == 1
        # Should be from the LAST block (1.0, 2.0, 3.0)
        assert "1.0000000000" in result.atoms[0]

    def test_stops_at_table_end_ignores_trailing_table(self) -> None:
        """A coordinate-shaped table after the final geometry must not inflate the
        atom count — the scan stops at the first non-matching line after the table."""
        block = """
 $molecule
 0 1
 $end

 Standard Nuclear Orientation (Angstroms)
    I     Atom           X            Y            Z
 ----------------------------------------------------------------
    1      O       0.0000000    0.0000000    0.0000000
    2      H       1.0000000    0.0000000    0.0000000
 ----------------------------------------------------------------

 Some later section with a coordinate-shaped table:
    1      C       9.0000000    9.0000000    9.0000000
    2      C       8.0000000    8.0000000    8.0000000
    3      C       7.0000000    7.0000000    7.0000000
"""
        result = parse_output_xyz(block)
        assert result is not None
        assert result.n_atoms == 2  # only the real geometry, not the trailing decoy
        assert all("9.0000000" not in a for a in result.atoms)


class TestParseXYZEdgeCases:
    def test_invalid_charge_mult(self) -> None:
        """Non-integer charge/mult on line 2 → None."""
        text = "1\nabc def\nH  0.0(  0.0  0.0\n"
        assert parse_xyz(text) is None

    def test_no_orientation_block(self) -> None:
        """Output without 'Standard Nuclear Orientation' → None."""
        text = "$molecule\n0 1\n$end\nSome output without orientation\n"
        result = parse_output_xyz(text)
        assert result is None

    def test_orientation_block_no_atoms(self) -> None:
        """Orientation block present but no coordinate lines → None."""
        text = (
            "$molecule\n0 1\n$end\n"
            "Standard Nuclear Orientation (Angstroms)\n"
            "  I     Atom           X            Y            Z\n"
            "-------\n"
            "no atom lines here\n"
        )
        result = parse_output_xyz(text)
        assert result is None


# ===================================================================
# parse_output_fragments
# ===================================================================


class TestParseOutputFragments:
    """The echoed $molecule tells us how the optimisation split its atoms."""

    def test_two_fragments(self) -> None:
        layout = parse_output_fragments(FRAGMENTED_OPT_OUTPUT)
        assert layout is not None
        assert (layout.charge, layout.multiplicity) == (0, 1)
        assert [(f.charge, f.multiplicity, f.n_atoms) for f in layout.fragments] == [
            (1, 1, 1),
            (-1, 1, 4),
        ]

    def test_anchors_to_the_first_block(self) -> None:
        """A trailing Z-matrix Print $molecule must not be mistaken for the layout.

        FRAGMENTED_OPT_OUTPUT ends with an unfragmented z-matrix block; picking that one
        up would yield no fragments at all.
        """
        layout = parse_output_fragments(FRAGMENTED_OPT_OUTPUT)
        assert layout is not None
        assert len(layout.fragments) == 2

    def test_no_molecule_block(self) -> None:
        assert parse_output_fragments("just some output\n") is None

    def test_unfragmented_molecule(self) -> None:
        """No '---' separators → nothing to inherit."""
        assert parse_output_fragments(OPT_OUTPUT) is None

    def test_molecule_read(self) -> None:
        assert parse_output_fragments("$molecule\nread\n$end\n") is None

    def test_missing_total_charge_line(self) -> None:
        text = "$molecule\n---\n0 1\nH  0.0  0.0  0.0\n$end\n"
        assert parse_output_fragments(text) is None

    def test_bad_total_charge_line(self) -> None:
        text = "$molecule\nnot a charge\n---\n0 1\nH  0.0  0.0  0.0\n$end\n"
        assert parse_output_fragments(text) is None

    def test_empty_fragment(self) -> None:
        text = "$molecule\n0 1\n---\n0 1\nH  0.0  0.0  0.0\n---\n\n$end\n"
        assert parse_output_fragments(text) is None

    def test_bad_fragment_header(self) -> None:
        text = "$molecule\n0 1\n---\nHe is not a header\nH  0.0  0.0  0.0\n$end\n"
        assert parse_output_fragments(text) is None

    def test_three_fragments_are_parsed(self) -> None:
        """Parsing is n-ary even though the builder only consumes two."""
        text = (
            "$molecule\n0 1\n"
            "---\n1 1\nLi  0.0  0.0  0.0\n"
            "---\n-1 1\nF   1.0  0.0  0.0\n"
            "---\n0 1\nO   2.0  0.0  0.0\nH  3.0  0.0  0.0\n"
            "$end\n"
        )
        layout = parse_output_fragments(text)
        assert layout is not None
        assert [f.n_atoms for f in layout.fragments] == [1, 1, 2]

    def test_ghost_atoms_are_counted(self) -> None:
        text = "$molecule\n0 1\n---\n0 1\n@He  0.0  0.0  0.0\nH  1.0  0.0  0.0\n$end\n"
        layout = parse_output_fragments(text)
        assert layout is not None
        assert layout.fragments[0].n_atoms == 2
