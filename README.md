# ansiscan

A small library for pulling ANSI/VT100 terminal escape sequences apart from
the real text they're mixed in with.

Anything that captures terminal output — a CI log, `script -q`, a tmux
`capture-pane`, a saved SSH session — ends up as a stream of printable text
interleaved with cursor moves, color codes, and window-title requests. You
usually want one of two things: the plain text with all of that stripped
out, or the individual sequences so you can inspect or reinterpret them.
`ansiscan` gives you both without pulling in a terminal-emulation library.

It does not try to *interpret* what a CSI sequence does (move cursor,
set color, and so on) — it just tells you where each sequence starts and
ends and whether it's a CSI, OSC, or a bare one-off escape. That's the
part that's fiddly to get right with a hand-rolled regex; what you do with
the parameters is up to you.

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

## Scope

Handled: CSI sequences (`ESC [ ... final-byte`, covering SGR colors,
cursor movement, erase commands, etc.), OSC sequences (`ESC ] ... BEL` or
`ESC ] ... ESC \`, covering window titles and terminal hyperlinks), and
bare two-byte escapes (`ESC` followed by one byte, covering charset
selection and similar).

Not yet handled: DCS, APC, and PM sequences, and 8-bit (non-ESC-prefixed)
C1 control codes. See the roadmap in the commit history.
