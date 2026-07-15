"""
brute_force.py — LAYER 1.

Computes Mean (M) and Temperature (T) of a combinatorial game by:
  1. Building the complete game tree (already done — input is a nested list).
  2. Walking bottom-up.
  3. At each non-terminal node, finding its left and right first stable
     alternating followers.
  4. Applying the stable theorem (Cases A/B/C/D from Kao's paper, section 2).

In this implementation there is no optimization, no pruning, no
handling of incomplete trees.

"""


# The stable-pair solver 
from types import SimpleNamespace

from stable_pair import find_stable_pair, _case_name

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
    Convert a nested-list game into a tree of GameNode objects.
    e.g. game = [11, [8, 0]]
    RETURNS
    GameNode(left=GameNode(value=11), right=GameNode(left=GameNode(value=8),
                                            right=GameNode(value=0)))  
    """
    if isinstance(game, (int, float)):
        return GameNode(value=game)
    return GameNode(left=build_tree(game[0]), right=build_tree(game[1]))


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
def compute_mt(node, verbose=False, trace=False, depth=0, path="G"):
    """
    Recursively compute M and T for every node in the tree, bottom-up.
    Fills in node.M and node.T in place.

    Output detail:
        verbose=False, trace=False : silent
        verbose=True,  trace=False : ONE LINE PER NODE -- the node, its stable
                                     pair (m, n) and case, and its M and T
        verbose=True,  trace=True  : the above, plus every step inside
                                     find_stable_pair (chains, each candidate
                                     pair, t_cand/m_cand, stability test,
                                     each advance). Large.

    `path` names the node in the usual follower notation: G, G^L, G^LR, ...
    """
    indent = "  " * depth

    if node.is_terminal:
        node.M = node.value
        node.T = 0
        if verbose:
            print("{}{}: terminal {}   ->   M={}, T={}".format(
                indent, path, node.value, node.M, node.T))
        return

    # Children first (post-order)
    compute_mt(node.left,  verbose, trace, depth + 1, path + "L")
    compute_mt(node.right, verbose, trace, depth + 1, path + "R")

    # Now both subtrees are fully evaluated — find stable pair.
    # Build the alternating-follower chains in the shared (depth, node, M, T)
    # tuple format that stable_pair.find_stable_pair expects. Every descendant
    # already has .M and .T filled in (post-order), so the readings are exact.
    lefts  = left_alternating_followers(node)    # [(1, G^L), (2, G^LR), ...]
    rights = right_alternating_followers(node)   # [(1, G^R), (2, G^RL), ...]
    lchain = [(d, nd, nd.M, nd.T) for (d, nd) in lefts]
    rchain = [(d, nd, nd.M, nd.T) for (d, nd) in rights]

    if trace:
        print("{}{}: finding stable pair ...".format(indent, path))
    # The shared solver prints its own step-by-step trace only when handed a
    # context whose .trace is true.
    ctx = SimpleNamespace(trace=True) if trace else None
    m, n, t_val, m_val = find_stable_pair(lchain, rchain, ctx=ctx)

    node.T = t_val
    node.M = m_val

    if verbose:
        print("{}{}: stable pair m={}, n={}  [{}]   ->   M={}, T={}".format(
            indent, path, m, n, _case_name(m, n), node.M, node.T))

# -----------------------------------------------------------------------------
# Combining all the above.
# -----------------------------------------------------------------------------
def brute_force_mt(game, verbose=False, trace=False):
    """
    Arguments:
        game : a nested-list game tree.
        verbose : if True, print one line per node (its stable pair, M and T).
        trace   : if True, also print every step inside find_stable_pair.
                  (trace only has an effect together with verbose.)

    Returns:
        (M, T) — the mean and temperature of the root.
    """
    root = build_tree(game)
    compute_mt(root, verbose=verbose, trace=trace)
    return (root.M, root.T)