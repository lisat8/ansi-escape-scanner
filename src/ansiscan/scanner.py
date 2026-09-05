"""Tokenize text that contains ANSI/VT100 terminal escape sequences.

This does not try to be a full terminal emulator. It only needs to answer
two questions reliably: where does an escape sequence start and end, and
what broad kind is it (CSI, OSC, or a bare one-off escape). That is enough
to strip codes, count them, or hand each one to something that actually
understands what the parameters mean (e.g. SGR color codes).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator

ESC = "\x1b"


class TokenKind(Enum):
    TEXT = auto()
    CSI = auto()
    OSC = auto()
    ESCAPE = auto()  # a lone ESC + one byte, e.g. ESC ( B or ESC =


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: str

    @property
    def is_escape(self) -> bool:
        return self.kind is not TokenKind.TEXT


# CSI: ESC [ , then parameter bytes 0x30-0x3F, intermediate bytes
# 0x20-0x2F, final byte 0x40-0x7E. Covers cursor movement, SGR colors,
# erase-line, etc.
_CSI = r"\x1b\[[0-9:;<=>?]*[ -/]*[@-~]"

# OSC: ESC ] , then anything up to BEL or the ESC \ string terminator.
# Covers window-title and hyperlink sequences.
_OSC = r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"

# A bare escape: ESC followed by exactly one byte that isn't [ or ].
# Covers charset selection, DECSC/DECRC, RIS, and similar single-shot codes.
_BARE = r"\x1b[^\[\]]"

_SEQUENCE = re.compile(f"(?:{_CSI}|{_OSC}|{_BARE})")


def iter_tokens(text: str) -> Iterator[Token]:
    """Split text into a stream of plain-text and escape-sequence tokens.

    A sequence that starts but never closes (truncated input, e.g. a log
    file cut off mid-OSC) is left as plain TEXT rather than dropped, so
    re-joining every token's `.text` always reproduces the input exactly.
    """
    pos = 0
    for match in _SEQUENCE.finditer(text):
        if match.start() > pos:
            yield Token(TokenKind.TEXT, text[pos:match.start()])
        seq = match.group(0)
        if seq.startswith(ESC + "["):
            kind = TokenKind.CSI
        elif seq.startswith(ESC + "]"):
            kind = TokenKind.OSC
        else:
            kind = TokenKind.ESCAPE
        yield Token(kind, seq)
        pos = match.end()
    if pos < len(text):
        yield Token(TokenKind.TEXT, text[pos:])


def strip(text: str) -> str:
    """Return text with every recognized escape sequence removed."""
    return "".join(tok.text for tok in iter_tokens(text) if tok.kind is TokenKind.TEXT)
