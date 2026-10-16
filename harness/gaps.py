#!/usr/bin/env python3
"""
gaps.py -- the automated hunt for what is missing, and for what is in
           there twice under two names.

THE PROBLEM THIS ATTACKS

Every other tool here computes over what is in front of it. None of them
can say "you left out the thing that decides this" -- and that error, the
wrong setup rather than the wrong number, is the one that has actually
changed answers.

So: automate the argument. Not the judgement -- the QUESTIONS.

THE DIVISION OF LABOUR

Code generates the questions deterministically. A language model answers
them. Never the other way round.

That split matters more here than anywhere else, because of a distinction
worth being precise about. A language model's CALIBRATION is poor. But
calibration is a FORECASTING skill. "Does belief A restate belief B?" and
"what is the strongest argument against this range?" are RECALL tasks,
and they fail differently. Being bad at assigning probabilities does not
make you bad at noticing that two paragraphs describe the same thing.

So the model is used only where recall is the skill, and the code decides
what gets asked and in what order. Nothing here trusts the model to assign
a number.

THE THREE PASSES

  1. OVERLAP. Every pair of beliefs, ranked by how much vocabulary their
     descriptions share. The top pairs get asked "is this the same thing
     twice?" This is the n-squared problem made tractable by ordering it:
     fourteen beliefs make ninety-one pairs, and you only need to look at
     the ones that could plausibly collide.

  2. COUNTER. For each belief, ask for the strongest case that its range
     is wrong in each direction. One-sided sourcing is invisible from
     inside a model and obvious from outside it.

  3. OMISSION. A fixed checklist of the error classes that change
     answers, each phrased as a question the model can answer from the
     world rather than from the file.

WHEN TO STOP

Not at a fixed depth. Run a pass, add what it finds, run again, and stop
when a pass adds nothing. That is a convergence criterion rather than a
count, and it is the right shape because the number of passes you need is
a property of the question, not of the method. A hard cap exists only to
stop a loop that has found a way to keep restating itself.

Run:  python harness/gaps.py <decision>
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402  (sits next to this file)
sys.path.insert(0, HERE)
import decide as D                                        # noqa: E402
import chain as CH                                        # noqa: E402

STOP = set("""the a an and or of to in for on with by is are was were be been
that this those these it its as at from not no if then than so but which who
whom whose what when where how why can could would should will shall may might
must do does did done have has had having only just more most less least very
much many some any all both each other same such own too also into over under
between about against during before after above below up down out off further
because while both either neither one two three per cent percent year years
annual annually value cost gain loss benefit""".split())


def terms(s):
    ws = re.findall(r"[a-z]{4,}", (s or "").lower())
    return {w for w in ws if w not in STOP}


def overlap(a, b):
    """Jaccard on the description vocabulary. Crude on purpose -- it only
    has to ORDER the pairs, not judge them. The judging is the model's."""
    ta, tb = terms(a), terms(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# The error classes that change answers.
# Each is phrased so a model can answer it from the world, not from the file.
OMISSIONS = [
    ("the baseline pays nothing",
     "Does the do-nothing option carry any cost term at all? If not, what "
     "does continuing actually cost per year, and who is already paying it? "
     "A model that charges every alternative for changing and charges the "
     "status quo nothing for continuing is biased toward leaving things "
     "alone, and that bias is invisible from inside it."),
    ("an option nobody listed",
     "What is a fifth thing someone could do here that is not in the option "
     "list? The winning option is sometimes one nobody had written "
     "down."),
    ("waiting is not an option here",
     "Is 'decide later' on the list? Uncertainty that resolves on its own "
     "makes delay valuable, and a model without a wait option always "
     "recommends acting -- not because acting is better, but because the "
     "alternative was never offered."),
    ("somebody bears a cost with no term",
     "Who is affected by this decision and has no belief representing them? "
     "If the answer is a person or group outside the model, the model is "
     "not measuring them and its total is not a total."),
    ("two names, one thing",
     "Which two beliefs here would a stranger describe using the same "
     "sentence? Double counting changes the ANSWER, unlike correlation, "
     "which only changes the spread."),
    ("one source, several beliefs",
     "Do several ranges trace back to the same study, dataset or episode? "
     "Then they are one piece of evidence wearing several hats, and the "
     "model is treating it as independent confirmation."),
    ("the question is not the one being asked",
     "Restate the decision in one sentence without using any word from the "
     "original. Does it still describe what the person wants to know?"),
    ("what the opposite model looks like",
     "Build the model that reaches the opposite conclusion. Which "
     "assumptions differ? If the answer is 'one term', that term is the "
     "whole decision and everything else is decoration."),
]


PASSES = paths.data("passes")


def log_pass(name, findings):
    """Record what a pass found and say whether it converged.

    Convergence is the stopping rule rather than a fixed depth, because
    how many passes a question needs is a property of the question. A pass
    that finds nothing new is the signal to stop; a fixed count of eight is
    too many for a simple decision and too few for a tangled one.

    The findings themselves come from a model answering the questions this
    file generates. The code only keeps score.
    """
    import json
    os.makedirs(PASSES, exist_ok=True)
    f = os.path.join(PASSES, name + ".json")
    log = []
    if os.path.exists(f):
        with open(f, encoding="utf-8") as fh:
            log = json.load(fh)
    seen = {x for pas in log for x in pas}
    fresh = [x for x in findings if x not in seen]
    log.append(findings)
    with open(f, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(log, fh, indent=2, ensure_ascii=False)
    return len(log), fresh, seen


def show_convergence(name):
    import json
    f = os.path.join(PASSES, name + ".json")
    if not os.path.exists(f):
        print("  No passes recorded yet. Answer the questions above, then")
        print(f"  log them:  gaps.log_pass('{name}', ['what you found', ...])")
        return
    with open(f, encoding="utf-8") as fh:
        log = json.load(fh)
    print("  CONVERGENCE")
    print("  " + "-" * 70)
    seen = set()
    for i, pas in enumerate(log, 1):
        fresh = [x for x in pas if x not in seen]
        seen |= set(pas)
        print(f"   pass {i}: {len(pas):>2} findings, {len(fresh):>2} of them new")
        for x in fresh:
            print(f"        + {x}")
    if log and not [x for x in log[-1] if x not in
                    {y for pas in log[:-1] for y in pas}]:
        print()
        D.para("CONVERGED. The last pass found nothing the earlier ones had "
               "not. Stop here -- further passes restate rather than "
               "discover, and each one still costs the same to read.")
    else:
        print()
        D.para("NOT CONVERGED. The last pass still found something new, so "
               "run another.")
    print()



# ---------------------------------------------------------------------
# CHAINS ARE NOT DECISIONS AND THEY FAIL DIFFERENTLY.
#
# A decision compares options and the damaging error is double counting,
# because it moves the mean. A chain multiplies conditional probabilities
# and the damaging error is the INDEPENDENCE ASSUMPTION, because nobody
# states it, it is never written in the file, and it is doing more work
# than any single link in it.
#
# So the checklist below is a different checklist, not a reworded one.
# ---------------------------------------------------------------------

CHAIN_OMISSIONS = [
    ("a route nobody listed",
     "The chain prices ONE mechanism. What is a different way the same "
     "outcome could arrive, which none of these links describes? Every "
     "unlisted route is priced at zero silently, and the product still "
     "looks complete because all of ITS OWN links are present."),
    ("the links are not independent",
     "P = P1 x P2 x P3 assumes each link is conditional on everything "
     "before it. Two failures hide here. First, links written as "
     "MARGINALS and multiplied as if conditional -- P(the roof goes on) "
     "rather than P(the roof goes on GIVEN the walls are up). "
     "Second, two links driven by the same underlying thing, so that the "
     "world where one succeeds is the world where the other does too. "
     "Both push the product too low. Which pairs here share a driver?"),
    ("the chain is longer than the question",
     "Every link added can only lower the number, so a claim can be made "
     "arbitrarily unlikely by decomposing it further. Is each link a "
     "genuinely separate hurdle that could fail on its own, or is one of "
     "them a restatement of the one before it under a different name? "
     "Splitting one hurdle into two does not make the world harder."),
    ("one link is the whole claim",
     "If a single link is far below the rest, the decomposition is "
     "decoration -- the claim is a one-link claim wearing three extra "
     "hats, and every other link is rounding. Say which link that is and "
     "whether the other links deserve their place."),
    ("a link has already resolved",
     "Has anything in this chain already happened, or already failed? A "
     "resolved link priced as a forecast is a known error. If it has happened, it is 1.0 and the rest of "
     "the chain has to carry the claim alone."),
    ("nobody will ever score this",
     "When does the claim resolve, and will anyone check? A horizon past "
     "a working lifetime makes the number a worldview rather than a "
     "forecast. If so, what NEAR-TERM claim does the same belief imply, "
     "which does resolve, and is it in the file?"),
    ("the claim is not the one being asked",
     "Restate the claim in one sentence using none of its own words. "
     "Does it still describe what the person wanted to know?"),
    ("what the opposite chain looks like",
     "Build the chain that reaches the opposite conclusion. Which link "
     "differs? If the answer is one link, that link is the whole claim "
     "and the rest is decoration."),
]


def dependence_bracket(links):
    """The arithmetic the independence assumption is hiding.

    Frechet bounds. For events with marginals p1..pn, the probability
    that ALL of them hold is bounded by

        max(0, sum(p) - (n-1))   <=   P(all)   <=   min(p)

    with no assumption whatsoever about how they relate. The independence
    product sits somewhere inside that interval, and where it sits tells
    you how much of the answer is coming from an assumption nobody wrote
    down rather than from the beliefs somebody did write down.

    This is the one part of a gaps run that is arithmetic rather than a
    question, and it belongs here because it is the chain-specific error.
    """
    ps = [l["p"] for l in links]
    n = len(ps)
    prod = 1.0
    for x in ps:
        prod *= x
    return {
        "product": prod,
        "upper": min(ps),
        "lower": max(0.0, sum(ps) - (n - 1)),
        "ratio": (min(ps) / prod) if prod else float("inf"),
    }


def chain_report(d, top_pairs=6):
    links = d["links"]
    n = len(links)
    print("=" * 74)
    print("  WHAT MIGHT BE MISSING FROM THIS CHAIN")
    print("=" * 74)
    print()
    D.para(f"{n} links. A chain fails differently from a decision: the "
           f"damaging error is not double counting, it is the independence "
           f"assumption, which is never written in the file and is doing "
           f"more work than any single link in it. So this starts with "
           f"arithmetic rather than a question.")
    print()

    b = dependence_bracket(links)
    print("  PASS 0 - HOW MUCH OF THE ANSWER IS THE INDEPENDENCE ASSUMPTION")
    print("  " + "-" * 70)
    print()
    print("   {:<44}{:>10}".format(
        "if the links were perfectly dependent", f"{b['upper']:.3f}"))
    print("   {:<44}{:>10}".format(
        "what the file computes (independent)", f"{b['product']:.3f}"))
    print("   {:<44}{:>10}".format(
        "the Frechet floor (worst case)", f"{b['lower']:.3f}"))
    print()
    D.para(f"Those bounds hold with NO assumption about how the links "
           f"relate. The independent product is {b['ratio']:.0f} times "
           f"smaller than the upper bound, and that factor is not a belief "
           f"anyone stated -- it is what independence buys, and it is "
           f"bigger than the effect of any single link being wrong.")
    print()
    rg = d.get("regimes")
    if rg:
        covered = [l["id"] for l in links if l.get("p_by_regime")]
        D.para(f"THIS FILE NO LONGER ASSUMES INDEPENDENCE. It carries a "
               f"`regimes` block naming a common driver at "
               f"P={rg['q']:.2f}, and {len(covered)} of {len(links)} links "
               f"are priced separately in each regime. The bracket above "
               f"still describes the naive product, which is printed for "
               f"comparison; the file's answer is the mixture. Note the "
               f"direction is not decided in advance -- naming a driver "
               f"can move the answer either way, because links that share "
               f"a cause do not all respond to it with the same sign.")
        if len(covered) < len(links):
            D.para("UNPRICED LINKS: "
                   + ", ".join(l["id"] for l in links
                               if not l.get("p_by_regime"))
                   + ". Those are being treated as independent of the "
                     "driver, which is a claim and should be a deliberate "
                     "one.")
    else:
        D.para("If any two links share a driver, the answer moves off the "
               "product -- and not necessarily upward. Name the driver and "
               "price each link in each of its regimes rather than fitting "
               "a correlation, because links sharing one cause can respond "
               "to it with opposite signs and a single coefficient cannot "
               "represent that.")
    print()

    print("  PASS 1 - SAME HURDLE TWICE?")
    print("  " + "-" * 70)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            a, c = links[i], links[j]
            ta = (a.get("statement", "") + " " + a.get("basis", ""))
            tc = (c.get("statement", "") + " " + c.get("basis", ""))
            pairs.append((overlap(ta, tc), a["id"], c["id"]))
    pairs.sort(reverse=True)
    for sc, x, y in pairs[:top_pairs]:
        print(f"   {sc:>5.2f} " + "#" * int(round(sc * 40)))
        print(f"         {x}")
        print(f"         {y}")
    print()
    D.para("ASK OF EACH: could one of these fail while the other succeeds? "
           "If not, they are one hurdle written twice, and multiplying them "
           "has halved the claim for free. Note this is the OPPOSITE "
           "correction from a decision, where double counting inflates. In "
           "a chain it deflates.")
    print()

    print("  PASS 2 - WHAT ARGUES AGAINST EACH LINK")
    print("  " + "-" * 70)
    D.para("For every link, the strongest case its probability is too high "
           "and the strongest that it is too low. Links with no basis block "
           "come first -- those are judgements written as decimals.")
    print()
    noref = [l for l in links if not l.get("basis")]
    withref = [l for l in links if l.get("basis")]
    for l in noref + withref:
        mark = "?" if not l.get("basis") else "~"
        rng = (f"[{l['low']:.2f}..{l['high']:.2f}]"
               if l.get("low") is not None else "point estimate")
        print(f"   {mark} {l['p']:.2f}  {rng:<16} {l['id']}")
    print()

    print("  PASS 3 - THE CHAIN OMISSION CHECKLIST")
    print("  " + "-" * 70)
    D.para("Eight error classes, and they are not the decision ones "
           "reworded. A chain has no options and no baseline, so half the "
           "decision checklist does not apply; and it has an independence "
           "assumption and a decomposition depth, which a decision does "
           "not.")
    print()
    for i, (name, q) in enumerate(CHAIN_OMISSIONS, 1):
        print(f"   {i}. {name.upper()}")
        for line in D.wrap(q, 66):
            print(f"      {line}")
        print()

    if d.get("outside_view"):
        print("  ALREADY ANSWERED")
        print("  " + "-" * 70)
        D.para("This chain already carries an outside_view block, so "
               "question 1 has been asked once and answered. That does not "
               "retire it -- one alternative route found is not evidence "
               "there is no second one.")
        print()


def report(d, top_pairs=8):
    us = d["uncertainties"]
    n = len(us)
    print("=" * 74)
    print("  WHAT MIGHT BE MISSING, AND WHAT MIGHT BE IN HERE TWICE")
    print("=" * 74)
    print()
    D.para(f"{n} beliefs means {n*(n-1)//2} pairs to check for double "
           f"counting. Ranked below by how much vocabulary each pair "
           f"shares, so the ones that could plausibly collide come first. "
           f"The ranking is arithmetic; the judgement is not.")
    print()

    print("  PASS 1 — SAME THING TWICE?")
    print("  " + "-" * 70)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = us[i], us[j]
            txt_a = (a.get("elicit", "") + " " + a.get("source", ""))
            txt_b = (b.get("elicit", "") + " " + b.get("source", ""))
            pairs.append((overlap(txt_a, txt_b), a["id"], b["id"]))
    pairs.sort(reverse=True)
    for sc, x, y in pairs[:top_pairs]:
        bar = "#" * int(round(sc * 40))
        print(f"   {sc:>5.2f} {bar}")
        print(f"         {x}")
        print(f"         {y}")
    print()
    D.para("ASK OF EACH: would a stranger describe both of these with the "
           "same sentence? If yes, merge them and halve the total -- do not "
           "keep both at half weight, which is a different and wrong "
           "correction.")
    print()

    print("  PASS 2 — WHAT ARGUES AGAINST EACH RANGE")
    print("  " + "-" * 70)
    D.para("For every belief, the strongest case that its range is too high, "
           "and the strongest that it is too low. One-sided sourcing is "
           "invisible from inside a model and obvious from outside one. "
           "Beliefs with no history block are listed first, because they "
           "have nothing behind them at all.")
    print()
    noref = [u for u in us if not u.get("history")]
    withref = [u for u in us if u.get("history")]
    for u in noref + withref:
        mark = "?" if not u.get("history") else "~"
        print(f"   {mark} {u['id']}   [{u['low']:,g} .. {u['high']:,g}]")
    print()

    print("  PASS 3 — THE OMISSION CHECKLIST")
    print("  " + "-" * 70)
    D.para("Not generic prompts. Each of these is an error class that "
           "changes answers, phrased so it can be answered from the world "
           "rather than from the file.")
    print()
    for i, (name, q) in enumerate(OMISSIONS, 1):
        print(f"   {i}. {name.upper()}")
        for line in D.wrap(q, 66):
            print(f"      {line}")
        print()

    print("  WHEN TO STOP")
    print("  " + "-" * 70)
    D.para("Run a pass. Add what it finds. Run again. Stop when a pass adds "
           "nothing new -- that is convergence, and it is the right "
           "criterion because the number of passes a question needs is a "
           "property of the question rather than of the method. A fixed "
           "depth of eight would be too many for a simple decision and too "
           "few for a tangled one.")
    print()
    D.para("AND STOP EARLIER THAN YOU WANT TO. Two independent arguments "
           "put the right size of a model like this at three or four "
           "moving parts: the square-root rule on what a sample can "
           "support, and the fact that checking grows as n-squared while "
           "the answer only grows as n. A pass that adds a ninth belief is "
           "usually making the model worse while making it feel better.")
    print()


def main():
    if len(sys.argv) < 2:
        fs = sorted(f[:-5] for f in os.listdir(D.DECISIONS)
                    if f.endswith(".json"))
        cs = sorted(f[:-5] for f in os.listdir(CH.CHAINS)
                    if f.endswith(".json"))
        print("decisions:", ", ".join(fs))
        print("chains:   ", ", ".join(cs))
        return
    name = sys.argv[1]
    dec = os.path.join(D.DECISIONS, name + ".json")
    chn = os.path.join(CH.CHAINS, name + ".json")
    if os.path.exists(dec):
        report(D.load(name))
    elif os.path.exists(chn):
        chain_report(CH.load(name))
    else:
        print(f"no decision or chain named '{name}'")
        return
    show_convergence(name)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
