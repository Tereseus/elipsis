#!/usr/bin/env python3
"""
evidence.py -- how good is the evidence, and was the test any good?

TWO IMPORTS FROM OUTSIDE INTELLIGENCE TRADECRAFT, both filling gaps
this toolkit had.

1. GRADE (medicine). Rates certainty of evidence -- but the valuable
   part is its DEFINITION: certainty that the true value falls within
   a range "or above or below a decision-making threshold."

   That clause fixes a common mistake: treating certainty as
   ABSOLUTE -- how wide is the interval. GRADE treats it as RELATIVE
   TO THE DECISION. A Frechet bound of 0 to 40%
   is useless in the abstract and completely decisive if the threshold
   is 50%.

   And it inverts a worry: adding more checks was supposed to make the
   tool say "cannot tell" more often. With a threshold, a wide
   interval often still decides, so this makes the tool answer MORE
   questions, not fewer.

2. SEVERITY (Deborah Mayo, error statistics). Evidence supports a
   claim only if the claim passed a test it COULD HAVE FAILED.

   This toolkit asks "is the claim fragile" -- does it survive a
   sweep. It never asked "was the sweep severe" -- could it have come
   out the other way. Those are different questions, and a claim can
   survive a weak test. A mirror that only ever ran gentle tests would
   look identical to one that works.

Run:  python harness/evidence.py
      python harness/evidence.py worked
"""

import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import router as R  # noqa: E402


# --------------------------------------------------------------------
# GRADE
# --------------------------------------------------------------------

CERTAINTY = [
    ("HIGH", "Very confident the true value lies close to the "
             "estimate. Further work is very unlikely to change it."),
    ("MODERATE", "Moderately confident. The true value is likely "
                 "close, but could be substantially different."),
    ("LOW", "Confidence is limited. The true value may be "
            "substantially different from the estimate."),
    ("VERY LOW", "Very little confidence. The true value is likely "
                 "substantially different. Say this out loud rather "
                 "than quoting the estimate."),
]

# The six things that drag certainty DOWN, from GRADE.
DOWNGRADE = [
    ("risk_of_bias", "Was the study or source built in a way that "
                     "could systematically favour one answer?"),
    ("inconsistency", "Do independent attempts at the same question "
                      "disagree with each other?"),
    ("indirectness", "Was it measured on a different population, "
                     "intervention or outcome than the one you care "
                     "about?"),
    ("imprecision", "Is the interval wide enough that both sides of "
                    "the decision sit inside it?"),
    ("publication_bias", "Would a result pointing the other way have "
                         "been published, or does the record only "
                         "contain the findings somebody wanted?"),
    ("dissemination_bias", "Even if published, would it have "
                           "circulated? A correct finding nobody "
                           "repeated is not in the evidence base you "
                           "actually sampled."),
]


def decides(lo, hi, threshold):
    """Does this interval settle the decision?

    The whole point of GRADE's framing. Precision only matters
    relative to the threshold you are deciding against.
    """
    if hi < threshold:
        return ("DECIDED - BELOW",
                "The entire interval sits below the threshold. You do "
                "not know the value and you do not need to.")
    if lo > threshold:
        return ("DECIDED - ABOVE",
                "The entire interval sits above the threshold. Same "
                "again: precision is irrelevant here.")
    return ("STRADDLES",
            "The threshold sits inside the interval. This is the only "
            "case where narrowing the estimate is worth paying for.")


# --------------------------------------------------------------------
# severity
# --------------------------------------------------------------------

SEVERITY = [
    {
        "id": "could_it_have_failed",
        "ask": "If the claim were false, would this test have shown "
               "it? Describe the specific result that would have "
               "refuted it.",
        "why": "If you cannot name the failing result, you did not "
               "run a test. You ran a demonstration.",
    },
    {
        "id": "did_you_look_where_it_would_break",
        "ask": "Did you check the conditions most likely to break the "
               "claim, or the ones nearest to hand?",
        "why": "Sweeping two start dates is not a specification "
               "curve. Sweeping the two that were easiest to find is "
               "a weak test wearing the name of a strong one.",
    },
    {
        "id": "was_the_alternative_given_a_chance",
        "ask": "Did the rival explanation get priced, or only "
               "mentioned?",
        "why": "Naming a confounder and moving on is not testing "
               "against it.",
    },
    {
        "id": "severity_of_the_passing_test",
        "ask": "Of all the ways this claim could have died, how many "
               "did you actually point at it? Give the number.",
        "why": "A claim that survived one question is not 'robust'. "
               "It is untested in ten other directions and you can "
               "count them.",
    },
    {
        "id": "would_a_false_claim_look_the_same",
        "ask": "Construct a false version of the claim. Would your "
               "evidence have looked any different?",
        "why": "The sharpest form of the question, and the fastest. "
               "If a false claim produces the same evidence, the "
               "evidence carries no information about which one you "
               "have.",
    },
]

