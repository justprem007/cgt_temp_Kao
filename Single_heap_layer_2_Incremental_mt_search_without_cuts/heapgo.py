"""
heapgo.py — Heapgo game rules for a SINGLE heap.

A heap is a list of (value, color) stones, e.g. [(2, 'red'), (3, 'red'), (5, 'blue')],
ordered bottom-to-top (the last element is the top of the heap).

These rules model ONE heap only. A position with several heaps is
a disjunctive sum in which a player may move in any heap — several independent
options — which this single-line engine does not represent. Such input is
rejected here.

"""

def moves(player, heap, game_point=0):
    """
    The one legal move for `player` on a single heap.

    Arguments:
        player     : 'left' or 'right'
        heap       : a single heap (list of (value, color) stones)
        game_point : accumulated score so far

    Returns:
        (new_heap, point) — the heap after the move and the accumulated score.
        Assumes the heap is non-empty (see is_terminal).
    """
    l = heap.copy()
    point = 0
    if player == 'left':
        # Left collects blue stones from the top, then one red stone.
        while len(l) > 0 and l[-1][1] == 'blue':
            point += l[-1][0]
            l.pop()
        if len(l) > 0:
            point += l[-1][0]
            l.pop()
    else:
        # Right collects red stones from the top, then one blue stone.
        while len(l) > 0 and l[-1][1] == 'red':
            point -= l[-1][0]
            l.pop()
        if len(l) > 0:
            point -= l[-1][0]
            l.pop()
    return (l, point + game_point)


def is_terminal(heap):
    """A single heap is terminal when it is empty (no stone left to take)."""
    return len(heap) == 0