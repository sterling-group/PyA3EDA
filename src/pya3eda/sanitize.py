"""Filename sanitization for safe filesystem paths."""

ESCAPE_MAP: dict[str, str] = {
    " ": "-space-",
    "(": "-lparen-",
    ")": "-rparen-",
    "[": "-lbracket-",
    "]": "-rbracket-",
    "{": "-lbrace-",
    "}": "-rbrace-",
    ",": "-comma-",
    ";": "-semicolon-",
    "*": "-asterisk-",
    "?": "-qmark-",
    "&": "-and-",
    "|": "-pipe-",
    "<": "-lt-",
    ">": "-gt-",
    '"': "-dq-",
    "'": "-sq-",
    "\\": "-backslash-",
    ":": "-colon-",
    "$": "-dollar-",
    "~": "-tilde-",
    "!": "-exclamation-",
    "=": "-equal-",
    "\t": "-tab-",
    "\n": "-newline-",
}


def sanitize(name: str) -> str:
    """Replace unsafe characters in *name* for use in file/directory names."""
    result = str(name)
    for char, replacement in ESCAPE_MAP.items():
        result = result.replace(char, replacement)
    return result.strip("_")
