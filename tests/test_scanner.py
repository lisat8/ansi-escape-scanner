import unittest

from ansiscan import Token, TokenKind, iter_tokens, iter_tokens_bytes, strip, strip_bytes

from . import fixtures


class RoundTripTests(unittest.TestCase):
    """Every token's text, joined back together, must reproduce the input
    exactly -- that's the guarantee callers rely on to strip or inspect
    sequences without risking data loss on malformed or truncated input."""

    def test_bytes_round_trip_reproduces_input(self):
        for name, data in fixtures.REAL_SESSIONS.items():
            with self.subTest(session=name):
                rebuilt = b"".join(tok.text for tok in iter_tokens_bytes(data))
                self.assertEqual(rebuilt, data)

    def test_str_round_trip_reproduces_input(self):
        for name, data in fixtures.REAL_SESSIONS.items():
            text = data.decode("utf-8")
            with self.subTest(session=name):
                rebuilt = "".join(tok.text for tok in iter_tokens(text))
                self.assertEqual(rebuilt, text)


class StripTests(unittest.TestCase):
    def test_strip_bytes_matches_expected(self):
        for name, data in fixtures.REAL_SESSIONS.items():
            with self.subTest(session=name):
                self.assertEqual(strip_bytes(data), fixtures.STRIPPED[name])

    def test_strip_str_matches_expected(self):
        for name, data in fixtures.REAL_SESSIONS.items():
            with self.subTest(session=name):
                text = data.decode("utf-8")
                expected = fixtures.STRIPPED[name].decode("utf-8")
                self.assertEqual(strip(text), expected)

    def test_strip_bytes_matches_strip_str_encoded(self):
        # the two APIs should agree on ASCII-safe input; if they diverge,
        # one of the two regex sets drifted from the other.
        for name, data in fixtures.REAL_SESSIONS.items():
            text = data.decode("utf-8")
            with self.subTest(session=name):
                self.assertEqual(strip_bytes(data), strip(text).encode("utf-8"))


class TokenKindTests(unittest.TestCase):
    def test_charset_selection_is_one_escape_token_not_split(self):
        # regression test: the bare-escape pattern used to only consume
        # ESC plus one byte, so ESC ( 0 came out as ESCAPE("\x1b(") + the
        # "0" leaking into the surrounding text token.
        data = fixtures.REAL_SESSIONS["charset_line_drawing"]
        tokens = list(iter_tokens_bytes(data))
        self.assertEqual(
            tokens,
            [
                Token(TokenKind.ESCAPE, b"\x1b(0"),
                Token(TokenKind.TEXT, b"lqqqqqqqk"),
                Token(TokenKind.ESCAPE, b"\x1b(B"),
                Token(TokenKind.TEXT, b"\n"),
            ],
        )

    def test_truncated_osc_is_left_as_plain_text(self):
        data = fixtures.REAL_SESSIONS["truncated_capture"]
        tokens = list(iter_tokens_bytes(data))
        self.assertEqual(tokens, [Token(TokenKind.TEXT, data)])

    def test_hyperlink_dcs_and_apc_are_classified_correctly(self):
        osc8 = fixtures.REAL_SESSIONS["osc8_hyperlink"]
        kinds = [tok.kind for tok in iter_tokens_bytes(osc8) if tok.is_escape]
        self.assertEqual(kinds, [TokenKind.OSC, TokenKind.OSC])

        dcs = fixtures.REAL_SESSIONS["dcs_decrqss_reply"]
        kinds = [tok.kind for tok in iter_tokens_bytes(dcs) if tok.is_escape]
        self.assertEqual(kinds, [TokenKind.DCS])

        apc = fixtures.REAL_SESSIONS["kitty_apc_graphics"]
        kinds = [tok.kind for tok in iter_tokens_bytes(apc) if tok.is_escape]
        self.assertEqual(kinds, [TokenKind.APC])


if __name__ == "__main__":
    unittest.main()
