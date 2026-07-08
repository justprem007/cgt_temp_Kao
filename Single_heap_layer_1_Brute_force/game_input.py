"""
game_input.py — game-format detection and the GameGenerator adapters.

This is the single place where a raw game input is recognised and wrapped for
the engine. It answers one question: "what kind of game is this, and how do I
produce its children on demand?" Nothing here computes mean or temperature.

Supported raw inputs (see `resolve_generator`):
    1. A nested-list game           (e.g. [11, [8, 0]])           -> NestedListGenerator
    2. A Heapgo position            (e.g. [[(2,'red'), (3,'red')]]) -> HeapgoGenerator
    3. A GameGenerator instance     (custom games)                -> passed through

Frontends (run.py, the test harnesses) call `resolve_generator` to build a
GameGenerator and hand that generator to incremental_mt. Curly-brace strings
are NOT handled here: they are text and are converted to nested lists by
game_parser.parse_game first (in run.py), then resolved here like any other
nested list.
"""

from abc import ABC, abstractmethod

import heapgo            # Heapgo game rules (used only by HeapgoGenerator)


# ===========================================================================
# GameGenerator interface and concrete implementations.
# ===========================================================================
class GameGenerator(ABC):
    """
    Abstract interface for generating game-tree children on demand.

    A 'state' is whatever opaque object identifies a position - the
    algorithm never inspects it directly, only passes it back to the
    generator. For nested-list games a state is just the sub-list; for
    Heapgo it's a (position, accumulated_game_point) tuple.
    """

    @abstractmethod
    def root_state(self):
        """Return the state representing the root position."""

    @abstractmethod
    def is_terminal(self, state) -> bool:
        """True iff `state` is a terminal (no further moves)."""

    @abstractmethod
    def terminal_value(self, state):
        """Numeric value of a terminal state. Only called when is_terminal."""

    @abstractmethod
    def left_child_state(self, state):
        """State after Left's move from `state`. Only called when not terminal."""

    @abstractmethod
    def right_child_state(self, state):
        """State after Right's move from `state`. Only called when not terminal."""


class NestedListGenerator(GameGenerator):
    """
    Generator for the nested-list format:
       terminal:     a number
       non-terminal: a [left_subtree, right_subtree] pair
    """

    def __init__(self, game):
        self._root = game

    def root_state(self):
        return self._root

    def is_terminal(self, state):
        return isinstance(state, (int, float))

    def terminal_value(self, state):
        return state

    def left_child_state(self, state):
        return state[0]

    def right_child_state(self, state):
        return state[1]


class HeapgoGenerator(GameGenerator):
    """
    Generator for a SINGLE Heapgo heap. State = (heap, accumulated_game_point).
    Uses heapgo.moves(...) for one ply at a time; no full-tree conversion.

    Accepted input is a bare single heap:
        [(2, 'red'), (3, 'red'), (5, 'blue')]

    Multiple heaps are NOT supported: with more than one heap a player has
    several independent moves (a disjunctive sum of heaps), which this
    single-line binary engine cannot represent. Non-single-heap input is
    rejected by heapgo.py (the rules) as soon as the search asks for a move.
    """

    def __init__(self, heap):
        self._root_heap = heap

    def root_state(self):
        return (self._root_heap, 0)

    def is_terminal(self, state):
        heap, _ = state
        return heapgo.is_terminal(heap)

    def terminal_value(self, state):
        _, game_point = state
        return game_point

    def left_child_state(self, state):
        heap, game_point = state
        new_heap, point = heapgo.moves('left', heap, game_point)
        return (new_heap, point)

    def right_child_state(self, state):
        heap, game_point = state
        new_heap, point = heapgo.moves('right', heap, game_point)
        return (new_heap, point)

# ---------------------------------------------------------------------------
# Input-format detection (so callers can hand us a raw game directly).
# ---------------------------------------------------------------------------
def _is_stone(x):
    return (isinstance(x, tuple) and len(x) == 2
            and isinstance(x[0], (int, float)) and x[1] in ('red', 'blue'))


def is_heapgo_position(G):
    """
    Recognize a single Heapgo heap: a non-empty list of (value, color) stones,
    e.g. [(2, 'red'), (3, 'red'), (5, 'blue')].

    Only this single-heap form is accepted. A list of heaps (e.g. [[...], [...]]
    or the old wrapped [[...]]) is not a valid input here.
    """
    return isinstance(G, list) and len(G) > 0 and all(_is_stone(e) for e in G)


def is_nested_list_game(G):
    if isinstance(G, (int, float)):
        return True
    if isinstance(G, list) and len(G) == 2:
        return is_nested_list_game(G[0]) and is_nested_list_game(G[1])
    return False


def resolve_generator(game):
    """Turn a raw game input into a GameGenerator."""
    if isinstance(game, GameGenerator):
        return game
    if is_heapgo_position(game):
        return HeapgoGenerator(game)
    if is_nested_list_game(game):
        return NestedListGenerator(game)
    raise ValueError(
        f"Unrecognised game input: {game!r}\n"
        "Expected a nested-list game, a Heapgo position, or a GameGenerator."
    )