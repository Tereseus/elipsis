#!/usr/bin/env python3
"""
mirror.py -- run the audit on your own correction.

THE ATTACK THIS ANSWERS, AND IT IS THE ONE WITH NO OTHER ANSWER.

A reply that sweeps somebody's number and leaves its own number
unswept has applied rigour to one side. Every individual finding can
be correct and the aggregate output still systematically biased,
because scrutiny only ever pointed one way. Scott Alexander's name for
it is an isolated demand for rigor, and it is the strongest available
objection to this whole project precisely because it is structural
rather than a matter of execution.

The fix is not a disclaimer. A CORRECTION IS A CLAIM. So point the
same eleven questions at it and publish what comes back.

A mirror that never fires is broken.

THE DOCTRINE IS UNCHANGED. The code asks; a model answers. Nothing
here infers whether a shape fires -- it generates the questions, holds
the answers somebody supplied, and does the arithmetic.

Run:  python harness/mirror.py
      python harness/mirror.py <case>
"""

import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import router as R  # noqa: E402


# --------------------------------------------------------------------
# the seven questions to ask of a correction
# --------------------------------------------------------------------

MIRROR = [
    {
        "id": "same_shape_back",
        "ask": "You said they made a choice at some point without "
               "declaring it. Did YOU make a choice at that same "
               "point? Name yours out loud.",
        "why": "The commonest failure. Sweeping their denominator and "
               "then quietly fixing your own is the whole objection "
               "in miniature.",
    },
    {
        "id": "new_shape_introduced",
        "ask": "Does your correction introduce a NEW analytic choice "
               "the original did not have -- a start date, a "
               "population, a baseline? Run the eleven questions on "
               "your own number and say which fire.",
        "why": "A correction can be more hostage to choices than the "
               "claim it corrects, and nobody checks because the "
               "correction arrives wearing the working.",
    },
    {
        "id": "constant_out_of_scope",
        "ask": "Did you import a published number and apply it "
               "outside the population it was measured on? Say so on "
               "the line where you use it, not in a footnote.",
        "why": "A citation makes a judgement call look like settled "
               "arithmetic. That is the mechanism of authority "
               "laundering and it is invisible to readers.",
    },
    {
        "id": "asymmetric_precision",
        "ask": "Did you demand a standard of them that your own "
               "number does not meet -- a stated rule, a "
               "pre-registered baseline, an interval?",
        "why": "Demanding a stated scoring rule while not stating "
               "yours is the same error one paragraph apart.",
    },
    {
        "id": "unswept_residual",
        "ask": "Your final number has a range. What is it, and did "
               "you report it, or just the point?",
        "why": "You objected that their point estimate hid a spread. "
               "Yours has one too.",
    },
    {
        "id": "direction_of_convenience",
        "ask": "Does your correction happen to move the answer toward "
               "something you already believed? If every correction "
               "you publish moves the same way, that is a finding "
               "about you.",
        "why": "Bias does not announce itself; it has to be counted.",
    },
    {
        "id": "decision_relevance",
        "ask": "Does your correction FLIP a conclusion, RESIZE one, "
               "or neither? Answer before publishing.",
        "why": "'Technically right and practically nothing' is a real "
               "verdict and saying it out loud is more credible than "
               "implying it mattered.",
    },
]


VERDICTS = {
    "HOLDS": "The claim survives the sweep. The number is what they "
             "said it was. PUBLISHING THESE IS WHAT MAKES THE REST "
             "MEAN ANYTHING -- a test that never passes carries no "
             "information.",
    "RESIZED": "The conclusion survives, the number does not. Say "
               "which conclusion survived.",
    "REVERSED": "The sweep changes the sign or the direction, not "
                "just the size.",
    "UNCHECKABLE": "The claim cannot be assessed from what is "
                   "available. Different from being wrong, and worth "
                   "saying.",
}


