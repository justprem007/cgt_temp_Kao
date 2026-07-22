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

from stable_pair import ColdGameError                     # re-exported for callers

# The individual search steps, one per file.
from sibling_rule import apply_sibling_rule
from run_four_trees import run_four_trees
from alt_first_search import _alt_first_search_terminals
from trace_format import _fmt_node

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
        'state', 'generator', 'path', 'is_terminal', '_value',
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

        # A terminal's value is NOT read here. The algorithm does not know a
        # terminal's value until a walk actually visits it, so we do not ask
        # the generator for it at node creation -- see the `value` property.
        self._value = None
        if self.is_terminal:
            # Terminal defaults - unvisited; visit_terminal() will fix later.
            self.M_l = -INFINITY
            self.M_u = INFINITY
            self.T_at_M_l = 0
            self.T_at_M_u = 0
            self.T_l = 0
            self.T_u = 0
        else:
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
    @property
    def value(self):
        """
        A terminal's value, read from the generator the first time it is
        needed -- i.e. when a walk visits this terminal. Internal nodes have
        no value (None).
        """
        if not self.is_terminal:
            return None
        if self._value is None:
            self._value = self.generator.terminal_value(self.state)
        return self._value

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
# Top-level API.
# ===========================================================================
def incremental_mt(generator,
                   mode="mean_and_temp",
                   time_limit_seconds=None,
                   max_walks=None,
                   verbose=False,
                   trace=False):
    """
    Layer-2 incremental MT-search with lazy tree generation.

    Arguments:
      generator           : a GameGenerator (built in run.py from the raw input
                            after validation). The engine expands it lazily and
                            performs no format detection or checking of its own.
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
        return (root.converged_mean() and root.converged_temp()
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
        ctx.clear_chain_terminal(term)   # a visited terminal is real; drop any dummy flag
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