import unittest

from ansiscan import (
    ColorTarget,
    CursorColumn,
    CursorDirection,
    CursorMove,
    CursorPosition,
    IndexedColor,
    NamedColor,
    ParsedCSI,
    RGBColor,
    SGRAttribute,
    parse_csi,
    parse_cursor,
    parse_sgr,
)


class ParseCSITests(unittest.TestCase):
    def test_splits_params_intermediate_and_final(self):
        parsed = parse_csi("\x1b[1;31m")
        self.assertEqual(parsed, ParsedCSI(("1", "31"), "", "m"))

    def test_no_params_is_empty_tuple(self):
        parsed = parse_csi("\x1b[m")
        self.assertEqual(parsed, ParsedCSI((), "", "m"))

    def test_keeps_empty_fields(self):
        # "\x1b[;5H" means "default row, column 5" -- the empty leading
        # field has to survive as "" rather than being dropped.
        parsed = parse_csi("\x1b[;5H")
        self.assertEqual(parsed.params, ("", "5"))

    def test_intermediate_byte_is_captured(self):
        parsed = parse_csi("\x1b[?25h")
        self.assertEqual(parsed, ParsedCSI(("?25",), "", "h"))
        parsed = parse_csi("\x1b[0 q")
        self.assertEqual(parsed, ParsedCSI(("0",), " ", "q"))

    def test_rejects_non_csi_text(self):
        self.assertIsNone(parse_csi("not an escape at all"))
        self.assertIsNone(parse_csi("\x1b]0;title\x07"))

    def test_rejects_trailing_garbage(self):
        # fullmatch means anything after the final byte invalidates it,
        # rather than silently parsing a prefix.
        self.assertIsNone(parse_csi("\x1b[1mtrailing"))

    def test_int_params_fills_omitted_with_default(self):
        parsed = parse_csi("\x1b[;5H")
        self.assertEqual(parsed.int_params(), (0, 5))
        self.assertEqual(parsed.int_params(default=1), (1, 5))

    def test_int_params_uses_leading_subparam(self):
        # "38:2:255:0:0" -- only the head before the first ":" matters here.
        parsed = parse_csi("\x1b[38:2:255:0:0m")
        self.assertEqual(parsed.int_params(), (38,))


class ParseSGRTests(unittest.TestCase):
    def test_raises_on_non_sgr_sequence(self):
        parsed = parse_csi("\x1b[2J")
        with self.assertRaises(ValueError):
            parse_sgr(parsed)

    def test_bare_reset_with_no_params(self):
        parsed = parse_csi("\x1b[m")
        self.assertEqual(parse_sgr(parsed), [SGRAttribute.RESET])

    def test_attribute_codes(self):
        parsed = parse_csi("\x1b[1;4m")
        self.assertEqual(
            parse_sgr(parsed), [SGRAttribute.BOLD, SGRAttribute.UNDERLINE]
        )

    def test_basic_foreground_and_background(self):
        parsed = parse_csi("\x1b[31;42m")
        self.assertEqual(
            parse_sgr(parsed),
            [
                NamedColor(ColorTarget.FOREGROUND, 1),
                NamedColor(ColorTarget.BACKGROUND, 2),
            ],
        )

    def test_bright_foreground_and_background(self):
        parsed = parse_csi("\x1b[91;101m")
        self.assertEqual(
            parse_sgr(parsed),
            [
                NamedColor(ColorTarget.FOREGROUND, 9),
                NamedColor(ColorTarget.BACKGROUND, 9),
            ],
        )

    def test_indexed_color(self):
        parsed = parse_csi("\x1b[38;5;208m")
        self.assertEqual(
            parse_sgr(parsed), [IndexedColor(ColorTarget.FOREGROUND, 208)]
        )

    def test_rgb_color(self):
        parsed = parse_csi("\x1b[48;2;255;100;0m")
        self.assertEqual(
            parse_sgr(parsed), [RGBColor(ColorTarget.BACKGROUND, 255, 100, 0)]
        )

    def test_extended_color_continues_after_consuming_its_fields(self):
        # the 38;5;208 shouldn't swallow the trailing bold code.
        parsed = parse_csi("\x1b[38;5;208;1m")
        self.assertEqual(
            parse_sgr(parsed),
            [IndexedColor(ColorTarget.FOREGROUND, 208), SGRAttribute.BOLD],
        )

    def test_truncated_extended_color_yields_no_directive(self):
        # "38;5" with no index after it is malformed; it should consume
        # what's there and move on instead of raising or misreading.
        parsed = parse_csi("\x1b[38;5;1m")
        self.assertEqual(
            parse_sgr(parsed),
            [IndexedColor(ColorTarget.FOREGROUND, 1)],
        )
        parsed = parse_csi("\x1b[38m")
        self.assertEqual(parse_sgr(parsed), [])

    def test_unknown_code_is_skipped(self):
        parsed = parse_csi("\x1b[59;1m")
        self.assertEqual(parse_sgr(parsed), [SGRAttribute.BOLD])

    def test_default_foreground_and_background(self):
        parsed = parse_csi("\x1b[39;49m")
        self.assertEqual(
            parse_sgr(parsed),
            [SGRAttribute.DEFAULT_FOREGROUND, SGRAttribute.DEFAULT_BACKGROUND],
        )


