"""
main.py — user entry point for Layer 1 (brute force).

You give it a game G in any of three formats. main.py figures out which format
it is, turns it into a nested list, and hands that to brute_force_mt:

  1. CGSuite string:  G = "{11 | {8 | 0}}"     -> parsed by game_parser
  2. Nested list:     G = [11, [8, 0]]          -> used as-is
  3. Heapgo heap:     G = [(2, 'red'), ...]      -> a single heap, expanded by
                                                    heapgo_to_tree

brute_force_mt only ever sees a nested-list game: it builds the full tree and
computes the mean and temperature bottom-up.

Which format an input is (the routing) is decided here in main.py. Checking
that an input is actually well-formed happens per format, at the point where it
becomes a nested list: a nested list is checked in brute_force.py as build_tree
walks it, a Heapgo heap is checked in heapgo.py during the conversion, and a
curly-brace string is checked in game_parser.py while it is parsed.
"""

from game_parser import parse_game
from heapgo_to_tree import heapgo_to_tree
from brute_force import brute_force_mt
from stable_pair import ColdGameError

def _prep_input(G):
    """
    Convert any of the three input forms into a nested-list game for
    brute_force_mt.
    """
    if isinstance(G, str):
        print("[main] CGSuite string -> parsing to nested-list")
        G = parse_game(G)
        print("[main] Parsed:", G)
        return G

    if isinstance(G, list) and len(G) > 0 and isinstance(G[0], tuple):
        print("[main] Heapgo heap -> converting to nested-list tree")
        return heapgo_to_tree(G)

    return G


def main():
    # ======= CHOOSE YOUR GAME HERE =======
    # Uncomment exactly ONE of the following.

    # --- CGSuite string ---
    #G = "{11 | {8 | 0}}"          # expect M=8, T=3
    #G = "{0 | 2}"                 # cold game -> ColdGameError

    # --- Nested list ---
    #G = [11, [8, 0]]              # expect M=8, T=3

    # --- Heapgo heap (single heap, bare form) ---
    #G = [(2, 'red'), (3, 'red'), (5, 'blue')]   # expect M=1, T=7
    #G = [(4, 'red'), (9, 'blue'), (6, 'red'), (3, 'red'), (1, 'blue')]

    # ======= RUN =======
    print("Input G =", G)
    print("---------------------------")

    game = _prep_input(G)

    print("---------------------------")
    print("Running LAYER 1 (brute force) ...")
    print("---------------------------")
    try:
        M, T = brute_force_mt(game, verbose=True)
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