PROVENANCE = {
    "MEASURED": "taken from a source, used inside the population it "
                "was measured on",
    "EXTENDED": "taken from a source, applied OUTSIDE its measured "
                "scope -- this is a judgement, not a citation",
    "MINE": "my own construction: a reference class I drew, a "
            "boundary I chose, a step I invented",
}


# --------------------------------------------------------------------
# cases
# --------------------------------------------------------------------

try:  # optional worked examples, loaded when present
    from private_examples import MIRROR_CASES as CASES
except ImportError:
    CASES = {}


# --------------------------------------------------------------------
# arithmetic
# --------------------------------------------------------------------

def family(series, year):
    return sum(series[year].values())


def sweep_windows(case):
    """The correction's own start-date sweep, which it never ran."""
    s = case["series"]
    end = max(s)
    rows = []
    for t0 in sorted(s):
        if t0 == end:
            continue
        a, b = family(s, t0), family(s, end)
        rows.append((t0, end, a, b, b - a))
    return rows


def sweep_denominators(case):
    """The correction reported a rate on a denominator it had just
    called unusable. This is what the rate does once you admit you do
    not know the denominator.

    Of N items that have come due, n were checked and k of those were
    hits. The N-n unchecked ones could be anything, so:

        r_min = k_low / N          every unchecked one a miss
        r_max = (k_high + N - n) / N   every unchecked one a hit
    """
    c = case["counts"]
    kl, kh, n = c["k_low"], c["k_high"], c["n_checked"]
    rows = []
    for N in case["denominators"]:
        lo = kl / float(N)
        hi = (kh + (N - n)) / float(N)
        rows.append((N, lo, hi, hi - lo))
    return rows


def sweep_rows(case):
    """Dispatch to whichever sweep this case's error needs."""
    return {"window": sweep_windows,
            "denominator": sweep_denominators}[case["recompute"]](case)


def wrap(t, w=66, ind="   "):
    return R.wrap(t, w, ind)


def rule(c="=", w=74):
    print(c * w)


# --------------------------------------------------------------------
# report
# --------------------------------------------------------------------

def symmetry_table(case):
    ids = [s["id"] for s in R.SHAPES]
    a = set(case["fired_on_original"])
    b = set(case["fired_on_correction"])
    print("  {:<22}{:>12}{:>14}".format(
        "shape", "the claim", "my correction"))
    print("  " + "-" * 60)
    only_mine = []
    for i in ids:
        if i not in a and i not in b:
            continue
        ta = "FIRED" if i in a else "--"
        tb = "FIRED" if i in b else "--"
        flag = ""
        if i in b and i not in a:
            flag = "   <-- ONLY ON MINE"
            only_mine.append(i)
        print("  {:<22}{:>12}{:>14}{}".format(i, ta, tb, flag))
    print()
    print("  {:<46}{:>6}".format("shapes firing on the claim", len(a)))
    print("  {:<46}{:>6}".format("shapes firing on my correction", len(b)))
    print("  {:<46}{:>6}".format(
        "firing ONLY on my correction", len(only_mine)))
    print()
    if only_mine:
        print(wrap(
            "That last number is the whole point of this file. Every "
            "shape in it is something I did to them after objecting "
            "to it being done. " + ", ".join(only_mine) + ".", 68, "  "))
    else:
        print(wrap(
            "Nothing fires only on the correction. That is the good "
            "case and it should be stated in the reply, because a "
            "mirror nobody ever sees fire is not evidence of "
            "anything.", 68, "  "))
    print()






try:  # optional worked re-runs, loaded when present
    from private_examples import recompute_window, recompute_denominator
except ImportError:
    def recompute_window(case):
        pass

    def recompute_denominator(case):
        pass


