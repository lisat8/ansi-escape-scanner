"""Read escape-code-bearing text uniformly from a file path or stdin.

Callers should not have to write an if/else for "did they pass a path or
do they want stdin". `read_source` takes either a path or None (or the
conventional "-") and returns the same thing either way.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]


def read_source(source: Optional[PathLike] = None) -> str:
    """Read text from `source`, or from stdin when it is None or "-".

    Reads bytes first and decodes with surrogateescape rather than the
    default strict UTF-8. Captured terminal output sometimes contains
    stray bytes that aren't valid UTF-8 (partial multi-byte sequences cut
    off by a resize, or raw bytes from a program that never adopted
    UTF-8 cleanly); surrogateescape lets those round-trip instead of
    raising or getting silently replaced with U+FFFD.
    """
    if source is None or source == "-":
        data = sys.stdin.buffer.read()
    else:
        data = Path(source).read_bytes()
    return data.decode("utf-8", errors="surrogateescape")
