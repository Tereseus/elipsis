#!/usr/bin/env python3
"""
chain.py -- a long-horizon claim, decomposed into links that can each be
            argued separately.

decide.py answers "what should I do". This answers "how likely is that",
which is a different question and needs a different shape. A claim about a
distant future is almost never one proposition -- it is a conjunction
wearing a single sentence, and the sentence hides which part is doing the
work:

    P(claim) = P(L1) x P(L2 | L1) x P(L3 | L1,L2) x ...

Two things fall out of writing it that way, and neither is visible in a
single gut number.

THE PRODUCT IS BRUTAL. Five links at 0.8 each is 0.33, not 0.8. People
state compound claims with the confidence of their strongest link. The
multiplication is the correction, and it is usually large.

THE MODAL FAILURE IS NOT THE OBVIOUS ONE. Decomposing shows WHICH link
kills the claim most often. That is frequently not the part being argued
about.

EVERY LINK DECLARES ITS REFERENCE CLASS, or admits it has none. A link with
no base rate behind it is a judgement written as a decimal, and the report
says so rather than letting it hide inside a product.

SCOREABILITY IS REPORTED, NOT ASSUMED. A claim resolving past any horizon
anyone can check is not a prediction, it is a worldview. It can still be
decomposed usefully -- but the tool says plainly that no ledger will ever
score it, and asks for the near-term version of the same belief instead.

THE PRODUCT CAN ALSO BE TOO BRUTAL. Split anything into enough stages,
price each near a noncommittal 0.5, and the multiplication says it cannot
happen. That is the multiple-stage fallacy, and this file had one guard
against it (the "Given ..." rule) where it needs three. A step can now
list other ROUTES through it and a number of ATTEMPTS, joined through a
named SHARED BLOCK so that retries are not priced as fresh coins; and
every report ends with a check for stacked middling guesses. See
"WAYS THROUGH A STEP" below.

Run:  python harness/chain.py <name>
      python harness/chain.py <name> audit [gut]   how done is this plan?
"""

import contextlib
import io
import json
import math
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402  (sits next to this file)
CHAINS = paths.data("chains")
N_DRAWS = 20000
SEED = 20260913

MARK = {"measured": " ", "estimated": "~", "guessed": "?"}



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


