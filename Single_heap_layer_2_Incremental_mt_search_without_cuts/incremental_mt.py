"""
incremental_mt.py — Layer 2 incremental MT-search with LAZY tree generation.

Tree nodes are generated on demand: starting from the raw root position, an
IncNode is created only when the algorithm first touches that position
(during a chain descent, sibling-rule access, or back-walk reconstruction).
The full game tree is NEVER materialised in advance.

Three input formats are accepted by `incremental_mt`:
    1. A nested-list game           (e.g. [11, [8, 0]])
    2. A Heapgo position            (e.g. [[(2,'red'), (3,'red'), (5,'blue')]])
    3. A GameGenerator instance     (custom games — implement the 5 methods)

The algorithm itself is unchanged: same per-node 6-field bookkeeping, same
sibling rule, same stable-theorem cases (A/B/C/D), same skip rule, same two
modes ("mean_only" vs "mean_and_temp"), same finite-sentinel arithmetic.
Only the *order in which terminals are discovered and visited* is set by the
alternating-first search:

    A^1 - from the root, the chain that starts Left and alternates (L,R,L,...)
          to the first terminal, then the chain that starts Right and
          alternates (R,L,R,...) to the first terminal. Every node passed
          through is collected.
    A^n - for each NON-terminal node of A^(n-1), in order, repeat that node's
          last move then alternate to a terminal, collecting the nodes passed
          through.

Terminals are visited in the order they appear across A^1, A^2, ... (see
_alt_first_search_terminals). Each non-terminal contributes its "alternate"
child while it sits in a chain and its "repeat" child when it seeds the next
A-set, so every terminal of the tree is visited exactly once.
"""

import time

from stable_pair import find_stable_pair, ColdGameError   # shared stable-pair solver
from game_input import (                                  # game-format detection + adapters
    GameGenerator,
    NestedListGenerator,
    HeapgoGenerator,
    resolve_generator,
)

# ===========================================================================
# Tuning knobs - edit here.
# ===========================================================================
INFINITY = 10_000          # sentinel for "very large"; must exceed any real score
TIME_LIMIT_SECONDS = 60.0  # default wall-clock cap; can be overridden per call
MEAN_EQ_TOL = 1e-9         # two means within this are treated as equal (Mod 1)


