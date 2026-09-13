"""Tokenize text that contains ANSI/VT100 terminal escape sequences.

This does not try to be a full terminal emulator. It only needs to answer
two questions reliably: where does an escape sequence start and end, and
what broad kind is it (CSI, OSC, DCS, APC, PM, or a bare one-off escape).
That is enough to strip codes, count them, or hand each one to something
that actually understands what the parameters mean (e.g. SGR color codes).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator, Union

ESC = "\x1b"
ESC_BYTES = b"\x1b"


class TokenKind(Enum):
    TEXT = auto()
    CSI = auto()
    OSC = auto()
    DCS = auto()
    APC = auto()
    PM = auto()
    ESCAPE = auto()  # a lone ESC + one byte, e.g. ESC ( B or ESC =


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: Union[str, bytes]

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

# DCS, APC, and PM are the other three ECMA-48 "string" sequences: ESC P,
# ESC _, and ESC ^ respectively, each running up to the ESC \ string
# terminator. Unlike OSC, real terminals don't accept BEL as a terminator
# for these, so only ESC \ closes them. DCS carries device-control data
# (e.g. Sixel graphics, tmux passthrough); APC and PM are rarely used in
# practice but are part of the same family and just as easy to bound.
_DCS = r"\x1bP[^\x1b]*\x1b\\"
_APC = r"\x1b_[^\x1b]*\x1b\\"
_PM = r"\x1b\^[^\x1b]*\x1b\\"

# A bare escape: ESC followed by exactly one byte that isn't the start of
# one of the multi-byte sequences above.
# Covers charset selection, DECSC/DECRC, RIS, and similar single-shot codes.
_BARE = r"\x1b[^\[\]P_^]"

_SEQUENCE = re.compile(f"(?:{_CSI}|{_OSC}|{_DCS}|{_APC}|{_PM}|{_BARE})")


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
        elif seq.startswith(ESC + "P"):
            kind = TokenKind.DCS
        elif seq.startswith(ESC + "_"):
            kind = TokenKind.APC
        elif seq.startswith(ESC + "^"):
            kind = TokenKind.PM
        else:
            kind = TokenKind.ESCAPE
        yield Token(kind, seq)
        pos = match.end()
    if pos < len(text):
        yield Token(TokenKind.TEXT, text[pos:])


def strip(text: str) -> str:
    """Return text with every recognized escape sequence removed."""
    return "".join(tok.text for tok in iter_tokens(text) if tok.kind is TokenKind.TEXT)


# ---------------------------------------------------------------------------
# Bytes API.
#
# Same rules as above, applied to raw bytes instead of decoded text. This is
# for callers that want to scan a captured session without deciding on a text
# encoding first, e.g. piping stdin straight through instead of routing it
# through read_source's surrogateescape decode.

_CSI_BYTES = rb"\x1b\[[0-9:;<=>?]*[ -/]*[@-~]"
_OSC_BYTES = rb"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
_DCS_BYTES = rb"\x1bP[^\x1b]*\x1b\\"
_APC_BYTES = rb"\x1b_[^\x1b]*\x1b\\"
_PM_BYTES = rb"\x1b\^[^\x1b]*\x1b\\"
_BARE_BYTES = rb"\x1b[^\[\]P_^]"

_SEQUENCE_BYTES = re.compile(
    b"(?:"
    + _CSI_BYTES
    + b"|"
    + _OSC_BYTES
    + b"|"
    + _DCS_BYTES
    + b"|"
    + _APC_BYTES
    + b"|"
    + _PM_BYTES
    + b"|"
    + _BARE_BYTES
    + b")"
)


def iter_tokens_bytes(data: bytes) -> Iterator[Token]:
    """Byte-string equivalent of `iter_tokens`.

    Splits raw bytes into plain-text and escape-sequence tokens without
    requiring the caller to decode first. Joining every token's `.text`
    back together reproduces `data` exactly, same guarantee as the str API.
    """
    pos = 0
    for match in _SEQUENCE_BYTES.finditer(data):
        if match.start() > pos:
            yield Token(TokenKind.TEXT, data[pos:match.start()])
        seq = match.group(0)
        if seq.startswith(ESC_BYTES + b"["):
            kind = TokenKind.CSI
        elif seq.startswith(ESC_BYTES + b"]"):
            kind = TokenKind.OSC
        elif seq.startswith(ESC_BYTES + b"P"):
            kind = TokenKind.DCS
        elif seq.startswith(ESC_BYTES + b"_"):
            kind = TokenKind.APC
        elif seq.startswith(ESC_BYTES + b"^"):
            kind = TokenKind.PM
        else:
            kind = TokenKind.ESCAPE
        yield Token(kind, seq)
        pos = match.end()
    if pos < len(data):
        yield Token(TokenKind.TEXT, data[pos:])


def strip_bytes(data: bytes) -> bytes:
    """Return data with every recognized escape sequence removed."""
    return b"".join(
        tok.text for tok in iter_tokens_bytes(data) if tok.kind is TokenKind.TEXT
    )
