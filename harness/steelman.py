#!/usr/bin/env python3
"""
steelman.py -- say what they MEANT before you audit what they WROTE.

WHERE THIS SITS. It runs first, ahead of everything:

    steelman  ->  router  ->  the eleven questions  ->  mirror
    what is         which        check the claim        audit your
    the claim       shape                               own correction

THE FAILURE IT EXISTS TO CATCH: an audit that attacks an illustration,
finds it wrong, and reports the argument refuted, when the argument never
rested on the illustration. That wins on a technicality and reports it as
a finding.

WHY THIS IS THE SAME DISEASE AS THE MIRROR. Reading someone at their
most literal while granting yourself interpretive latitude is an
isolated demand for rigor one level up. The mirror catches it inside
the arithmetic; this catches it before the arithmetic starts.

THE ONE THING THAT MAKES THIS AUDITABLE RATHER THAN GENEROUS: you must
declare what you SUPPLIED. A steelman built from words the author
never used is just a different claim, and possibly an easier one.
`supplied` is the field that keeps it honest, and it is required.

THE DOCTRINE IS UNCHANGED. Code asks; a model answers.

Run:  python harness/steelman.py
      python harness/steelman.py <case>
"""

import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import router as R  # noqa: E402


# --------------------------------------------------------------------
# the seven questions, asked BEFORE the eleven
# --------------------------------------------------------------------

STEELMAN = [
    {
        "id": "strongest_version",
        "ask": "State the claim as its most capable defender would put "
               "it, not as it was written. Someone speaking casually "
               "is not drafting a contract.",
        "why": "The words are a lossy encoding of the argument. "
               "Auditing the encoding and reporting on the argument is "
               "a category error, and it is the commonest way a "
               "correct-looking rebuttal misses entirely.",
    },
    {
        "id": "what_you_supplied",
        "ask": "List EVERY word, premise, number or connection you "
               "added to get there. Not a summary -- the actual list.",
        "why": "This is the only thing separating a steelman from a "
               "different and easier claim of your own invention. If "
               "you cannot list what you added, you have not "
               "steelmanned, you have substituted.",
    },
    {
        "id": "load_bearing_words",
        "ask": "Which words are load-bearing and which are incidental?",
        "why": "Attacking word choice looks like rigour and is "
               "usually pedantry. The test is whether correcting the "
               "word changes the conclusion.",
    },
    {
        "id": "different_mechanism",
        "ask": "Does the strongest version work through a DIFFERENT "
               "mechanism than the words suggest? Name both.",
        "why": "A weak illustration often sits on top of a strong "
               "mechanism. Refuting the illustration leaves the "
               "mechanism standing and untested.",
    },
    {
        "id": "which_are_you_auditing",
        "ask": "Which version are you about to check -- the literal "
               "one or the steelman? Say so before you start.",
        "why": "Undeclared, this is where the switch happens: refute "
               "the literal one, report as though you addressed the "
               "argument.",
    },
    {
        "id": "would_they_accept_it",
        "ask": "Would the author recognise your steelman as their "
               "argument? If you cannot ask them, say that it is your "
               "construction.",
        "why": "A steelman can be a strawman in the other direction "
               "-- an argument you find easier to engage with rather "
               "than the one they hold. Being generous is not the "
               "same as being accurate.",
    },
    {
        "id": "reduces_to_a_parameter",
        "ask": "Does the strongest version collapse to ONE measurable "
               "quantity? If so, name it. That is the whole argument.",
        "why": "The best steelmans do. 'Will this spiral out of "
               "control' becomes 'is R above 1', which is a number "
               "somebody can go and measure. That conversion is the "
               "single most valuable thing this step produces.",
    },
]


VERDICTS = {
    "SAME": "The literal claim and the strongest version are the same "
            "claim. Audit either. This is the easy case and it is "
            "rarer than you would like.",
    "STRENGTHENED": "The steelman is materially stronger than the "
                    "words. Audit the steelman and say that is what "
                    "you are doing.",
    "DIFFERENT_MECHANISM": "The strongest version works through a "
                           "different causal route than the wording "
                           "implies. Route the STEELMAN through the "
                           "eleven questions, not the words.",
    "TECHNICALITY": "YOU REFUTED THE LITERAL CLAIM AND THE STEELMAN "
                    "SURVIVES UNTOUCHED. This is a failure state, not "
                    "a finding. Do not publish it as one. Go back and "
                    "check the version that is actually load-bearing.",
}


# --------------------------------------------------------------------
# cases
# --------------------------------------------------------------------

try:  # optional worked examples, loaded when present
    from private_examples import STEELMAN_CASES as CASES
except ImportError:
    CASES = {}


def wrap(t, w=66, ind="   "):
    return R.wrap(t, w, ind)


def rule(c="=", w=74):
    print(c * w)


def report(name):
    case = CASES[name]
    rule()
    print("  THE STEELMAN -- " + case["title"])
    rule()
    print()
    print("  WHAT THEY WROTE")
    print(wrap(case["literal"], 68, "     "))
    print()
    print("  WHAT I ATTACKED")
    print(wrap(case["what_i_attacked"], 68, "     "))
    print()
    print("  WHAT THEY MEANT")
    print(wrap(case["steelman"], 68, "     "))
    print()
    print("  WHAT I SUPPLIED TO GET THERE")
    for s in case["supplied"]:
        print(wrap("- " + s, 66, "     "))
    print()
    rule("-")
    print("  THE SEVEN QUESTIONS")
    rule("-")
    for i, q in enumerate(STEELMAN, 1):
        print()
        print("  {}. {}".format(i, q["id"].upper().replace("_", " ")))
        print(wrap("ASK: " + q["ask"], 66, "     "))
        print()
        print(wrap("ANSWER: " + case["answers"].get(q["id"], "(unanswered)"),
                   66, "     "))
    print()
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
    """What gets appended to a published reply when the steelman and
    the literal claim differ."""
    case = CASES[name]
    out = ["WHAT I TOOK YOU TO MEAN", "",
           wrap(case["steelman"], 62, "   "), "",
           "   WHAT I ADDED TO GET THERE, WHICH YOU DID NOT SAY", ""]
    for s in case["supplied"]:
        out.append(wrap("- " + s, 60, "      "))
    out += ["", "   I AM AUDITING THE VERSION ABOVE, not the wording.",
            "   If that is not your argument, say so and I will run "
            "the one",
            "   you meant instead.", ""]
    ans = case["answers"].get("reduces_to_a_parameter", "")
    if ans and ans.lower().startswith("yes"):
        out += ["   IT REDUCES TO ONE NUMBER", wrap(ans, 60, "      "),
                ""]
    return "\n".join(out)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in CASES:
        report(sys.argv[1])
        rule("-")
        print("  WHAT GETS APPENDED TO THE PUBLISHED REPLY")
        rule("-")
        print()
        print(public_block(sys.argv[1]))
        return

    rule()
    print("  THE STEELMAN -- ask these BEFORE the eleven")
    rule()
    print()
    print(wrap(
        "The words are a lossy encoding of the argument. Audit the "
        "encoding, report on the argument, and you will produce true "
        "findings about points nobody was making. State the strongest "
        "version first, declare what you supplied to build it, and say "
        "which version you are checking.", 70, "  "))
    print()
    print("  ORDER OF OPERATIONS")
    print("  " + "-" * 68)
    print("     steelman  ->  router  ->  the eleven  ->  mirror")
    print("     what is       which       check the       audit your")
    print("     the claim     shape       claim           correction")
    print()
    for i, q in enumerate(STEELMAN, 1):
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
    print("  cases: " + ", ".join(CASES))
    print()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