class ParseCursorTests(unittest.TestCase):
    def test_relative_moves_default_count_to_one(self):
        parsed = parse_csi("\x1b[A")
        self.assertEqual(
            parse_cursor(parsed), CursorMove(CursorDirection.UP, 1)
        )

    def test_relative_moves_with_explicit_count(self):
        parsed = parse_csi("\x1b[12B")
        self.assertEqual(
            parse_cursor(parsed), CursorMove(CursorDirection.DOWN, 12)
        )

    def test_zero_count_defaults_to_one(self):
        parsed = parse_csi("\x1b[0C")
        self.assertEqual(
            parse_cursor(parsed), CursorMove(CursorDirection.FORWARD, 1)
        )

    def test_all_relative_directions(self):
        cases = {
            "A": CursorDirection.UP,
            "B": CursorDirection.DOWN,
            "C": CursorDirection.FORWARD,
            "D": CursorDirection.BACK,
            "E": CursorDirection.NEXT_LINE,
            "F": CursorDirection.PREVIOUS_LINE,
        }
        for final, direction in cases.items():
            with self.subTest(final=final):
                parsed = parse_csi(f"\x1b[3{final}")
                self.assertEqual(parse_cursor(parsed), CursorMove(direction, 3))

    def test_cursor_column(self):
        parsed = parse_csi("\x1b[10G")
        self.assertEqual(parse_cursor(parsed), CursorColumn(10))

    def test_cursor_column_defaults_to_one(self):
        parsed = parse_csi("\x1b[G")
        self.assertEqual(parse_cursor(parsed), CursorColumn(1))

    def test_cursor_position_both_axes(self):
        parsed = parse_csi("\x1b[5;10H")
        self.assertEqual(parse_cursor(parsed), CursorPosition(5, 10))

    def test_cursor_position_hvp_alias(self):
        parsed = parse_csi("\x1b[5;10f")
        self.assertEqual(parse_cursor(parsed), CursorPosition(5, 10))

    def test_cursor_position_missing_fields_default_to_one(self):
        parsed = parse_csi("\x1b[H")
        self.assertEqual(parse_cursor(parsed), CursorPosition(1, 1))
        parsed = parse_csi("\x1b[;5H")
        self.assertEqual(parse_cursor(parsed), CursorPosition(1, 5))

    def test_unrecognized_final_byte_returns_none(self):
        parsed = parse_csi("\x1b[2J")
        self.assertIsNone(parse_cursor(parsed))


if __name__ == "__main__":
    unittest.main()