# ===========================================================================
# IncNode - lazy node with per-node bookkeeping.
# ===========================================================================
class IncNode:
    """
    Lazy node. `.left` and `.right` are generated on first access via
    the GameGenerator and cached.

    Bookkeeping (same six fields as before):
       (M_u, T_at_M_u)  - from G_u tree
       (M_l, T_at_M_l)  - from G_l tree
       T_u              - from G_h tree (mean_and_temp only)
       T_l              - from G_c tree (mean_and_temp only)
    Plus two flags:
       four_tree_ran    - True once any per-node four-tree update has run.
       chain_terminal   - True iff dummied & not yet walked-through.
    """

    __slots__ = (
        'state', 'generator', 'path', 'is_terminal', 'value',
        '_left', '_right',
        'M_l', 'M_u', 'T_at_M_l', 'T_at_M_u', 'T_l', 'T_u',
        'four_tree_ran', 'chain_terminal',
        'mean_locked', 'temp_locked',
    )

    def __init__(self, state, generator, path=''):
        self.state = state
        self.generator = generator
        self.path = path
        self.is_terminal = generator.is_terminal(state)
        self._left = None
        self._right = None
        self.four_tree_ran = False
        self.chain_terminal = False
        # Mod 2: once a node's mean bound (M_l == M_u) or temperature bound
        # (T_l == T_u) closes, it is LOCKED and never recomputed again.
        self.mean_locked = False
        self.temp_locked = False

        if self.is_terminal:
            self.value = generator.terminal_value(state)
            # Terminal defaults - unvisited; visit_terminal() will fix later.
            self.M_l = -INFINITY
            self.M_u = INFINITY
            self.T_at_M_l = 0
            self.T_at_M_u = 0
            self.T_l = 0
            self.T_u = 0
        else:
            self.value = None
            # Internal defaults.
            self.M_l = -INFINITY
            self.M_u = INFINITY
            self.T_at_M_l = 0
            self.T_at_M_u = INFINITY
            self.T_l = 0
            self.T_u = INFINITY

    # Lazy children -----------------------------------------------------
    @property
    def left(self):
        if self.is_terminal:
            raise AttributeError("Terminal node has no left child")
        if self._left is None:
            child_state = self.generator.left_child_state(self.state)
            self._left = IncNode(child_state, self.generator, self.path + 'L')
        return self._left

    @property
    def right(self):
        if self.is_terminal:
            raise AttributeError("Terminal node has no right child")
        if self._right is None:
            child_state = self.generator.right_child_state(self.state)
            self._right = IncNode(child_state, self.generator, self.path + 'R')
        return self._right

    # ------------------------------------------------------------------
    def visit_terminal(self):
        assert self.is_terminal
        v = self.value
        self.M_l = self.M_u = v
        self.T_at_M_l = self.T_at_M_u = 0
        self.T_l = self.T_u = 0
        self.four_tree_ran = True
        self.mean_locked = True   # terminal mean is exact
        self.temp_locked = True   # terminal temperature is exactly 0

    def is_visited_terminal(self):
        return (self.is_terminal
                and self.M_l == self.M_u
                and -INFINITY < self.M_l < INFINITY)

    def converged_mean(self):
        return (self.M_l == self.M_u
                and -INFINITY < self.M_l < INFINITY)

    def converged_temp(self):
        return (self.T_l == self.T_u
                and 0 <= self.T_l < INFINITY)

    def converged_mean_and_temp(self):
        return self.converged_mean() and self.T_l == self.T_u


# ===========================================================================
# Context: tracks visited paths and the chain_terminal set.
# ===========================================================================
class _MTContext:
    """Internal scratch state for one incremental_mt run."""

    __slots__ = ('mode', 'visited_paths', 'chain_terminals', 'trace')

    def __init__(self, mode):
        self.mode = mode
        self.visited_paths = set()       # paths already walked
        self.chain_terminals = set()     # IncNode objects flagged chain_terminal
        self.trace = False               # set by incremental_mt() if trace=True

    def mark_chain_terminal(self, node):
        node.chain_terminal = True
        self.chain_terminals.add(node)

    def clear_chain_terminal(self, node):
        if node.chain_terminal:
            node.chain_terminal = False
        self.chain_terminals.discard(node)


# ===========================================================================
# Trace helpers.
# ===========================================================================
def _fmt_node(n):
    """Short single-line description of an IncNode for trace output.

    For an UNVISITED terminal the true value is HIDDEN -- the algorithm
    isn't supposed to use it until the terminal is actually visited in a
    walk, so the trace shouldn't reveal it either. We do show the
    dummy-edge bookkeeping (M_l, M_u set by sibling rule from prior walks)
    because that information IS visible to the algorithm.
    """
    p = f"'{n.path}'" if n.path else "<root>"
    if n.is_terminal:
        if n.is_visited_terminal():
            return f"{p}[term-visited={n.value}]"
        return (f"{p}[term-unvisited "
                f"M=[{n.M_l},{n.M_u}] "
                f"Tu@Mu={n.T_at_M_u} Tl@Ml={n.T_at_M_l}]")
    tag = ("4tree" if n.four_tree_ran
           else ("chainT" if n.chain_terminal else "fresh"))
    return (f"{p}[{tag} "
            f"M=[{n.M_l},{n.M_u}] T=[{n.T_l},{n.T_u}] "
            f"Tu@Mu={n.T_at_M_u} Tl@Ml={n.T_at_M_l}]")


def _fmt_chain(chain):
    """Compact one-line rendering of a chain list."""
    if not chain:
        return "(empty)"
    return "[" + ", ".join(
        f"(d={d}, '{n.path or chr(949)}', M={M}, T={T})"
        for d, n, M, T in chain
    ) + "]"


