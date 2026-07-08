"""
main.py — User entry point for LAYER 1 (brute force).

Accepts three input formats for a game G:
  1. CGSuite string:  G = "{11 | {8 | 0}}"     (parsed to nested-list here)
  2. Nested list:     G = [11, [8, 0]]          (passed straight to brute_force)
  3. Heapgo heap:     G = [(2, 'red'), ...]      (a single heap; passed straight
                                                  to brute_force, which converts
                                                  it to a tree)

brute_force_mt builds the full tree and computes the mean and temperature
bottom-up. Format detection lives in game_input.py (used by brute_force);
curly-brace strings are the only form that needs preprocessing here.
"""

from game_parser import parse_game
from brute_force import brute_force_mt, ColdGameError


def _prep_input(G):
    """
    CGSuite strings are parsed to nested-list form (game_parser). Every other
    input — a single Heapgo heap or a nested-list game — is handed straight to
    brute_force_mt, which detects a Heapgo heap and converts it itself.
    """
    if isinstance(G, str):
        print("[main] Detected CGSuite string input")
        G = parse_game(G)
        print("[main] Parsed to nested-list:", G)
    return G


def main():
    # ======= CHOOSE YOUR GAME HERE =======
    # Uncomment exactly ONE of the following.

    # --- CGSuite string ---
    # G = "{11 | {8 | 0}}"          # Position A from Kao's paper; expect M=8, T=3
    # G = "{11 | {6 | 0}}"          # Position B from Kao's paper; expect M=7, T=4
    # G = "{0 | 2}"                 # cold game -> ColdGameError

    # --- Nested list ---
    # G = [11, [8, 0]]              # same as Position A

    # --- Heapgo heap (single heap, bare form) ---
    G = [(2, 'red'), (3, 'red'), (5, 'blue')]   # expect M=1, T=7
    # G = [(4, 'red'), (9, 'blue'), (6, 'red'), (3, 'red'), (1, 'blue')]

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