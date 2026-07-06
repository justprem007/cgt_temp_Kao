"""
game_parser.py — Parse CGSuite-style game notation into nested lists.

The input must be a game in brace form, {L | R}. A bare number on its own
(e.g. "11") is NOT accepted here: raise an "unexpected format" error instead.
Numbers are only valid as the terminals *inside* a brace group.

Approach (simple, by design):
    1) check every character is allowed (digits . - { } | and whitespace)
    2) convert  {  ->  [
    3) convert  }  ->  ]
    4) convert  |  ->  ,
    5) let Python parse the resulting literal (ast.literal_eval). It checks for
       balanced brackets, commas, and valid numbers.
    6) check the structure: the whole input is a brace group {L | R},
       every branch has exactly TWO options, every terminal is a number

Examples:
    "{11 | {8 | 0}}"       -> [11, [8, 0]]
    "{11|{6|0}}"           -> [11, [6, 0]]   (whitespace ignored)
    "11"                   -> ParseError (bare number, not a {L | R} game)
"""

import ast


class ParseError(Exception):
    pass


_ALLOWED = set("0123456789.-{}|")


def parse_game(text):
    """Parse a CGSuite-style '{L | R}' game string into a nested list."""
    if not isinstance(text, str):
        raise ParseError(
            f"Unexpected format: expected a '{{L | R}}' string, "
            f"got {type(text).__name__} {text!r}"
        )

    s = ''.join(text.split())          # strip all whitespace
    if not s:
        raise ParseError("Empty input")

    # 1) reject any unexpected symbol (e.g. '*', letters)
    for ch in s:
        if ch not in _ALLOWED:
            raise ParseError(
                f"Unexpected symbol {ch!r}. Only numbers, '{{', '}}' and '|' "
                "are allowed (no '*' or other symbols)."
            )

    # 2-4) the three substitutions
    s = s.replace('{', '[').replace('}', ']').replace('|', ',')

    # 5) let Python parse the literal; malformed input fails here
    try:
        game = ast.literal_eval(s)
    except (ValueError, SyntaxError) as e:
        raise ParseError(f"Malformed game expression: {e}")

    # 6a) the whole input must be a brace group, not a bare number
    if not isinstance(game, list):
        raise ParseError(
            f"Unexpected format: expected a game in '{{L | R}}' form, "
            f"got a bare number {game!r}"
        )

    # 6b) structure check on every branch/terminal
    _check(game)
    return game


def _check(g):
    """Every branch must be [L, R]; every terminal must be a number."""
    if isinstance(g, list):
        if len(g) != 2:
            raise ParseError(
                f"Each '{{L | R}}' must have exactly two options, got {len(g)}: {g}"
            )
        _check(g[0])
        _check(g[1])
    elif not isinstance(g, (int, float)):
        raise ParseError(f"Terminals must be numbers, got {g!r}")


# -----------------------------------------------------------------------------
# Quick self-test
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    good_cases = [
        ("{11 | {8 | 0}}",          [11, [8, 0]]),
        ("{11|{6|0}}",              [11, [6, 0]]),
        ("{-5 | 10}",               [-5, 10]),
        ("{3.5 | -2.75}",           [3.5, -2.75]),
        ("{24 | {{11 | {8 | 0}} | {11 | {6 | 0}}}}",
         [24, [[11, [8, 0]], [11, [6, 0]]]]),
    ]
    for text, expected in good_cases:
        got = parse_game(text)
        status = "OK " if got == expected else "FAIL"
        print("{}  parse_game({!r:40}) = {}  (expected {})".format(
            status, text, got, expected))

    # Reject: bare numbers, non-strings, bad symbols, malformed / non-binary
    bad_cases = ["11", "-5", "3.5", 11, "{* | 0}", "{a | b}",
                 "{1 | }", "{1 | 2", "{1 | 2 | 3}", ""]
    for text in bad_cases:
        try:
            got = parse_game(text)
            print("FAIL  Expected ParseError for {!r}, but got {}".format(text, got))
        except ParseError as e:
            print("OK    ParseError for {!r}: {}".format(text, e))