# ===========================================================================
# Sibling rule + dummy edge.
# ===========================================================================
def apply_sibling_rule(parent, walked_direction, s, ctx):
    """
    During the back-walk: at `parent`, the path just descended via
    `walked_direction` ('L' or 'R'). The SIBLING side gets tightened by `s`.
    Visited terminals are not touched (their M is already exact).
    Newly-touched terminal siblings are registered with `ctx`.
    """
    if walked_direction == 'L':
        sibling = parent.right
        side = "right"
    else:
        sibling = parent.left
        side = "left"

    tr = ctx.trace
    if tr:
        print(f"      [sibling-rule] at parent {_fmt_node(parent)}, "
              f"walked='{walked_direction}', s={s}")
        print(f"        sibling={side} -> {_fmt_node(sibling)}")

    if sibling.is_visited_terminal():
        if tr:
            print(f"        sibling is a visited terminal; no change")
        return

    if sibling.four_tree_ran:
        # Sibling has REAL bounds from its own back-walk; we must not
        # disturb them with a dummy-edge approximation. (This regressed
        # mean_only test 4 when an earlier version of this fix reset
        # T_at_M_u to 0 on a four_tree_ran L node at root, corrupting
        # the chain reading.)
        if tr:
            print(f"        sibling is four_tree_ran with real bounds; "
                  f"no change")
        return

    if walked_direction == 'L':
        old_Mu = sibling.M_u
        sibling.M_u = min(sibling.M_u, s)
        # Dummy edge is terminal-like: T=0 on BOTH sides, so both
        # T_at_M_u and T_at_M_l read 0 -- otherwise the chain reading
        # in upper-vs-lower mode disagrees with the node's own T_l/T_u
        # (the bug Prem flagged: chain reads T=10000 while node shows
        # T_l=T_u=0).
        sibling.T_at_M_u = 0
        sibling.T_at_M_l = 0
        if tr:
            print(f"        sibling.M_u: {old_Mu} -> {sibling.M_u}, "
                  f"T_at_M_u <- 0, T_at_M_l <- 0")
        if not sibling.is_terminal:
            sibling.T_l = 0
            sibling.T_u = 0
            ctx.mark_chain_terminal(sibling)
            if tr:
                print(f"        sibling marked chain_terminal "
                      f"(T_l=T_u=0)")
    else:  # 'R'
        old_Ml = sibling.M_l
        sibling.M_l = max(sibling.M_l, s)
        sibling.T_at_M_l = 0
        sibling.T_at_M_u = 0
        if tr:
            print(f"        sibling.M_l: {old_Ml} -> {sibling.M_l}, "
                  f"T_at_M_l <- 0, T_at_M_u <- 0")
        if not sibling.is_terminal:
            sibling.T_l = 0
            sibling.T_u = 0
            ctx.mark_chain_terminal(sibling)
            if tr:
                print(f"        sibling marked chain_terminal "
                      f"(T_l=T_u=0)")


# ===========================================================================
# Chain construction.
# ===========================================================================
def build_chain(start, first_direction, mode, ctx, label=""):
    """
    Alternating chain rooted at `start`. Returns list of
    (depth, node, M_reading, T_reading). Stops at terminal or
    chain_terminal node. Newly-encountered terminals are registered.
    """
    tr = ctx.trace
    chain = []
    current = start
    next_dir = first_direction
    depth = 0
    while True:
        current = current.left if next_dir == 'L' else current.right
        depth += 1
        if mode == 'upper':
            M_r, T_r = current.M_u, current.T_at_M_u
        else:
            M_r, T_r = current.M_l, current.T_at_M_l
        chain.append((depth, current, M_r, T_r))
        if tr:
            stop = ""
            if current.is_terminal:
                stop = "  [STOP: terminal]"
            elif current.chain_terminal:
                stop = "  [STOP: chain_terminal]"
            print(f"        chain step depth={depth} dir='{next_dir}': "
                  f"{_fmt_node(current)} -> read M={M_r}, T={T_r}{stop}")
        if current.is_terminal:
            break
        if current.chain_terminal:
            break
        next_dir = 'R' if next_dir == 'L' else 'L'
    if tr:
        print(f"        {label}chain = {_fmt_chain(chain)}")
    return chain


