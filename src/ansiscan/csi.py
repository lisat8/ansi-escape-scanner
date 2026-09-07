"""Interpret the parameters inside CSI escape sequences.

`scanner.iter_tokens` finds CSI sequences and hands back their raw text
(e.g. "\\x1b[38;5;208m") without saying what it means. This module parses
that text into structured data for the two kinds of CSI sequence callers
run into most often: SGR (colors and text attributes) and cursor
movement. Anything else, parse_csi still gives you the raw parameter
fields to work with yourself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple, Union

_CSI_PARTS = re.compile(
    r"\x1b\[(?P<params>[0-9:;<=>?]*)(?P<intermediate>[ -/]*)(?P<final>[@-~])"
)


@dataclass(frozen=True)
class ParsedCSI:
    """The parameter, intermediate, and final-byte parts of one CSI sequence."""

    params: Tuple[str, ...]
    intermediate: str
    final: str

    def int_params(self, default: int = 0) -> Tuple[int, ...]:
        """Parameters as integers, with omitted fields filled in as `default`.

        CSI parameters are `;`-separated and any field can be empty (e.g.
        "\\x1b[;5H" means "default row, column 5"), so this isn't just
        `int(p)` for each piece. Sub-parameters after a `:` (as SGR uses
        for `38:2:r:g:b`) aren't relevant here; only the leading piece of
        each field is converted.
        """
        result = []
        for p in self.params:
            head = p.split(":", 1)[0]
            result.append(int(head) if head else default)
        return tuple(result)


def parse_csi(sequence: str) -> Optional[ParsedCSI]:
    """Break a raw CSI sequence string (as produced by iter_tokens) into
    its parameter, intermediate, and final-byte parts.

    Returns None if `sequence` isn't a well-formed CSI sequence.
    """
    match = _CSI_PARTS.fullmatch(sequence)
    if match is None:
        return None
    raw_params = match.group("params")
    params = tuple(raw_params.split(";")) if raw_params else ()
    return ParsedCSI(params, match.group("intermediate"), match.group("final"))


# ---------------------------------------------------------------------------
# SGR (Select Graphic Rendition): text color and attributes.


class SGRAttribute(Enum):
    RESET = auto()
    BOLD = auto()
    DIM = auto()
    ITALIC = auto()
    UNDERLINE = auto()
    BLINK = auto()
    REVERSE = auto()
    CONCEAL = auto()
    STRIKETHROUGH = auto()
    NOT_BOLD_OR_DIM = auto()
    NOT_ITALIC = auto()
    NOT_UNDERLINE = auto()
    NOT_BLINK = auto()
    NOT_REVERSE = auto()
    NOT_CONCEAL = auto()
    NOT_STRIKETHROUGH = auto()
    DEFAULT_FOREGROUND = auto()
    DEFAULT_BACKGROUND = auto()


_SGR_ATTRIBUTES = {
    0: SGRAttribute.RESET,
    1: SGRAttribute.BOLD,
    2: SGRAttribute.DIM,
    3: SGRAttribute.ITALIC,
    4: SGRAttribute.UNDERLINE,
    5: SGRAttribute.BLINK,
    7: SGRAttribute.REVERSE,
    8: SGRAttribute.CONCEAL,
    9: SGRAttribute.STRIKETHROUGH,
    22: SGRAttribute.NOT_BOLD_OR_DIM,
    23: SGRAttribute.NOT_ITALIC,
    24: SGRAttribute.NOT_UNDERLINE,
    25: SGRAttribute.NOT_BLINK,
    27: SGRAttribute.NOT_REVERSE,
    28: SGRAttribute.NOT_CONCEAL,
    29: SGRAttribute.NOT_STRIKETHROUGH,
    39: SGRAttribute.DEFAULT_FOREGROUND,
    49: SGRAttribute.DEFAULT_BACKGROUND,
}

_BASIC_FOREGROUND = range(30, 38)
_BASIC_BACKGROUND = range(40, 48)
_BRIGHT_FOREGROUND = range(90, 98)
_BRIGHT_BACKGROUND = range(100, 108)


class ColorTarget(Enum):
    FOREGROUND = auto()
    BACKGROUND = auto()


@dataclass(frozen=True)
class NamedColor:
    """One of the 16 basic ANSI colors: index 0-7 normal, 8-15 bright."""

    target: ColorTarget
    index: int


@dataclass(frozen=True)
class IndexedColor:
    """A 256-color palette entry, from `38;5;N` / `48;5;N`."""

    target: ColorTarget
    index: int


@dataclass(frozen=True)
class RGBColor:
    """A truecolor value, from `38;2;R;G;B` / `48;2;R;G;B`."""

    target: ColorTarget
    red: int
    green: int
    blue: int


SGRDirective = Union[SGRAttribute, NamedColor, IndexedColor, RGBColor]


def parse_sgr(parsed: ParsedCSI) -> List[SGRDirective]:
    """Turn the parameters of an SGR sequence (final byte 'm') into a list
    of directives, in the order they appear.

    Raises ValueError if `parsed` isn't an SGR sequence. A code this
    module doesn't recognize is skipped rather than raising, since SGR
    codes vary by terminal and an unknown one shouldn't break parsing of
    the rest of the sequence.
    """
    if parsed.final != "m":
        raise ValueError(f"not an SGR sequence: final byte {parsed.final!r}")
    # a bare "ESC [ m" carries no parameters at all, which means "reset"
    codes = parsed.int_params() or (0,)
    directives: List[SGRDirective] = []
    i = 0
    while i < len(codes):
        code = codes[i]
        if code in _BASIC_FOREGROUND:
            directives.append(NamedColor(ColorTarget.FOREGROUND, code - 30))
        elif code in _BASIC_BACKGROUND:
            directives.append(NamedColor(ColorTarget.BACKGROUND, code - 40))
        elif code in _BRIGHT_FOREGROUND:
            directives.append(NamedColor(ColorTarget.FOREGROUND, code - 90 + 8))
        elif code in _BRIGHT_BACKGROUND:
            directives.append(NamedColor(ColorTarget.BACKGROUND, code - 100 + 8))
        elif code in (38, 48):
            target = ColorTarget.FOREGROUND if code == 38 else ColorTarget.BACKGROUND
            consumed, directive = _parse_extended_color(target, codes[i + 1:])
            i += consumed
            if directive is not None:
                directives.append(directive)
        elif code in _SGR_ATTRIBUTES:
            directives.append(_SGR_ATTRIBUTES[code])
        i += 1
    return directives


def _parse_extended_color(
    target: ColorTarget, rest: Tuple[int, ...]
) -> Tuple[int, Optional[SGRDirective]]:
    """Parse the mode/value fields that follow a 38 or 48 code.

    Returns (number of extra fields consumed, directive or None).
    Malformed or truncated fields consume whatever is there and yield no
    directive, rather than raising.
    """
    if not rest:
        return 0, None
    mode = rest[0]
    if mode == 5 and len(rest) >= 2:
        return 2, IndexedColor(target, rest[1])
    if mode == 2 and len(rest) >= 4:
        return 4, RGBColor(target, rest[1], rest[2], rest[3])
    return len(rest), None


# ---------------------------------------------------------------------------
# Cursor movement.


class CursorDirection(Enum):
    UP = auto()
    DOWN = auto()
    FORWARD = auto()
    BACK = auto()
    NEXT_LINE = auto()
    PREVIOUS_LINE = auto()


@dataclass(frozen=True)
class CursorMove:
    """A relative cursor move: CUU/CUD/CUF/CUB/CNL/CPL."""

    direction: CursorDirection
    count: int


@dataclass(frozen=True)
class CursorColumn:
    """An absolute column move (CHA, final byte 'G'). 1-based, per the wire format."""

    column: int


@dataclass(frozen=True)
class CursorPosition:
    """An absolute row+column move (CUP/HVP, final byte 'H' or 'f'). 1-based."""

    row: int
    column: int


CursorDirective = Union[CursorMove, CursorColumn, CursorPosition]

_CURSOR_MOVE_FINAL = {
    "A": CursorDirection.UP,
    "B": CursorDirection.DOWN,
    "C": CursorDirection.FORWARD,
    "D": CursorDirection.BACK,
    "E": CursorDirection.NEXT_LINE,
    "F": CursorDirection.PREVIOUS_LINE,
}


def parse_cursor(parsed: ParsedCSI) -> Optional[CursorDirective]:
    """Interpret a CSI sequence as a cursor movement command.

    Returns None if `parsed.final` isn't one of the movement commands
    this module understands. A parameter that's zero or omitted defaults
    to 1, matching how real terminals treat an implicit count.
    """
    if parsed.final in _CURSOR_MOVE_FINAL:
        params = parsed.int_params()
        count = params[0] if params and params[0] else 1
        return CursorMove(_CURSOR_MOVE_FINAL[parsed.final], count)
    if parsed.final == "G":
        params = parsed.int_params()
        column = params[0] if params and params[0] else 1
        return CursorColumn(column)
    if parsed.final in ("H", "f"):
        params = parsed.int_params()
        row = params[0] if len(params) >= 1 and params[0] else 1
        column = params[1] if len(params) >= 2 and params[1] else 1
        return CursorPosition(row, column)
    return None
