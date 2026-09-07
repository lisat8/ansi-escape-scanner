# ansiscan

A small library for pulling ANSI/VT100 terminal escape sequences apart from
the real text they're mixed in with.

Anything that captures terminal output — a CI log, `script -q`, a tmux
`capture-pane`, a saved SSH session — ends up as a stream of printable text
interleaved with cursor moves, color codes, and window-title requests. You
usually want one of two things: the plain text with all of that stripped
out, or the individual sequences so you can inspect or reinterpret them.
`ansiscan` gives you both without pulling in a terminal-emulation library.

The scanner itself does not try to *interpret* what a CSI sequence does
(move cursor, set color, and so on) — it just tells you where each
sequence starts and ends and whether it's a CSI, OSC, or a bare one-off
escape. That's the part that's fiddly to get right with a hand-rolled
regex. For the two kinds of CSI sequence you run into most often — SGR
colors/attributes and cursor movement — `ansiscan.parse_sgr` and
`ansiscan.parse_cursor` parse the parameters for you; anything else you
get as raw parameter fields and interpret yourself.

## Install

Not published anywhere yet. For now, clone it and either run from the
`src` layout or `pip install -e .` in a virtualenv.

## Usage

Reading from a file:

```python
from ansiscan import read_source, strip

text = read_source("build.log")
print(strip(text))
```

Reading from stdin (pass `None` or `"-"`):

```python
from ansiscan import read_source, strip

text = read_source(None)
print(strip(text))
```

so this works the way you'd expect from the shell:

```sh
some-colorful-build-tool | python -c "
from ansiscan import read_source, strip
print(strip(read_source(None)))
"
```

Inspecting the sequences instead of discarding them:

```python
from ansiscan import iter_tokens, read_source

for token in iter_tokens(read_source("session.log")):
    if token.is_escape:
        print(token.kind.name, repr(token.text))
```

`iter_tokens` yields `Token(kind, text)` objects covering the whole input,
in order, so joining every token's `.text` back together always
reproduces the original string exactly — including any escape sequence
that got cut off mid-stream because the capture ended abruptly.

Parsing SGR color/attribute codes and cursor movement out of a CSI
token:

```python
from ansiscan import TokenKind, iter_tokens, parse_csi, parse_cursor, parse_sgr

for token in iter_tokens(read_source("session.log")):
    if token.kind is not TokenKind.CSI:
        continue
    parsed = parse_csi(token.text)
    if parsed.final == "m":
        for directive in parse_sgr(parsed):
            print(directive)
    else:
        move = parse_cursor(parsed)
        if move is not None:
            print(move)
```

## Scope

Handled: CSI sequences (`ESC [ ... final-byte`, covering SGR colors,
cursor movement, erase commands, etc.), OSC sequences (`ESC ] ... BEL` or
`ESC ] ... ESC \`, covering window titles and terminal hyperlinks), and
bare two-byte escapes (`ESC` followed by one byte, covering charset
selection and similar).

Parsed, not just located: SGR color and attribute codes (16-color,
256-color, and truecolor foreground/background, plus the common
attributes like bold and underline), and cursor movement commands
(CUU/CUD/CUF/CUB/CNL/CPL, CHA, CUP/HVP).

Not yet handled: DCS, APC, and PM sequences, and 8-bit (non-ESC-prefixed)
C1 control codes. See the roadmap in the commit history.