# ===========================================================================
# Four-tree update at a single node.
# ===========================================================================
def run_four_trees(node, mode, ctx):
    if node.is_terminal:
        return

    tr = ctx.trace

    # Mod 2: capture which halves were ALREADY locked coming in (before this
    # round runs), so we know which trees to skip and how to judge failures.
    skip_mean = node.mean_locked          # mean already known
    skip_temp = node.temp_locked          # temperature already known
    temp_in_play = (mode == "mean_and_temp")

    if tr:
        print(f"      [run_four_trees] at {_fmt_node(node)}, mode={mode}"
              f"{'  [mean locked]' if skip_mean else ''}"
              f"{'  [temp locked]' if (skip_temp and temp_in_play) else ''}")

    # If everything that applies is already locked, there is nothing to do.
    if skip_mean and (not temp_in_play or skip_temp):
        if tr:
            print(f"      node fully locked (M={node.M_l}"
                  f"{'' if not temp_in_play else f', T={node.T_l}'}); "
                  f"skipping all trees")
        node.four_tree_ran = True
        ctx.clear_chain_terminal(node)
        return

    failed = []

    # ---- mean trees (G_u, G_l): only if mean not locked ----
    if not skip_mean:
        try:
            if tr:
                print(f"      -- G_u (upper mean: chain L upper, chain R upper) --")
            t, m = _run_tree(node, 'L', 'upper', 'R', 'upper', ctx)
            node.M_u, node.T_at_M_u = m, t
            if tr:
                print(f"      G_u: node.M_u <- {m}, node.T_at_M_u <- {t}")
        except ColdGameError as e:
            failed.append('G_u')
            if tr:
                print(f"      G_u FAILED ({e}); node.M_u kept at {node.M_u}")

        try:
            if tr:
                print(f"      -- G_l (lower mean: chain L lower, chain R lower) --")
            t, m = _run_tree(node, 'L', 'lower', 'R', 'lower', ctx)
            node.M_l, node.T_at_M_l = m, t
            if tr:
                print(f"      G_l: node.M_l <- {m}, node.T_at_M_l <- {t}")
        except ColdGameError as e:
            failed.append('G_l')
            if tr:
                print(f"      G_l FAILED ({e}); node.M_l kept at {node.M_l}")

        # Lock the mean only once the node is FULLY converged: the mean has
        # closed (M_l == M_u) AND the temperature has closed (T_l == T_u, i.e.
        # the hot tree T_h and cold tree T_c agree). Locking on the mean alone
        # is wrong -- the mean can close a walk or two before everything below
        # is explored, freezing a stale T_at_M_u that the parent's upper chain
        # then reads. Waiting for the temperature to close too guarantees the
        # subtree is settled, so nothing half-baked gets frozen.
        if node.converged_mean() and node.T_l == node.T_u:
            node.mean_locked = True
            if tr:
                print(f"      *** MEAN LOCKED at {node.M_l} (no further "
                      f"G_u/G_l for this node) ***")
    elif tr:
        print(f"      mean already locked at {node.M_l}; skipping G_u, G_l")

    # ---- temperature trees (G_h, G_c): only in mean_and_temp & not locked ----
    if temp_in_play:
        if not skip_temp:
            try:
                if tr:
                    print(f"      -- G_h (hot/T_u: chain L upper, chain R lower) --")
                t, _ = _run_tree(node, 'L', 'upper', 'R', 'lower', ctx)
                node.T_u = t
                if tr:
                    print(f"      G_h: node.T_u <- {t}")
            except ColdGameError as e:
                failed.append('G_h')
                if tr:
                    print(f"      G_h FAILED ({e}); node.T_u kept at {node.T_u}")

            try:
                if tr:
                    print(f"      -- G_c (cold/T_l: chain L lower, chain R upper) --")
                t, _ = _run_tree(node, 'L', 'lower', 'R', 'upper', ctx)
                node.T_l = t
                if tr:
                    print(f"      G_c: node.T_l <- {t}")
            except ColdGameError as e:
                failed.append('G_c')
                if tr:
                    print(f"      G_c FAILED ({e}); node.T_l kept at {node.T_l}")

            # Lock the temperature if it just closed.
            if node.converged_temp():
                node.temp_locked = True
                if tr:
                    print(f"      *** TEMP LOCKED at {node.T_l} (no further "
                          f"G_h/G_c for this node) ***")
        elif tr:
            print(f"      temp already locked at {node.T_l}; skipping G_h, G_c")

    # ---- cold-game detection ----
    # We attempt 2 mean trees (unless mean was locked) and, in mean_and_temp,
    # 2 temp trees (unless temp was locked). A node is cold iff every tree we
    # ACTUALLY attempted failed AND we carried in no locked half to fall back
    # on. A locked half coming in means the node already has real information,
    # so it is not cold.  (mean_only mode never runs temp trees, but that is
    # NOT prior information -- so it must not suppress the raise.)
    num_attempted = (0 if skip_mean else 2)
    if temp_in_play and not skip_temp:
        num_attempted += 2
    had_prior_info = skip_mean or (temp_in_play and skip_temp)

    if num_attempted > 0 and len(failed) == num_attempted and not had_prior_info:
        raise ColdGameError(f"All attempted trees failed at node: {failed}")

    node.four_tree_ran = True
    ctx.clear_chain_terminal(node)
    if tr:
        print(f"      node now four_tree_ran=True: {_fmt_node(node)}")


