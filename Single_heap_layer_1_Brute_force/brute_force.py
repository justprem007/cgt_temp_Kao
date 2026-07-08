"""
brute_force.py — LAYER 1.

Computes Mean (M) and Temperature (T) of a combinatorial game by:
  1. Building the complete game tree (already done — input is a nested list).
  2. Walking bottom-up.
  3. At each non-terminal node, finding its left and right first stable
     alternating followers.
  4. Applying the stable theorem (Cases A/B/C/D from Kao's paper, section 2).

This is the REFERENCE implementation. No optimization, no pruning, no
handling of incomplete trees. Any later layer must produce the same M and T.

=======================================================================
NOTATION (from Kao 2000)
=======================================================================
  G^L    = the position after Left's move from G.
  G^R    = the position after Right's move from G.

  Left alternating followers of G :  G^L, G^LR, G^LRL, G^LRLR, ...
  Right alternating followers of G:  G^R, G^RL, G^RLR, G^RLRL, ...

  Level m: the m-th left alternating follower G^{L(m)} is reached by m moves
  (starting with L, alternating).

  G^{L(m)} is the LEFT FIRST STABLE alternating follower of G  iff
      T(G^{L(i)}) > T(G^{L(m)})   for  0 < i < m       (unstable above)
      T(G^{L(m)}) <= T(G)                               (stable at G's temp)

  But note: when computing T(G) itself, we don't know T(G) yet.
  Kao's approach — followed here — is: the stable pair is found jointly
  with T(G) via a consistency condition. See find_stable_pair() below.

=======================================================================
THE STABLE THEOREM (Section 2 of Kao's paper)
=======================================================================
  Let G^{L(m)}, G^{R(n)} be the left and right first stable alternating
  followers of G. Then:

    Case A:  m odd,  n odd   =>  M(G) = (M(G^{L(m)}) + M(G^{R(n)})) / 2
                                 T(G) = (M(G^{L(m)}) - M(G^{R(n)})) / 2

    Case B:  m odd,  n even  =>  M(G) = M(G^{R(n)})
                                 T(G) = M(G^{L(m)}) - M(G^{R(n)})

    Case C:  m even, n odd   =>  M(G) = M(G^{L(m)})
                                 T(G) = M(G^{L(m)}) - M(G^{R(n)})

    Case D:  m even, n even  =>  M(G) = M(G^{L(m)}) = M(G^{R(n)})
                                 T(G) = max( T(G^{L(m)}), T(G^{R(n)}) )
"""


# The stable-pair solver and the ColdGameError exception now live in
# stable_pair.py and are shared with the Layer-2 incremental implementation.
# ColdGameError is re-exported here so existing imports keep working.
from stable_pair import find_stable_pair, ColdGameError


