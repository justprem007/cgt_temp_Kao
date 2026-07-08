"""
stable_pair.py — stable-pair solver (Kao's stable theorem).

LOGIC:

  * Kao's four stable-theorem cases (A/B/C/D), section 2 of the paper.
  * Stability is a TEMPERATURE-ONLY condition: a (left, right) pair is stable
    iff LS_T <= t_cand and RS_T <= t_cand. Means never enter the stability
    test -- they only feed the t_cand/m_cand formula.
  * Exception: in the (even, even) Case D, a pair is only stable when the two
    means agree (within MEAN_EQ_TOL); otherwise it is forced unstable and the
    search advances toward the higher temperature (left on a tie).
  * When a pair is unstable the search advances the unstable/hotter side by
    one follower and re-tests. 

INTERFACE:
  find_stable_pair(lefts, rights, ctx=None) -> (m, n, t_cand, m_cand)
    lefts, rights : [(depth, node, M_reading, T_reading), ...]
                    -- already-built alternating-follower chains. 
    returns        : (m, n, t_cand, m_cand)
                       m, n            stable depths along the two chains
                       t_cand, m_cand  the resulting T(G), M(G)
    raises ColdGameError if both chains exhaust without a stable pair.

  ctx (optional) : if it has a truthy .trace attribute, the search prints a
                   step-by-step trace. Callers that want no trace pass None.
"""


class ColdGameError(Exception):
    """
    Raised when the stable-pair search produces a negative candidate
    temperature, indicating a cold game position. Kao's algorithm assumes
    hot games (Left's options >= Right's options).
    """
    pass


# Tolerance for mean-equality test of Case D (absorbs floating-point rounding).
MEAN_EQ_TOL = 1e-9         # two means within this are treated as equal (Mod 1)
#This is required so that there is no difference between -9.0 and -8.999999999999998.

def _case_name(m, n):
    mo, no = m % 2 == 1, n % 2 == 1
    if mo and no:  return "A (m odd, n odd)"
    if mo:         return "B (m odd, n even)"
    if no:         return "C (m even, n odd)"
    return "D (m even, n even)"


# ===========================================================================
# Stable theorem.
# ===========================================================================
def _apply_stable_theorem(m, n, LS_M, LS_T, RS_M, RS_T):
    m_odd = (m % 2 == 1)
    n_odd = (n % 2 == 1)
    if m_odd and n_odd:                                  # Case A
        return ((LS_M - RS_M) / 2, (LS_M + RS_M) / 2)
    if m_odd:                                            # Case B (m odd, n even)
        return (LS_M - RS_M, RS_M)
    if n_odd:                                            # Case C (m even, n odd)
        return (LS_M - RS_M, LS_M)
    return (max(LS_T, RS_T), LS_M )                      # Case D


def find_stable_pair(lefts, rights, ctx=None):
    """
    lefts, rights : [(depth, node, M_reading, T_reading), ...]
    Returns (m, n, T_cand, M_cand) -- the stable depths m, n plus the
    resulting T(G), M(G). Raises ColdGameError if both chains exhaust.
    """
    tr = ctx is not None and ctx.trace

    if not lefts or not rights:
        if tr:
            print(f"        find_stable_pair: empty chain -> ColdGameError")
        raise ColdGameError("Empty chain")

    li = ri = 0
    it = 0

    while True:
        it += 1
        L_depth, _, LS_M, LS_T = lefts[li]
        R_depth, _, RS_M, RS_T = rights[ri]
        m, n = L_depth, R_depth

        t_cand, m_cand = _apply_stable_theorem(m, n, LS_M, LS_T, RS_M, RS_T)

        # Stability is TEMPERATURE-ONLY: a pair is stable iff both chain
        # temperatures are at or below the candidate temperature.
        ls_ok = (LS_T <= t_cand)
        rs_ok = (RS_T <= t_cand)

        # Exception Case D: in the (even, even) case (Case D)
        # if the means differ the pair is NOT genuinely stable: force it
        # unstable regardless of temperature and advance as usual (toward the
        # higher temperature; left on a tie -- handled by the branch below).
        even_even = (m % 2 == 0) and (n % 2 == 0)
        means_differ = abs(LS_M - RS_M) > MEAN_EQ_TOL
        forced_unstable = even_even and means_differ
        if forced_unstable:
            ls_ok = False
            rs_ok = False

        if tr:
            print(f"        find_stable_pair iter {it}: "
                  f"li={li} ri={ri}  m={m} n={n}  case {_case_name(m, n)}")
            print(f"          LS_M={LS_M}, LS_T={LS_T}  "
                  f"RS_M={RS_M}, RS_T={RS_T}")
            print(f"          t_cand={t_cand}, m_cand={m_cand}")
            extra = ""
            if forced_unstable:
                extra = ("   [Case D: even-even & means differ "
                         "-> FORCED UNSTABLE]")
            print(f"          ls_ok={ls_ok} (LS_T<=t_cand), "
                  f"rs_ok={rs_ok} (RS_T<=t_cand){extra}")
        if ls_ok and rs_ok:
            if tr:
                print(f"          STABLE -> return (T={t_cand}, M={m_cand})")
            return (m, n, t_cand, m_cand)

        ls_bot = (li == len(lefts) - 1)
        rs_bot = (ri == len(rights) - 1)

        if not ls_ok and not rs_ok:
            # Advance the side with the higher temperature; left on a tie.
            if LS_T > RS_T:
                want = 'L'
            elif RS_T > LS_T:
                want = 'R'
            else:
                want = 'L'
        elif not ls_ok:
            want = 'L'
        else:
            want = 'R'

        if want == 'L' and ls_bot:
            if rs_bot:
                if tr:
                    print(f"          both chains at bottom -> ColdGameError")
                raise ColdGameError("Both chains at bottom; no stable pair")
            want = 'R'
        elif want == 'R' and rs_bot:
            if ls_bot:
                if tr:
                    print(f"          both chains at bottom -> ColdGameError")
                raise ColdGameError("Both chains at bottom; no stable pair")
            want = 'L'

        if tr:
            print(f"          want={want} (advancing)")

        # Advance the wanted side by one follower. The ls_bot / rs_bot checks
        # above already guaranteed the wanted side is not at its last index
        # (otherwise we switched sides or raised ColdGameError), so li+1 / ri+1
        # is always in range here.
        if want == 'L':
            li += 1
            if tr:
                print(f"          advance li -> {li}")
        else:
            ri += 1
            if tr:
                print(f"          advance ri -> {ri}")