def _run_tree(node, L_dir, L_mode, R_dir, R_mode, ctx):
    if ctx.trace:
        print(f"        building chain L (first='{L_dir}', mode={L_mode}):")
    lefts  = build_chain(node, L_dir, L_mode, ctx, label="L-")
    if ctx.trace:
        print(f"        building chain R (first='{R_dir}', mode={R_mode}):")
    rights = build_chain(node, R_dir, R_mode, ctx, label="R-")
    _m, _n, t_cand, m_cand = find_stable_pair(lefts, rights, ctx=ctx)
    return (t_cand, m_cand)


def _alt_first_search_terminals(root, ctx=None):
    """Yield terminal IncNodes in alternating-first-search (A^n) order.

    A^1: from the root, the chain that starts Left and then alternates
         (L, R, L, ...) up to the first terminal, followed by the chain that
         starts Right and alternates (R, L, R, ...) up to the first terminal.
         Every node passed through is collected (terminals and non-terminals).
    A^n (n >= 2): for each NON-terminal node of A^(n-1), in order, repeat that
         node's last move and then alternate up to a terminal, collecting the
         nodes passed through.

    Terminals are yielded in the order they appear, one A-set after another.
    Because each non-terminal X contributes its "alternate" child while X sits
    in a chain and its "repeat" child when X seeds the next set, both children
    of every non-terminal are eventually expanded, so every terminal of the
    tree is yielded exactly once.
    """
    tr = getattr(ctx, "trace", False) if ctx is not None else False

    def chain_from(start, first_dir):
        """From `start`, step `first_dir`, then strictly alternate, collecting
        each node up to (and including) the first terminal."""
        nodes = []
        node = start
        d = first_dir
        while True:
            node = node.left if d == 'L' else node.right
            nodes.append(node)
            if node.is_terminal:
                break
            d = 'R' if d == 'L' else 'L'
        return nodes

    # A^1: Left-first chain, then Right-first chain, both from the root.
    A = chain_from(root, 'L') + chain_from(root, 'R')
    level = 1
    while A:
        if tr:
            print("  A^{} = {{ {} }}".format(
                level, ", ".join("G^" + (n.path or "") for n in A)))
        # Yield this set's terminals, in order.
        for node in A:
            if node.is_terminal:
                yield node
        # Build the next set from this set's non-terminals, in order, each
        # repeating its own last move and then alternating.
        nxt = []
        for node in A:
            if not node.is_terminal:
                nxt += chain_from(node, node.path[-1])
        A = nxt
        level += 1