class GameNode:
    """
    Node in a complete game tree.
      value       : terminal score (only set when is_terminal is True)
      left, right : child GameNodes (only set when is_terminal is False)
      M, T        : the mean and temperature (filled by compute_mt)
    """
    def __init__(self, value=None, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right
        self.is_terminal = (left is None and right is None)
        self.M = None
        self.T = None

    def __repr__(self):
        if self.is_terminal:
            return "Terminal(value={}, M={}, T={})".format(self.value, self.M, self.T)
        return "Node(M={}, T={})".format(self.M, self.T)


# -----------------------------------------------------------------------------
# Build a GameNode tree from the nested-list input format.
# -----------------------------------------------------------------------------
def build_tree(game):
    """
    Convert nested-list game input into a tree of GameNode objects.
      number                -> terminal GameNode
      [left, right]         -> non-terminal GameNode with child trees
    """
    if isinstance(game, (int, float)):
        return GameNode(value=game)
    if isinstance(game, list) and len(game) == 2:
        left_tree = build_tree(game[0])
        right_tree = build_tree(game[1])
        return GameNode(left=left_tree, right=right_tree)
    raise ValueError("Invalid game input: {!r}".format(game))


# -----------------------------------------------------------------------------
# Walk down alternating followers and collect them (including depth).
# -----------------------------------------------------------------------------
def left_alternating_followers(node):
    """
    Return a list of (depth, follower_node) for the left alternating followers
    of `node`: depth 1 = G^L, depth 2 = G^LR, depth 3 = G^LRL, ...
    Stops when we hit a terminal (terminals are INCLUDED in the list).

    The walker starts by taking a LEFT branch; then at each subsequent step
    it alternates (right, left, right, ...).
    """
    followers = []
    current = node
    next_direction = 'L'          # first step is Left (by definition of G^L)
    depth = 0
    while not current.is_terminal:
        if next_direction == 'L':
            current = current.left
        else:
            current = current.right
        depth += 1
        followers.append((depth, current))
        # alternate direction for next step
        next_direction = 'R' if next_direction == 'L' else 'L'
    return followers


def right_alternating_followers(node):
    """Symmetric to left_alternating_followers but starts with R."""
    followers = []
    current = node
    next_direction = 'R'
    depth = 0
    while not current.is_terminal:
        if next_direction == 'R':
            current = current.right
        else:
            current = current.left
        depth += 1
        followers.append((depth, current))
        next_direction = 'L' if next_direction == 'R' else 'R'
    return followers


# -----------------------------------------------------------------------------
# Bottom-up M and T computation.
# -----------------------------------------------------------------------------
def compute_mt(node, verbose=False, depth=0):
    """
    Recursively compute M and T for every node in the tree, bottom-up.
    Fills in node.M and node.T in place.
    """
    indent = "  " * depth

    if node.is_terminal:
        node.M = node.value
        node.T = 0
        if verbose:
            print("{}Terminal: value={}  =>  M={}, T={}".format(
                indent, node.value, node.M, node.T))
        return

    # Children first (post-order)
    compute_mt(node.left,  verbose, depth + 1)
    compute_mt(node.right, verbose, depth + 1)

    # Now both subtrees are fully evaluated — find stable pair.
    if verbose:
        print("{}Internal node: finding stable pair ...".format(indent))
    # Build the alternating-follower chains in the shared (depth, node, M, T)
    # tuple format that stable_pair.find_stable_pair expects. Every descendant
    # already has .M and .T filled in (post-order), so the readings are exact.
    lefts  = left_alternating_followers(node)    # [(1, G^L), (2, G^LR), ...]
    rights = right_alternating_followers(node)   # [(1, G^R), (2, G^RL), ...]
    lchain = [(d, nd, nd.M, nd.T) for (d, nd) in lefts]
    rchain = [(d, nd, nd.M, nd.T) for (d, nd) in rights]
    m, n, t_val, m_val = find_stable_pair(lchain, rchain)

    # Determine which case applied (for logging)
    case = _case_name(m, n)
    node.T = t_val
    node.M = m_val

    if verbose:
        print("{}  Stable pair fixed: m={}, n={}   ({})".format(indent, m, n, case))


def _case_name(m, n):
    odd_m = (m % 2 == 1)
    odd_n = (n % 2 == 1)
    if odd_m and odd_n: return "Case A (m odd, n odd)"
    if odd_m:           return "Case B (m odd, n even)"
    if odd_n:           return "Case C (m even, n odd)"
    return "Case D (m even, n even)"


# -----------------------------------------------------------------------------
# Top-level API
# -----------------------------------------------------------------------------
def brute_force_mt(game, verbose=False):
    """
    Top-level entry point for Layer 1.

    Arguments:
        game    : nested-list game tree (terminals are numbers; internal nodes
                  are [left, right]).
        verbose : if True, print the full bottom-up trace.

    Returns:
        (M, T) — the mean and temperature of the root.
    """
    root = build_tree(game)
    compute_mt(root, verbose=verbose)
    return (root.M, root.T)