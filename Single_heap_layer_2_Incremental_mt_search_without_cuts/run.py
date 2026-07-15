"""
run.py - User entry point for LAYER 2 (incremental MT-search).

Accepts three input formats for a game G:
  1. CGSuite string:    G = "{11 | {8 | 0}}"      (parsed to nested-list)
  2. Nested list:       G = [11, [8, 0]]           (passed straight through)
  3. Heapgo position:   G = [[(2,'red'), ...]]     (passed straight through)

The LAZY incremental_mt expands the game tree on demand. For Heapgo and
nested-list inputs there is NO upfront tree conversion: game_input wraps the
input in a NestedListGenerator or HeapgoGenerator and incremental_mt
generates IncNodes only when the algorithm descends to them.

CGSuite strings are parsed to nested-list form because no streaming
CGSuite parser exists in this project; this is a one-time text->list
conversion, not a tree-expansion step.

Two computation modes:
  - "mean_only"     -> runs only G_u and G_l (4 fields per node).
                       Stops when M_l == M_u at the root.
  - "mean_and_temp" -> runs all four trees   (6 fields per node).
                       Stops when M_l == M_u AND T_l == T_u at the root.

Two stop conditions in both modes:
  - Convergence (above).
  - Wall-clock time limit (TIME_LIMIT_SECONDS in incremental_mt.py,
    overridable per call below).
"""

from game_parser import parse_game
from game_input import resolve_generator
from stable_pair import ColdGameError
from incremental_mt import incremental_mt


def _prep_input(G):
    """
    Resolve G into a GameGenerator for incremental_mt.

    Curly-brace strings are parsed to nested-list form first (game_parser);
    every other form is handed to game_input.resolve_generator, which is the
    SINGLE place that decides heapgo vs nested-list vs generator. The engine
    then receives a ready-built generator and performs no format detection of
    its own.
    """
    if isinstance(G, str):
        print("[run] Detected CGSuite string input")
        G = parse_game(G)
        print(f"[run] Parsed to nested-list: {G}")

    generator = resolve_generator(G)
    print(f"[run] Built {type(generator).__name__} (detection lives in game_input.py)")
    return generator


def main():
    # ======= CHOOSE YOUR GAME HERE =======
    # Uncomment exactly ONE of the following.

    # --- CGSuite string ---
    # G = "{11 | {8 | 0}}"            # Position A from Kao's paper; expect M=8, T=3
    # G = "{11 | {6 | 0}}"            # Position B from Kao's paper; expect M=7, T=4
    # G = "{0|2}"                     # cold game -> ColdGameError

    # --- Nested list ---
    # G = [11, [8, 0]]
    # G = [[10, 6], [[0, -4], -10]]   # Heapgo running example; expect M=1, T=7

    # --- Heapgo position (consumed directly, no tree conversion) ---
    G = [(2, 'red'), (3, 'red'), (5, 'blue')]   # expect M=1, T=7
    # G = [[(4, 'red'), (9, 'blue'), (6, 'red'), (3, 'red'), (1, 'blue')]]
    # G = [[(4, 'red'), (3, 'blue'), (4, 'blue'), (4, 'blue'), (5, 'red'), (5, 'red')]]

    # ======= CHOOSE MODE =======
    # "mean_only"     -> compute M bounds only (faster; G_u + G_l).
    # "mean_and_temp" -> compute both M and T bounds (all four trees).
    MODE = "mean_and_temp"

    # ======= TIME LIMIT (seconds) =======
    # None -> use the module default TIME_LIMIT_SECONDS from incremental_mt.py.
    # Set to a float to override for this run.
    TIME_LIMIT = None

    # ======= MAX WALKS (terminal-visit cap) =======
    # Integer N -> visit at most N terminal nodes, then report whatever
    #              bounds have been established (status = walk_limit_reached).
    # "max" / None -> run until convergence or the tree is exhausted.
    MAX_WALKS = "max"

    # ======= VERBOSE =======
    # VERBOSE = True prints walk-by-walk bounds at every back-walk step
    #               (the high-level summary).
    # TRACE   = True prints EVERY internal step: each sibling-rule update,
    #               every chain step, every find_stable_pair iteration, the
    #               outcome of each of the four trees (G_u, G_l, G_h, G_c).
    #               Output is large; intended for hand-verifying the algorithm.
    #               TRACE = True implies VERBOSE = True.
    VERBOSE = True
    TRACE   = False


    # ======= RUN =======
    print("Input G          =", G)
    print("Mode             =", MODE)
    print(f"TIME_LIMIT (s)   = {TIME_LIMIT}   (None = engine default)")
    print(f"MAX_WALKS        = {MAX_WALKS}")
    print(f"VERBOSE          = {VERBOSE}")
    print(f"TRACE            = {TRACE}")
    print("-" * 60)

    G_for_alg = _prep_input(G)

    print("-" * 60)
    print("Running LAYER 2 (lazy incremental MT-search) ...")
    print("-" * 60)

    try:
        res = incremental_mt(G_for_alg,
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