# ===========================================================================
# Top-level API.
# ===========================================================================
def incremental_mt(game,
                   mode="mean_and_temp",
                   time_limit_seconds=None,
                   max_walks=None,
                   verbose=False,
                   trace=False):
    """
    Layer-2 incremental MT-search with lazy tree generation.

    Arguments:
      game                : nested-list game, Heapgo position, or GameGenerator.
      mode                : "mean_only" or "mean_and_temp" (default).
      time_limit_seconds  : wall-clock cap (defaults to TIME_LIMIT_SECONDS).
      max_walks           : cap on the number of terminal-visit walks. Pass an
                            integer N to visit at most N terminals and then
                            return whatever bounds have been established so far.
                            Pass None (default) or the string "max"/"all" to
                            run until convergence or the tree is exhausted.
      verbose             : if True, print a walk-by-walk trace.
      trace               : if True, print EVERY internal step (sibling rule,
                            chain build, find_stable_pair iterations, four-tree
                            outcomes). Implies verbose. Output is large.

    Returns a dict:
      status      : "converged" | "timeout" | "walk_limit_reached"
                    | "did_not_converge"
      walks_done  : number of terminal-visit walks completed
      M_l, M_u    : final mean bounds at the root
      T_l, T_u    : final temperature bounds at root (None in mean_only)
      elapsed     : wall-clock time in seconds

    Raises ColdGameError on cold-game positions.
    """
    if mode not in ("mean_only", "mean_and_temp"):
        raise ValueError("mode must be 'mean_only' or 'mean_and_temp'")
    if time_limit_seconds is None:
        time_limit_seconds = TIME_LIMIT_SECONDS
    # Normalize max_walks: None / "max" / "all" mean unlimited.
    if max_walks is None or (isinstance(max_walks, str)
                             and max_walks.lower() in ("max", "all")):
        max_walks = float("inf")
    elif not (isinstance(max_walks, int) and max_walks > 0):
        raise ValueError("max_walks must be a positive int, None, "
                         "or 'max'/'all'")
    if trace:
        verbose = True  # trace implies verbose

    t_start = time.time()
    elapsed = lambda: time.time() - t_start

    generator = resolve_generator(game)
    root = IncNode(generator.root_state(), generator, path='')

    # Mod 3: snapshot of the root's bounds as of the LAST FULLY-COMPLETED
    # walk. Every terminal return reports from this snapshot, so an
    # interrupted (partial) walk is never reported -- we fall back to the
    # last good state. Initialized to the pre-walk root state (walks=0).
    snap = {
        "walks": 0,
        "M_l": root.M_l, "M_u": root.M_u,
        "T_l": root.T_l, "T_u": root.T_u,
    }

    def take_snapshot(walks):
        snap["walks"] = walks
        snap["M_l"], snap["M_u"] = root.M_l, root.M_u
        snap["T_l"], snap["T_u"] = root.T_l, root.T_u

    def result(status):
        return {
            "status":     status,
            "walks_done": snap["walks"],
            "M_l":        snap["M_l"],
            "M_u":        snap["M_u"],
            "T_l":        snap["T_l"] if mode == "mean_and_temp" else None,
            "T_u":        snap["T_u"] if mode == "mean_and_temp" else None,
            "elapsed":    elapsed(),
        }

    def converged():
        return (root.converged_mean_and_temp()
                if mode == "mean_and_temp"
                else root.converged_mean())

    if root.is_terminal:
        root.visit_terminal()
        take_snapshot(0)
        return result("converged")

    ctx = _MTContext(mode)
    ctx.trace = trace

    if verbose:
        print(f"\nmode={mode}, time_limit={time_limit_seconds}s, "
              f"max_walks={max_walks}, INFINITY={INFINITY}")
        print("Terminals are visited in alternating-first-search (A^n) order.")

    walks_done = 0

    # Terminals are scheduled in alternating-first-search order. The generator
    # yields each terminal exactly once, A-set after A-set; the back-walk below
    # (chains, sibling rule, four-trees, convergence) is unchanged.
    term_gen = _alt_first_search_terminals(root, ctx)

    while True:
        # ---- stopping criterion: time limit (checked BEFORE a new walk) ----
        if elapsed() > time_limit_seconds:
            if verbose:
                print(f"\nTIMEOUT before walk {walks_done + 1} "
                      f"({elapsed():.3f}s); reporting walk {snap['walks']}")
            return result("timeout")

        # ---- stopping criterion: walk-count cap ----
        if walks_done >= max_walks:
            if verbose:
                print(f"\nWALK LIMIT reached: {walks_done} walk(s) "
                      f"completed (max_walks={max_walks})")
            return result("walk_limit_reached")

        # ---- next terminal in A^n order ----
        term = None
        for cand in term_gen:
            if cand.path not in ctx.visited_paths:   # defensive; A^n is unique
                term = cand
                break
        if term is None:
            break  # all terminals visited

        path = term.path
        ctx.visited_paths.add(path)
        # NOTE (Mod 3): walks_done is NOT incremented yet. It is bumped only
        # after the back-walk runs to completion, so an interrupted walk does
        # not count and is not reported.
        walk_index = walks_done + 1

        if verbose:
            print(f"\n=== Walk {walk_index}: visit {term.value} "
                  f"via '{path}' ===")

        term.visit_terminal()
        s = term.value

        # ---- collect ancestors root -> term (lazy lookups along the way) ----
        ancestors = [root]
        for letter in path:
            ancestors.append(ancestors[-1].left if letter == 'L'
                             else ancestors[-1].right)

        # ---- back-walk (interruptible) ----
        # The root is ancestors[0], processed LAST. Time is checked BEFORE
        # each step; if the limit is crossed we abandon the walk immediately.
        # Because the root is updated only on the final step, an abandoned
        # walk leaves the root holding the previous walk's value, which is
        # exactly what `snap` already records.
        interrupted = False
        for i in range(len(ancestors) - 2, -1, -1):
            if elapsed() > time_limit_seconds:
                interrupted = True
                if verbose:
                    print(f"\nTIMEOUT mid-walk {walk_index} "
                          f"({elapsed():.3f}s); abandoning this walk, "
                          f"reporting walk {snap['walks']}")
                break
            parent = ancestors[i]
            dir_taken = path[i]
            if trace:
                name = "root" if i == 0 else f"depth_{i}"
                print(f"\n  -- back-walk step at {name} "
                      f"(path '{parent.path or chr(949)}'), "
                      f"descended dir='{dir_taken}' --")
                print(f"     before: {_fmt_node(parent)}")
            apply_sibling_rule(parent, dir_taken, s, ctx)
            run_four_trees(parent, mode=mode, ctx=ctx)

            if verbose:
                name = "root" if i == 0 else f"depth_{i}"
                if mode == "mean_and_temp":
                    print(f"  {name}: M=[{parent.M_l}, {parent.M_u}]  "
                          f"T=[{parent.T_l}, {parent.T_u}]")
                else:
                    print(f"  {name}: M=[{parent.M_l}, {parent.M_u}]")

        if interrupted:
            return result("timeout")

        # ---- walk fully completed ----
        walks_done = walk_index
        take_snapshot(walks_done)

        # ---- stopping criterion: convergence (checked at walk end) ----
        if converged():
            if verbose:
                if mode == "mean_and_temp":
                    print(f"\nCONVERGED at walk {walks_done}: "
                          f"M={root.M_l}, T={root.T_l}")
                else:
                    print(f"\nCONVERGED at walk {walks_done}: M={root.M_l}")
            return result("converged")

    # Queue exhausted without meeting any explicit stop criterion.
    return result("converged" if converged() else "did_not_converge")