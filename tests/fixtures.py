"""Escape-sequence-bearing bytes as real programs actually emit them.

These aren't minimal made-up examples; each one is what you'd actually see
if you captured the named tool's output with `script -q` or a `tmux
capture-pane`. Using real shapes catches cases a hand-picked test string
would miss, like sequences with empty parameter fields or an intermediate
byte before the final one.
"""

REAL_SESSIONS = {
    # `ls --color=auto`: SGR reset, then per-entry color, name, reset.
    "ls_color": (
        b"\x1b[0m\x1b[01;34mDocuments\x1b[0m\n"
        b"\x1b[01;34mDownloads\x1b[0m\n"
        b"\x1b[01;32mrun.sh\x1b[0m\n"
        b"notes.txt\n"
    ),
    # `git diff --color`: bold header lines, cyan hunk header, red/green body.
    "git_diff_color": (
        b"\x1b[1mdiff --git a/foo.py b/foo.py\x1b[m\n"
        b"\x1b[1m--- a/foo.py\x1b[m\n"
        b"\x1b[1m+++ b/foo.py\x1b[m\n"
        b"\x1b[36m@@ -1,3 +1,3 @@\x1b[m\n"
        b"\x1b[31m-old line\x1b[m\n"
        b"\x1b[32m+new line\x1b[m\n"
    ),
    # bash PS1 setting the window title (OSC 0) then a colored prompt.
    "shell_prompt": (
        b"\x1b]0;user@host: ~/project\x07"
        b"\x1b[01;32muser@host\x1b[00m:\x1b[01;34m~/project\x1b[00m$ "
    ),
    # tmux redrawing a pane: hide cursor, home, clear line, status text, show cursor.
    "tmux_redraw": b"\x1b[?25l\x1b[1;1H\x1b[2Ksession: 0 windows\x1b[?25h",
    # a log line using a truecolor SGR code instead of a basic/indexed one.
    "truecolor_log": b"\x1b[38;2;255;100;0mWARNING\x1b[0m: disk usage above threshold\n",
    # an OSC 8 terminal hyperlink wrapping visible text.
    "osc8_hyperlink": b"\x1b]8;;https://example.com\x1b\\click here\x1b]8;;\x1b\\\n",
    # curses-style charset selection: switch G0 to DEC special graphics to
    # draw a box border, then switch back to ASCII. This is the case the
    # old bare-escape pattern mis-split.
    "charset_line_drawing": b"\x1b(0lqqqqqqqk\x1b(B\n",
    # a capture that got cut off mid-OSC, e.g. the process was killed while
    # writing a window title. No terminator ever arrives.
    "truncated_capture": b"before\x1b]0;partial windowtitle that never ends",
    # a terminal's DECRQSS reply reporting the current SGR state, carried in a DCS.
    "dcs_decrqss_reply": b"\x1bP1$r0;1;4m\x1b\\",
    # kitty's terminal graphics protocol, which rides on an APC sequence.
    "kitty_apc_graphics": b"\x1b_Ga=T,f=100;VGVzdA==\x1b\\hello\n",
}

# What `strip`/`strip_bytes` should leave behind for each session above.
STRIPPED = {
    "ls_color": b"Documents\nDownloads\nrun.sh\nnotes.txt\n",
    "git_diff_color": (
        b"diff --git a/foo.py b/foo.py\n"
        b"--- a/foo.py\n"
        b"+++ b/foo.py\n"
        b"@@ -1,3 +1,3 @@\n"
        b"-old line\n"
        b"+new line\n"
    ),
    "shell_prompt": b"user@host:~/project$ ",
    "tmux_redraw": b"session: 0 windows",
    "truecolor_log": b"WARNING: disk usage above threshold\n",
    "osc8_hyperlink": b"click here\n",
    "charset_line_drawing": b"lqqqqqqqk\n",
    # unrecognized (no terminator ever showed up), so nothing gets stripped.
    "truncated_capture": REAL_SESSIONS["truncated_capture"],
    "dcs_decrqss_reply": b"",
    "kitty_apc_graphics": b"hello\n",
}
