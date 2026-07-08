"""
main.py — User entry point.

Accepts three input formats for a game G:
  1. CGSuite string:     G = "{11 | {8 | 0}}"
  2. Nested list:        G = [11, [8, 0]]
  3. Heapgo position:    G = [[(2, 'red'), (3, 'red'), (5, 'blue')]]

Auto-detects which format was given, converts to a uniform nested-list tree,
and runs Layer 1 (brute force) to compute mean and temperature.
"""

from game_parser import parse_game
from heapgo_to_tree import heapgo_to_tree
from brute_force import brute_force_mt, ColdGameError


# -----------------------------------------------------------------------------
# Format detection
# -----------------------------------------------------------------------------
def is_heapgo_position(G):
    """
    A Heapgo position looks like:  [ [ (v,'color'), (v,'color'), ... ], ... ]
    i.e. a list whose elements are lists of (number, string) tuples.
    """
    if not isinstance(G, list) or len(G) == 0:
        return False
    for heap in G:
        if not isinstance(heap, list):
            return False
        for stone in heap:
            if not (isinstance(stone, tuple) and len(stone) == 2):
                return False
            v, c = stone
            if not isinstance(v, (int, float)):
                return False
            if c not in ('red', 'blue'):
                return False
    return True


def is_nested_list_tree(G):
    """
    A valid generic game tree: number, or [left, right] with valid subtrees.
    """
    if isinstance(G, (int, float)):
        return True
    if isinstance(G, list) and len(G) == 2:
        return is_nested_list_tree(G[0]) and is_nested_list_tree(G[1])
    return False


def to_tree(G):
    """Convert any of the three input formats to a nested-list game tree."""
    if isinstance(G, str):
        print("[main] Detected CGSuite string input")
        tree = parse_game(G)
        print("[main] Parsed tree:", tree)
        return tree

    if is_heapgo_position(G):
        print("[main] Detected Heapgo position input")
        tree = heapgo_to_tree(G)
        print("[main] Converted to tree:", tree)
        return tree

    if is_nested_list_tree(G):
        print("[main] Detected nested-list tree input")
        return G

    raise ValueError(
        "Unrecognized game input format. Expected one of:\n"
        "  - CGSuite string like '{11 | {8 | 0}}'\n"
        "  - Nested list like [11, [8, 0]]\n"
        "  - Heapgo position like [[(2, 'red'), (3, 'red'), (5, 'blue')]]"
    )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    # ======= CHOOSE YOUR GAME HERE =======
    # Uncomment ONE of the following.

    # --- CGSuite string ---
    # G = "{11 | {8 | 0}}"          # Position A from Kao's paper;  expect M=8, T=3
    # G = "{11 | {6 | 0}}"          # Position B from Kao's paper;  expect M=7, T=4
    #G="{0|2}"

    # --- Nested list ---
    #G = [11, [8, 0]]              # same as Position A
    
    # --- Heapgo position ---
    #G =  [[(2,'red'),(7,'blue'),(10,'blue')]]
    #G = [[(2, 'red'), (3, 'red'), (5, 'blue')]]   # expect M=1, T=7
    #G = [[(4, 'red'), (9, 'blue'), (6, 'red'), (3, 'red'), (1, 'blue')]]
    #G = [[(7, 'blue'), (8, 'red'), (1, 'blue')]]
    #G = [[(4, 'red'), (3, 'blue'), (4, 'blue'), (4, 'blue'), (5, 'red'), (5, 'red')]]
    G = [[(8,'red'),(7,'blue'),(3,'red'),(5,'blue'),(5,'blue'),(4,'red')]]

    # ======= RUN =======
    print("Input G =", G)
    print("---------------------------")

    tree = to_tree(G)

    print("---------------------------")
    print("Running LAYER 1 (brute force) ...")
    print("---------------------------")
    try:
        M, T = brute_force_mt(tree, verbose=True)
    except ColdGameError:
        print("---------------------------")
        print("FINAL RESULT:  Cold game (no hot mean/temperature)")
        print("---------------------------")
        return

    print("---------------------------")
    print("FINAL RESULT:  Mean = {} ,  Temperature = {}".format(M, T))
    print("---------------------------")


if __name__ == "__main__":
    main()