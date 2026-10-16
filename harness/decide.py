#!/usr/bin/env python3
"""
decide.py -- expected value, breakdown values, and the value of information,
             with history entering as a CALIBRATED SIGNAL rather than as an
             assertion.

WHY THIS EXISTS
Out-of-sample transfer error in the social sciences runs at roughly 93-99%
of the effect size (Vivalt, 635 papers). History does not tell you what will
happen.

That does not stop deciding, because a decision needs less. It needs to know
which option survives the range of things that might be true. History is
good at bounding a range even when it is useless at picking a point.

So history enters here in exactly two places: as the source of the ranges,
with its provenance attached, and as a NOISY SIGNAL whose noise is set by the
transfer-error literature itself.

FIVE OUTPUTS

  EXPECTED VALUE, as a distribution
      Monte Carlo over your stated ranges. The spread and P(wins), not a
      point estimate.

  CONTRIBUTIONS
      Every term of every option, at its mean, sorted by size, plus the
      margin between the top two decomposed term by term. This answers
      "why did that win?" arithmetically instead of rhetorically. If one
      term carries the margin, the decision is about that term and the rest
      of the argument is decoration.

  BREAKDOWN VALUES
      For each belief, the exact value at which the winner changes. Root-find
      by bisection. This is the number that tells you how fragile you are.

  EVPI -- expected value of PERFECT information
      EVPI(t) = E_t[ max_a EV(a|t) ] - max_a E_t[ EV(a) ]
      What knowing t exactly before choosing would be worth. An upper bound
      on the value of any research whatsoever into t.

  EVSI -- expected value of HISTORIC information            <-- the new one
      You never learn t exactly. History hands you a signal that is wrong by
      some amount:
                s = t + e,      e ~ Normal(0, k * sd(t))
      k is the transfer error. Vivalt's median is about 0.95. Bold et al.
      found a Kenyan program at 0.21 SD replicate at exactly 0.00 under a
      different implementer, same country and same year -- that is k >= 1.
      Then
            EVSI(t) = E_s[ max_a EV(a | posterior(t|s)) ] - max_a E_t[EV(a)]
      and always  0 <= EVSI <= EVPI.

      EVSI/EVPI is the share of the achievable value that history can
      actually deliver. It is usually small, and that number is the honest
      answer to "can the past decide this?"

      A belief with no reference class gets EVSI = 0 by construction. There
      is no signal to receive. You are choosing under ignorance, and the
      tool says so rather than dressing it up.

LINEARITY
Payoffs are linear in the uncertainties: coefficients plus a constant, no
expression evaluation. Restrictive, and it buys something real -- under a
linear payoff only the posterior MEAN matters, so EVPI and EVSI come out
exactly instead of by nested simulation. If your payoff is not linear, say
so rather than pretending.

PROVENANCE IS MANDATORY
Every belief declares where its range came from: measured, estimated, or
guessed. The report states what share of the total uncertainty is guessed.
A made-up range drives the answer exactly as hard as a real one, and the
only defence is showing which is which.

A SIXTH, ON REQUEST: IS A TEST WORTH RUNNING?
      The same EVSI with the noise set by a test you have not run yet
      instead of by history, times the periods left after it, minus what
      it costs. See `test_value` below.

Run:  python harness/decide.py <name>
      python harness/decide.py <name> --test <belief> <outcome_sd> [horizon_days]
"""

import json
import math
import os
import random
import re
import sys