def load(name):
    p = os.path.join(CHAINS, name if name.endswith(".json") else name + ".json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


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


def _tri(lo, hi, m, rng):
    if lo is None or hi is None or hi <= lo:
        return m
    return min(1.0, max(0.0, rng.triangular(lo, hi, m)))


def draw(l, rng):
    w = l.get("_ways")
    if w:
        ps = [_tri(x["low"], x["high"], x["p"], rng) for x in w["ways"]]
        return step_p(ps, [x["attempts"] for x in w["ways"]], w["s"])
    return _tri(l.get("low"), l.get("high"), l["p"], rng)


def spread(links, n=N_DRAWS, seed=SEED):
    """The product with every link drawn from its own range.
    Returns (mean, 5th percentile, 95th percentile)."""
    rng = random.Random(seed)
    draws = []
    for _ in range(n):
        v = 1.0
        for l in links:
            v *= draw(l, rng)
        draws.append(v)
    draws.sort()
    return (sum(draws) / len(draws), draws[int(0.05 * (len(draws) - 1))],
            draws[int(0.95 * (len(draws) - 1))])


# ------------------------------------------------ ways through a step ---
# The multiplication corrects people who state a compound claim with the
# confidence of its strongest link. Overdone, it manufactures doom: six
# stages at 50% each give 0.5^6 = 1.6%. Yudkowsky named this the
# multiple-stage fallacy and gave three causes:
#
#   1. stages priced on their own, when each should be priced GIVEN that
#      every earlier one went through -- the "Given ..." rule above;
#   2. one way through each stage, when there are often several, or the
#      same way can simply be tried again;
#   3. middling numbers written for "I don't know", which multiply into
#      "almost impossible".
#
# Cause 2 is represented here. A link can list other `routes` through the
# same step and a number of `attempts`, and they are joined honestly --
# not as independent chances, which is only the optimistic end, but
# through a named `shared_block`: the one obstacle that would stop every
# route and every retry at once, which is how retries usually fail.
#
#     P(step) = (1 - s) x [ 1 - PROD_i ( 1 - p_i/(1 - s) ) ^ k_i ]
#
# s is the chance of the shared block, p_i the one-try chance of way i
# (the step itself is way 1), k_i its attempts. At s = 0 the ways fail for
# their own reasons: the upper end. At its largest possible value,
# s = 1 - max(p_i), every failure is the shared one and the step is worth
# only its best single try: the lower end. Both ends are printed, so the
# choice of s is visible instead of buried in a product.
#
# Cause 3 is the check at the end of every report, `multistage_check`.

def step_p(ps, ks, s):
    """P(step) from one-try chances ps, attempts ks and shared block s.
    s is capped at 1 - max(ps): a shared block cannot be likelier than
    the best way's own failure, or that way would fail more often than it
    is tried."""
    s = min(max(0.0, s), 1.0 - max(ps))
    if s >= 1.0:
        return 0.0
    miss = 1.0
    for p, k in zip(ps, ks):
        miss *= (1.0 - min(1.0, p / (1.0 - s))) ** k
    return (1.0 - s) * (1.0 - miss)


def _ways(l):
    """The ways through a step: the step itself first, then its routes."""
    return [{"id": w["id"], "p": w["p"], "low": w.get("low"),
             "high": w.get("high"), "attempts": max(1, int(w.get("attempts", 1)))}
            for w in [l] + list(l.get("routes") or [])]


def apply_ways(links):
    """Replace every step that has routes or retries by its combined chance.

    Returns NEW dicts for those steps and leaves the caller's untouched. A
    chain passed inline is often saved straight afterwards, and a report
    must never rewrite the numbers it was given.
    """
    out = []
    for l in links:
        if not (l.get("routes") or int(l.get("attempts", 1)) > 1):
            out.append(l)
            continue
        ways = _ways(l)
        ps = [w["p"] for w in ways]
        ks = [w["attempts"] for w in ways]
        sb = l.get("shared_block") or {}
        s_given = float(sb.get("p", 0.0))
        s = min(max(0.0, s_given), 1.0 - max(ps))
        n = dict(l)
        n["p_one_try"] = l["p"]
        n["p"] = step_p(ps, ks, s)
        n["low"] = step_p([w["low"] if w["low"] is not None else w["p"]
                           for w in ways], ks, s)
        n["high"] = step_p([w["high"] if w["high"] is not None else w["p"]
                            for w in ways], ks, s)
        n["_ways"] = {"ways": ways, "s": s, "s_given": s_given,
                      "capped": s_given > s + 1e-12,
                      "what": sb.get("what", ""),
                      "lower": max(ps), "upper": step_p(ps, ks, 0.0)}
        out.append(n)
    return out


def print_ways(l):
    w = l["_ways"]
    txt = "; ".join(f"'{x['id']}' {x['p']:.2f}"
                    + (f" x {x['attempts']} tries" if x["attempts"] > 1 else "")
                    for x in w["ways"])
    para(f"WAYS THROUGH: {txt}.", indent="        ", w=64)
    if w["s"] > 0 and w["what"]:
        use = (f"Using {l['p']:.2f}, with the shared obstacle named: "
               f"{w['what']}, at {w['s']:.2f}.")
    else:
        use = (f"Using {l['p']:.2f}, the upper end, because no shared "
               f"obstacle is named. Name what would stop every way through "
               f"at once, and price it, to move off the bound.")
    para(f"If one obstacle blocks them all this step is worth "
         f"{w['lower']:.2f}; if each fails for its own reasons, "
         f"{w['upper']:.2f}. " + use, indent="        ", w=64)
    if w["capped"]:
        para(f"The shared obstacle was priced at {w['s_given']:.2f}, above "
             f"1 minus the best way's chance, which would make that way "
             f"fail more often than it is tried. Capped at {w['s']:.2f}.",
             indent="        ", w=64)


MIDDLING = (0.35, 0.65)
DEFAULT_HIGH = 0.8   # a step that usually goes through once the earlier ones have


def middling_steps(links):
    """Steps sitting near a coin flip with nothing measured behind them."""
    lo, hi = MIDDLING
    return [l for l in links
            if lo <= l["p"] <= hi
            and (l.get("provenance", "guessed") == "guessed"
                 or not l.get("basis"))]


def high_end(point, steps):
    """The product with those steps at the top of their own stated ranges,
    or at DEFAULT_HIGH where no range above the point was given."""
    v, fallback = point, False
    for l in steps:
        h = l.get("high")
        if h is None or h <= l["p"]:
            h, fallback = DEFAULT_HIGH, True
        v *= h / l["p"] if l["p"] > 0 else 1.0
    return min(1.0, v), fallback


GIVEN = re.compile(r"\s*(given|if|assuming|once|after|with)\b", re.I)


def multistage_findings(d, links, point):
    """The three causes of the multiple-stage fallacy, checked. Returns a
    list of (name, text) findings; empty means the pattern is absent."""
    out = []
    mids = middling_steps(links)
    if len(mids) >= 2:
        hi, fallback = high_end(point, mids)
        ids = ", ".join("'" + l["id"] + "'" for l in mids)
        out.append(("middling", (
            f"{len(mids)} steps sit between {MIDDLING[0]} and {MIDDLING[1]} "
            f"with nothing measured behind them: {ids}. A middling number is "
            f"what gets written for 'I don't know', and multiplying several "
            f"makes almost anything look unlikely: six steps at 0.5 give "
            f"0.016. With those steps at the top of their own ranges"
            + (f" ({DEFAULT_HIGH} where none was stated)" if fallback else "")
            + f", the product is {hi:.3f} instead of {point:.3f}, "
            f"{(hi / point if point else float('inf')):.1f} times higher. "
            f"Before trusting the low number, ask of each one: given that "
            f"every earlier step went through, is this still close to a "
            f"coin flip?"), hi))
    loose = [l for l in links[1:] if not GIVEN.match(l.get("statement", ""))]
    if loose:
        ids = ", ".join("'" + l["id"] + "'" for l in loose)
        out.append(("unconditioned", (
            f"{len(loose)} step(s) after the first do not say what they "
            f"assume: {ids}. Each must be priced assuming every earlier step "
            f"went through. Priced on its own it is usually too low, because "
            f"earlier successes make later steps easier."), None))
    if (len(links) >= 4 and not any(l.get("_ways") for l in links)
            and not d.get("outside_view")):
        out.append(("one_route", (
            f"No step lists another way through or a second attempt, and "
            f"there is no outside view, so every route nobody wrote down is "
            f"priced at zero. Add `routes` or `attempts` to a step, or an "
            f"`outside_view` to the chain."), None))
    return out


def multistage_check(d, links, point):
    print("=" * 74)
    print("  THE MULTIPLE-STAGE CHECK -- could this be too pessimistic?")
    print("=" * 74)
    print()
    found = multistage_findings(d, links, point)
    if not found:
        para("No stack of guessed middling steps, every later step says what "
             "it assumes, and other routes have been considered. This is "
             "not the multiple-stage pattern.")
        print()
        return
    para("Multiplying steps corrects overconfidence, and overdone it "
         "manufactures doom. These are the places this chain could be "
         "doing that:")
    print()
    for _, text, _ in found:
        bullet(text)
        print()


def bullet(s, w=66):
    for i, line in enumerate(wrap(s, w)):
        print(("   - " if i == 0 else "     ") + line)


def check_observed(links):
    """A link marked `already_occurred` is not a forecast.

    A link that describes something that has already happened, priced as
    though it might not, discounts the claim for a fact.

    A conjunction of events and a conjunction of structural conditions are
    different objects. Mixing them silently understates the claim, because
    every structural fact enters as a discount.
    """
    bad = [l for l in links
           if l.get("already_occurred") and l["p"] < 0.95]
    if bad:
        print("=" * 74)
        print("  LINKS PRICED AS FORECASTS THAT HAVE ALREADY HAPPENED")
        print("=" * 74)
        print()
        for l in bad:
            print(f"   {l['id']}  at p={l['p']:.2f}")
            para("This is marked as already observed. A completed event "
                 "does not get a probability below 1 -- pricing it as "
                 "uncertain discounts the whole claim for something that "
                 "is not in doubt.", indent="      ", w=64)
            print()
    for l in links:
        if l.get("already_occurred"):
            l["p"] = 1.0
            l["low"] = l["high"] = 1.0
    return links


def regime_mixture(d, independent):
    """Dependence between links, done by naming the thing that causes it.

    Dependencies between links need not point the same way: one common
    cause can raise some links together and lower others. Patching
    correlations onto point probabilities cannot represent that.

    So the driver is named instead, and every link is priced twice: once
    in the world where it happens and once in the world where it does not.

        P(claim) = q x PROD p_i|crisis  +  (1-q) x PROD p_i|calm

    That is a mixture over a latent common cause, and it is the honest
    shape because the dependence is now a claim about the world that can
    be argued with, rather than a number chosen to make two links lean.

    THE ARITHMETIC CHECKS ITSELF. Each link still carries its marginal p,
    and the mixture must reproduce it: q x p|crisis + (1-q) x p|calm has
    to equal the p that was there before. If it does not, the split has
    quietly changed the belief instead of decomposing it, and this says so
    rather than letting it through.
    """
    rg = d.get("regimes")
    if not rg:
        return independent, None

    q = rg["q"]
    names = rg.get("names", ["crisis", "calm"])
    hi, lo = names[0], names[1]
    links = d["links"]

    print("=" * 74)
    print("  THE DEPENDENCE BETWEEN THE LINKS, WITH ITS CAUSE NAMED")
    print("=" * 74)
    print()
    para(rg["driver"])
    print()
    print(f"   {MARK.get(rg.get('provenance','guessed'),'?')} "
          f"P({hi}) = {q:.2f} over the window")
    para("BASIS: " + rg["basis"], indent="        ", w=64)
    print()

    print("  {:<30}{:>10}{:>10}{:>12}{:>10}".format(
        "", hi, lo, "mixture", "stated"))
    print("  " + "-" * 70)
    ph, pl = 1.0, 1.0
    bad = []
    for l in links:
        br = l.get("p_by_regime")
        a = br[hi] if br else l["p"]
        b = br[lo] if br else l["p"]
        ph *= a
        pl *= b
        mix = q * a + (1 - q) * b
        ok = abs(mix - l["p"]) < 0.005
        if not ok:
            bad.append((l["id"], mix, l["p"]))
        print("  {:<30}{:>10.2f}{:>10.2f}{:>12.3f}{:>10.2f}{}".format(
            l["id"][:30], a, b, mix, l["p"], "" if ok else "  <-- DRIFT"))
    print()
    if bad:
        para("THE SPLIT HAS MOVED A BELIEF. The regime probabilities above "
             "do not average back to the marginal that was already in the "
             "file, which means this is not a decomposition of the existing "
             "number -- it is a different number wearing a decomposition. "
             "Fix the split or change the marginal deliberately, but do not "
             "let it happen by accident: " +
             ", ".join(f"{i} ({m:.3f} vs {p:.2f})" for i, m, p in bad))
        print()
    else:
        para("Every link's two regime values average back to the marginal "
             "that was already there, so nothing has been quietly revised. "
             "What changed is only the CORRELATION, which is the thing this "
             "block exists to represent.")
        print()

    mixed = q * ph + (1 - q) * pl
    row = "  {:<40}{:>8.4f}  = {:>6.2%}"
    print("  " + "-" * 70)
    print(row.format(f"if {hi}:  all links", ph, ph))
    print(row.format(f"if {lo}:   all links", pl, pl))
    print(row.format("mixture over the driver", mixed, mixed))
    print(row.format("what independence gave", independent, independent))
    print()
    d_rel = (mixed / independent - 1) if independent else 0.0
    para(f"The dependence moves the answer by {d_rel:+.0%} in relative "
         f"terms, from {independent:.2%} to {mixed:.2%}. "
         + ("It went DOWN, which means the driver pushes some links the "
            "opposite way from others, and those negative dependences "
            "outweigh the positive ones. Naming the driver is what let the "
            "arithmetic settle that."
            if mixed < independent else
            "It went UP, which is the usual direction when links share a "
            "driver -- the worlds where one succeeds are the worlds where "
            "the others do too, and independence prices those worlds as if "
            "they were rare."))
    print()
    return mixed, {"q": q, "hi": hi, "lo": lo, "p_hi": ph, "p_lo": pl}


def outside_view(d, inside, rinfo=None):
    """The base-rate route to the same outcome.

    A chain is an INSIDE view. It walks the specific mechanism somebody has
    in mind and multiplies out the steps. That is the right way to price a
    mechanism and it has one characteristic failure: it can only price the
    mechanism it was given. Every route to the same outcome that nobody
    wrote down is priced at zero, silently, and the product looks complete
    because all its own links are there.

    An outside view fixes exactly that and nothing else. It asks how often
    the outcome happens AT ALL to cases like this one, by any route,
    and it needs no view about which route. Kahneman and Lovallo's argument
    for it is that the inside view is where planners systematically go
    wrong; the argument for keeping BOTH is that the outside view cannot
    tell you which lever to pull.

    The two are combined as independent routes:

        P(either) = 1 - (1 - P_inside)(1 - P_outside)

    which is right when the routes really are separate and slightly
    overstates when they are not. Both being partly driven by the same
    underlying cause is the obvious way they could correlate, so the
    combined number is an upper bound.
    """
    ov = d.get("outside_view")
    if not ov:
        return inside

    yrs = ov.get("horizon_years", d.get("horizon_years", 1))
    annual = ov["annual_rate"]
    any_onset = 1 - (1 - annual) ** yrs
    cond = ov["conditional"]
    out = any_onset * cond

    # The two routes are NOT independent when a driver has been named -- the
    # same shock can move the chain and the onset rate. Combining them
    # inside each regime and mixing afterwards is the only place that can
    # be represented; combining the two mixed numbers at the end throws the
    # correlation away.
    by_regime = ov.get("annual_rate_by_regime")
    if rinfo and by_regime:
        q, hi, lo = rinfo["q"], rinfo["hi"], rinfo["lo"]
        oh = (1 - (1 - by_regime[hi]) ** yrs) * cond
        ol = (1 - (1 - by_regime[lo]) ** yrs) * cond
        bh = 1 - (1 - rinfo["p_hi"]) * (1 - oh)
        bl = 1 - (1 - rinfo["p_lo"]) * (1 - ol)
        both = q * bh + (1 - q) * bl
        naive = 1 - (1 - inside) * (1 - out)
        out = q * oh + (1 - q) * ol
        mixed_note = (oh, ol, bh, bl, naive)
    else:
        both = 1 - (1 - inside) * (1 - out)
        mixed_note = None

    print("=" * 74)
    print("  THE OUTSIDE VIEW -- the route the chain does not contain")
    print("=" * 74)
    print()
    para(ov["what_the_chain_misses"])
    print()
    print(f"   {MARK.get(ov.get('provenance','guessed'),'?')} base rate  "
          f"{annual:.3%} per year")
    para(ov["what_it_measures"], indent="        ", w=64)
    para("SOURCE: " + ov["source"], indent="        ", w=64)
    print()
    print("  " + "-" * 70)
    row = "  {:<34}{:>8.3f}  = {:>6.1%}"
    print(row.format(f"P(any onset in {yrs} years)", any_onset, any_onset))
    print(row.format("x P(this outcome | an onset)", cond, cond))
    print("  " + "-" * 70)
    print(row.format("P(outcome by the other route)", out, out))
    print()
    para("CONDITIONAL BASIS: " + ov["conditional_basis"])
    print()

    print("  " + "-" * 70)
    print(row.format("inside view  (the chain)", inside, inside))
    print(row.format("outside view (any other route)", out, out))
    print(row.format("BOTH ROUTES", both, both))
    print()
    if mixed_note:
        oh, ol, bh, bl, naive = mixed_note
        q, hi, lo = rinfo["q"], rinfo["hi"], rinfo["lo"]
        print("  " + "-" * 70)
        print(f"  BOTH ROUTES, INSIDE EACH REGIME  (q = {q:.2f})")
        print("  " + "-" * 70)
        print(row.format(f"if {hi}:  chain {rinfo['p_hi']:.3f}, other "
                         f"{oh:.3f}", bh, bh))
        print(row.format(f"if {lo}:   chain {rinfo['p_lo']:.3f}, other "
                         f"{ol:.3f}", bl, bl))
        print(row.format("mixed over the driver", both, both))
        print(row.format("if the routes were independent", naive, naive))
        print()
        para(f"Treating the two routes as independent gave {naive:.2%}. "
             f"They are not independent: the same shock moves the chain "
             f"and the onset rate, so the worlds where either route fires are "
             f"largely the SAME worlds, and counting them separately "
             f"double-counts the overlap. Combining inside each regime and "
             f"mixing afterwards gives {both:.2%}. The gap is "
             f"{abs(naive-both)/both:.0%} of the answer -- small here only "
             f"because both routes are unlikely, and it would not stay "
             f"small if they were not.")
        print()
    share = out / both if both else 0.0
    para(f"The route nobody had written down carries {share:.0%} of the "
         f"total and raises the answer by "
         f"{(both/inside - 1) if inside else 0:.0%} in relative terms -- "
         f"from {inside:.1%} to {both:.1%}. Which is the useful shape of "
         f"result: the omission was real and it does not change the "
         f"verdict. A chain that had moved from 1% to 30% on one added "
         f"pathway would mean the original chain was answering a different "
         f"question.")
    print()
    if ov.get("why_this_is_not_the_same_event"):
        para("WHAT THIS BASE RATE IS NOT: "
             + ov["why_this_is_not_the_same_event"])
        print()
    para("AND NOTE WHAT THE GRADE AT THE TOP DOES NOT COVER. It is "
         "computed from the chain's links and nothing else, so it "
         "describes the "
         f"{inside:.1%} rather than the {both:.1%}. This block adds one "
         "measured number, the base rate, and one estimated one, the "
         "conditional -- roughly the same mix the chain already had, which "
         "is why folding it in would not move the band. The grade is still "
         "answering a slightly narrower question than the final line is.")
    print()
    return both


def report(d):
    links = check_observed(d["links"])
    if not links:
        print("  THIS CHAIN HAS NO LINKS, so there is nothing to multiply.")
        print()
        for k in ("_why_there_are_no_links", "_the_answer"):
            if d.get(k):
                para(str(d[k]))
                print()
        return
    links = apply_ways(links)
    d = dict(d, links=links)      # the caller's copy is never rewritten

    # influence = how much the claim loses to this link, which is what the
    # leave-one-out section computes further down
    point = 1.0
    for l in links:
        point *= l["p"]
    weights = [((point / l["p"] - point) if l["p"] > 0 else 0.0,
                l.get("provenance", "guessed"), l["id"]) for l in links]
    print_grade(weights, lambda t: wrap(t, 70))

    print("=" * 74)
    print("  THE CLAIM")
    print("=" * 74)
    print()
    para(d["claim"], indent="     ")
    print()
    if d.get("horizon_years", 0) > 60:
        print("  " + "-" * 70)
        para("NOBODY WILL EVER SCORE THIS. It resolves in "
             f"{d['horizon_years']:,} years. That is not a criticism of the "
             "belief, it is a fact about the sentence: a claim that cannot "
             "be checked by anyone alive is a worldview, not a forecast, "
             "and the ledger discipline that makes the rest of this project "
             "mean anything cannot touch it. The decomposition below is "
             "still worth doing -- it shows which part of the belief is "
             "load-bearing -- but the final number carries no track record "
             "and never will.")
        print()

    print("=" * 74)
    print("  THE CHAIN")
    print("=" * 74)
    print()
    print("      P(claim) = " + " x ".join(f"P{i+1}" for i in range(len(links))))
    print()
    run = 1.0
    for i, l in enumerate(links):
        prov = l.get("provenance", "guessed")
        run *= l["p"]
        rng_s = (f"[{l['low']:.2f}..{l['high']:.2f}]"
                 if l.get("low") is not None else "point")
        print(f" {MARK.get(prov,'?')}P{i+1}  {l['p']:.2f}  {rng_s:>14}"
              f"   running {run:>6.3f}   {l['id']}")
        para(l["statement"], indent="        ", w=64)
        if l.get("basis"):
            para("BASIS: " + l["basis"], indent="        ", w=64)
        if not l.get("basis"):
            print("        NO REFERENCE CLASS. A judgement written as a "
                  "decimal.")
        if l.get("_ways"):
            print_ways(l)
        print()

    point = run
    print("  " + "-" * 70)
    print(f"  POINT ESTIMATE: {point:.3f}  =  {point:.1%}")
    print()
    para("Note what the multiplication did. The least confident link is "
         f"{min(l['p'] for l in links):.2f}; the product is {point:.3f}. "
         "People state compound claims with the confidence of their "
         "strongest link, and this is the size of that error.")
    print()

    # ---- uncertainty over the links themselves -------------------------
    mc, lo5, hi95 = spread(links)
    print(f"  WITH THE LINKS THEMSELVES UNCERTAIN: {mc:.3f}"
          f"   (5th {lo5:.3f}, 95th {hi95:.3f})")
    print()
    chain_product = point

    # ---- dependence between the links, then the route it does not have --
    point, rinfo = regime_mixture(d, point)
    outside_view(d, point, rinfo)

    # ---- which link kills it? ------------------------------------------
    print("=" * 74)
    print("  HOW IT FAILS, when it fails")
    print("=" * 74)
    print()
    para("Each link set to CERTAIN in turn, everything else left alone. The "
         "rise is how much that link was costing the claim -- which is the "
         "same as how often it is the thing that kills it.")
    print()
    print("  {:<34}{:>10}{:>12}".format("if this were certain", "P becomes", "gain"))
    rows = []
    for i, l in enumerate(links):
        without = point / l["p"] if l["p"] > 0 else float("inf")
        rows.append((without - point, l, without))
    for gain, l, without in sorted(rows, reverse=True, key=lambda t: t[0]):
        print("  {:<34}{:>10.3f}{:>12.3f}".format(l["id"], without, gain))
    print()
    worst = max(rows, key=lambda t: t[0])[1]
    para(f"THE CLAIM DIES AT '{worst['id']}' MORE THAN ANYWHERE ELSE.")
    if worst.get("why_it_matters"):
        print()
        para(worst["why_it_matters"])
    print()

    # ---- and the opposite error ----------------------------------------
    multistage_check(d, links, chain_product)

    # ---- provenance ----------------------------------------------------
    print("=" * 74)
    print("  HOW MUCH OF THIS IS MADE UP")
    print("=" * 74)
    print()
    for prov in ("measured", "estimated", "guessed"):
        sel = [l for l in links if l.get("provenance", "guessed") == prov]
        print(f"   {prov:<12}{len(sel):>3} link(s)   "
              + ", ".join(l["id"] for l in sel))
    print()
    noref = [l for l in links if not l.get("basis")]
    if noref:
        para("No reference class at all: "
             + ", ".join("'" + l["id"] + "'" for l in noref)
             + ". Those are judgements written as decimals and multiplied "
               "with the rest, which lends them a precision they have not "
               "earned.")
        print()

    if d.get("scoreable_version"):
        print("=" * 74)
        print("  THE SAME BELIEF, IN A FORM THAT CAN BE SCORED")
        print("=" * 74)
        print()
        para("The long-horizon claim is unfalsifiable by construction. But a "
             "worldview that implies it also implies things about the next "
             "few years, and those resolve. If the near-term versions come "
             "out wrong, the long one was wrong for the same reasons.")
        print()
        for s in d["scoreable_version"]:
            print(f"   p={s['p']:.2f}  by {s['resolves']}")
            para(s["claim"], indent="        ", w=64)
            print()


def _both(p):
    """A probability both ways, in whichever base keeps it readable."""
    if p >= 0.01 or p <= 0:
        return f"{p * 100:.1f} in 100 ({(1 - p) * 100:.1f} not)"
    return f"{p * 1000:.1f} in 1,000 ({(1 - p) * 1000:.1f} not)"


def _times(x):
    return f"{x:.1f}" if x < 10 else f"{x:,.0f}"


def plan_audit(d, gut=None):
    """HOW DONE IS THIS PLAN? The short form of the chain report, with the
    author's own number set against it.

    The chain report answers "how likely is this". A person holding a plan
    usually wants something narrower: I feel 70% done, am I? So this puts
    the gut number next to the product, gives the spread, names the one
    step that swings it and the one to check first, and runs the
    multiple-stage check -- because an audit that only ever says "less
    done than you think" is a pessimism machine, not an audit.

    CHECK THIS FIRST is the step with the most to lose per unit of
    evidence behind it: its leave-one-out gain times the share of it that
    was NOT measured. A decisive step that was measured is less urgent
    than a decisive step that was guessed.
    """
    with contextlib.redirect_stdout(io.StringIO()):
        links = check_observed([dict(l) for l in d.get("links", [])])
    print("=" * 74)
    print("  HOW DONE IS THIS PLAN?")
    print("=" * 74)
    print()
    para(d.get("claim", "(no claim stated)"), indent="     ")
    print()
    if not links:
        para("No steps are written down, so there is nothing to multiply. "
             "List what has to go right, each step priced GIVEN the ones "
             "before it, and run this again.")
        return
    links = apply_ways(links)
    dd = dict(d, links=links)
    point = 1.0
    for l in links:
        point *= l["p"]
    mc, lo5, hi95 = spread(links)
    with contextlib.redirect_stdout(io.StringIO()):
        mixed, rinfo = regime_mixture(dd, point)
        final = outside_view(dd, mixed, rinfo)

    row = "  {:<16}{}"
    if gut is not None:
        print(row.format("YOUR GUT", _both(gut)))
    print(row.format("THE STEPS", _both(point)))
    base, word = (100, "100") if hi95 >= 0.01 else (1000, "1,000")
    print(row.format("THEIR SPREAD",
                     f"{lo5 * base:.1f} to {hi95 * base:.1f} in {word} (5th "
                     f"to 95th percentile, every step uncertain)"
                     if hi95 - lo5 > 1e-12 else
                     "none -- no step was given a range, so the product is "
                     "a single point"))
    extra = []
    if rinfo:
        extra.append("the common cause named")
    if d.get("outside_view"):
        extra.append("the route the steps do not contain")
    if extra and abs(final - point) > 1e-12:
        print(row.format("WITH THE REST", _both(final) + "  -- with "
                         + " and ".join(extra)))
    print()
    marks = " × ".join(f"{l['p']:.2f}" + ("*" if l.get("_ways") else "")
                       for l in links)
    para(f"P = {marks} ≈ {point:.4f}", indent="     ", w=66)
    para("Each number is one step's chance, given that every step before "
         "it went through. × means multiplied by, ≈ means approximately, "
         "and P is the chance the whole plan comes off."
         + (" A * marks a step that combines other ways through, or "
            "retries." if any(l.get("_ways") for l in links) else ""),
         indent="     ", w=66)
    print()

    if gut is not None and final > 0:
        ratio = gut / final
        if ratio > 1.25:
            odds = ((gut / (1 - gut)) / (final / (1 - final))
                    if 0 < gut < 1 and final < 1 else float("inf"))
            para(f"Your number is {_times(ratio)} times the last figure "
                 f"above ({_times(odds)} times in odds). That gap is the "
                 f"part of the plan not yet paid for -- or, if the "
                 f"multiple-stage check below fires, partly the price of "
                 f"multiplying guesses.")
        elif ratio < 0.8:
            para("The steps give MORE than your gut. Either one hurdle is "
                 "being counted twice in your head, or a step below is "
                 "priced too generously.")
        else:
            para("Your gut and the steps agree, within a quarter either way.")
        print()

    gains = [((point / l["p"] - point) if l["p"] > 0 else float("inf"), l)
             for l in links]
    g_swing, swing = max(gains, key=lambda t: t[0])
    g_first, first = max(gains, key=lambda t: t[0] * (1 - PROV_SCORE.get(
        t[1].get("provenance", "guessed"), 0.0)))
    print("  THE STEP THAT SWINGS IT")
    para(f"'{swing['id']}' at {swing['p']:.2f}. If it were certain, the "
         f"steps would give {_both(min(1.0, point + g_swing))}. "
         + swing["statement"])
    print()
    print("  CHECK THIS FIRST")
    if g_first * (1 - PROV_SCORE.get(first.get("provenance", "guessed"),
                                     0.0)) <= 0:
        para("Every step that matters was measured. What is left to check "
             "is the structure: a missing route, or steps that fail "
             "together.")
    elif first is swing:
        para(f"The same step, '{first['id']}'. It swings the answer most and "
             f"it is {first.get('provenance', 'guessed')}, not measured.")
    else:
        para(f"'{first['id']}' at {first['p']:.2f}. It costs the plan the "
             f"most for the least evidence behind it: it is "
             f"{first.get('provenance', 'guessed')}, while "
             f"'{swing['id']}' is "
             f"{swing.get('provenance', 'guessed')}.")
    print()
    print("  THE MULTIPLE-STAGE CHECK -- could this be too pessimistic?")
    found = multistage_findings(dd, links, point)
    if not found:
        para("Not the pattern: no stack of guessed middling steps, every "
             "later step says what it assumes, and other routes have been "
             "considered.")
        print()
    for _, text, _ in found:
        bullet(text)
        print()
    print("  WHAT MIGHT STILL BE MISSING")
    for q in ("Another way through any step, or a second attempt at it? "
              "Add it as `routes` or `attempts`.",
              "Steps that would succeed or fail together? Name the common "
              "cause as `regimes`.",
              "One hurdle written twice, cutting the product in half for "
              "free?"):
        bullet(q)
    print()
    para("Run `find_gaps` on this chain for the full hunt, and `chain` for "
         "the whole working.")


def elicit(d, name):
    """Emit a BLANK elicitation sheet for a chain.

    WHY THIS IS NOT THE DECISION SHEET WITH THE WORDS CHANGED

    A decision elicits magnitudes in some unit and asks for a transfer
    error alongside each one. A chain elicits CONDITIONAL PROBABILITIES,
    and that difference produces three requirements the decision sheet has
    no reason to carry.

    FIRST, the conditioning has to be forced. P2 in a chain is not "does
    the roof go on", it is "does the roof go on GIVEN that the walls are
    already up". An author who answers the marginal
    when the model multiplies conditionals has broken the arithmetic
    without touching a number, and the mistake is invisible afterwards
    because both answers are decimals between nought and one. So the sheet
    says it loudly and repeats it at every link.

    SECOND, the dependence has to be asked about directly. The damaging
    error in a chain is not a wrong link, it is the independence
    assumption. An author who prices every link and says nothing about how
    they relate has answered the easy part.

    THIRD, only the STATEMENTS go on the sheet, never the bases. That is
    easier here than in a decision: a chain's statement field describes an
    event and is neutral by construction, while the basis field is the
    argument for the number. Sending the argument would hand the new
    author the old author's conclusion and destroy the only thing a panel
    is for.

    WHAT THIS IS ACTUALLY FOR. When every number in a file has a single
    source, further passes by the same author cannot fix that -- they are
    the same prior re-expressed. Two authors who share a prior reduce the
    shared error by almost nothing, however strong they are.
    """
    links = d["links"]
    rg = d.get("regimes")
    print("=" * 74)
    print("ELICITATION SHEET  --  CHAIN")
    print("=" * 74)
    print()
    print("Paste everything below to another model, or fill it in yourself.")
    print("Do NOT show it the existing numbers, and do NOT show it the")
    print("reasoning already in the file. The entire value is in the")
    print("estimate being made independently; an author who has seen the")
    print("existing answer is not a second author, it is an echo.")
    print()
    print("-" * 74)
    print()
    print("THE CLAIM")
    para(d["claim"], indent="  ")
    print()
    print(f"  Horizon: {d.get('horizon_years','?')} years.")
    print()
    print("-" * 74)
    print()
    print("WHAT YOU ARE BEING ASKED FOR")
    print()
    para("This claim is broken into steps, and it holds only if EVERY step "
         "holds. For each step, give three numbers between 0 and 1:", "  ")
    print()
    print("    low / high : a range you would defend, not a 95% interval")
    print("    mode       : where you think it most likely sits")
    print()
    para("READ EACH STATEMENT AS A CONDITIONAL. Every step after the first "
         "is to be priced GIVEN that all the earlier ones have already "
         "happened -- not the chance it happens at all. These are the same "
         "kind of number and they are wildly different sizes, and answering "
         "the wrong one breaks the arithmetic without leaving a trace, "
         "because both are decimals between nought and one. Where a "
         "statement opens with 'Given...', that is what it means.", "  ")
    print()

    if rg:
        hi, lo = rg.get("names", ["crisis", "calm"])[0], \
                 rg.get("names", ["crisis", "calm"])[1]
        para(f"THIS CHAIN SPLITS THE WORLD IN TWO. The author before you "
             f"judged that the steps are not independent, and named a "
             f"common cause. You are asked to price every step TWICE -- "
             f"once in the world called '{hi}', once in the world called "
             f"'{lo}' -- and to say how likely that world is. If you think "
             f"the split is wrong, or that the cause named is the wrong "
             f"cause, say so in `objections`; that is worth more than the "
             f"numbers.", "  ")
        print()
        print(f"  THE TWO WORLDS")
        para(rg.get("elicit") or
             "[WARNING: no neutral description of the driver exists in "
             "this file, so the one below is the author's own framing and "
             "may carry their conclusion with it] " + rg["driver"], "    ")
        print()
        print(f"    P({hi}) at some point in the window = ___")
        print()

    print("-" * 74)
    for i, l in enumerate(links, 1):
        print()
        print(f"STEP {i}: {l['id']}")
        for line in wrap(l["statement"], 70):
            print("  " + line)
        if l.get("already_occurred"):
            print("  [this one has already happened -- price it 1.0]")
        if rg:
            print(f"    in '{hi}':  low = ___  high = ___  mode = ___")
            print(f"    in '{lo}':   low = ___  high = ___  mode = ___")
        else:
            print("    low = ___   high = ___   mode = ___")
    print()
    print("-" * 74)
    print()
    print("NOW THE PART THAT MATTERS MORE THAN THE NUMBERS")
    print()
    for q in [
        "MISSING ROUTE. These steps describe ONE way the claim could come "
        "true. What is a different way, which none of them describes? An "
        "unlisted route is priced at zero silently, and the answer still "
        "looks complete because every step that IS listed is present.",

        "DEPENDENCE. Which pairs of steps would succeed or fail together, "
        "and in which direction? Name the thing that would cause both. "
        "Multiplying the steps assumes that, given the earlier ones, each "
        "is independent -- and that assumption is usually doing more work "
        "than any single number in the sheet.",

        "ONE STEP TWICE. Could any two of these fail for exactly the same "
        "reason? If so they are one hurdle written twice, and multiplying "
        "them has cut the claim in half for free.",

        "TOO MANY STEPS. Every step added can only lower the answer, so a "
        "claim can be made arbitrarily unlikely by chopping it finer. Is "
        "each of these a genuinely separate hurdle that could fail on its "
        "own?",

        "THE CLAIM ITSELF. Restate it in one sentence using none of its "
        "own words. Does it still describe something worth knowing, and is "
        "it specific enough that one probability can cover it?",
    ]:
        for line in wrap(q, 70):
            print("  " + line)
        print()
    print("-" * 74)
    print()
    print("Return as JSON:")
    print()
    print("  {\"author\": \"<model name>\",")
    if rg:
        print(f"   \"q\": {{\"low\": _, \"high\": _, \"mode\": _}},")
        print("   \"links\": {\"<id>\": {\"" + hi + "\": {\"low\": _, "
              "\"high\": _, \"mode\": _},")
        print("                        \"" + lo + "\":  {\"low\": _, "
              "\"high\": _, \"mode\": _}}, ...},")
    else:
        print("   \"links\": {\"<id>\": {\"low\": _, \"high\": _, "
              "\"mode\": _}, ...},")
    print("   \"missing_routes\": [\"...\"],")
    print("   \"dependencies\":   [\"...\"],")
    print("   \"objections\":     [\"...\"]}")
    print()
    print(f"Save it as harness/panels/{name}/<author>.json, then run:")
    print(f"  python harness/panel.py {name}")


def main():
    if len(sys.argv) < 2:
        fs = sorted(f[:-5] for f in os.listdir(CHAINS) if f.endswith(".json"))
        print("chains:", ", ".join(fs))
        print("usage: chain.py <name> [elicit | audit [gut]]")
        return
    if len(sys.argv) > 2 and sys.argv[2] == "elicit":
        elicit(load(sys.argv[1]), sys.argv[1])
        return
    if len(sys.argv) > 2 and sys.argv[2] == "audit":
        plan_audit(load(sys.argv[1]),
                   float(sys.argv[3]) if len(sys.argv) > 3 else None)
        return
    report(load(sys.argv[1]))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
