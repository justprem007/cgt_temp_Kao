"""
trace_format.py — one-line renderings of a node and a chain, for trace output.

Formatting only; nothing here computes anything. Kept separate because the
sibling rule, chain builder and four-tree runner all print with it.
"""


def _fmt_node(n):
    """Short single-line description of an IncNode for trace output.

    An UNVISITED terminal has no value yet -- it is not read from the
    generator until a walk visits it -- so no value is printed for it. The
    dummy-edge bookkeeping (M_l, M_u, set by the sibling rule in earlier
    walks) IS part of the algorithm's state, so that is printed.
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
