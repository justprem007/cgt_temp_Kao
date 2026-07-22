"""
run_four_trees.py — evaluate the four derived trees at a node.

    G_u  upper mean         (chain L upper, chain R upper)
    G_l  lower mean         (chain L lower, chain R lower)
    G_h  hot / T_u          (chain L upper, chain R lower)
    G_c  cold / T_l         (chain L lower, chain R upper)

Each is one call to the shared stable-pair solver on a pair of chains; the
results tighten the node's bounds. Mod 2: a bound that has already closed is
locked and its tree is skipped.
"""

from stable_pair import find_stable_pair, ColdGameError

from trace_format import _fmt_node
from build_chain import build_chain


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
        if node.converged_mean() and node.converged_temp():
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
