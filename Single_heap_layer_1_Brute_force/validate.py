"""
validate.py — checks that a game input is in a correct format.

This module checks that an input is correctly written. main.py knows which
format it has and calls the matching function; each raises InvalidGameError if
the input is malformed.

    parse_curly(text)   CGSuite string, e.g. "{11 | {8 | 0}}"
                        -> RETURNS the equivalent nested list.
                           Checking a curly string means reading it, so the
                           result is returned rather than parsed a second time.
    check_nested(G)     nested list, e.g. [11, [8, 0]]        -> returns None
    check_heapgo(G)     single Heapgo heap, e.g. [(2, 'red')] -> returns None
                        (heapgo_to_tree does the conversion)

This file imports nothing from the project, so any module can import it.
"""

import ast


class InvalidGameError(Exception):
    """Raised when a game input is not in a correct format."""
    pass


COLORS = ('red', 'blue')
_CURLY_ALLOWED = set("0123456789.-{}|")


# ---------------------------------------------------------------------------
# 1. CGSuite curly-brace string:  "{11 | {8 | 0}}"
# ---------------------------------------------------------------------------
def parse_curly(text):
    """
    Check a CGSuite-style '{L | R}' string AND return it as a nested list.

    The three substitutions  {->[  }->]  |->,  turn a curly game into the
    nested-list form, so checking the string means reading it: swap the
    brackets, read the result, hand it to check_nested. Since we have the
    nested list by then, we return it instead of parsing the string twice.
    """
    if not isinstance(text, str):
        raise InvalidGameError(
            f"Expected a '{{L | R}}' string, got {type(text).__name__}: {text!r}"
        )

    s = ''.join(text.split())            # whitespace is not significant
    if not s:
        raise InvalidGameError("Empty input")

    for ch in s:                         # only these symbols exist in a game
        if ch not in _CURLY_ALLOWED:
            raise InvalidGameError(
                f"Unexpected symbol {ch!r}. Only numbers, '{{', '}}' and '|' "
                "are allowed (no '*' or other symbols)."
            )

    s = s.replace('{', '[').replace('}', ']').replace('|', ',')
    try:
        game = ast.literal_eval(s)
    except (ValueError, SyntaxError) as e:
        raise InvalidGameError(f"Malformed curly-bracket game: {e}")

    if not isinstance(game, list):       # a bare number is not a game
        raise InvalidGameError(
            f"Expected a game in '{{L | R}}' form, got a bare number {text!r}"
        )

    check_nested(game)                   # groups are {L | R}, terminals numeric
    return game

# ---------------------------------------------------------------------------
def check_nested(G):
    """
    Check a nested-list game: a number, or a 2-element [left, right] whose
    parts are themselves nested-list games.
    """
    if isinstance(G, bool):                  # bool is an int in Python; reject it
        raise InvalidGameError(f"Terminals must be numbers, got {G!r}")
    if isinstance(G, (int, float)):
        return
    if isinstance(G, list) and len(G) == 2:
        check_nested(G[0])
        check_nested(G[1])
        return
    raise InvalidGameError(
        f"Invalid nested-list game: expected a number or a 2-element "
        f"[left, right], got {G!r}"
    )


# ---------------------------------------------------------------------------
# 3. Heapgo heap:  [(2, 'red'), (3, 'red'), (5, 'blue')]
# ---------------------------------------------------------------------------
def check_heapgo(G):
    """
    Check a single Heapgo heap: a non-empty list of (value, color) stones,
    value a number and color 'red' or 'blue'.

    Only ONE heap is allowed. Several heaps would give a player several move
    options (a disjunctive sum), which this engine does not model.
    """
    if not isinstance(G, list) or len(G) == 0:
        raise InvalidGameError(
            f"A Heapgo heap must be a non-empty list of (value, color) stones; "
            f"got {G!r}"
        )
    for stone in G:
        if not (isinstance(stone, tuple) and len(stone) == 2):
            raise InvalidGameError(
                "Several heaps of Heapgo are not supported (a player would then have "
                f"several options). Offending element: {stone!r}"
            )
        value, color = stone
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise InvalidGameError(f"Stone value must be a number, got {value!r}")
        if color not in COLORS:
            raise InvalidGameError(
                f"Stone color must be one of {COLORS}, got {color!r}"
            )


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    good = [
        (parse_curly,  "{11 | {8 | 0}}"),
        (parse_curly,  "{-5 | 10}"),
        (parse_curly,  "{3.5|{-2.75|0}}"),
        (check_nested, [11, [8, 0]]),
        (check_nested, 5),
        (check_heapgo, [(2, 'red'), (3, 'red'), (5, 'blue')]),
    ]
    for fn, G in good:
        fn(G)
        print(f"OK    {fn.__name__:13} {str(G):38} accepted")

    bad = [
        (parse_curly,  "{* | 0}"),                       # bad symbol
        (parse_curly,  "{1 | 2"),                        # unbalanced
        (parse_curly,  "{1 | 2 | 3}"),                   # not binary
        (parse_curly,  "11"),                            # bare number
        (check_nested, [1, 2, 3]),                       # not binary
        (check_nested, "x"),                             # not a game
        (check_heapgo, [(2, 'green')]),                  # bad color
        (check_heapgo, [[(2, 'red')], [(3, 'blue')]]),   # several heaps
        (check_heapgo, []),                              # empty
    ]
    for fn, G in bad:
        try:
            fn(G)
            print(f"FAIL  {fn.__name__:13} {str(G):38} accepted!")
        except InvalidGameError as e:
            print(f"OK    {fn.__name__:13} {str(G):38} rejected: {str(e)[:34]}")