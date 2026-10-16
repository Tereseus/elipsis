#!/usr/bin/env python3
"""
publish.py -- which questions this tool must not answer in public, and what
              an honest disclaimer actually says.

Two separate problems, and only one of them is about wording.

THE FIRST IS A REFUSAL CLASS, NOT A CAVEAT.

Some questions turn the model into a weapon by being answered at all. The
clearest is attribution: publish "21% actor A, 17% actor B" for an attack
and you have not described the world, you have published a scoring function.
An actor who wants to act and be misread now knows exactly which signals to
plant, and the model cannot detect a well-executed false flag by
construction -- if the signals are planted, the model reads the planted
signals and reports them as evidence.

So attribution is not a question to answer carefully. It is a question to
decline: answering does not adjust the frame, it inverts what the output
does. A number that names an actor who can move the inputs is an
instruction, not an estimate.

THE SECOND IS THAT "1% ACCURATE" IS ITSELF A FAKE NUMBER.

It sounds humble and it is not. It is unfalsifiable, it invites the reader
to round it mentally to "well, it is something", and it is not even the
right kind of quantity -- a model that says 70% and is right 70% of the
time is perfectly calibrated, not 70% accurate. Probabilistic forecasts do
not have an accuracy. They have a CALIBRATION, and calibration has to be
measured against resolved outcomes rather than asserted.

The honest disclaimer is therefore three computed numbers and no adjectives:
what share of the answer was measured, how wrong every input could be
before the answer flips, and the author's actual Brier score against a
naive baseline. All three come out of the tool. None of them is a
self-assessment.

Run:  python harness/publish.py <decision-or-chain>
"""

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


# Question classes that get worse, not better, by being answered in public.
# The test is not sensitivity. It is whether a named party can MOVE THE
# INPUTS once they know the output.
REFUSE = [
    ("attribution",
     ["who did", "who was behind", "responsible for", "false flag",
      "attributable to", "perpetrator", "which actor", "who carried out"],
     "ATTRIBUTION OF AN ACT TO AN ACTOR. Publishing a probability that "
     "names a suspect publishes the scoring function an adversary needs to "
     "be misread. The model cannot detect a competent false flag, because "
     "planted signals are exactly the signals it reads."),
    ("targeting",
     ["which target", "most vulnerable", "weakest point", "where to strike",
      "best place to attack", "least defended"],
     "TARGET SELECTION. An ordered list of vulnerabilities is an operational "
     "product regardless of the intent behind the question."),
    ("named private individual",
     ["is he", "is she", "did he", "did she", "this person"],
     "A NAMED PRIVATE INDIVIDUAL. A probability attached to a person who "
     "cannot answer back is not analysis."),
]

# Classes that are fine to publish and get BETTER for it, because the game
# is coordination rather than conflict.
ENCOURAGE = (
    "Questions where publication helps are the ones where the parties want "
    "to find a shared answer: infrastructure, energy routing, disaster "
    "preparedness, trade terms, anything where several parties each run "
    "their own model and the useful output is where those models disagree. "
    "That disagreement separates a fight about FACTS, which evidence can "
    "settle, from a fight about VALUES, which it cannot -- and knowing "
    "which one you are in is most of what a negotiation needs.")


def screen(text):
    t = (text or "").lower()
    hits = []
    for name, pats, why in REFUSE:
        if any(p in t for p in pats):
            hits.append((name, why))
    return hits


def disclaimer(measured_share, error_tolerance, brier, baseline):
    """Three computed numbers. No adjectives, no self-assessed accuracy."""
    return [
        "WHAT THIS IS",
        "",
        "A consistency check on stated beliefs, not a forecast. It computes "
        "what a set of assumptions implies and which of them the answer "
        "depends on. It knows nothing about the world that somebody did not "
        "type into it.",
        "",
        "THREE NUMBERS, ALL COMPUTED, NONE ASSERTED",
        "",
        f"  {measured_share:.0%} of what drives this answer was MEASURED.",
        "     The rest is judgement anchored on historical cases.",
        "",
        f"  {error_tolerance:.0%} ERROR TOLERANCE. Every input would have to "
        "be wrong",
        "     by that much, all in the worst direction at once, before the",
        "     answer reverses. This is not a probability.",
        "",
        f"  BRIER {brier:.3f} against a naive baseline of {baseline:.3f}.",
        "     The author's actual record on resolved predictions. Lower is",
        "     better. Above the baseline means worse than assuming nothing",
        "     changes.",
        "",
        "WHAT IT CANNOT DO",
        "",
        "It cannot tell you that a whole factor is missing, because it only "
        "computes over what is in front of it. That error -- the wrong "
        "setup rather than the wrong number -- takes a person arguing to "
        "catch.",
    ]


def report(name):
    import decide as D
    try:
        d = D.load(name)
        kind = "decision"
    except Exception:
        import chain as C
        d = C.load(name)
        kind = "chain"

    text = d.get("decision") or d.get("claim", "")
    print("=" * 74)
    print("  PUBLICATION SCREEN")
    print("=" * 74)
    print()
    for line in D.wrap(text, 70):
        print("  " + line)
    print()
    hits = screen(text)
    if hits:
        print("  DO NOT PUBLISH THIS ONE.")
        print("  " + "-" * 70)
        for nm, why in hits:
            print(f"   class: {nm}")
            for line in D.wrap(why, 68):
                print("      " + line)
            print()
        print("  The objection is not that the answer is uncertain. It is "
              "that")
        print("  publishing the answer changes what the answer is for.")
    else:
        print("  NO REFUSAL CLASS TRIGGERED.")
        print("  " + "-" * 70)
        for line in D.wrap(ENCOURAGE, 70):
            print("  " + line)
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    report(sys.argv[1])


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
