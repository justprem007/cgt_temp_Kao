"""
build_chain.py — build one alternating chain from a node.

Walks G^L, G^LR, G^LRL, ... (or the R-first version), reading each node's mean
and temperature in the requested mode ('upper' or 'lower'). Stops at a real
terminal, or early at a dummied (chain_terminal) node -- one the sibling rule
has just given a terminal-like reading, so descending past it would only expand
unexplored subtrees for no new information.
"""

from trace_format import _fmt_node, _fmt_chain


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