def report(name):
    case = CASES[name]
    rule()
    print("  THE MIRROR -- " + case["title"])
    rule()
    print()
    print("  THE CLAIM")
    print(wrap(case["original"], 68, "     "))
    print()
    print("  MY CORRECTION")
    print(wrap(case["correction"], 68, "     "))
    print()
    rule("-")
    print("  SIDE BY SIDE")
    rule("-")
    print()
    symmetry_table(case)
    rule("-")
    print("  THE SEVEN QUESTIONS")
    rule("-")
    for i, q in enumerate(MIRROR, 1):
        print()
        print("  {}. {}".format(i, q["id"].upper().replace("_", " ")))
        print(wrap("ASK: " + q["ask"], 66, "     "))
        print()
        ans = case["answers"].get(q["id"], "(unanswered)")
        print(wrap("ANSWER: " + ans, 66, "     "))
    print()
    rule("-")
    {"window": recompute_window,
     "denominator": recompute_denominator}[case["recompute"]](case)
    rule()
    v = case["verdict"]
    print("  VERDICT: " + v)
    rule()
    print()
    print(wrap(VERDICTS[v], 68, "  "))
    print()
    print(wrap(case["closing"], 68, "  "))
    print()


def public_block(name):
    """The compact thing that gets appended to a published reply."""
    case = CASES[name]
    a = set(case["fired_on_original"])
    b = set(case["fired_on_correction"])
    only = [i for i in b if i not in a]
    out = ["WHAT I DID THAT THEY ALSO DID", ""]
    if not only:
        out.append("   Nothing. The same eleven questions were run on "
                   "my own")
        out.append("   number and none fired that did not fire on "
                   "theirs.")
    else:
        for i in only:
            note = case.get("notes", {}).get(i)
            if not note:
                raise KeyError(
                    "case '{}' has no note for shape '{}'. Every shape "
                    "that fires on your own correction needs its own "
                    "objection written out, or the public block "
                    "quotes the wrong one at the reader.".format(
                        name, i))
            out.append("   " + i)
            out.append(wrap(note, 62, "      "))
            out.append("")
    out += ["   THE SWEEP, RUN ON MY OWN NUMBER", ""]
    if case["recompute"] == "window":
        for t0, t1, x, y, d in sweep_windows(case):
            out.append("      {} to {}   {:+.1f} points".format(
                t0, t1, d))
    else:
        for N, lo, hi, w in sweep_denominators(case):
            out.append("      N = {:<4}  {:.0f}% to {:.0f}%".format(
                N, 100 * lo, 100 * hi))
    out += ["", "   VERDICT: " + case["verdict"],
            "   DOES IT FLIP A CONCLUSION? "
            + ("Yes." if case["verdict"] == "REVERSED" else "No.")]
    return "\n".join(out)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in CASES:
        report(sys.argv[1])
        print()
        rule("-")
        print("  WHAT GETS APPENDED TO THE PUBLISHED REPLY")
        rule("-")
        print()
        print(public_block(sys.argv[1]))
        print()
        return

    rule()
    print("  THE MIRROR -- run the audit on your own correction")
    rule()
    print()
    print(wrap(
        "A correction is a claim. Point the same eleven questions at "
        "it and publish what comes back. Without this the output is "
        "an isolated demand for rigor: every finding correct, the "
        "aggregate biased, because scrutiny only ever went one way.",
        68, "  "))
    print()
    for i, q in enumerate(MIRROR, 1):
        print("  {}. {}".format(i, q["id"].upper().replace("_", " ")))
        print(wrap(q["ask"], 64, "       "))
        print(wrap("WHY: " + q["why"], 64, "       "))
        print()
    rule("-")
    print("  VERDICTS")
    rule("-")
    for k, v in VERDICTS.items():
        print()
        print("  " + k)
        print(wrap(v, 64, "     "))
    print()
    rule("-")
    print("  WHERE EVERY NUMBER IN A REPLY CAME FROM")
    rule("-")
    for k, v in PROVENANCE.items():
        print()
        print("  " + k)
        print(wrap(v, 64, "     "))
    print()
    print("  cases: " + ", ".join(CASES))
    print()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
