"""
alt_first_search.py — the order in which terminals are visited.

Yields the game's terminals in "alternate-first" order: each non-terminal
contributes its alternating follower chain, level by level, so the walks probe
the parts of the tree that matter to the stable-pair search first rather than
sweeping left to right.
"""


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
