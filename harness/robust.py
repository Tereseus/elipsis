#!/usr/bin/env python3
"""
robust.py -- the parts of decision analysis that need no weights, no
             probabilities, or no trust in either.

WHY THIS EXISTS

The standing objection to everything else in this project is correct: the
weights are judgements, nobody can measure most of them, and a number built
on invented inputs inherits their arbitrariness however carefully it is
computed.

Decision analysis has known this since the 1950s and built four escape
routes. Each one drops an assumption and returns a weaker conclusion that
is correspondingly harder to argue with. None of them is novel; all four
are standard and none were in this project until now.

  1. STOCHASTIC DOMINANCE  (Hadar & Russell 1969, Hanoch & Levy 1969)
     If option A first-order dominates B, then EVERY decision-maker who
     prefers more to less prefers A -- whatever their values, whatever
     their risk attitude. No weights are consulted because none are
     needed. Second-order dominance is the same guarantee restricted to
     risk-averse preferences.
     This is the strongest conclusion available anywhere in the file, and
     it is immune to the whole objection.

  2. MINIMAX REGRET  (Savage 1951)
     Drop the probabilities entirely. For each option, find the worst
     regret it could produce across every state of the world, and take
     the option whose worst regret is smallest. Needs no distribution and
     no likelihoods -- only the payoff ranges.

  3. ROBUSTNESS RADIUS
     How wrong can every input be, at once, before the answer changes?
     Under a linear payoff this is exact, and it has a clean identity:
     the smallest coordinated error that flips the verdict, measured in
     standard deviations, is exactly the z-score. The uniform version is
     more useful in conversation -- 'if every number I gave you is off by
     35%, does the answer move?' -- and is also exact.

  4. ADVERSARIAL CONSTRUCTION
     Do not ask whether the answer is robust. Ask an opponent to break
     it as cheaply as possible, then read what they had to assume. Under
     a linear payoff the cheapest attack is computable in closed form,
     and what it moves is more informative than any sensitivity table --
     because it is the argument someone who disagrees with you is
     actually going to make.

Run:  python harness/robust.py <decision>
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decide as D                                        # noqa: E402


# ------------------------------------------------- stochastic dominance ---

def _cdf_grid(samples, grid):
    s = sorted(samples)
    n = len(s)
    out, i = [], 0
    for x in grid:
        while i < n and s[i] <= x:
            i += 1
        out.append(i / n)
    return out


def dominance(evs, a, b, points=400):
    """Does a dominate b, and in which order?

    FIRST ORDER: CDF_a(x) <= CDF_b(x) everywhere. Every decision-maker who
    prefers more to less agrees, regardless of values or risk attitude.

    SECOND ORDER: the integral of CDF_a stays below that of CDF_b. Every
    RISK-AVERSE decision-maker agrees. Weaker premise, weaker conclusion,
    still no weights consulted.
    """
    lo = min(min(evs[a]), min(evs[b]))
    hi = max(max(evs[a]), max(evs[b]))
    if hi <= lo:
        return "identical", 0.0
    grid = [lo + (hi - lo) * i / (points - 1) for i in range(points)]
    ca, cb = _cdf_grid(evs[a], grid), _cdf_grid(evs[b], grid)
    step = (hi - lo) / (points - 1)

    if all(x <= y + 1e-12 for x, y in zip(ca, cb)):
        gap = max(y - x for x, y in zip(ca, cb))
        return "first order", gap
    ia = ib = 0.0
    ok = True
    worst = 0.0
    for x, y in zip(ca, cb):
        ia += x * step
        ib += y * step
        worst = max(worst, ib - ia)
        if ia > ib + 1e-9:
            ok = False
            break
    if ok:
        return "second order", worst
    return "none", 0.0


# -------------------------------------------------------- minimax regret ---

def minimax_regret(d, n=4000):
    """Savage. No probabilities used -- only the payoff of each option in
    each sampled state, and the regret of not having picked the best one.

    Reported because expected value quietly assumes you are indifferent
    between a sure thing and a gamble with the same mean, and on one-shot
    decisions almost nobody is.
    """
    evs = D.simulate(d, n=n)
    names = list(evs)
    worst = {x: 0.0 for x in names}
    for i in range(n):
        best = max(evs[x][i] for x in names)
        for x in names:
            worst[x] = max(worst[x], best - evs[x][i])
    return worst


# ----------------------------------------------------- robustness radius ---

def radius(d, na, nb):
    """How wrong can everything be, together, before the answer flips?

    The margin is linear:  D = SUM_i dB_i * theta_i
    Write v_i = dB_i * sigma_i. Moving belief i by z_i of its own standard
    deviations changes the margin by v_i * z_i. The smallest coordinated
    move that reaches zero is then the minimum-norm solution of

        v . z = -E[D]

    which is  ||z||_2 = |E[D]| / ||v||_2  -- exactly the z-score. The
    cheapest attack is z = -E[D] * v / ||v||^2, and the L-infinity version
    (every belief wrong by the same fraction of a standard deviation) is
    |E[D]| / SUM_i |v_i|.
    """
    parts, ed, sd, p, sd_n, p_n, bsd = D.pair_margin(d, na, nb)
    v = [(name, db * s) for name, db, mu, s in parts]
    l2 = math.sqrt(sum(x * x for _, x in v))
    l1 = sum(abs(x) for _, x in v)
    if l2 <= 0:
        return None
    # minimum-norm solution: z = -E[D] * v / ||v||^2, in units of each
    # belief's own standard deviation
    attack = [(name, -ed * x / (l2 * l2)) for name, x in v]
    return {
        "margin": ed,
        "l2_radius": abs(ed) / l2,              # combined sigmas, = z-score
        "uniform_radius": abs(ed) / l1 if l1 else float("inf"),
        "attack": sorted(attack, key=lambda t: -abs(t[1])),
        "parts": parts,
    }


def uniform_error_flip(d, na, nb):
    """'If every number I gave you is wrong by X of its own spread, in the
    worst possible direction, does the answer change?' -- answered exactly."""
    r = radius(d, na, nb)
    return None if r is None else r["uniform_radius"]


