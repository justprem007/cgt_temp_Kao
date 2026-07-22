"""
sibling_rule.py — the dummy-edge update applied at a walked parent.

When a walk descends one side of a node, the sibling on the other side has not
been explored. The sibling rule hands it a bound derived from the score the walk
brought back, with temperature 0, so that later chains can read it like a
terminal instead of expanding its subtree.

Which bound is set depends on the direction walked:
    walked 'L' (Left)  -> the sibling gets an UPPER bound (M_u)
    walked 'R' (Right) -> the sibling gets a LOWER bound (M_l)

A sibling that is NOT itself a terminal is additionally flagged
`chain_terminal`: it now reads like a terminal, so build_chain stops there. The
flag is cleared later, once a walk genuinely goes through that node.

Interface
---------
    apply_sibling_rule(parent, walked_direction, s, ctx) -> None

    parent           : the IncNode the walk just passed through
    walked_direction : 'L' or 'R' -- the side the walk descended
    s                : the terminal score carried back up to `parent`
    ctx              : search context (holds the trace flag and the
                       chain_terminal set)
    returns          : None -- the work is a side effect on the SIBLING node
                       (its M_l or M_u, its T fields, its chain_terminal flag)

Example
-------
    Game: heapgo [(2,'red'), (3,'red'), (5,'blue')].
    Walk 1 descends 'L' from the root and brings back the score 6.

        apply_sibling_rule(parent=<root>, walked_direction='L', s=6, ctx=ctx)

    The sibling is node 'R':

        before:  M=[-10000, 10000]  T=[0, 10000]  chain_terminal=False
        after :  M=[-10000, 6]      T=[0, 0]      chain_terminal=True

    Only the upper mean moved (10000 -> 6), because the walk went Left. 'R' is
    an internal node, so it is now flagged chain_terminal. (Had the sibling been
    a real terminal, the flag would stay False -- a terminal already stops a
    chain on its own.)
"""

from trace_format import _fmt_node


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
        # Any not-yet-real sibling becomes a dummy: T=0 on both sides and
        # flagged chain_terminal, so a chain reads it like a terminal and
        # stops. (A real terminal reached here is not yet visited either;
        # its flag is cleared when visit_terminal runs.)
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
        # Any not-yet-real sibling becomes a dummy (see the L branch above).
        sibling.T_l = 0
        sibling.T_u = 0
        ctx.mark_chain_terminal(sibling)
        if tr:
            print(f"        sibling marked chain_terminal "
                  f"(T_l=T_u=0)")