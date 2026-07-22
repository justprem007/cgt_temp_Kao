"""
run.py — user entry point for Layer 2 ( alternating first incremental MT-search without cuts).

You give it a game G in one of three formats. run.py works out which format it
is, has validate.py check that it is correctly written, builds the matching
GameGenerator, and hands that to incremental_mt:

  1. CGSuite string:  G = "{11 | {8 | 0}}"      -> validate.parse_curly
                                                    (checks it and returns the
                                                    nested list in one step)
                                                    then NestedListGenerator,
  2. Nested list:     G = [11, [8, 0]]          -> validate.check_nested
                                                    (used as-is),
                                                    then NestedListGenerator
  3. Heapgo heap:     G = [(2, 'red'), ...]     -> validate.check_heapgo
                                                    (used as-is),
                                                    then HeapgoGenerator

incremental_mt only sees a GameGenerator: it expands the game tree on demand,
generating nodes only as the search descends. The generator's methods are
called to get the root state, check if a state is terminal, get its value, 
and get its left and right child states.
"""

import validate
from validate import InvalidGameError
from game_input import NestedListGenerator, HeapgoGenerator
from stable_pair import ColdGameError
from incremental_mt import incremental_mt


def _prep_input(G):
    """ Detect G's format, check it, and return a ready-to-run GameGenerator. """

    # --- 1. CGSuite curly-bracket string ---
    if isinstance(G, str):
        print("[run] Input type: CGSuite string")
        tree = validate.parse_curly(G)      # checks it and returns the nested list
        print("[run] Format OK. Nested-list:", tree)
        return NestedListGenerator(tree)

    # --- 2. Heapgo heap ---
    if isinstance(G, list) and len(G) > 0 and isinstance(G[0], tuple):
        print("[run] Input type: Heapgo heap")
        validate.check_heapgo(G)
        print("[run] Format OK")
        return HeapgoGenerator(G)

    # --- 3. Nested list ---
    print("[run] Input type: nested list")
    validate.check_nested(G)
    print("[run] Format OK")
    return NestedListGenerator(G)


def main():
    # ======= CHOOSE YOUR GAME HERE =======
    # Uncomment exactly ONE of the following.

    # --- CGSuite string ---
    # G = "{11 | {8 | 0}}"            # Position A from Kao's paper; expect M=8, T=3
    # G = "{11 | {6 | 0}}"            # Position B from Kao's paper; expect M=7, T=4
    # G = "{0 | 2}"                   # cold game -> ColdGameError

    # --- Nested list ---
    # G = [11, [8, 0]]
    # G = [[10, 6], [[0, -4], -10]]   # Heapgo running example; expect M=1, T=7

    # --- Heapgo heap (single heap; consumed lazily, no tree conversion) ---
    G = [(2, 'red'), (3, 'red'), (5, 'blue')]   # expect M=1, T=7
    # G = [(4, 'red'), (9, 'blue'), (6, 'red'), (3, 'red'), (1, 'blue')]

    # ======= CHOOSE MODE =======
    # "mean_only"     -> compute M bounds only (faster; G_u + G_l).
    # "mean_and_temp" -> compute both M and T bounds (all four trees).
    MODE = "mean_and_temp"

    # ======= TIME LIMIT (seconds) =======
    # None -> use the module default TIME_LIMIT_SECONDS from incremental_mt.py.
    # Set to a float to override for this run.
    TIME_LIMIT = None

    # ======= MAX WALKS (terminal-visit cap) =======
    # Integer N -> visit at most N terminal nodes, then report whatever bounds
    #              have been established (status = walk_limit_reached).
    # "max" / None -> run until convergence or the tree is exhausted.
    MAX_WALKS = "max"

    # ======= VERBOSE / TRACE =======
    # VERBOSE = True prints walk-by-walk bounds at every back-walk step.
    # TRACE   = True prints EVERY internal step (sibling-rule updates, chain
    #           steps, find_stable_pair iterations, the four-tree outcomes).
    #           Output is large; TRACE = True implies VERBOSE = True.
    #
    # Long output can be saved to a file:
    #     python run.py > output.txt
    #     python -X utf8 run.py > output.txt 
    VERBOSE = True
    TRACE   = True

    # ======= RUN =======
    print("Input G          =", G)
    print("Mode             =", MODE)
    print(f"TIME_LIMIT (s)   = {TIME_LIMIT}   (None = engine default)")
    print(f"MAX_WALKS        = {MAX_WALKS}")
    print(f"VERBOSE          = {VERBOSE}")
    print(f"TRACE            = {TRACE}")
    print("-" * 60)

    try:
        generator = _prep_input(G)
    except InvalidGameError as e:
        print("-" * 60)
        print("INVALID INPUT:", e)
        print("-" * 60)
        return

    print("-" * 60)
    print("Running LAYER 2 (alternating first incremental MT-search without cuts) ...")
    print("-" * 60)

    try:
        res = incremental_mt(generator,
                             mode=MODE,
                             time_limit_seconds=TIME_LIMIT,
                             max_walks=MAX_WALKS,
                             verbose=VERBOSE,
                             trace=TRACE)
    except ColdGameError as e:
        print("-" * 60)
        print("FINAL RESULT:  Cold game (no hot mean/temperature)")
        print(f"  Detail: {e}")
        print("-" * 60)
        return

    # ======= REPORT =======
    print("-" * 60)
    print("FINAL RESULT")
    print("-" * 60)
    print(f"  Status      : {res['status']}")
    print(f"  Walks done  : {res['walks_done']}")
    print(f"  Elapsed     : {res['elapsed']*1000:.3f} ms")

    if MODE == "mean_and_temp":
        if res["status"] == "converged":
            print(f"  Mean        : {res['M_l']}")
            print(f"  Temperature : {res['T_l']}")
        else:
            print(f"  Mean bounds         : [{res['M_l']}, {res['M_u']}]")
            print(f"  Temperature bounds  : [{res['T_l']}, {res['T_u']}]")
    else:  # mean_only
        if res["status"] == "converged":
            print(f"  Mean        : {res['M_l']}")
        else:
            print(f"  Mean bounds : [{res['M_l']}, {res['M_u']}]")
    print("-" * 60)


if __name__ == "__main__":
    main()