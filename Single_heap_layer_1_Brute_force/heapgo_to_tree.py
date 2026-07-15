"""
heapgo_to_tree.py — Convert a single-heap Heapgo position into the nested-list
game format, and (optionally) show it as an ASCII game tree.

    terminal      -> accumulated game_point (a number)
    non-terminal  -> [left_subtree, right_subtree]

Input is a bare single heap [(value, colour), ...].
"""

import heapgo

try:
    from treelib import Tree
except ImportError:                       # for visualization purposes only.
    Tree = None


def heapgo_to_tree(heap, game_point=0):
    """Recursively convert a single Heapgo heap to a nested-list game tree."""
    if heapgo.is_terminal(heap):
        return game_point

    left_heap, left_score = heapgo.moves('left', heap, game_point)
    right_heap, right_score = heapgo.moves('right', heap, game_point)

    return [heapgo_to_tree(left_heap, left_score),
            heapgo_to_tree(right_heap, right_score)]


# -----------------------------------------------------------------------------
# Visualization: nested list -> treelib Tree -> ASCII.
# -----------------------------------------------------------------------------
def build_tree(game, root_tag="G"):
    """Turn a nested-list game into a treelib.Tree.

    Terminals become leaf nodes tagged with their value; each internal
    node [L, R] gets an 'L:' child (Left's move) and an 'R:' child
    (Right's move). Node identifiers are unique paths so equal values in
    different places never collide.
    """
    if Tree is None:
        raise ImportError("treelib is not installed. Cannot build a tree for visualization.")

    tree = Tree()

    def add(node, nid, tag, parent):
        tree.create_node(tag=tag, identifier=nid, parent=parent)
        if isinstance(node, list):        # internal: [left, right]
            add(node[0], nid + "L", "L: " + _label(node[0]), nid)
            add(node[1], nid + "R", "R: " + _label(node[1]), nid)

    add(game, "root", root_tag + " " + _label(game), None)
    return tree


def _label(node):
    """One-line label: a number for a terminal, '.' for an internal node."""
    return "." if isinstance(node, list) else str(node)


def show_tree(game, root_tag="G"):
    """Print the ASCII game tree for a nested-list game."""
    build_tree(game, root_tag).show(line_type="ascii-em")


def show_heapgo(heap):
    """Convenience: convert a single heap and print its ASCII game tree."""
    game = heapgo_to_tree(heap)
    print("Heapgo G =", heap)
    print("As tree  =", game)
    print()
    show_tree(game)
    return game

# -----------------------------------------------------------------------------
# Quick self-test
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    G = [(2, 'red'), (3, 'red'), (5, 'blue')]
    tree = heapgo_to_tree(G)
    print("---------------------------")
    print("Self test")
    print("---------------------------")
    print("Heapgo G =", G)
    print("As tree  =", tree)
    expected = [[10, 6], [[0, -4], -10]]
    print("Expected =", expected)
    print("Match    =", tree == expected)

# -----------------------------------------------------------------------------
# Generating the game tree of a heapgo game.
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    #G = [(2, 'red'), (3, 'red'), (5, 'blue')]
    G = [(4, 'red'), (3, 'blue'), (4, 'blue'), (4, 'blue'), (5, 'red'), (5, 'red')]
    tree = heapgo_to_tree(G)
    print("---------------------------")
    print("Generating ASCII tree")
    print("---------------------------")
    print("Heapgo G =", G)
    print("As tree  =", tree)

    if Tree is not None:
        print()
        show_tree(tree)
    else:
        print("\n(treelib not installed; skipping ASCII tree.)")
