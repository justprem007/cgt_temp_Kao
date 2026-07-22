"""
game_input.py — the GameGenerator adapters for the incremental_mt engine.

A GameGenerator answers one question for incremental_mt: "given a position
(state), what are its children?" Nothing here computes mean or temperature, and
nothing here checks the input format — the input is validated once, up front, in
run.py (via validate.py), so by the time a generator is built the game is known
to be well-formed.

Two built-in generators:
    NestedListGenerator  — for a nested-list game, e.g. [11, [8, 0]]
    HeapgoGenerator      — for a single Heapgo heap, e.g. [(2,'red'),(3,'red')]

Adding a new game: subclass GameGenerator here, implement its five methods, then
plug it into run.py
"""

from abc import ABC, abstractmethod

import heapgo            # Heapgo game rules (used only by HeapgoGenerator)


class GameGenerator(ABC):
    """
    Abstract interface for generating game-tree children on demand.

    A 'state' is whatever opaque object identifies a position — the algorithm
    never inspects it directly, only passes it back to the generator. For
    nested-list games a state is just the sub-list; for Heapgo it is a
    (heap, accumulated_game_point) tuple.
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
    Generator for a nested-list game.

      input        : a nested list, e.g. [11, [8, 0]]
      state        : the sub-list at a position (the root is the whole game)
      terminal     : a number
      non-terminal : a [left_subtree, right_subtree] pair
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
    Generator for a SINGLE Heapgo heap, one player at a time (no full-tree
    conversion); uses heapgo.moves(...).

      input        : a bare single heap, e.g. [(2, 'red'), (3, 'red'), (5, 'blue')]
      state        : (heap, accumulated_game_point)
      terminal     : an empty heap; its value is the accumulated game_point
      non-terminal : a heap with stones left; Left/Right take one move via heapgo
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