def _utf8_stdout():
    """Only when run directly. Importing this module must NOT touch the
    parent's stdout -- the MCP server speaks JSON-RPC over that stream and
    reconfiguring it underneath would corrupt the protocol."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402  (sits next to this file)
DECISIONS = paths.data("decisions")
N_DRAWS = 20000
SEED = 20260912

# Median transfer error from Vivalt's 635-paper meta-analysis. Used when a
# belief cites history but does not state its own.
DEFAULT_TRANSFER_ERROR = 0.95

# HOW THE SIGNAL NOISE IS SPECIFIED.
#
# WRONG: set k = tau/sigma directly from Vivalt's
# median relative error of 0.95. Two separate errors.
#
#   1. MISMATCHED DENOMINATORS. Vivalt's statistic is
#          median|error| / |effect magnitude|
#      and k is
#          tau / (prior SD).
#      Those share no denominator.
#
#   2. MEDIAN IS NOT A STANDARD DEVIATION. For centred normal error,
#      median|e| = 0.67449*tau, so tau = median|e| / 0.67449.
#
# Also wrong in principle: making noise a RATIO to the prior means that
# widening an elicited prior silently improves the assumed evidence. A
# study's error does not shrink because an analyst got less confident.
#
# RIGHT: state the noise ABSOLUTELY, in the belief's own units, because
# that is a property of the evidence rather than of the prior.
#
#   history.signal_sd     tau, directly, in the belief's units
#   history.vivalt_ratio  + history.effect_magnitude
#                         tau = ratio/0.67449 * magnitude
#
# k = tau/sigma is then DERIVED and reported for interpretation only. It
# is never an input again.
MEDIAN_ABS_TO_SD = 0.6744897501960817

CLAMPED = []      # EVSI estimates that hit the EVPI ceiling, reported not hidden

# THE ELICITOR IS A COMMON FACTOR, and ignoring that manufactures confidence.
#
# Channels are not independent draws from the world. One person wrote all of
# them, in one sitting, in one mood, from one reading. If that person is
# systematically pessimistic by some amount, EVERY channel is shifted the same
# way, and that shift never averages out.
#
# Treat the beliefs as independent and the arithmetic does something ugly:
#     E[D]  grows like n      (n channels, tilted the same way)
#     sd[D] grows like sqrt(n)  (variances add)
#     E/sd  grows like sqrt(n)  ->  P goes to 100% by COUNTING ALONE
# Four times the channels, twice the z-score, free.
#
# The fix is one shared term. Write each belief as
#     theta_i = draw_i + sigma_i * b,     b ~ Normal(0, BIAS)
# with ONE b per scenario, shared across every channel. Then
#     Var[D] = SUM (dB*sigma)^2  +  BIAS^2 * (SUM dB*sigma)^2
# and the second term grows like n^2, so sd grows like n and the z-score
# stops climbing. Confidence now has to be earned rather than counted.
#
# 0.35 means: the author is typically wrong by a third of a belief spread,
# in the same direction, across the whole model. That is generous.
DEFAULT_ELICITOR_BIAS = 0.35

MARK = {"measured": " ", "estimated": "~", "guessed": "?"}


def both_ways(p, for_label, against_label, what):
    """Never print a bare percentage.

    Four different quantities in these reports were all rendering as '%':
    the probability an option wins, the robustness radius, the share of
    value historical evidence can reach, and the share of a model's
    uncertainty that was guessed. Only the first is a probability. A reader
    who sees 43% assumes it is one, because that is the default reading of
    a percent sign, and they are right to.

    So every percentage now says what it measures and gives both sides.
    """
    return ("{:.0%} {}   /   {:.0%} {}      ({})"
            .format(p, for_label, 1 - p, against_label, what))


# ----------------------------------------------------------------- legend ---
# A formula nobody can read is the same as no formula. Every symbol this
# file prints is defined here in plain English, and the definition is
# printed alongside every derivation that uses it -- not once at the top
# where it scrolls away.

SYMBOLS = [
    ("θ", "theta",
     "ONE UNCERTAIN THING. A belief you hold as a range instead of a "
     "number. In this file there are {n} of them: {ex}, and so on."),
    ("θ_i", "theta-sub-i",
     "'the i-th one of them'. i is only a counter -- 1, 2, 3 ... {n}. "
     "It means 'each belief in turn', nothing more."),
    ("Σ_i", "sigma, capital",
     "ADD UP, over every i. Σ_i x_i is just x_1 + x_2 + x_3 + ... "
     "The capital sigma means addition and nothing else."),
    ("a, b", "",
     "AN OPTION -- one of the things you could do. Here: {opts}."),
    ("β", "beta",
     "HOW MUCH A BELIEF COUNTS FOR AN OPTION. β_{{a,i}} is the multiplier "
     "on belief i inside option a. In this file every one is +1 (a "
     "benefit), -1 (a cost), or 0 (that belief does not touch that "
     "option)."),
    ("Δ", "delta",
     "THE DIFFERENCE IN. Δβ_i means 'how much more belief i counts for "
     "the first option than for the second'. If a belief counts the same "
     "for both, its Δβ is zero and it drops out of the comparison "
     "entirely -- which is why most of the {n} beliefs never appear in "
     "the margin."),
    ("c_a", "c-sub-a",
     "A FIXED AMOUNT attached to option a regardless of any belief. Zero "
     "everywhere in this file, but the formula carries it."),
    ("EV(a)", "expected value",
     "WHAT OPTION a IS WORTH ON AVERAGE, in {unit}. Average across "
     "everything you are unsure about."),
    ("D", "",
     "THE DIFFERENCE BETWEEN THE TOP TWO OPTIONS. D = EV(first) - "
     "EV(second). If D is above zero the first one wins. D is itself "
     "uncertain, because it is built out of ranges, so D has a spread "
     "too -- that is the whole point of computing it."),
    ("E[...]", "expectation",
     "THE AVERAGE OF. E[θ] is the average value of that belief across "
     "its range. E[D] is the average difference between the two options."),
    ("Var[...]", "variance",
     "HOW SPREAD OUT. Big variance means the number moves around a lot. "
     "It is in squared units, which is why the square root is taken to "
     "get back to {unit}."),
    ("μ", "mu",
     "THE AVERAGE of one belief. Same thing as E[θ], written shorter "
     "when it appears inside a bigger formula."),
    ("σ", "sigma, small",
     "THE SPREAD of one belief -- the square root of its variance, in "
     "{unit}. Roughly: how far from its average it typically lands."),
    ("Φ", "Phi, capital",
     "THE BELL-CURVE LOOKUP. Feed it 'how many spreads above zero' and "
     "it returns a probability. Φ(0) = 50%, Φ(1) = 84%, Φ(2) = 98%. "
     "Used here ONLY as a second opinion on the simulation."),
    ("x", "",
     "A SPECIFIC VALUE that one belief might turn out to take, as "
     "opposed to the whole range."),
    ("x*", "x-star",
     "THE BREAKDOWN VALUE. The exact value of x at which the winning "
     "option changes. Your answer survives on one side of it and flips "
     "on the other."),
    ("k", "",
     "TRANSFER ERROR. How wrong history is when you carry a finding from "
     "where it was measured to where you want to use it. k = 0 means the "
     "past transfers perfectly. k = 1 means the error is as big as the "
     "thing being measured."),
    ("λ", "lambda",
     "SHRINKAGE. How far a historical finding moves your belief toward "
     "what it says. λ = 1/(1+k²). At k = 0.95 it is 0.53, so history "
     "moves you about halfway and then stops."),
    ("s", "",
     "THE SIGNAL. What history actually tells you -- the true value plus "
     "an error."),
    ("ε", "epsilon",
     "THE ERROR in that signal. Assumed bell-curve shaped, centred on "
     "zero, with spread k×σ."),
    ("f, F, G", "",
     "THE SHAPE OF A BELIEF. f is how likely each value is; F is how "
     "much of the range sits below a point; G is the running average "
     "contribution up to that point. Bookkeeping for the integral."),
    ("∫", "integral",
     "ADD UP CONTINUOUSLY. The same idea as Σ, but across a smooth range "
     "rather than a list of items."),
]

SYMS = {s[0]: s for s in SYMBOLS}


def legend_lines(keys, d, w=62):
    """Plain-English definitions for just the symbols a formula uses."""
    n = len(d["uncertainties"])
    ex = ", ".join(u["id"] for u in d["uncertainties"][:2])
    opts = ", ".join(o["name"] for o in d["options"])
    unit = d.get("unit", "units")
    out = []
    for kk in keys:
        if kk not in SYMS:
            continue
        sym, spoken, desc = SYMS[kk]
        desc = desc.format(n=n, ex=ex, opts=opts, unit=unit)
        head = f"{sym}" + (f"  ({spoken})" if spoken else "")
        out.append(head)
        for line in wrap(desc, w):
            out.append("     " + line)
    return out



# --------------------------------------------------------- how rough? ---
# A provenance count is not enough. A model can be 90% measured and still
# hang entirely on its one guessed input, because the thing carrying the
# answer is rarely the thing taking up the most room. So provenance is
# weighted by INFLUENCE -- how much each input actually moves the result --
# and the grade is that weighted average.

PROV_SCORE = {"measured": 1.0, "estimated": 0.45, "guessed": 0.0}

GRADES = [
    (0.75, "SOLID",
     "Most of what decides this was measured by somebody. Treat the number "
     "as a real estimate rather than an opinion with decimals."),
    (0.50, "REASONABLE",
     "Anchored on real cases, but the parts doing the most work are "
     "judgements about how those cases transfer. The direction is more "
     "trustworthy than the magnitude."),
    (0.25, "ROUGH",
     "Mostly judgement. The structure of the answer -- what matters, what "
     "cannot matter, where it flips -- is worth more than the number."),
    (0.00, "MOSTLY GUESSWORK",
     "Almost nothing here was measured. This is arithmetic performed on "
     "somebody's opinions, and its value is that it makes those opinions "
     "explicit and checkable, not that the number is right."),
]


def grade_from(weights):
    """weights: [(influence, provenance, label), ...]"""
    tot = sum(w for w, _, _ in weights) or 1.0
    score = sum(w * PROV_SCORE.get(p, 0.0) for w, p, _ in weights) / tot
    shares = {}
    for kind in ("measured", "estimated", "guessed"):
        shares[kind] = sum(w for w, p, _ in weights if p == kind) / tot
    for cut, name, gloss in GRADES:
        if score >= cut:
            return score, name, gloss, shares
    return score, "MOSTLY GUESSWORK", GRADES[-1][2], shares


def print_grade(weights, wrapper):
    score, name, gloss, shares = grade_from(weights)
    heaviest = max(weights, key=lambda t: t[0]) if weights else None
    print("=" * 74)
    print(f"  HOW ROUGH IS THIS?   {name}")
    print("=" * 74)
    print()
    print("  {:>5.0%} of what drives this answer was MEASURED".format(
        shares["measured"]))
    print("  {:>5.0%} was ESTIMATED from real cases".format(
        shares["estimated"]))
    print("  {:>5.0%} was GUESSED with nothing behind it".format(
        shares["guessed"]))
    print()
    for line in wrapper(gloss):
        print("  " + line)
    if heaviest:
        print()
        for line in wrapper(
                "The single input carrying the most weight here is "
                f"'{heaviest[2]}', and it is {heaviest[1]}. If that one is "
                f"wrong, so is the answer, whatever the rest of the model "
                f"is made of."):
            print("  " + line)
    print()


def resolve_measured(d):
    """MEASUREMENT INSTEAD OF ELICITATION.

    A belief may carry `from_trial` instead of low/high/mode. Its range is
    then computed from an actual randomised n-of-1 result -- the estimate
    becomes the mode, the confidence interval becomes the bounds, the
    standard error becomes the signal noise, and provenance becomes
    "measured" rather than somebody's guess.

    This is the only path in the project by which a number arrives without
    anyone arguing it into existence. Everything else in every model is an
    elicited judgement, and the reports say so.

    A trial whose outcome was NOT blind to its assignment is marked
    "estimated" rather than "measured", and its range is widened by the
    measurement bias the design permits. An unblinded measurement is not a
    weaker measurement; it is an upper bound wearing a measurement's
    clothes, and it does not get the promotion.
    """
    import trial as TR
    for u in d.get("uncertainties", []):
        ft = u.get("from_trial")
        if not ft:
            continue
        r = TR.analyse(ft["rows"], ft.get("blinded"))
        if "estimate" not in r:
            raise ValueError(f"{u['id']}: trial has too little data")
        est, lo, hi = r["estimate"], r["ci_low"], r["ci_high"]
        if ft.get("blinded") is True:
            u["provenance"] = "measured"
        else:
            u["provenance"] = "estimated"
            # widen by the bias an unblinded design permits, which is about
            # the size of the smallest effect the trial could have detected
            pad = r["mde_at_this_n"]
            lo, hi = lo - pad, hi + pad
        u["low"], u["high"], u["mode"] = lo, hi, est
        u.setdefault("history", {})["signal_sd"] = r["std_error"]
        u["_from_trial"] = {
            "n_A": r["n_A"], "n_B": r["n_B"], "blinded": ft.get("blinded"),
            "estimate": est, "ci": [r["ci_low"], r["ci_high"]],
            "mde": r["mde_at_this_n"]}
    return d


def load(name):
    p = os.path.join(DECISIONS, name if name.endswith(".json") else name + ".json")
    with open(p, encoding="utf-8") as f:
        return resolve_measured(json.load(f))


# ------------------------------------------------------------- sampling ---

def draw(u, rng):
    """Triangular if a mode is given, uniform otherwise. Triangular is the
    honest default when someone says 'between X and Y, probably around Z'."""
    lo, hi = u["low"], u["high"]
    if lo == hi:
        return lo
    m = u.get("mode")
    if m is None:
        return rng.uniform(lo, hi)
    return rng.triangular(lo, hi, m)


def prior_mean(u):
    lo, hi, m = u["low"], u["high"], u.get("mode")
    return (lo + hi + m) / 3.0 if m is not None else (lo + hi) / 2.0


def prior_sd(u):
    lo, hi, m = u["low"], u["high"], u.get("mode")
    if lo == hi:
        return 0.0
    if m is None:
        return (hi - lo) / math.sqrt(12.0)
    v = (lo * lo + hi * hi + m * m - lo * hi - lo * m - hi * m) / 18.0
    return math.sqrt(max(0.0, v))


def payoff(option, theta):
    v = option.get("constant", 0.0)
    for k, coef in option.get("terms", {}).items():
        v += coef * theta[k]
    return v


# ------------------------------------------------------------ the maths ---

def signal_noise(u):
    """tau for a belief: the absolute SD of the historical signal's error,
    in the belief's own units. Returns (tau, how_it_was_obtained) or
    (None, None) when no reference class exists.

    Precedence: an explicit signal_sd, then a Vivalt-style relative ratio
    against a STATED effect magnitude, then the legacy ratio-to-sigma with
    its normalisation repaired.
    """
    h = u.get("history")
    if not h:
        return None, None
    if h.get("signal_sd") is not None:
        return float(h["signal_sd"]), "stated absolutely"
    ratio = h.get("vivalt_ratio")
    mag = h.get("effect_magnitude")
    if ratio is not None:
        if mag is None:
            mag = abs(prior_mean(u))       # the belief's own scale
            how = "vivalt ratio x |mean|, magnitude not stated"
        else:
            how = "vivalt ratio x stated magnitude"
        return float(ratio) / MEDIAN_ABS_TO_SD * float(mag), how
    # legacy: transfer_error was written as tau/sigma but CALIBRATED as a
    # relative-error ratio. Honour the calibration, repair the denominator.
    te = h.get("transfer_error", DEFAULT_TRANSFER_ERROR)
    return (float(te) / MEDIAN_ABS_TO_SD * abs(prior_mean(u)),
            "legacy transfer_error, renormalised")


def derived_k(u):
    """tau/sigma, computed rather than assumed. None if no reference class."""
    tau, how = signal_noise(u)
    if tau is None:
        return None, None, None
    sg = prior_sd(u)
    return (tau, (tau / sg if sg > 0 else float("inf")), how)


def bias_sd(d):
    return d.get("elicitor_bias", {}).get("sd", DEFAULT_ELICITOR_BIAS)


def bias_dirs(d):
    """Which way the shared author-tilt pushes each belief.

    A bias that lifts EVERY number does nothing to a comparison -- it
    cancels. That is not the failure mode anyway. The real one is
    direction-aligned: someone who already believes the answer sets every
    COST a little high and every BENEFIT a little low, in one sitting,
    without noticing. So the shared shift follows whether a belief is a
    cost or a benefit, and the terms reinforce instead of cancelling.

    ORDER INDEPENDENCE. An earlier version read the sign off options[0],
    which made the whole model depend on the order the options happened to
    be listed in -- and if the first option was a do-nothing baseline with
    no terms at all, every direction defaulted to +1, the shared shift
    degenerated into a level shift, and it cancelled. Same file, same
    numbers, different confidence.

    The sign now comes from the sum of a belief's coefficients across ALL
    options, which cannot depend on their order. A belief that enters
    every option identically sums to something that still has a sign; a
    belief that enters perfectly symmetrically sums to zero and drops out
    of the common factor, which is correct -- it cannot carry a shared
    tilt if it pushes both ways equally. An explicit "direction" field on
    a belief overrides the inference, because this is a modelling choice
    and deserves to be stated rather than guessed.
    """
    out = {}
    for u in d["uncertainties"]:
        explicit = u.get("direction")
        if explicit in ("cost", "benefit"):
            out[u["id"]] = -1.0 if explicit == "cost" else 1.0
            continue
        tot = sum(o.get("terms", {}).get(u["id"], 0.0) for o in d["options"])
        out[u["id"]] = 0.0 if tot == 0 else (-1.0 if tot < 0 else 1.0)
    return out


def simulate(d, fixed=None, n=N_DRAWS, seed=SEED, bias=None):
    rng = random.Random(seed)
    us = d["uncertainties"]
    bsd = bias_sd(d) if bias is None else bias
    sds = {u["id"]: prior_sd(u) for u in us}
    dirs = bias_dirs(d)
    evs = {o["name"]: [] for o in d["options"]}
    for _ in range(n):
        b = rng.gauss(0.0, bsd) if bsd else 0.0   # ONE shared shift per world
        theta = {}
        for u in us:
            theta[u["id"]] = (fixed[u["id"]] if fixed and u["id"] in fixed
                              else draw(u, rng)
                              + sds[u["id"]] * b * dirs[u["id"]])
        for o in d["options"]:
            evs[o["name"]].append(payoff(o, theta))
    return evs


def mean(xs):
    return sum(xs) / len(xs)


def pct(xs, p):
    s = sorted(xs)
    return s[max(0, min(len(s) - 1, int(p * (len(s) - 1))))]


def means(d):
    return {u["id"]: prior_mean(u) for u in d["uncertainties"]}


def baseline(d, mus=None):
    """max_a E[EV(a)] -- exact, because the payoff is linear."""
    mus = mus or means(d)
    return max(payoff(o, mus) for o in d["options"])


def breakdown(d, uid):
    """Bisect on one belief to find where the winning option changes.
    Everything else held at its prior mean. Exact under linearity."""
    us = {u["id"]: u for u in d["uncertainties"]}
    u = us[uid]
    base = means(d)

    def winner_at(x):
        th = dict(base)
        th[uid] = x
        return max(d["options"], key=lambda o: payoff(o, th))["name"]

    lo_w, hi_w = winner_at(u["low"]), winner_at(u["high"])
    if lo_w == hi_w:
        return None, lo_w
    lo, hi = u["low"], u["high"]
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if winner_at(mid) == lo_w:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0, (lo_w, hi_w)


def _lines(d, uid, mus, conditional=True):
    """Each option, as a straight line in the one belief being learned.

    CONDITIONAL ON THE SHARED FACTOR. An earlier version held every other
    belief at its MARGINAL mean while varying this one. That is only valid
    under independence -- and the same file introduces a shared author
    factor that makes the beliefs dependent, so the two halves of the
    method contradicted each other.

    The repair is exact here. Write

        theta_i = base_i + sigma_i * b * dir_i,     b ~ N(0, B^2)

    Observing theta_k = x is a noisy observation of b:

        E[b | x] = dir_k * B^2 * (x - mu_k) / (sigma_k * (1 + B^2))
        E[theta_j | x] = mu_j + sigma_j * dir_j * E[b | x]

    which is LINEAR in x, so every option is still a straight line and the
    closed-form envelope integral survives. Learning one belief now moves
    the others, as it must.
    """
    us = {u["id"]: u for u in d["uncertainties"]}
    dirs = bias_dirs(d)
    B = bias_sd(d)
    sk = prior_sd(us[uid])
    c = 0.0
    if conditional and B > 0 and sk > 0:
        c = dirs[uid] * B * B / (sk * (1.0 + B * B))

    out = []
    for o in d["options"]:
        terms = o.get("terms", {})
        slope = terms.get(uid, 0.0)
        th = dict(mus)
        th[uid] = 0.0
        inter = payoff(o, th)
        if c:
            # every other belief drifts with x through the shared factor
            drift = sum(terms.get(j, 0.0) * prior_sd(us[j]) * dirs[j]
                        for j in us if j != uid)
            slope += c * drift
            inter -= c * mus[uid] * drift
        out.append((inter, slope, o["name"]))
    return out


def _segments(lines, lo, hi):
    """Upper envelope of a set of lines on [lo, hi], as (p, q, c, k) pieces.
    max_a EV(a|x) is the upper envelope, and it is piecewise linear and
    convex. Break it at the pairwise intersections and it integrates
    exactly."""
    xs = {lo, hi}
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            c1, k1, _ = lines[i]
            c2, k2, _ = lines[j]
            if abs(k1 - k2) > 1e-12:
                x = (c2 - c1) / (k1 - k2)
                if lo < x < hi:
                    xs.add(x)
    xs = sorted(xs)
    segs = []
    for p, q in zip(xs, xs[1:]):
        mid = (p + q) / 2.0
        c, k, _ = max(lines, key=lambda L: L[0] + L[1] * mid)
        segs.append((p, q, c, k))
    return segs


def _cdf_moment(u, x):
    """(F(x), integral of t*f(t) from low to x) for the prior. Closed form
    for both the uniform and the triangular case."""
    a, b = float(u["low"]), float(u["high"])
    c = u.get("mode")
    if b <= a:
        return (1.0, a) if x >= a else (0.0, 0.0)
    x = min(max(x, a), b)
    if c is None:
        return (x - a) / (b - a), (x * x - a * a) / (2.0 * (b - a))
    c = float(c)
    if x <= c:
        s = 2.0 / ((b - a) * (c - a)) if c > a else 0.0
        F = (x - a) ** 2 / ((b - a) * (c - a)) if c > a else 0.0
        G = s * ((x ** 3 - a ** 3) / 3.0 - a * (x * x - a * a) / 2.0)
        return F, G
    # mass and moment of the whole left triangle, then the right piece
    if c > a:
        sL = 2.0 / ((b - a) * (c - a))
        FL = (c - a) / (b - a)
        GL = sL * ((c ** 3 - a ** 3) / 3.0 - a * (c * c - a * a) / 2.0)
    else:
        FL, GL = 0.0, 0.0
    if b > c:
        sR = 2.0 / ((b - a) * (b - c))
        F = 1.0 - (b - x) ** 2 / ((b - a) * (b - c))
        G = GL + sR * (b * (x * x - c * c) / 2.0 - (x ** 3 - c ** 3) / 3.0)
    else:
        F, G = FL, GL
    return F, G


def flip_profile(d, winner, n=N_DRAWS, seed=SEED):
    """In the draws where the OTHER option wins, which beliefs had moved,
    and by how far?

    EVPI varies one belief and freezes the rest, so it is structurally
    blind to an answer that only reverses when several things go the same
    way at once. This finds that coalition: for every draw where the
    verdict flips, average each belief, and report the shift from its
    overall average in units of its own spread.
    """
    rng = random.Random(seed)
    us = d["uncertainties"]
    acc = {u["id"]: [] for u in us}
    hits = 0
    for _ in range(n):
        th = {u["id"]: draw(u, rng) for u in us}
        if max(d["options"], key=lambda o: payoff(o, th))["name"] != winner:
            hits += 1
            for kk, v in th.items():
                acc[kk].append(v)
    if hits == 0:
        return 0.0, []
    rows = []
    for u in us:
        m, s = prior_mean(u), prior_sd(u)
        cm = mean(acc[u["id"]]) if acc[u["id"]] else m
        rows.append((abs(cm - m) / s if s else 0.0, u["id"], m, cm, s))
    rows.sort(reverse=True)
    return hits / float(n), rows


def certainty_equivalent(xs, R):
    """Exponential utility, u(x) = -exp(-x/R), and its certainty equivalent

        CE = -R * ln( E[ exp(-x/R) ] )

    R is risk tolerance in the payoff's own units: roughly the stake at
    which you would decline a 50/50 bet to win R and lose R/2. Smaller R is
    more risk-averse. As R goes to infinity CE converges on the plain mean,
    which is why expected value is the risk-neutral special case rather
    than the neutral default it looks like.

    Standard (Howard's risk tolerance). Without it every verdict quietly
    assumes risk neutrality on decisions that are taken once and cannot be
    unwound.
    """
    if not R or R <= 0:
        return None
    m = max(xs)
    tot = sum(math.exp(-(x - m) / R) for x in xs) / len(xs)
    return -R * (math.log(tot) - m / R)


def evppi_subset(d, ids, n=6000):
    """EVPPI over a GROUP of beliefs learned together.

    EVPI resolves one belief at a time and is therefore blind by
    construction to answers that only reverse when several move together.
    Standard in health technology assessment (Strong & Oakley).
    """
    mus = means(d)
    base = baseline(d, mus)
    rng = random.Random(SEED + 31)
    byid = {u["id"]: u for u in d["uncertainties"]}
    tot = 0.0
    for _ in range(n):
        th = dict(mus)
        for i in ids:
            th[i] = draw(byid[i], rng)
        tot += max(payoff(o, th) for o in d["options"])
    return max(0.0, tot / n - base)


def phi(z):
    """Standard normal CDF. Used only for closed-form CHECKS on the Monte
    Carlo, never as the primary estimate."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def ev_analytic(d):
    """E[EV(a)] and sd(EV(a)) in closed form.

        E[EV(a)]   = c_a + SUM_i B(a,i) * E[O_i]
        Var[EV(a)] = SUM_i B(a,i)^2 * Var[O_i]        [O_i independent]

    The variance identity needs the beliefs to be independent, which is an
    assumption the file cannot check and the reader should.
    """
    mus = means(d)
    out = {}
    for o in d["options"]:
        m = payoff(o, mus)
        v = 0.0
        for u in d["uncertainties"]:
            b = o.get("terms", {}).get(u["id"], 0.0)
            v += b * b * prior_sd(u) ** 2
        out[o["name"]] = (m, math.sqrt(v))
    return out


def pair_margin(d, na, nb):
    """The difference of two options is itself linear:

        D = EV(a) - EV(b) = SUM_i [B(a,i) - B(b,i)] * O_i

    so E[D] and Var[D] are closed form, and P(a beats b) has a CLT
    approximation that can be checked against the simulation. Divergence
    between the two is a signal that the sum is too skewed for the normal
    approximation -- worth knowing, not worth hiding.
    """
    a = next(x for x in d["options"] if x["name"] == na)
    b = next(x for x in d["options"] if x["name"] == nb)
    mus = means(d)
    parts, ed, vd = [], 0.0, 0.0
    for u in d["uncertainties"]:
        db = (a.get("terms", {}).get(u["id"], 0.0)
              - b.get("terms", {}).get(u["id"], 0.0))
        if db == 0:
            continue
        s = prior_sd(u)
        parts.append((u["id"], db, mus[u["id"]], s))
        ed += db * mus[u["id"]]
        vd += db * db * s * s
    naive = math.sqrt(vd)
    # the common-factor term: grows like n^2, so it eventually dominates
    dirs = bias_dirs(d)
    co = sum(db * s * dirs[nm] for nm, db, _, s in parts)
    bsd = bias_sd(d)
    sd = math.sqrt(vd + (bsd * co) ** 2)
    f = lambda x: (phi(ed / x) if x > 0 else (1.0 if ed > 0 else 0.0))
    return parts, ed, sd, f(sd), naive, f(naive), bsd


def flip_algebra(d, uid, na, nb):
    """Closed form for the breakdown value, instead of only bisecting.

        EV_a(x) = EV_b(x)
        x* = [ (c_b - c_a) + SUM_{i!=k} (B(b,i) - B(a,i)) * mu_i ]
             / [ B(a,k) - B(b,k) ]
    """
    mus = means(d)
    a = next(x for x in d["options"] if x["name"] == na)
    b = next(x for x in d["options"] if x["name"] == nb)
    ka = a.get("terms", {}).get(uid, 0.0)
    kb = b.get("terms", {}).get(uid, 0.0)
    if abs(ka - kb) < 1e-12:
        return None
    th = dict(mus)
    th[uid] = 0.0
    ia, ib = payoff(a, th), payoff(b, th)     # intercepts at x = 0
    return (ib - ia) / (ka - kb), ia, ib, ka, kb


def evpi_detail(d, uid):
    """EVPI plus the working: the envelope pieces and their numeric
    contributions, so the integral can be read rather than trusted."""
    mus = means(d)
    u = {x["id"]: x for x in d["uncertainties"]}[uid]
    lo, hi = float(u["low"]), float(u["high"])
    base = baseline(d, mus)
    if hi <= lo:
        return 0.0, [], base
    lines = _lines(d, uid, mus)
    rows, total = [], 0.0
    for p, q, c, k in _segments(lines, lo, hi):
        Fp, Gp = _cdf_moment(u, p)
        Fq, Gq = _cdf_moment(u, q)
        who = max(lines, key=lambda L: L[0] + L[1] * ((p + q) / 2.0))[2]
        piece = c * (Fq - Fp) + k * (Gq - Gp)
        rows.append((p, q, who, c, k, Fq - Fp, Gq - Gp, piece))
        total += piece
    return max(0.0, total - base), rows, base


def evpi(d, uid):
    """EXACT, not simulated.

    EVPI(t) = E_t[ max_a EV(a|t) ] - max_a E_t[ EV(a) ]

    The first term is the integral of a piecewise-linear convex envelope
    against the prior density. Both have closed forms, so this returns a
    number with no Monte Carlo error at all.

    That matters more than it sounds. The simulated version rectified its
    own sampling noise -- max(0, estimate) turns symmetric noise around a
    true zero into a positive number, and the tool then reported worthless
    research as valuable. Exactness is the fix, not more draws.
    """
    mus = means(d)
    u = {x["id"]: x for x in d["uncertainties"]}[uid]
    lines = _lines(d, uid, mus)
    lo, hi = float(u["low"]), float(u["high"])
    if hi <= lo:
        return 0.0
    total = 0.0
    for p, q, c, k in _segments(lines, lo, hi):
        Fp, Gp = _cdf_moment(u, p)
        Fq, Gq = _cdf_moment(u, q)
        total += c * (Fq - Fp) + k * (Gq - Gp)
    return max(0.0, total - baseline(d, mus))


def evsi(d, uid, n=4000, particles=300):
    """Expected value of a NOISY historic signal about one belief.

    Particle-filter posterior: the prior is triangular, so there is no
    conjugate update. Draw particles from the prior, weight each by the
    Gaussian likelihood of the observed signal, take the weighted mean.
    Under a linear payoff the posterior mean is a sufficient statistic, so
    that is all that is needed.

    Returns (evsi, k). A belief with no `history` block returns (0.0, None):
    there is no signal to receive.
    """
    u = {x["id"]: x for x in d["uncertainties"]}[uid]
    hist = u.get("history")
    if not hist:
        return 0.0, None, None

    sigma_sig, k, _how = derived_k(u)
    sd = prior_sd(u)
    # Shrinkage. Under a Gaussian prior and a Gaussian signal,
    #     s = O + e,  e ~ N(0, k*sigma)
    #     E[O|s] = mu + L*(s - mu),   L = sigma^2 / (sigma^2 + k^2 sigma^2)
    #                                   = 1 / (1 + k^2)
    # L is how far history moves you toward what it says. At Vivalt's
    # median k = 0.95 that is 0.53 -- history gets you barely half way.
    lam = 1.0 / (1.0 + k * k) if k not in (None, float("inf")) else 0.0
    if sd <= 0:
        return 0.0, k, lam
    sigma = max(1e-9, sigma_sig)
    return _evsi_core(d, u, sigma, n, particles), k, lam


def _evsi_core(d, u, sigma, n=4000, particles=300, record=True):
    """The expected value of ONE noisy signal s = t + e, e ~ N(0, sigma),
    about belief u, received before choosing. Shared by the historic
    signal above and by a proposed test (`test_value`), which differ only
    in where sigma comes from: transfer error for history, the test's own
    standard error for a test. `record` keeps test calls out of the
    CLAMPED list, which belongs to the decision report -- the MCP server
    is one long-lived process, and a stray entry would surface in the next
    unrelated report."""
    uid = u["id"]
    mus = means(d)
    rng = random.Random(SEED + 11)
    lines = _lines(d, uid, mus)

    # The option that is best WITHOUT any signal. Its line is the control
    # variate: E[c* + k* m(S)] = c* + k* E[theta] = the baseline, exactly,
    # because the posterior mean is unbiased for the prior mean. So every
    # sampled term below is the non-negative gap between the envelope and
    # that line, and the estimator cannot rectify noise into fake value.
    cs, ks, _ = max(lines, key=lambda L: L[0] + L[1] * prior_mean(u))

    # Recentre the particle cloud on the analytic prior mean, so a finite
    # particle set cannot bias the posterior toward changing the argmax.
    parts = [draw(u, rng) for _ in range(particles)]
    shift = prior_mean(u) - (sum(parts) / len(parts))
    parts = [p + shift for p in parts]
    two_s2 = 2.0 * sigma * sigma

    tot = 0.0
    for _ in range(n):
        s = rng.gauss(draw(u, rng), sigma)
        wsum = 0.0
        xsum = 0.0
        for p in parts:
            dd = s - p
            w = math.exp(-(dd * dd) / two_s2)
            wsum += w
            xsum += w * p
        post = xsum / wsum if wsum > 0 else prior_mean(u)
        env = max(c + kk * post for c, kk, _ in lines)
        tot += env - (cs + ks * post)
    got = max(0.0, tot / n)

    # EVSI <= EVPI is a theorem (a noisy signal cannot beat knowing the
    # answer). If the estimate breaches it, that is residual Monte Carlo
    # error, not a discovery. Clamp, and never report the impossible.
    cap = evpi(d, uid)
    # Recentring particles does not prove the
    # estimator is unbiased AFTER the maximisation -- max is non-linear, so
    # E[max] need not inherit unbiasedness from E[posterior mean]. The clamp
    # therefore stays, but it is now REPORTED when it binds rather than
    # silently absorbing whatever the estimator got wrong.
    if record and got > cap * 1.02 and cap > 1e-9:
        CLAMPED.append((uid, got, cap))
    return min(got, cap)


# ------------------------------------------ is a test worth running? ---
# History is one signal. A test you have not run yet is another, and it
# is priced by exactly the same maths: the only thing that changes is
# where the noise comes from. For a two-arm n-of-1 test of `days` days,
# half on each arm, the estimate of the effect has standard error
#
#     SE = sigma x sqrt( 2 / (days/2) )       sigma = the outcome's daily SD
#
# which is the same SE trial.py's `mde` uses. An instrument that can see
# the arm adds a bias that more days cannot shrink, so it enters as a
# floor under the noise:
#
#     noise = sqrt( SE^2 + bias^2 )
#
# The value of the test is the EVSI of that signal, and what matters is
# the value NET of what the test costs:
#
#     net(days) = EVSI(days) - fixed_cost - cost_per_day x days
#
# Two things fall out that no power calculation shows. A belief that
# cannot change the choice has EVPI = 0, so no test of it is worth
# anything to THIS decision, however interesting the question. And the
# value climbs toward EVPI with diminishing returns while the cost climbs
# in a straight line, so past some length every extra day loses money.
# voiage (Apache-2.0, github.com/edithatogo/voiage) calls the net figure
# ENBS, the expected net benefit of sampling; this is the same idea for
# one belief, a linear payoff, and a test run on yourself.

DEFAULT_TEST_DAYS = (14, 28, 56, 112, 224)

# UNITS, because this is where a value-of-information number goes wrong.
# If the decision is scored as a RATE ("units per day"), then EVSI is
# a rate too: choosing better pays off on every future period the choice
# applies to. A test's cost is a TOTAL -- so many days spent partly on the
# worse option. The two only compare once the rate is multiplied by a
# HORIZON: how many periods the choice will actually last. Left out, the
# comparison sets one day's gain against a whole test's cost and says no
# test is ever worth running.


PERIOD_DAYS = {"day": 1.0, "week": 7.0, "month": 30.44, "year": 365.25}


def rate_period(unit):
    """The period a rate unit is 'per', in days, or None for a total."""
    m = re.search(r"\b(?:per|a|each)\s+(day|week|month|year)\b|/\s*"
                  r"(day|week|month|year)\b", unit or "", re.I)
    return PERIOD_DAYS[(m.group(1) or m.group(2)).lower()] if m else None


def periods_after(d, days, horizon_days):
    """How many of the decision's periods the choice runs for AFTER the
    test ends. Information only pays once it has arrived, so a long test
    inside a short horizon leaves little time to use what it found. For a
    unit that is already a total, this is 1."""
    per = rate_period(d.get("unit", ""))
    if per is None or not horizon_days:
        return 1.0
    return max(0.0, float(horizon_days) - int(days)) / per


def gap_top_two(d):
    """EV(best) - EV(second) at the current means, and their names."""
    mus = means(d)
    evs = sorted(((payoff(o, mus), o["name"]) for o in d["options"]),
                 reverse=True)
    if len(evs) < 2:
        return 0.0, evs[0][1] if evs else None, None
    return evs[0][0] - evs[1][0], evs[0][1], evs[1][1]


def default_cost_per_day(d):
    """A two-arm test spends half its days on the option you would
    otherwise not pick. Half the current gap is that price per test day."""
    return 0.5 * gap_top_two(d)[0]


def test_value(d, uid, outcome_sd, days, cost_per_day=None, fixed_cost=0.0,
               unblind_bias=0.0, horizon_days=None, n=2000, particles=300):
    """Value, cost and net value of a proposed two-arm test of one belief.
    Value is EVSI x the periods left after the test; cost is fixed +
    per-day x days; both in the decision's unit, as totals."""
    u = {x["id"]: x for x in d["uncertainties"]}[uid]
    per_arm = int(days) // 2
    if per_arm < 1:
        raise ValueError("a two-arm test needs at least 2 days")
    if cost_per_day is None:
        cost_per_day = default_cost_per_day(d)
    se = float(outcome_sd) * math.sqrt(2.0 / per_arm)
    noise = math.sqrt(se * se + float(unblind_bias or 0.0) ** 2)
    rate = (_evsi_core(d, u, max(1e-9, noise), n, particles, record=False)
            if prior_sd(u) > 0 else 0.0)
    H = periods_after(d, days, horizon_days)
    value = rate * H
    cost = float(fixed_cost) + float(cost_per_day) * int(days)
    return {"days": int(days), "se": se, "noise": noise, "evsi": rate,
            "periods_after": H, "value": value, "cost": cost,
            "net": value - cost}


def test_value_report(d, uid, outcome_sd, days=None, cost_per_day=None,
                      fixed_cost=0.0, unblind_bias=0.0, horizon_days=None):
    """Print whether a proposed test of one belief is worth running, and
    return the rows."""
    us = {x["id"]: x for x in d["uncertainties"]}
    if uid not in us:
        raise ValueError(f"no belief '{uid}' in this decision; it has: "
                         + ", ".join(us))
    u = us[uid]
    unit = d.get("unit", "units")
    per = rate_period(unit)
    rate = per is not None
    horizon = horizon_days
    total_unit = (f"{unit}, summed over the days after the test"
                  if rate and horizon else unit)
    days_list = ([int(days)] if isinstance(days, (int, float))
                 else [int(x) for x in (days or DEFAULT_TEST_DAYS)])
    gap, top, second = gap_top_two(d)
    cpd_default = cost_per_day is None
    cpd = default_cost_per_day(d) if cpd_default else float(cost_per_day)
    cap = evpi(d, uid)

    print("=" * 74)
    print("  IS THIS TEST WORTH RUNNING?")
    print("=" * 74)
    print()
    para(f"Decision: {d.get('decision', '(unnamed)')} Without testing, "
         f"'{top}' wins at the current beliefs"
         + (f", ahead of '{second}' by {gap:.4g} {unit}" if second else "")
         + f". The test would measure '{uid}', now held between {u['low']} "
         f"and {u['high']}"
         + (f" (most likely {u['mode']})" if u.get("mode") is not None
            else "")
         + f", with a daily outcome SD of {outcome_sd}.")
    print()
    if rate and not horizon:
        para(f"WARNING: THE HORIZON IS MISSING. This decision is scored as a "
             f"rate ({unit}), so better information pays off on every "
             f"period the choice lasts. Pass `horizon`, the number of those "
             f"periods the choice will apply for. Without it the table "
             f"below credits the test with ONE period's gain against its "
             f"whole cost, which undervalues every test.")
        print()
    para(f"THE CEILING. Even a perfect answer about '{uid}' is worth "
         f"{cap:.4g} {unit}"
         + (f", or {cap * float(horizon) / per:.4g} if it were known today "
            f"and used for all {float(horizon):g} days" if rate and horizon
            else "")
         + f" (its EVPI). No test of it can be worth more.")
    print()
    if cap <= 1e-12:
        para("SO DON'T RUN IT FOR THIS DECISION. Nothing a test could find "
             f"inside the stated range of '{uid}' would change the choice. "
             f"It may still be worth knowing for its own sake, but it buys "
             f"nothing here.")
        print()
        return []
    para(f"THE COST PER TEST DAY is {cpd:.4g} {unit}"
         + (" -- by default, half the gap between the top two options, "
            "because a two-arm test spends half its days on the one you "
            "would otherwise not pick" if cpd_default else "")
         + (f", plus a fixed cost of {float(fixed_cost):.4g}"
            if fixed_cost else "") + ".")
    print()
    rows = [test_value(d, uid, outcome_sd, n_days, cpd, fixed_cost,
                       unblind_bias, horizon) for n_days in days_list]
    head = "  {:>6}{:>12}{:>14}{:>12}{:>14}"
    print(head.format("days", "noise", "worth", "costs", "net"))
    print("  " + "-" * 58)
    for r in rows:
        print(head.format(r["days"], f"{r['noise']:.3g}", f"{r['value']:.4g}",
                          f"{r['cost']:.4g}", f"{r['net']:+.4g}"))
    print()
    best = max(rows, key=lambda r: r["net"])
    if best["net"] <= 0:
        para(f"NO LENGTH PAYS FOR ITSELF. The most any of these is worth is "
             f"{max(r['value'] for r in rows):.4g} ({total_unit}), and each "
             f"costs more than it is worth. Decide on what you know now.")
    else:
        para(f"WORTH RUNNING: {best['days']} days is the best of these, "
             f"worth {best['value']:.4g} and costing {best['cost']:.4g}, "
             f"so a net gain of {best['net']:.4g} ({total_unit}). It "
             f"captures {best['evsi'] / cap:.0%} of the ceiling.")
    if unblind_bias:
        print()
        para(f"The instrument can see the arm, adding a fixed error of about "
             f"{unblind_bias} that more days cannot shrink. The value levels "
             f"off below the ceiling however long the test runs; blinding "
             f"the measurement raises that ceiling and extra days do not.")
    print()
    r, b = best, float(unblind_bias or 0.0)
    maths("THE MATHS, for the " + str(r["days"]) + "-day row",
          ["SE = σ × √(2 ÷ (n ÷ 2))",
           f"   = {outcome_sd} × √(2 ÷ {r['days'] // 2}) = {r['se']:.4g}"],
          ["noise = √(SE² + b²)",
           f"      = √({r['se']:.4g}² + {b:.4g}²) = {r['noise']:.4g}"],
          ["worth(n) = EVSI(n) × H,   H = (T − n) ÷ p",
           f"         = {r['evsi']:.4g} × {r['periods_after']:.4g} "
           f"= {r['value']:.4g}"],
          ["net(n) = worth(n) − c₀ − c × n",
           f"       = {r['value']:.4g} − {float(fixed_cost):.4g} − "
           f"{cpd:.4g} × {r['days']} = {r['net']:+.4g}"])
    print("      WHAT THE SYMBOLS MEAN")
    for sym, meaning in [
            ("n", "the number of days, split evenly between the two arms"),
            ("σ", "the daily outcome's standard deviation, " + str(outcome_sd)),
            ("SE", "the standard error of the effect the test measures"),
            ("b", "bias from an instrument that can see which arm the day "
                  "was in (0 if blinded)"),
            ("EVSI(n)", "the expected value of seeing that noisy result "
                        "before choosing, never above the ceiling, in " + unit),
            ("H", "how many of the decision's periods are left after the "
                  "test, the only time its answer can be used (1 if the "
                  "unit is already a total)"),
            ("T", "the horizon: days from now the choice will apply for"
                  + (f", {float(horizon):g}" if horizon else "")),
            ("p", "days in one period of the unit"
                  + (f", {per:g}" if per else "")),
            ("c₀, c", "the fixed cost, and the cost per test day"),
            ("√ ² ÷ × −", "square root, squared, divided by, times, minus")]:
        for i, line in enumerate(wrap(meaning, 50)):
            print("        " + (f"{sym:<12}" if i == 0 else " " * 12) + line)
    print()
    return rows


# --------------------------------------------------------------- report ---

def wrap(s, w=68):
    out, line = [], ""
    for word in s.split():
        if len(line) + len(word) + 1 > w:
            out.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        out.append(line)
    return out


def para(s, indent="    ", w=68):
    for line in wrap(s, w):
        print(indent + line)


def maths(title, *blocks, legend=None, d=None):
    """Print a derivation: the formula in standard notation, then the same
    formula with the numbers substituted in.

    This exists because a number with its working hidden is an assertion.
    Every result in this file shows its denominator.
    """
    print(f"    --- {title} " + "-" * max(0, 62 - len(title)))
    for b in blocks:
        if b is None:
            continue
        for line in (b if isinstance(b, (list, tuple)) else [b]):
            print("      " + line)
        print()
    if legend and d is not None:
        print("      WHAT THE SYMBOLS MEAN")
        for line in legend_lines(legend, d):
            print("        " + line)
        print()


def confidence_words(p):
    """Plain English for a probability, so nobody has to decide for
    themselves whether 68% is a lot."""
    if p < 0.55:
        return ("A COIN FLIP", "The model cannot tell you. Do not let a "
                "number this close talk you into anything -- it is saying "
                "the two options are worth about the same.")
    if p < 0.70:
        return ("A LEAN, NOT A DECISION", "Real but weak. Roughly one in "
                "three of your own possible worlds says the opposite. If "
                "something outside the model pulls the other way, follow it.")
    if p < 0.85:
        return ("A CLEAR ANSWER", "Most of your stated uncertainty points "
                "the same way. Not certainty, but enough to act on without "
                "further work.")
    if p < 0.95:
        return ("STRONG", "It would take several things being wrong at once "
                "to reverse this.")
    return ("NOT CLOSE", "Stop researching and act. If it still feels "
            "closer than this, something that decides it is missing from "
            "the model.")


def verdict(d, evs, names, wins, rows):
    """THE ANSWER, on its own, before any of the working."""
    top = rows[0]
    p = wins[top] / N_DRAWS
    band, gloss = confidence_words(p)

    print("=" * 74)
    print("  THE ANSWER")
    print("=" * 74)
    print()

    q = d.get("headline_question")
    yes = d.get("headline_yes_option")
    if q and yes in wins:
        py = wins[yes] / N_DRAWS
        print(f"     {q}")
        print()
        print(f"          {py:.0%}  YES" if py >= 0.5 else
              f"          {py:.0%}  yes   ({1-py:.0%} no)")
        print()
        b2, g2 = confidence_words(max(py, 1 - py))
        print(f"     {py:.0%} of {N_DRAWS:,} runs came out FOR it.")
        print(f"     {1-py:.0%} came out AGAINST it.")
        print()
        print(f"     Above 50% is yes. Below is no.")
        print(f"     This is {b2.lower()}.")
        print()
        for line in wrap(g2):
            print("     " + line)
        print()
        print("  " + "-" * 70)
        print()

    print("     DO THIS:   " + top)
    print()
    for n in rows:
        bar = "#" * int(round(wins[n] / N_DRAWS * 40))
        print(f"       {n:<26}{wins[n]/N_DRAWS:>5.0%}  {bar}")
    print()
    print(f"     HOW SURE:  {p:.0%} of runs picked {top},")
    print(f"                {1-p:.0%} picked something else.  -- {band}")
    print()
    for line in wrap(gloss):
        print("     " + line)
    print()
    if len(rows) > 1:
        gap = mean(evs[rows[0]]) - mean(evs[rows[1]])
        print(f"     By how much: {gap:,.1f} {d.get('unit','')}")
        print(f"     ...which only means something next to the spread of")
        print(f"     the options themselves: {pct(evs[rows[0]], .05):,.0f} to "
              f"{pct(evs[rows[0]], .95):,.0f}.")
        print()
    print("     Everything below this line is the working. You do not have")
    print("     to read it to act on the number above -- but the number")
    print("     above is only as good as the numbers it was built from,")
    print("     and those are listed first.")
    print()


def report(d):
    unit = d.get("unit", "")
    us = d["uncertainties"]
    mus = means(d)

    _evs = simulate(d)
    _names = [o["name"] for o in d["options"]]
    _wins = {n: 0 for n in _names}
    for _i in range(N_DRAWS):
        _wins[max(_names, key=lambda n: _evs[n][_i])] += 1
    _rows = sorted(_names, key=lambda n: -mean(_evs[n]))

    # influence = share of the top-two margin this belief actually moves
    if len(_rows) > 1:
        _parts, _ed, _sd, _p, _sn, _pn, _b = pair_margin(d, _rows[0], _rows[1])
        _by = {u["id"]: u for u in d["uncertainties"]}
        _w = [(abs(db * sg), _by[nm].get("provenance", "guessed"), nm)
              for nm, db, mu, sg in _parts]
    else:
        _w = [(abs(prior_sd(u)), u.get("provenance", "guessed"), u["id"])
              for u in d["uncertainties"]]
    print_grade(_w, lambda t: wrap(t, 70))

    verdict(d, _evs, _names, _wins, _rows)

    print("=" * 74)
    print("DECISION: " + d["decision"])
    print("=" * 74)
    print("  payoffs in: " + unit)
    print(f"  {len(d['options'])} options, {len(us)} beliefs, {N_DRAWS:,} draws")
    print()

    # ---- beliefs and where they came from -----------------------------
    print("  BELIEFS AND THEIR PROVENANCE")
    print("  " + "-" * 70)
    for u in us:
        prov = u.get("provenance", "guessed")
        rng_s = "[{:,.0f} .. {:,.0f}]".format(u["low"], u["high"])
        print(" {}{:<26}{:>19}  mean {:>7,.0f}".format(
            MARK.get(prov, "?"), u["id"], rng_s, prior_mean(u)))
        src = u.get("source")
        if src:
            para(src, indent="      ", w=66)
        h = u.get("history")
        if h:
            kk = h.get("transfer_error")
            if kk is None:
                kk, kwhere = DEFAULT_TRANSFER_ERROR, "DEFAULT, from Vivalt"
            else:
                kwhere = "set by hand for this belief -- a judgement"
            print("      the cases this range was built from:")
            for c in h.get("cases", []):
                print("        {:>9,.0f}  {}".format(
                    c.get("value", 0), c.get("name", "?")))
            print("      k = {:.2f}   ({})   ->   λ = {:.2f}".format(
                kk, kwhere, 1.0 / (1.0 + kk * kk)))
        else:
            print("      NO CASES. This range has no reference class behind")
            print("      it. It is a judgement written as a number.")
    print()
    print("   blank = measured    ~ = estimated    ? = guessed, nobody knows")
    print()
    para("WHERE THE NUMBERS COME FROM, stated plainly. The case values "
         "above are historical anchors recalled from training data, not "
         "fetched from a live source -- order-of-magnitude, not audited. "
         "The low/high/mode of each belief is then MY judgement about what "
         "those cases bound. And k is also my judgement, one belief at a "
         "time, except where it falls back to the default.")
    print()
    para("THAT DEFAULT, 0.95, is the one number here with a real source. "
         "Eva Vivalt assembled about 635 impact evaluations and asked a "
         "single question of them: if you know the measured effect at "
         "sites 1 to n-1, how well does that predict site n? The median "
         "absolute error came out at 93-99% of the size of the effect "
         "itself. In other words the typical study, carried somewhere "
         "else, is wrong by about as much as the whole thing it measured. "
         "That is where k = 0.95 comes from, and it is why λ = 0.53.")
    print()

    evs = simulate(d)
    names = [o["name"] for o in d["options"]]

    # ---- expected value ------------------------------------------------
    print("  EXPECTED VALUE")
    print("  " + "-" * 70)

    sub = []
    for u in us:
        if u.get("mode") is not None:
            sub.append("E[θ_{:<26}] = ({:,.0f} + {:,.0f} + {:,.0f})/3 = {:>9,.2f}"
                       .format(u["id"], u["low"], u["high"], u["mode"],
                               prior_mean(u)))
        else:
            sub.append("E[θ_{:<26}] = ({:,.0f} + {:,.0f})/2 = {:>9,.2f}"
                       .format(u["id"], u["low"], u["high"], prior_mean(u)))
    maths("THE FORMULA",
          ["EV(a) = c_a + Σ_i β_{a,i} · E[θ_i]",
           "",
           "E[θ] = (lo + hi + mode)/3     for a triangular belief",
           "E[θ] = (lo + hi)/2            for a uniform one",
           "",
           "Var[EV(a)] = Σ_i β²_{a,i} · Var[θ_i]     (θ independent)",
           "Var[θ] = (lo² + hi² + m² - lo·hi - lo·m - hi·m)/18"],
          ["SUBSTITUTED:"] + sub,
          legend=["θ", "θ_i", "Σ_i", "a, b", "β", "c_a", "EV(a)",
                  "E[...]", "Var[...]"], d=d)

    ana = ev_analytic(d)
    lines_eq = []
    for o in d["options"]:
        terms = [(k, cf) for k, cf in o.get("terms", {}).items()]
        s = "  +  ".join("({:+g})({:,.0f})".format(cf, mus[k])
                         for k, cf in terms)
        lines_eq.append(f"EV({o['name']})")
        for chunk in wrap("= " + s, 62):
            lines_eq.append("   " + chunk)
        lines_eq.append("   = {:,.2f}      sd = {:,.0f}".format(*ana[o["name"]]))
        lines_eq.append("")
    maths("EACH OPTION, SUBSTITUTED", lines_eq,
          legend=["EV(a)", "β", "σ"], d=d)

    print("  These are PROBABILITIES: the share of runs each option won.")
    print("  They sum to 100% across the options.")
    print()
    print(f"  {'option':<26}{'mean':>12}{'5th':>12}{'95th':>12}{'P(wins)':>10}")
    wins = {n: 0 for n in names}
    for i in range(N_DRAWS):
        wins[max(names, key=lambda n: evs[n][i])] += 1
    rows = sorted(names, key=lambda n: -mean(evs[n]))
    for n in rows:
        print(f"  {n:<26}{mean(evs[n]):>12,.0f}{pct(evs[n], .05):>12,.0f}"
              f"{pct(evs[n], .95):>12,.0f}{wins[n] / N_DRAWS:>9.0%}")
    print()

    lead = rows[0]
    R = d.get("risk_tolerance")
    if R:
        print("  RISK AVERSION  -- certainty equivalent at tolerance "
              f"{R:,.0f}")
        print("  " + "-" * 70)
        ces = {n: certainty_equivalent(evs[n], R) for n in names}
        for n in sorted(names, key=lambda x: -(ces[x] or -9e9)):
            print("  {:<26}{:>12,.0f}{:>14,.0f}".format(
                n, mean(evs[n]), ces[n]))
        ce_lead = max(names, key=lambda x: ces[x])
        print()
        if ce_lead != lead:
            para(f"RISK AVERSION CHANGES THE ANSWER. Expected value picks "
                 f"'{lead}'; a decision-maker with tolerance {R:,.0f} picks "
                 f"'{ce_lead}'. Expected value is the right criterion over "
                 f"many similar bets and a strange one for a choice taken "
                 f"once that cannot be unwound.")
        else:
            para(f"'{lead}' wins on expected value and on certainty "
                 f"equivalent. Risk attitude is not deciding this.")
        print()

    if len(rows) > 1:
        gap = mean(evs[lead]) - mean(evs[rows[1]])
        print(f"  {lead} leads {rows[1]} by {gap:,.0f} {unit} on average "
              f"and wins {wins[lead] / N_DRAWS:.0%} of draws.")
        if wins[lead] / N_DRAWS < 0.75:
            print("  That is not a decision. It is a coin flip with a tilt.")
        print()

    # ---- WHY: term-by-term contributions -------------------------------
    print("  WHY  -- every term at its mean, largest first")
    print("  " + "-" * 70)
    for n in rows:
        o = next(x for x in d["options"] if x["name"] == n)
        terms = [(cf * mus[k], k, cf) for k, cf in o.get("terms", {}).items()]
        terms.sort(key=lambda t: -abs(t[0]))
        c = o.get("constant", 0.0)
        tot = c + sum(t[0] for t in terms)
        print(f"  {n}   =  {tot:>10,.0f}")
        if c:
            print(f"      {'constant':<26}{c:>+11,.0f}")
        for val, k, cf in terms:
            cs = f"{cf:+g}x" if cf not in (1, -1) else ("+" if cf > 0 else "-")
            print(f"      {k:<26}{val:>+11,.0f}   ({cs} {mus[k]:,.0f})")
        print()

    if len(rows) > 1:
        a = next(x for x in d["options"] if x["name"] == rows[0])
        b = next(x for x in d["options"] if x["name"] == rows[1])
        keys = set(a.get("terms", {})) | set(b.get("terms", {}))
        diff = []
        for k in keys:
            ca = a.get("terms", {}).get(k, 0.0)
            cb = b.get("terms", {}).get(k, 0.0)
            if ca != cb:
                diff.append(((ca - cb) * mus[k], k, ca - cb))
        # Ties broken by name: `keys` is a set, whose order changes from one
        # process to the next, so equal terms used to swap places between
        # runs of the same file.
        diff.sort(key=lambda t: (-abs(t[0]), t[1]))
        total = sum(t[0] for t in diff)
        # Share of the FORCES in play, not of the net margin. Dividing by
        # the net gives nonsense like "345%" whenever terms push opposite
        # ways and cancel -- which is the normal case, not the exception.
        gross = sum(abs(t[0]) for t in diff) or 1.0
        print(f"  THE MARGIN: {rows[0]} over {rows[1]}, decomposed")
        print("  " + "-" * 70)

        (parts, ed, sdd, pclt, sd_n, p_n, bsd) = pair_margin(
            d, rows[0], rows[1])
        emean = "  +  ".join("({:+g})({:,.0f})".format(db, mu)
                             for _, db, mu, _ in parts)
        evar = "  +  ".join("({:+g})²({:,.0f})²".format(db, s)
                            for _, db, _, s in parts)
        maths("THE FORMULA",
              ["D  =  EV(" + rows[0] + ")  -  EV(" + rows[1] + ")",
               "   =  Σ_i [β_{a,i} - β_{b,i}] · θ_i",
               "",
               "E[D]   = Σ_i Δβ_i · μ_i",
               "Var[D] = Σ_i Δβ_i² · σ_i²",
               "P(a beats b) ≈ Φ( E[D] / √Var[D] )      (CLT, approximate)"],
              ["SUBSTITUTED:",
               "E[D]   = " + emean,
               "       = {:,.2f}".format(ed),
               "Var[D] = " + evar,
               "       = {:,.0f}      √Var[D] = {:,.1f}".format(sdd * sdd, sdd),
               "",
               "P ≈ Φ({:,.2f} / {:,.1f}) = Φ({:.4f}) = {:.1%}"
               .format(ed, sdd, ed / sdd if sdd else 0, pclt),
               "simulated P = {:.1%}   ({:,} draws)"
               .format(wins[rows[0]] / N_DRAWS, N_DRAWS),
               "",
               "THE SHARED-AUTHOR CORRECTION, which is doing real work here:",
               "  Var[D] = Σ Δβ²σ²  +  b²·(Σ Δβσ)²      b = {:.2f}".format(bsd),
               "         = {:,.0f}  +  {:,.0f}".format(
                   sd_n ** 2, sdd ** 2 - sd_n ** 2),
               "  sd(D)  = {:,.1f}   (was {:,.1f} treating channels as"
               .format(sdd, sd_n),
               "           independent)",
               "  P      = {:.0%}    (was {:.0%})".format(pclt, p_n),
               "",
               "The second term exists because ONE author wrote every",
               "channel. A systematic tilt in that author shifts them all",
               "the same way and never averages out. Without it, adding",
               "channels drives P to 100% by counting alone."],
              legend=["D", "EV(a)", "Σ_i", "β", "Δ", "θ_i", "E[...]",
                      "Var[...]", "μ", "σ", "Φ"], d=d)
        for val, k, cf in diff:
            share = abs(val) / gross
            bar = "#" * int(round(share * 26))
            print(f"      {k:<27}{val:>+11,.0f}  {share:>5.0%} {bar}")
        print(f"      {'NET MARGIN':<27}{total:>+11,.0f}")
        print(f"      {'forces in play':<27}{gross:>11,.0f}")
        print()
        if abs(total) < 0.25 * gross:
            para(f"The margin is {abs(total)/gross:.0%} of the forces "
                 f"producing it: {gross:,.0f} of push, netting to "
                 f"{total:,.0f}. Two large opposed terms nearly cancelling "
                 f"is the most fragile shape a decision can have -- a "
                 f"modest error in either one reverses the answer.")
            print()
        elif diff and abs(diff[0][0]) / gross > 0.6:
            para(f"One term, '{diff[0][1]}', carries "
                 f"{abs(diff[0][0]) / gross:.0%} of the forces in play. This "
                 f"decision is about that and almost nothing else. Every "
                 f"other argument here is decoration.")
            print()

    # ---- is one side better evidenced than the other? --------------------
    if len(rows) > 1:
        a0 = next(x for x in d["options"] if x["name"] == rows[0])
        b0 = next(x for x in d["options"] if x["name"] == rows[1])
        side = {"for": [], "against": [], "blind": []}
        for u in us:
            db = (a0.get("terms", {}).get(u["id"], 0.0)
                  - b0.get("terms", {}).get(u["id"], 0.0))
            if db == 0:
                continue
            val = db * mus[u["id"]]
            h = u.get("history")
            kk = (h or {}).get("transfer_error", DEFAULT_TRANSFER_ERROR)
            if not h:
                side["blind"].append((abs(val), u["id"]))
            else:
                side["for" if val > 0 else "against"].append(
                    (abs(val), kk, u["id"]))

        def wk(rs):
            m = sum(r[0] for r in rs)
            return (m, sum(r[0] * r[1] for r in rs) / m) if m else (0.0, None)

        mf, kf = wk(side["for"])
        ma, ka = wk(side["against"])
        if kf is not None and ka is not None:
            print("  EVIDENCE QUALITY ON EACH SIDE")
            print("  " + "-" * 70)
            para("Two sides of an argument are rarely evidenced equally "
                 "well. This weights each channel's transfer error by how "
                 "much that channel actually contributes, so you can see "
                 "whether the winning case rests on better or worse "
                 "evidence than the losing one.")
            print()
            print("  {:<34}{:>8}{:>10}{:>8}".format(
                "", "mass", "avg k", "avg λ"))
            print("  {:<34}{:>8,.0f}{:>10.2f}{:>8.2f}".format(
                "supports " + rows[0], mf, kf, 1 / (1 + kf * kf)))
            print("  {:<34}{:>8,.0f}{:>10.2f}{:>8.2f}".format(
                "supports " + rows[1], ma, ka, 1 / (1 + ka * ka)))
            if side["blind"]:
                print("  {:<34}{:>8,.0f}{:>10}{:>8}".format(
                    "no reference class at all",
                    sum(r[0] for r in side["blind"]), "--", "0.00"))
            print()
            better, worse = ("winning", "losing") if kf < ka else \
                            ("losing", "winning")
            if abs(kf - ka) >= 0.15:
                lo_k, hi_k = min(kf, ka), max(kf, ka)
                para(f"THE TWO SIDES ARE NOT EVIDENCED EQUALLY. The "
                     f"{better} case rests on evidence that transfers at "
                     f"k = {lo_k:.2f} (λ = {1/(1+lo_k*lo_k):.2f}); the "
                     f"{worse} case on evidence at k = {hi_k:.2f} "
                     f"(λ = {1/(1+hi_k*hi_k):.2f}).")
                print()
                if kf > ka:
                    para("The winning side is the WORSE-EVIDENCED one. That "
                         "is the configuration to distrust: the verdict is "
                         "being carried by the channels whose findings "
                         "transfer least well. It does not make the verdict "
                         "wrong. It does mean the verdict would move more "
                         "than it looks if those channels were measured "
                         "properly, and it should not be stated with "
                         "confidence.")
                else:
                    para("The winning side is the BETTER-EVIDENCED one, "
                         "which is the configuration you want: the answer "
                         "is carried by the channels that transfer best.")
            print()

    # ---- is doing nothing being charged for anything? --------------------
    empty = [o for o in d["options"] if not o.get("terms")]
    if empty:
        print("  THE BASELINE CARRIES NO TERMS")
        print("  " + "-" * 70)
        para("'" + empty[0]["name"] + "' has no costs in this model. That is "
             "arithmetically fine -- everything is measured relative to it "
             "and a constant cancels -- but it is not neutral to read.")
        print()
        para("A model shaped this way charges every alternative for the "
             "change it makes and charges the current arrangement nothing "
             "for continuing. The costs of acting are concrete, immediate "
             "and land on identifiable people. The costs of NOT acting are "
             "diffuse, already being paid, and are usually being paid by "
             "someone who is not in the model. Both appear here as zero "
             "against a list of specific negative numbers, and that is a "
             "systematic bias toward leaving things alone.")
        print()
        para("It matters most on exactly the questions where it is least "
             "welcome: whether to disrupt an arrangement that works well "
             "for whoever built it. Every disruption cost is visible and "
             "every year of the arrangement continuing is free.")
        print()
        para("TWO THINGS TO CHECK BEFORE BELIEVING A RESULT WITH THIS "
             "SHAPE. What does the baseline cost per year, stated out "
             "loud, so its size sits next to the remedy's? And who bears "
             "it -- if the answer is someone with no term in the model, "
             "the model is not measuring them.")
        print()

    # ---- is the answer an artefact of how it was carved up? --------------
    print("  STRUCTURAL BALANCE  -- is the shape doing the work?")
    print("  " + "-" * 70)
    para("A correction, tested rather than asserted: SPLITTING a channel "
         "into sub-channels does NOT move the verdict. Total mass is what "
         "the mean depends on, not how many boxes it is divided into -- "
         "splitting one benefit into three leaves the average identical "
         "and slightly REDUCES the spread, because independent pieces "
         "average out. So a lopsided count is not itself an arithmetic "
         "bias.")
    print()
    para("What does move the verdict is OMISSION -- a channel that should "
         "carry mass and carries none. A model that gives one option no "
         "downside at all produces a 100% result before a single number "
         "is examined. So read the counts below as an ELICITATION "
         "warning, not an arithmetic one: if you found five ways to say "
         "bad and three to say good, the question is whether you looked "
         "as hard on both sides, not whether the arithmetic is skewed.")
    print()
    print(f"  {'option':<26}{'+terms':>8}{'+mass':>10}{'-terms':>8}{'-mass':>10}")
    worst = None
    for o in d["options"]:
        pos = [cf * mus[k] for k, cf in o.get("terms", {}).items()
               if cf * mus[k] > 0]
        neg = [cf * mus[k] for k, cf in o.get("terms", {}).items()
               if cf * mus[k] < 0]
        print(f"  {o['name']:<26}{len(pos):>8}{sum(pos):>10,.0f}"
              f"{len(neg):>8}{sum(neg):>10,.0f}")
        if pos and neg:
            r = max(len(pos), len(neg)) / min(len(pos), len(neg))
            if worst is None or r > worst[0]:
                worst = (r, o["name"], len(pos), len(neg))
    print()
    if worst and worst[0] >= 1.5:
        para(f"'{worst[1]}' carries {worst[2]} benefit channel(s) against "
             f"{worst[3]} cost channel(s). Go and look for the missing "
             f"channels on the thin side before believing the verdict. "
             f"Not because the count is unfair -- it is not -- but because "
             f"a side you thought about in one lump is a side you probably "
             f"under-counted. The asymmetry is evidence about your search, "
             f"not about the world.")
        print()

    print("  LEAVE-ONE-OUT  -- does the verdict survive dropping a channel?")
    print("  " + "-" * 70)
    base_w = max(d["options"], key=lambda o: payoff(o, mus))["name"]
    flips = []
    for u in us:
        th = dict(mus)
        th[u["id"]] = 0.0
        w = max(d["options"], key=lambda o: payoff(o, th))["name"]
        gap = (payoff(max(d["options"], key=lambda o: payoff(o, th)), th)
               - sorted(payoff(o, th) for o in d["options"])[-2])
        flag = "FLIPS TO " + w if w != base_w else "holds"
        if w != base_w:
            flips.append(u["id"])
        print("   drop {:<26} {:<22} margin {:>9,.0f}".format(
            u["id"], flag, gap))
    print()
    if flips:
        para("THE VERDICT IS HOSTAGE TO THE CARVING. Removing "
             + ", ".join("'" + f + "'" for f in flips)
             + " reverses it. That is not evidence about the world, it is "
               "evidence about how the question was cut up. Before "
               "believing the headline, decide whether that channel "
               "deserves to be one channel, or three, or none.")
    else:
        para(f"'{base_w}' survives the removal of any single channel. The "
             f"verdict is not resting on one term, which is the weakest "
             f"good thing that can be said about it.")
    print()

    # ---- breakdown values -----------------------------------------------
    print("  BREAKDOWN VALUES  -- where the answer flips")
    print("  " + "-" * 70)
    maths("THE FORMULA",
          ["x* is the value of θ_k at which two options are exactly equal,",
           "every other belief held at its mean:",
           "",
           "    c_a + β_{a,k}·x*  +  Σ_{i≠k} β_{a,i}·μ_i",
           "  = c_b + β_{b,k}·x*  +  Σ_{i≠k} β_{b,i}·μ_i",
           "",
           "         (c_b - c_a) + Σ_{i≠k} (β_{b,i} - β_{a,i})·μ_i",
           "  x*  =  ------------------------------------------------",
           "                     β_{a,k} - β_{b,k}",
           "",
           "Write I_a for the whole intercept (everything but θ_k), and",
           "this is just  x* = (I_b - I_a) / (β_{a,k} - β_{b,k})."],
          legend=["x", "x*", "θ_i", "β", "c_a", "μ", "Σ_i", "a, b"], d=d)
    any_flip = False
    for u in us:
        x, w = breakdown(d, u["id"])
        if x is None:
            print("   {:<26} no flip in [{:,.0f}, {:,.0f}] -- {} throughout"
                  .format(u["id"], u["low"], u["high"], w))
        else:
            any_flip = True
            print("   {:<26} FLIPS AT {:,.0f}  ({} below / {} above)"
                  .format(u["id"], x, w[0], w[1]))
            alg = flip_algebra(d, u["id"], w[0], w[1])
            if alg:
                xs, ia, ib, ka, kb = alg
                print("        x* = ({:,.2f} - {:,.2f}) / ({:+g} - {:+g})"
                      .format(ib, ia, ka, kb))
                print("           = {:,.2f} / {:+g}  =  {:,.2f}"
                      .format(ib - ia, ka - kb, xs))
    if not any_flip:
        print()
        para("No single belief flips the answer on its own. That means "
             "either the decision is genuinely lopsided, or it only flips "
             "on COMBINATIONS -- two things going wrong together. Check the "
             "percentile columns above: if the winner's 5th percentile sits "
             "below the runner-up's 95th, combinations do flip it.")
    print()

    # ---- value of information -------------------------------------------
    print("  VALUE OF INFORMATION")
    print("  " + "-" * 70)
    print(f"  {'belief':<28}{'EVPI':>9}{'EVSI':>9}{'EVSI/EVPI':>10}{'k':>6}{'λ':>6}")
    print(f"  {'':<28}{'(perfect)':>9}{'(history)':>9}")
    maths("THE FORMULA",
          ["EVPI(θ_k) = E_θk[ max_a EV(a|θ_k) ]  -  max_a E_θk[ EV(a) ]",
           "",
           "The other beliefs are NOT frozen: they are conditioned on the",
           "shared factor, so learning one moves the rest. Freezing them",
           "would contradict the dependence introduced further down.",
           "",
           "Under a linear payoff, max_a EV(a|x) is the upper envelope of",
           "straight lines: piecewise linear and convex. So the expectation",
           "is an exact integral, not a simulation --",
           "",
           "    E[max] = Σ_segments ∫_p^q (c + β·x) f(x) dx",
           "           = Σ_segments [ c·(F(q)-F(p)) + β·(G(q)-G(p)) ]",
           "",
           "where F is the prior CDF and G(x) = ∫ t·f(t) dt, both closed",
           "form for triangular and uniform. Zero Monte Carlo error.",
           "",
           "EVSI(θ_k): history hands you s = θ_k + ε,  ε ~ N(0, τ),",
           "where τ is stated in the belief's OWN UNITS, not as a ratio.",
           "",
           "    λ = σ²/(σ² + τ²) = 1/(1 + k²),   k = τ/σ  (DERIVED)",
           "    E[θ|s] ≈ μ + λ·(s - μ)        <- APPROXIMATION, not exact",
           "",
           "That shrinkage is EXACT only for a Gaussian prior. These priors",
           "are triangular, so it is a Bayes linear (best affine) estimate.",
           "It can fall outside the support: for Triangular(-1,0,1) with",
           "k=1 and signal 3 it returns 1.5, where the true posterior mean",
           "is 0.850. The computation below uses a particle posterior, not",
           "this formula -- the formula is shown to explain the shape.",
           "",
           "    EVSI = E_s[ max_a EV(a | E[θ|s]) ] - max_a E[EV(a)]",
           "",
           "λ is the whole argument in one number: how far",
           "the past moves you toward what it says. λ=1 means history is",
           "truth; λ=0.5 means it gets you exactly half way.",
           "",
           "Setting k=0.95 directly from Vivalt (λ≈0.53) is wrong --",
           "Vivalt's ratio has a different denominator, and a median is",
           "not a standard deviation."],
          legend=["θ", "E[...]", "EV(a)", "β", "c_a", "x", "∫", "Σ_i",
                  "f, F, G", "s", "ε", "k", "λ", "μ", "σ"], d=d)
    rowsvi = []
    for u in us:
        p = evpi(d, u["id"])
        s, k, lam = evsi(d, u["id"])
        rowsvi.append((p, s, k, u, lam))
    rowsvi.sort(key=lambda t: -t[0])
    for p, s, k, u, lam in rowsvi:
        prov = u.get("provenance", "guessed")
        ratio = f"{s / p:.0%}" if p > 1 else "-"
        ks = f"{k:.2f}" if k is not None else "--"
        ls = f"{lam:.2f}" if lam is not None else "--"
        print(" {}{:<27}{:>9,.0f}{:>9,.0f}{:>10}{:>6}{:>6}".format(
            MARK.get(prov, "?"), u["id"], p, s, ratio, ks, ls))
    print()

    # Show the integral, with numbers, for anything that is worth anything.
    for p, s, k, u, lam in rowsvi:
        if p < 1.0:
            continue
        val, segrows, base = evpi_detail(d, u["id"])
        blk = ["max_a E[EV(a)]  =  {:,.2f}      (the no-information baseline)"
               .format(base), "",
               "envelope pieces of  max_a EV(a | θ = x):"]
        for (pp, qq, who, c, kk, dF, dG, piece) in segrows:
            blk.append("  x ∈ [{:>8,.0f}, {:>8,.0f}]   {:<18} L(x) = {:,.1f} "
                       "{:+g}·x".format(pp, qq, who, c, kk))
            blk.append("      ΔF = {:.4f}   ΔG = {:>12,.1f}   "
                       "contribution = {:>10,.2f}".format(dF, dG, piece))
        blk += ["",
                "E[max] = {:,.2f}".format(sum(r[7] for r in segrows)),
                "EVPI   = {:,.2f} - {:,.2f}  =  {:,.2f}"
                .format(sum(r[7] for r in segrows), base, val)]
        if k is not None:
            blk += ["",
                    "λ = 1/(1 + {:.2f}²) = {:.4f}     √λ = {:.4f}"
                    .format(k, lam, math.sqrt(lam)),
                    "EVSI = {:,.2f}      EVSI/EVPI = {:.1%}"
                    .format(s, s / val if val else 0),
                    "(√λ = {:.1%} is the rough Gaussian expectation; the gap"
                    .format(math.sqrt(lam)),
                    " is skew in the triangular prior)"]
        else:
            blk += ["",
                    "No history block → no signal exists → EVSI = 0.",
                    "This is not a missing input. It is the finding."]
        maths("EVPI / EVSI FOR '" + u["id"] + "'", blk,
              legend=["f, F, G", "λ", "k", "x"], d=d)
    para("EVPI is the ceiling: what knowing a thing EXACTLY would be worth. "
         "EVSI is what HISTORY can deliver, given that history transfers "
         "badly. k is the transfer error: 0 means the past is a perfect "
         "guide, 1 means the historic signal's error is as large as the "
         "thing it measures. k defaults to 0.95, the median across Vivalt's "
         "635 papers. A belief with no reference class gets EVSI 0 and "
         "k '--' -- there is no signal to go and find.")
    print()

    # EVPI is blind to combinations by construction. Learn the top few
    # together and see how much that was hiding.
    top_ids = [r[3]["id"] for r in rowsvi[:4]]
    if len(top_ids) >= 2:
        joint = evppi_subset(d, top_ids)
        singles = sum(r[0] for r in rowsvi[:4])
        print("  LEARNED TOGETHER RATHER THAN ONE AT A TIME (EVPPI)")
        print("  " + "-" * 70)
        print("   {:<44}{:>10,.0f}".format(
            "sum of the four separately", singles))
        print("   {:<44}{:>10,.0f}".format(
            "all four learned jointly", joint))
        print()
        if joint > singles * 1.25:
            para("Learning them TOGETHER is worth substantially more than "
                 "learning them one at a time. That gap is the value EVPI "
                 "cannot see: it varies one belief and freezes the rest, so "
                 "an answer that only reverses on a combination registers "
                 "as worth nothing to research. The joint figure is the "
                 "honest one.")
        else:
            para("Close to the sum of the parts, so this decision is not "
                 "combination-driven and the single-belief EVPIs above are "
                 "not misleading.")
        print()

    # The headline the table is already saying. Across every belief: how
    # much of the total decidable value can the past actually reach?
    sum_p = sum(r[0] for r in rowsvi)
    sum_s = sum(r[1] for r in rowsvi)
    if sum_p > 1.0:
        frac = sum_s / sum_p
        print(f"  HISTORY CAN REACH {frac:.0%} OF WHAT IS DECIDABLE HERE.")
        para(f"Perfect knowledge of everything uncertain is worth "
             f"{sum_p:,.0f} {unit}. Historic evidence, at the transfer "
             f"errors above, delivers {sum_s:,.0f}. The gap is not "
             f"ignorance you can read your way out of.")
        blind = [r[3] for r in rowsvi if r[0] > 1.0 and r[2] is None]
        if blind:
            print()
            para("And it is concentrated: "
                 + ", ".join("'" + u["id"] + "'" for u in blind)
                 + (" carries " if len(blind) == 1 else " together carry ")
                 + "{:.0%}".format(
                     sum(r[0] for r in rowsvi if r[2] is None) / sum_p)
                 + " of the decidable value with NO reference class at all. "
                   "No amount of reading decides that part. It is judgement "
                   "or it is nothing.")
        print()

    top_p, top_s, top_k, top_u, top_l = rowsvi[0]

    if top_p < 1.0:
        p_up = wins[rows[1]] / N_DRAWS if len(rows) > 1 else 0.0
        para("NO SINGLE BELIEF IS WORTH RESOLVING. Move any one of them "
             "across its whole range -- with the others conditioned on it "
             f"through the shared factor -- and {lead} still wins. Note the "
             "careful wording: this is NOT the same as saying the answer "
             "is safe.")
        print()
        if p_up >= 0.05:
            para(f"Because the simulation disagrees: {rows[1]} wins "
                 f"{p_up:.0%} of draws. Both are true at once, and together "
                 f"they say something specific and useful --")
            print()
            para(f"THE ANSWER IS COMBINATION-DRIVEN. It never turns on one "
                 f"thing going differently. It turns on several going the "
                 f"same way at once. Single-variable research is worth "
                 f"nothing here, and the verdict is still only {1-p_up:.0%} "
                 f"safe. EVPI is blind to this by construction: it varies "
                 f"one belief and freezes the rest.")
            print()
            share, prof = flip_profile(d, lead)
            if prof:
                print("    WHAT IT TAKES -- the coalition that flips it")
                print("    " + "-" * 64)
                print("    {:<28}{:>9}{:>11}{:>10}".format(
                    "belief", "average", "when flips", "shift"))
                for z, name, m, cm, s in prof[:6]:
                    print("    {:<28}{:>9,.0f}{:>11,.0f}{:>9.2f}σ".format(
                        name, m, cm, z))
                print()
                para("Read the last column as: how far this belief has to "
                     "move from its average, in its own spreads, in the "
                     "worlds where the answer reverses. Nothing here is "
                     "extreme on its own. That is the point -- it is "
                     "several ordinary shifts landing together, which no "
                     "single-variable analysis can see and no argument "
                     "about one channel can settle.")
        else:
            para("And the simulation agrees: the runner-up wins only "
                 f"{p_up:.0%} of draws. Two readings remain, opposite in "
                 "implication:")
            print()
            para("(1) It is genuinely not close. Stop researching, act.")
            para("(2) Your ranges are too narrow, or the belief that "
                 "actually decides this is not in the model at all. If the "
                 "answer feels closer than the number says, this is it.")
            print()
            para("You cannot tell those apart from inside the model. That "
                 "is the honest limit of what this computes.")
    else:
        para(f"Knowing '{top_u['id']}' exactly is worth {top_p:,.0f} {unit}. "
             f"That is the ceiling on research into it.")
        if top_k is None:
            print()
            para("And there is no reference class for it, so history offers "
                 "nothing at all. It has to be measured directly, or the "
                 "decision has to be made without it.")
        elif top_s < max(1.0, top_p * 0.05):
            print()
            para(f"But historic evidence about it is worth only "
                 f"{top_s:,.0f}. At a transfer error of {top_k:.2f} the past "
                 f"cannot resolve this one. Measuring it directly is the "
                 f"only thing that helps; reading more history is not.")
        else:
            print()
            para(f"Historic evidence captures {top_s / top_p:.0%} of that "
                 f"-- {top_s:,.0f} {unit} -- at a transfer error of "
                 f"{top_k:.2f}. That is the part of this question the past "
                 f"can actually answer.")
        zeros = [r[3] for r in rowsvi if r[0] < max(1.0, top_p * 0.02)]
        if zeros:
            print()
            para("Worth approximately nothing: "
                 + ", ".join("'" + u["id"] + "'" for u in zeros)
                 + ". The same option wins whatever these turn out to be. "
                   "If you have been arguing about them, you have been "
                   "arguing about something that does not decide this.")
    print()

    # ---- how much of this is invented? -----------------------------------
    guessed = [u for u in us if u.get("provenance", "guessed") == "guessed"]
    spread = {u["id"]: abs(u["high"] - u["low"]) for u in us}
    tot_sp = sum(spread.values()) or 1.0
    print("  HOW MUCH OF THIS IS MADE UP")
    print("  " + "-" * 70)
    print("  NOT a probability. The share of the model's total uncertainty")
    print("  contributed by beliefs of each kind.")
    print()
    for prov in ("measured", "estimated", "guessed"):
        sel = [u for u in us if u.get("provenance", "guessed") == prov]
        sh = sum(spread[u["id"]] for u in sel) / tot_sp
        print(f"   {prov:<14}{len(sel):>3} belief(s){sh:>9.0%} of total range")
    print()
    if guessed:
        g = sum(spread[u["id"]] for u in guessed) / tot_sp
        para(f"{g:.0%} of the uncertainty in this model is GUESSED: "
             + ", ".join("'" + u["id"] + "'" for u in guessed)
             + ". A made-up range drives the result exactly as hard as a "
               "measured one. Replace these, or read the output as "
               "arithmetic performed on fiction.")
        print()

    print("  This computes what the stated beliefs imply. It says nothing")
    print("  about whether those beliefs are correct.")
    print()
    verdict(d, evs, names, wins, rows)


def elicit_swing(d, name):
    """SWING WEIGHTING -- a better way to ask, from the SMART protocol.

    Asking someone for a number in a made-up unit is asking them to do the
    one thing people are worst at. They will produce a number, it will be
    anchored on whatever they read last, and they cannot tell you why it is
    not twice as large.

    Swing weighting asks a different question, and people answer it well:
    imagine every belief sits at its WORST value. Which single one would
    you most want to swing to its best? That is a ranking, and rankings are
    stable, checkable against each other, and hard to anchor. Then only one
    scale has to be set -- the top item is 100 -- and everything else is a
    ratio to a thing already chosen, which is again a comparison rather
    than a scaling.

    The magnitudes still come from a person. The difference is that they
    come from a question that person can actually answer.
    """
    print("=" * 74)
    print("SWING WEIGHTING SHEET  --  " + d["decision"])
    print("=" * 74)
    print()
    for line in wrap(
        "Do NOT start by writing numbers. Numbers in an unfamiliar unit "
        "are the hardest thing to produce reliably, and the first one you "
        "write will anchor every one after it. Work through these three "
        "steps in order."):
        print("  " + line)
    print()
    print("  STEP 1 -- THE WORST WORLD")
    print("  " + "-" * 70)
    for line in wrap(
        "Picture every one of these at its worst plausible value at the "
        "same time. Sit in that world for a moment before continuing."):
        print("  " + line)
    print()
    for u in d["uncertainties"]:
        print(f"      {u['id']}")
    print()
    print("  STEP 2 -- ONE SWING AT A TIME")
    print("  " + "-" * 70)
    for line in wrap(
        "From that worst world you may move exactly ONE of them to its "
        "best plausible value. Which do you pick? Write 1 beside it. Then, "
        "starting again from the worst world, which would you pick second? "
        "Write 2. Continue until all are ranked. Rank every one -- ties "
        "are allowed but should be rare, and a tie usually means the two "
        "are really one belief."):
        print("  " + line)
    print()
    for u in d["uncertainties"]:
        print(f"      ____   {u['id']}")
    print()
    print("  STEP 3 -- ONE SCALE, SET BY COMPARISON")
    print("  " + "-" * 70)
    for line in wrap(
        "Your number 1 is worth 100. For each of the others, ask only: "
        "how big is THAT swing compared to the 100 one? Half as good is "
        "50. A tenth is 10. You are never inventing a number in a strange "
        "unit -- every answer is a ratio against something you have "
        "already chosen."):
        print("  " + line)
    print()
    for u in d["uncertainties"]:
        print(f"      ____ /100   {u['id']}      worst ____   best ____")
    print()
    print("  " + "-" * 70)
    for line in wrap(
        "The worst and best values are the low and high of the range. The "
        "swing weight is what tells us how much a move across that range "
        "actually matters, which is the part a bare number hides. If your "
        "ranking in step 2 disagrees with the numbers in step 3, TRUST "
        "THE RANKING and change the numbers -- that inconsistency is the "
        "single most useful thing this sheet produces."):
        print("  " + line)
    print()


def elicit(d, name):
    """Emit a BLANK elicitation sheet: the channel list and what each one
    means, with every number stripped out.

    This is the interface for reducing b. The shared-author term is large
    because one mind set all the ranges in one sitting. Hand this sheet to
    a different mind, get the numbers back, and the disagreement between
    the sheets MEASURES b instead of assuming it.
    """
    print("=" * 74)
    print("ELICITATION SHEET  --  " + d["decision"])
    print("=" * 74)
    print()
    print("Paste everything below to another model, or fill it in yourself.")
    print("Do NOT show it the existing numbers. The whole value is in the")
    print("estimate being made independently.")
    print()
    print("-" * 74)
    print()
    print("You are estimating inputs to a decision model. For each channel")
    print("below, give four numbers:")
    print()
    print("  low   / high  : a range you would defend, not a 95% interval")
    print("  mode          : where you think it most likely sits")
    print("  k             : TRANSFER ERROR of the evidence behind it.")
    print("                  0.0 = the past transfers perfectly")
    print("                  0.5 = good reference class, close domain")
    print("                  0.95 = the median across Vivalt's 635 impact")
    print("                         evaluations -- assume this by default")
    print("                  >1.0 = the historical signal's error exceeds")
    print("                         the effect it measures (e.g. a lab")
    print("                         finding carried to a different domain)")
    print()
    print("SIGN -- GIVE EVERY NUMBER AS A POSITIVE MAGNITUDE, costs")
    print("included. The model already knows which channels are costs and")
    print("subtracts them itself; a channel marked COST with the value 40")
    print("means 'this costs 40', not 'this gains 40'. A NEGATIVE number")
    print("here is a strong and unusual claim -- that a channel labelled")
    print("COST in fact ran the other way and was a benefit. Use it only")
    print("if you mean exactly that.")
    print()
    print(f"Unit: {d.get('unit','')}")
    u0 = d.get("_the_unit_is_arbitrary_and_that_is_fine")
    if u0:
        for line in wrap(u0, 70):
            print("  " + line)
    print()
    print("Say if you think a channel is missing, double-counted, or should")
    print("not be in the model. Omissions are the only thing that moves the")
    print("answer's mean, so that note is worth more than the numbers.")
    print()
    print("-" * 74)
    for u in d["uncertainties"]:
        print()
        print(f"CHANNEL: {u['id']}")
        # Prefer a purpose-written NEUTRAL definition. The `source` field
        # is written for a reader who already has the answer, and carries
        # judgements about magnitude and evidence quality,
        # which are exactly the two things being asked for. Leaking them
        # correlates the new author with the old one and destroys the only
        # thing a panel is for.
        src = u.get("elicit")
        if not src:
            src = u.get("source", "")
            print("  [WARNING: no neutral prompt for this channel -- the")
            print("   text below may leak the file author's conclusions]")
        for line in wrap(src, 70):
            print("  " + line)
        print("  low = ___   high = ___   mode = ___   k = ___")
    print()
    print("-" * 74)
    print()
    print("Return as JSON:  {\"author\": \"<model name>\", \"channels\": ")
    print("  {\"<id>\": {\"low\": _, \"high\": _, \"mode\": _, \"k\": _}, ...},")
    print("  \"missing\": [\"...\"], \"objections\": [\"...\"]}")
    print()
    print(f"Save it as harness/panels/{name}/<author>.json, then run:")
    print(f"  python harness/panel.py {name}")


def main():
    if len(sys.argv) > 2 and sys.argv[2] == "--elicit":
        elicit(load(sys.argv[1]), sys.argv[1])
        return
    if len(sys.argv) > 2 and sys.argv[2] == "--swing":
        elicit_swing(load(sys.argv[1]), sys.argv[1])
        return
    if len(sys.argv) > 4 and sys.argv[2] == "--test":
        test_value_report(load(sys.argv[1]), sys.argv[3], float(sys.argv[4]),
                          horizon_days=(float(sys.argv[5])
                                        if len(sys.argv) > 5 else None))
        return
    if len(sys.argv) < 2:
        fs = sorted(f[:-5] for f in os.listdir(DECISIONS) if f.endswith(".json"))
        print("decisions:", ", ".join(fs))
        return
    report(load(sys.argv[1]))


if __name__ == "__main__":
    _utf8_stdout()
    main()