VERDICTS = {
    "SEVERE": "The claim passed a test it could plausibly have "
              "failed. This is the only case where surviving means "
              "something.",
    "WEAK": "The claim survived, but the test could not realistically "
            "have refuted it. Surviving is not evidence. Say so.",
    "DEMONSTRATION": "No failing result was specified. Nothing was "
                     "tested; something was illustrated. Do not "
                     "report it as support.",
}


# --------------------------------------------------------------------
# worked examples
# --------------------------------------------------------------------

try:  # optional worked examples, loaded when present
    from private_examples import EVIDENCE_WORKED as WORKED
except ImportError:
    WORKED = []


def wrap(t, w=66, ind="   "):
    return R.wrap(t, w, ind)


def rule(c="=", w=74):
    print(c * w)


def worked():
    rule()
    print("  WHEN A WIDE INTERVAL STILL DECIDES")
    rule()
    print()
    print(wrap(
        "GRADE's definition: certainty that the true value falls in a "
        "range OR ABOVE OR BELOW A DECISION THRESHOLD. Precision only "
        "has to beat the threshold, not be good in the abstract.",
        70, "  "))
    print()
    print("  {:<44}{:>12}{:>14}".format("case", "interval", "verdict"))
    print("  " + "-" * 70)
    for w in WORKED:
        v, _ = decides(w["lo"], w["hi"], w["threshold"])
        print("  {:<44}{:>12}{:>14}".format(
            w["case"][:42],
            "{:.0%}-{:.0%}".format(w["lo"], w["hi"]),
            v.split(" - ")[0]))
    print()
    for w in WORKED:
        v, expl = decides(w["lo"], w["hi"], w["threshold"])
        print("  " + "-" * 70)
        print("  " + w["case"])
        print("     interval   {:.1%} to {:.1%}".format(w["lo"], w["hi"]))
        print("     threshold  {:.0%}".format(w["threshold"]))
        print(wrap("why that threshold: " + w["why_threshold"], 64,
                   "     "))
        print()
        print("     " + v)
        print(wrap(expl, 64, "     "))
        print(wrap(w["note"], 64, "     "))
        print()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "worked":
        worked()
        return

    rule()
    print("  EVIDENCE -- GRADE certainty, and Mayo severity")
    rule()
    print()
    print("  CERTAINTY, four levels (GRADE)")
    print("  " + "-" * 68)
    for k, v in CERTAINTY:
        print()
        print("   " + k)
        print(wrap(v, 62, "     "))
    print()
    print("  " + "-" * 68)
    print("  SIX THINGS THAT DRAG CERTAINTY DOWN")
    print("  " + "-" * 68)
    for k, v in DOWNGRADE:
        print()
        print("   " + k.upper().replace("_", " "))
        print(wrap(v, 62, "     "))
    print()
    print("  " + "-" * 68)
    print("  AND THE PART THAT MATTERS MOST")
    print("  " + "-" * 68)
    print()
    print(wrap(
        "Certainty is relative to a DECISION THRESHOLD, not absolute. "
        "Before asking how precise an estimate is, ask what it is "
        "being compared against. A 0-to-40% interval is useless in "
        "the abstract and decisive against a 50% threshold.", 68, "  "))
    print()
    rule("-")
    print("  SEVERITY -- was the test capable of failing?")
    rule("-")
    print()
    print(wrap(
        "Mayo's criterion: evidence supports a claim only if the "
        "claim passed a test it COULD HAVE FAILED. This toolkit asks "
        "whether a claim is fragile. It never asked whether the sweep "
        "was severe. A claim can survive a weak test, and a mirror "
        "that only ran gentle tests would look identical to one that "
        "works.", 68, "  "))
    print()
    for i, q in enumerate(SEVERITY, 1):
        print("  {}. {}".format(i, q["id"].upper().replace("_", " ")))
        print(wrap(q["ask"], 64, "       "))
        print(wrap("WHY: " + q["why"], 64, "       "))
        print()
    print("  " + "-" * 68)
    print("  VERDICTS")
    print("  " + "-" * 68)
    for k, v in VERDICTS.items():
        print()
        print("   " + k)
        print(wrap(v, 62, "     "))
    print()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
