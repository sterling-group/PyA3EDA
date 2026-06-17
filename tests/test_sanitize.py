"""Tests for pya3eda.sanitize — filename sanitization."""

from __future__ import annotations

from pya3eda.sanitize import sanitize


class TestSanitize:
    def test_passthrough_safe_names(self) -> None:
        assert sanitize("prop2enal") == "prop2enal"
        assert sanitize("wB97X-V") == "wB97X-V"
        assert sanitize("def2-SVP") == "def2-SVP"

    def test_escapes_parentheses(self) -> None:
        result = sanitize("B3LYP(D3)")
        assert "(" not in result
        assert ")" not in result
        assert "-lparen-" in result
        assert "-rparen-" in result

    def test_escapes_equals(self) -> None:
        result = sanitize("eda2=1")
        assert "=" not in result
        assert "-equal-" in result

    def test_escapes_space(self) -> None:
        result = sanitize("my file")
        assert " " not in result
        assert "-space-" in result

    def test_no_leading_trailing_underscores(self) -> None:
        result = sanitize("_name_")
        assert not result.startswith("_")
        assert not result.endswith("_")