# ----------------------------------------------------------- reporting ---

def report(d):
    evs = D.simulate(d)
    names = [o["name"] for o in d["options"]]
    rows = sorted(names, key=lambda n: -D.mean(evs[n]))
    lead = rows[0]

    print("=" * 74)
    print("  CONCLUSIONS THAT DO NOT NEED THE WEIGHTS")
    print("=" * 74)
    print()
    D.para("Everything below drops an assumption the main report relies on. "
           "The conclusions are weaker and much harder to argue with.")
    print()

    # ---- 1. dominance ---------------------------------------------------
    print("  1. STOCHASTIC DOMINANCE  -- no weights, no risk attitude")
    print("  " + "-" * 70)
    found = False
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            kind, gap = dominance(evs, a, b)
            if kind in ("first order", "second order"):
                found = True
                print(f"   {a}  dominates  {b}   ({kind}, gap {gap:.3f})")
    if not found:
        print("   none")
        print()
        D.para("No option dominates another. That is informative rather than "
               "disappointing: it means the ranking genuinely depends on "
               "values or on risk attitude, so anyone who disagrees with the "
               "verdict is disagreeing about something real and not about "
               "arithmetic.")
    else:
        print()
        D.para("FIRST ORDER means every decision-maker who prefers more to "
               "less agrees, whatever their values and whatever their "
               "attitude to risk. SECOND ORDER means every risk-averse one "
               "does. Neither consults a single weight, so neither can be "
               "undone by the weights being wrong. This is the strongest "
               "thing this project can say about anything.")
    print()

    # ---- 2. minimax regret ---------------------------------------------
    print("  2. MINIMAX REGRET  (Savage)  -- no probabilities at all")
    print("  " + "-" * 70)
    mr = minimax_regret(d)
    best_mr = min(mr, key=lambda k: mr[k])
    for n in sorted(mr, key=lambda k: mr[k]):
        print(f"   {n:<28}worst regret {mr[n]:>12,.0f}")
    print()
    if best_mr == lead:
        D.para(f"'{best_mr}' minimises worst-case regret AND maximises "
               f"expected value. Those are different criteria resting on "
               f"different assumptions, and they agree here.")
    else:
        D.para(f"DISAGREEMENT WORTH NOTICING. Expected value picks "
               f"'{lead}'; minimax regret picks '{best_mr}'. The first "
               f"assumes you are indifferent between a certainty and a "
               f"gamble of equal mean; the second refuses to use "
               f"probabilities at all. Which is right depends on whether "
               f"this decision is repeated -- expected value is the correct "
               f"criterion over many similar bets and a strange one for a "
               f"single irreversible choice.")
    print()

    # ---- 3 & 4. radius and adversary ------------------------------------
    if len(rows) > 1:
        r = radius(d, rows[0], rows[1])
        if r:
            print("  3. ROBUSTNESS RADIUS  -- how wrong can everything be?")
            print("  " + "-" * 70)
            D.maths("THE FORMULA",
                    ["margin  D = Σ_i Δβ_i · θ_i,      v_i = Δβ_i · σ_i",
                     "",
                     "smallest coordinated error that flips it:",
                     "     ‖z‖₂ = |E[D]| / ‖v‖₂        (combined σ)",
                     "",
                     "every belief wrong by the same fraction of its spread:",
                     "     z_uniform = |E[D]| / Σ_i |v_i|"],
                    ["SUBSTITUTED:",
                     "E[D]    = {:,.2f}".format(r["margin"]),
                     "‖v‖₂    = {:,.2f}".format(
                         abs(r["margin"]) / r["l2_radius"]),
                     "Σ|v|    = {:,.2f}".format(
                         abs(r["margin"]) / r["uniform_radius"]
                         if r["uniform_radius"] else 0),
                     "",
                     "‖z‖₂        = {:.3f} combined standard deviations"
                     .format(r["l2_radius"]),
                     "z_uniform   = {:.3f} of each belief's own spread"
                     .format(r["uniform_radius"])],
                    legend=["D", "Δ", "β", "σ", "θ_i", "Σ_i", "E[...]"], d=d)
            u = r["uniform_radius"]
            print("   THIS PERCENTAGE IS NOT A PROBABILITY.")
            print()
            D.para(f"It is an ERROR TOLERANCE. Every single number in this "
                   f"model would have to be wrong by {u:.0%} of its own "
                   f"spread, all in the worst direction at once, before the "
                   f"answer reverses.")
            print()
            D.para(f"So: the verdict SURVIVES any coordinated error up to "
                   f"{u:.0%}, and FAILS to coordinated error beyond "
                   f"{u:.0%}. Higher is safer -- which is the opposite of "
                   f"how you read a probability, and the reason it is "
                   f"labelled.")
            print()
            if u < 0.15:
                D.para("That is a small amount of coordinated error, and "
                       "coordinated error is exactly what one author "
                       "writing every number in one sitting produces. Treat "
                       "this verdict as unsettled.")
            elif u < 0.40:
                D.para("Moderate. A consistent tilt of that size is well "
                       "within what a single author can introduce without "
                       "noticing, so the verdict is real but not safe.")
            else:
                D.para("That is a large coordinated error to require. The "
                       "verdict survives most ways of being wrong about the "
                       "inputs, which is the useful sense in which a number "
                       "built from judgements can still be worth something.")
            print()

            print("  4. THE CHEAPEST ATTACK  -- what an opponent moves first")
            print("  " + "-" * 70)
            D.para("Not a sensitivity table. The minimum-effort change that "
                   "reverses the verdict, solved exactly. This is the "
                   "argument someone who disagrees with you is going to "
                   "make, whether or not they know why they picked it.")
            print()
            print("   {:<28}{:>14}{:>16}".format(
                "belief", "move by", "in its own σ"))
            byid = {u_["id"]: u_ for u_ in d["uncertainties"]}
            for name, z in r["attack"][:8]:
                sg = D.prior_sd(byid[name])
                print("   {:<28}{:>14,.2f}{:>15.2f}σ".format(
                    name, z * sg, z))
            print()
            top = r["attack"][0]
            D.para(f"An opponent starts with '{top[0]}'. If you cannot "
                   f"defend that one number, the verdict is theirs, and no "
                   f"amount of care about the other beliefs compensates.")
            print()


def main():
    if len(sys.argv) < 2:
        fs = sorted(f[:-5] for f in os.listdir(D.DECISIONS)
                    if f.endswith(".json"))
        print("decisions:", ", ".join(fs))
        return
    report(D.load(sys.argv[1]))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
