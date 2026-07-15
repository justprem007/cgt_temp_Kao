"""
main.py — user entry point for Layer 1 (brute force).

You give it a game G in one of three formats. main.py works out which format it
is, has validate.py check that it is correctly written, converts it to a nested
list, and hands that to brute_force_mt:

  1. CGSuite string:  G = "{11 | {8 | 0}}"     -> validate.parse_curly
                                                  (checks it and returns the
                                                   nested list in one step)
  2. Nested list:     G = [11, [8, 0]]          -> validate.check_nested,
                                                  then used as-is
  3. Heapgo heap:     G = [(2, 'red'), ...]      -> validate.check_heapgo,
                                                  then heapgo_to_tree

brute_force_mt only sees a nested-list game: it builds the full tree and
computes the mean and temperature bottom-up.
"""

import time

import validate
from validate import InvalidGameError
from heapgo_to_tree import heapgo_to_tree
from brute_force import brute_force_mt
from stable_pair import ColdGameError


def _prep_input(G):
    """
    Work out which format G is, check it, and return it as a nested-list game.

    Returns (tree, convert_ms) -- convert_ms is the time spent turning the input
    into a nested list (None for a nested list, which needs no conversion).

    """
    # --- 1. CGSuite curly-bracket string ---
    if isinstance(G, str):
        print("[main] Input type: CGSuite string")
        t0 = time.perf_counter()
        tree = validate.parse_curly(G)      # checks it and returns the nested list
        convert_ms = (time.perf_counter() - t0) * 1000
        print("[main] Format OK. Nested-list:", tree)
        return tree, convert_ms

    # --- 2. Heapgo heap ---
    if isinstance(G, list) and len(G) > 0 and isinstance(G[0], tuple):
        print("[main] Input type: Heapgo heap")
        validate.check_heapgo(G)
        print("[main] Format OK")
        t0 = time.perf_counter()
        tree = heapgo_to_tree(G)
        convert_ms = (time.perf_counter() - t0) * 1000
        print("[main] Converted to nested-list:", tree)
        return tree, convert_ms

    # --- 3. Nested list ---
    print("[main] Input type: nested list")
    validate.check_nested(G)
    print("[main] Format OK")
    return G, None                          # already a nested list; nothing to convert


def main():
    # ======= CHOOSE YOUR GAME HERE =======
    # Uncomment exactly ONE of the following.

    # --- CGSuite string ---
    #G = "{11 | {8 | 0}}"          # expect M=8, T=3
    #G = "{0 | 2}"                 # cold game -> ColdGameError

    # --- Nested list ---
    #G = [11, [8, 0]]              # expect M=8, T=3

    # --- Heapgo heap (single heap) ---
    #G = [(2, 'red'), (3, 'red'), (5, 'blue')]   # expect M=1, T=7
    G = [(4, 'red'), (9, 'blue'), (6, 'red'), (3, 'red'), (1, 'blue')]

    # ======= OUTPUT DETAIL =======
    # VERBOSE = False              -> just the final mean and temperature
    # VERBOSE = True, TRACE = False -> ONE LINE PER NODE: the node (G, G^L,
    #                                 G^LR, ...), its stable pair (m, n) and
    #                                 case, and its mean and temperature
    # VERBOSE = True, TRACE = True  -> the above, plus every step inside
    #                                 find_stable_pair (the candidate pairs,
    #                                 t_cand/m_cand, the stability test, each
    #                                 advance). This gets LARGE on big games.
    #
    # The timings below are always measured on a separate, silent run, so
    # printing never inflates them.
    #
    # ------- Saving the output to a file -------
    # TRACE output can be far too long to read in a console. Redirect it:
    #
    #     python main.py > output.txt
    #
    # The output is plain ASCII, force UTF-8:
    #
    #     python -X utf8 main.py > output.txt
    VERBOSE = False
    TRACE   = False

    # ======= RUN =======
    print("Input G =", G)
    print("---------------------------")

    try:
        game, convert_ms = _prep_input(G)
    except InvalidGameError as e:
        print("---------------------------")
        print("INVALID INPUT:", e)
        print("---------------------------")
        return

    print("---------------------------")
    print("Running LAYER 1 (brute force) ...")
    print("---------------------------")
    try:
        # The verbose run is for reading; its printing would dwarf the maths,
        # so the timed run below is silent.
        M, T = brute_force_mt(game, verbose=VERBOSE, trace=TRACE)

        t0 = time.perf_counter()
        brute_force_mt(game, verbose=False)
        solve_ms = (time.perf_counter() - t0) * 1000
    except ColdGameError:
        print("---------------------------")
        print("FINAL RESULT:  Cold game (no hot mean/temperature)")
        print("---------------------------")
        return

    print("---------------------------")
    print("FINAL RESULT:  Mean = {} ,  Temperature = {}".format(M, T))
    print("  Convert (heapgo/curly -> nested list) : "
          + ("n/a (input was already a nested list)" if convert_ms is None
             else f"{convert_ms:.4f} ms"))
    print(f"  Solve   (mean & temperature)          : {solve_ms:.4f} ms")
    print("---------------------------")


if __name__ == "__main__":
    main()