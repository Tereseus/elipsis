#!/usr/bin/env python3
"""
loop.py -- can you just go and check instead?

THE QUESTION THAT COMES BEFORE EVERY OTHER TOOL IN THIS PROJECT, and
the one it never asked. Every module here -- the sweeps, the mirror,
the steelman, the Frechet bounds -- is COMPENSATION FOR A BROKEN
FEEDBACK LOOP. If you could just check, you would not need any of it.
You would check.

So the first output of an honest analysis toolkit is sometimes "put
this down and go and look", and until now it had no way to say that.

A thermostat holds a room at 20 degrees with no theory of
thermodynamics whatsoever. No heat-transfer equations, no knowledge of
the insulation, no weather forecast. It measures and corrects, and it
beats an open-loop system with an excellent model. LOOP QUALITY
SUBSTITUTES FOR MODEL QUALITY, and it is usually far cheaper to buy.

FOUR GATES, ALL OF WHICH MUST PASS before "go and measure" is the
right advice. Getting one of them wrong is how a fast data feed turns
into an expensive treadmill.

  1. RATE           is the loop faster than the thing it watches?
  2. CLOSURE        is the ERROR fed back, or only new input?
  3. RESOLUTION     can one cycle tell signal from noise?
  4. SURVIVABILITY  is the failure of a single cycle acceptable?

Gate 1 is the one people think of. Gate 2 is the one that quietly
fails in almost every "continuously updating" system ever built. Gate
4 is the one that stops you learning whether the bridge holds by
driving over it.

Run:  python harness/loop.py
      python harness/loop.py cases
"""

import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import router as R  # noqa: E402


# --------------------------------------------------------------------
# gate 1 -- rate
# --------------------------------------------------------------------

# These cut points are a CHOICE, not a measurement. Five corrections is
# roughly what a simple correcting controller needs to settle; one is a
# single shot with no second chance. Re-cut them if your domain
# disagrees -- and say so if you do.
FAST = 5.0
EVEN = 1.0


def rate(t_loop, t_change):
    """R = T_change / T_loop. How many corrections before it moves?

    Both times in the SAME unit. t_loop of None means the claim never
    resolves, which is a different and worse situation than slow.
    """
    if t_loop is None:
        return (None, "NO LOOP AT ALL",
                "The claim has no resolution date. You will never find "
                "out, so there is no error to feed back and no cycle "
                "to run. This is not a slow loop; it is an open one, "
                "and it is where most contested political claims live. "
                "The honest output here is a BOUND and a statement "
                "that the question is unresolvable, not a number.")
    if t_loop <= 0:
        return (float("inf"), "GO AND LOOK NOW",
                "It resolves immediately. Any analysis you do is more "
                "expensive than the observation. Stop and observe.")
    r = float(t_change) / float(t_loop)
    if r >= FAST:
        return (r, "MEASURE, DO NOT MODEL",
                "You get about {:.0f} corrections before the situation "
                "moves. That is enough for checking to beat "
                "forecasting outright. Running the full pipeline here "
                "buys an answer you could have had cheaper by "
                "waiting.".format(r))
    if r >= EVEN:
        return (r, "BOTH",
                "About {:.1f} corrections before the situation moves. "
                "The loop works but barely; a model earns its keep on "
                "the first cycle or two, and after that the "
                "measurements should take over. Do not let the model "
                "keep talking once the data arrives.".format(r))
    return (r, "MODEL ONLY, AND EXPECT TO BE WRONG",
            "You get about {:.2f} of a correction -- the situation "
            "turns over faster than you find out. Nothing you learn "
            "arrives in time to be applied. This is where the hard "
            "questions live, and the difficulty is "
            "NOT complexity.".format(r))


# --------------------------------------------------------------------
# gate 2 -- closure
# --------------------------------------------------------------------

CLOSURE = [
    {
        "id": "observable",
        "ask": "Can you measure the ERROR -- the gap between what you "
               "said and what happened -- not merely observe the "
               "outcome?",
        "why": "This requires having written down what you said, in "
               "advance, in terms that resolve. A forecast recorded "
               "as 'tensions will rise' has no error signal however "
               "clearly the outcome arrives.",
    },
    {
        "id": "attributable",
        "ask": "Can you separate your error from the noise of the "
               "process?",
        "why": "One observation of a random process is not an error. "
               "Being wrong once about a coin says nothing. See gate "
               "3 for how many cycles it actually takes.",
    },
    {
        "id": "actionable",
        "ask": "Is there a lever? Can the NEXT call be different "
               "because of what you learned?",
        "why": "Knowing you were wrong is worth nothing if the "
               "procedure that produced it cannot change. A great "
               "many dashboards are in this state and their owners "
               "believe they have a feedback loop.",
    },
]


def closure(observable, attributable, actionable):
    """All three, or it is not a closed loop however fast the data."""
    fails = []
    if not observable:
        fails.append("observable")
    if not attributable:
        fails.append("attributable")
    if not actionable:
        fails.append("actionable")
    if not fails:
        return ("CLOSED",
                "The error is measurable, distinguishable and "
                "actionable. This is a real loop.")
    return ("OPEN -- " + ", ".join(fails) + " failed",
            "THIS IS A TREADMILL, NOT A LOOP. New data arrives and "
            "the case is recomputed, but nothing corrects, because "
            "the error never comes back. It costs more than doing the "
            "analysis once and it feels like progress, which is the "
            "dangerous part. Re-running on new input is the INPUT "
            "half; the scoring step is what makes it a loop.")


# --------------------------------------------------------------------
# gate 3 -- resolution
# --------------------------------------------------------------------

def cycles_to_detect(sigma, delta):
    """n = (sigma / delta)^2 -- cycles before a real change is visible.

    Standard result: the noise in a mean of n observations falls as
    the square root of n, so seeing a shift of delta through noise of
    sigma needs roughly (sigma/delta) squared of them.
    """
    if delta == 0:
        return None
    n = (float(sigma) / abs(float(delta))) ** 2
    return n


def resolution(sigma, delta, cycles_available):
    n = cycles_to_detect(sigma, delta)
    if n is None:
        return (None, "NO SIGNAL",
                "A drift of zero is never detectable. You are watching "
                "noise.")
    if n <= cycles_available:
        return (n, "RESOLVABLE",
                "About {:.0f} cycles to see the real movement, and you "
                "have {:.0f}. The loop can actually detect "
                "something.".format(n, cycles_available))
    return (n, "CHASING NOISE",
            "About {:.0f} cycles needed and only {:.0f} available. "
            "Every correction you make inside that window is a "
            "response to noise, and correcting on noise AMPLIFIES it "
            "-- control engineers call it hunting. Slow the loop down "
            "or widen what counts as a change worth acting "
            "on.".format(n, cycles_available))


# --------------------------------------------------------------------
# gate 4 -- survivability
# --------------------------------------------------------------------

SURVIVABILITY = (
    "Is the failure of ONE cycle acceptable? A fast loop is not the "
    "same as an affordable one. You do not learn whether the bridge "
    "holds by driving over it, however quickly the answer comes back. "
    "Where a single failed cycle is catastrophic, irreversible or "
    "expensive beyond the value of the answer, gate 1 is irrelevant "
    "and you need the model even though checking would be faster. "
    "This is the whole reason destructive testing is done on samples "
    "and simulation is done on bridges.")


# --------------------------------------------------------------------
# worked cases
# --------------------------------------------------------------------

CASES = [
    {
        "name": "How long will this job take? (construction)",
        "t_loop": 8, "t_change": 78, "unit": "weeks",
        "loop_is": "estimate the job, do the job, compare",
        "change_is": "how fast your crew, suppliers and conditions "
                     "drift -- a year or two",
        "note": "The single clearest case for putting the pipeline "
                "down. Eight comparable jobs beats any amount of "
                "reasoning about this one.",
    },
    {
        "name": "Is there asbestos in this building?",
        "t_loop": 3, "t_change": 520, "unit": "days",
        "loop_is": "send the sample, get the lab result",
        "change_is": "the building does not change",
        "note": "Extreme R. And yet the base-rate error is still "
                "worth knowing, because the test is imperfect -- "
                "gate 1 passing does not make gate 3 pass.",
    },
    {
        "name": "Will this supplier deliver on time?",
        "t_loop": 3, "t_change": 52, "unit": "weeks",
        "loop_is": "one delivery",
        "change_is": "supplier stability -- staff, ownership, "
                     "capacity",
        "note": "Their last twenty deliveries are the answer. Their "
                "promise is not evidence about their promise.",
    },
]
try:  # optional worked examples, loaded when present
    from private_examples import LOOP_CASES
    CASES += LOOP_CASES
except ImportError:
    pass


def wrap(t, w=66, ind="   "):
    return R.wrap(t, w, ind)


def check(t_loop, t_change, unit="units"):
    """Gate 1 rendered, with the formula, substitution and legend."""
    r, verdict, expl = rate(t_loop, t_change)
    out = []
    out.append("CHECKING WHETHER YOU CAN JUST GO AND MEASURE INSTEAD")
    out.append("")
    if t_loop is None:
        out.append("   T_loop      never resolves")
    else:
        out.append("   T_loop      {} {}".format(t_loop, unit))
    out.append("   T_change    {} {}".format(t_change, unit))
    out.append("")
    out.append("   on paper       R = T_change / T_loop")
    if r is None:
        out.append("   substituted    undefined -- there is no T_loop")
    elif r == float("inf"):
        out.append("   substituted    resolves immediately")
    else:
        out.append("   substituted    R = {} / {} = {:.2f}".format(
            t_change, t_loop, r))
    out.append("")
    out.append("   LEGEND")
    out.append("     R          how many times you get to correct "
               "before")
    out.append("                the situation itself has moved on")
    out.append("     T_loop     how long from making the call until "
               "you")
    out.append("                find out whether it was right")
    out.append("     T_change   how long before the situation that "
               "produced")
    out.append("                the call has shifted enough that the "
               "right")
    out.append("                answer is now different")
    out.append("     /          divided by")
    out.append("     =          is equal to")
    out.append("")
    out.append("     R above {:.0f}  checking beats forecasting".format(
        FAST))
    out.append("     R near {:.0f}   you want both".format(EVEN))
    out.append("     R below {:.0f}  you never get to correct".format(
        EVEN))
    out.append("")
    out.append("   " + verdict)
    out.append(wrap(expl, 64, "   "))
    return "\n".join(out)


def cases():
    print("=" * 74)
    print("  WORKED CASES -- can you just go and check?")
    print("=" * 74)
    print()
    print("  {:<42}{:>9}{:>8}{:>13}".format(
        "question", "T_loop", "R", "verdict"))
    print("  " + "-" * 72)
    for c in CASES:
        r, v, _ = rate(c["t_loop"], c["t_change"])
        tl = "never" if c["t_loop"] is None else str(c["t_loop"])
        rs = "--" if r is None else "{:.1f}".format(r)
        print("  {:<42}{:>9}{:>8}{:>13}".format(
            c["name"][:40], tl, rs, v.split(",")[0].split(" --")[0][:12]))
    print()
    for c in CASES:
        r, v, expl = rate(c["t_loop"], c["t_change"])
        print("  " + "-" * 72)
        print("  " + c["name"])
        print()
        print("     T_loop     {}  ({})".format(
            "never" if c["t_loop"] is None
            else "{} {}".format(c["t_loop"], c["unit"]), c["loop_is"]))
        print("     T_change   {} {}  ({})".format(
            c["t_change"], c["unit"], c["change_is"]))
        if r is not None and r != float("inf"):
            print("     R          {:.1f}".format(r))
        print()
        print("     " + v)
        print(wrap(expl, 62, "     "))
        print()
        print(wrap(c["note"], 62, "     "))
        print()
    print("  " + "-" * 72)
    print(wrap(
        "HOW ROUGH: every number above is an order-of-magnitude figure "
        "chosen to illustrate, not measured. What survives is the SIGN "
        "of the comparison -- construction far above 1, the hard "
        "questions at or below it. Do not quote the ratios.", 70, "  "))
    print()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "cases":
        cases()
        return

    print("=" * 74)
    print("  THE T_loop CHECK -- can you just go and measure instead?")
    print("=" * 74)
    print()
    print(wrap(
        "Every other module in this project is COMPENSATION FOR A "
        "BROKEN FEEDBACK LOOP. If you could just check, you would not "
        "need the sweeps, the mirror, the steelman or the bounds. You "
        "would check. So run this first: sometimes the right output of "
        "an analysis toolkit is 'put this down and go and look', and "
        "until now it had no way to say so.", 70, "  "))
    print()
    print("  " + "-" * 70)
    print("  GATE 1 -- RATE. Is the loop faster than the thing it "
          "watches?")
    print("  " + "-" * 70)
    print()
    print("     R = T_change / T_loop")
    print()
    print(wrap(
        "A thermostat has no theory of thermodynamics and still holds "
        "the room, because it measures and corrects. Loop quality "
        "substitutes for model quality and costs far less. The "
        "substitution works while R stays above 1.", 68, "  "))
    print()
    print(wrap(
        "THIS IS WHY THE HARD QUESTIONS ARE HARD. Not complexity -- a "
        "feedback loop slower than the thing it is watching, so "
        "nothing you learn arrives in time to be applied.",
        68, "  "))
    print()
    print("  " + "-" * 70)
    print("  GATE 2 -- CLOSURE. Is the ERROR fed back, or only input?")
    print("  " + "-" * 70)
    print()
    print(wrap(
        "The gate that quietly fails in almost every continuously "
        "updating system ever built. Re-running a case on fresh data "
        "is the input half. Without the scoring step nothing corrects, "
        "and you have bought a treadmill that feels like progress.",
        68, "  "))
    print()
    for i, q in enumerate(CLOSURE, 1):
        print("  {}. {}".format(i, q["id"].upper()))
        print(wrap(q["ask"], 64, "       "))
        print(wrap("WHY: " + q["why"], 64, "       "))
        print()
    print("  " + "-" * 70)
    print("  GATE 3 -- RESOLUTION. Can a cycle tell signal from noise?")
    print("  " + "-" * 70)
    print()
    print("     n = (sigma / delta)^2")
    print()
    print("     n       cycles needed before a real change is visible")
    print("     sigma   the spread of the noise, cycle to cycle")
    print("     delta   the size of the real movement you want to see")
    print("     /       divided by")
    print("     ^2      squared, because averaging n observations only")
    print("             shrinks their noise by the square root of n")
    print()
    print(wrap(
        "Faster is not better past this point. Correct inside the "
        "detection window and you are responding to noise, which "
        "amplifies it -- control engineers call it hunting, and a "
        "thermostat with too tight a deadband cycles the furnace to "
        "death. Re-estimate a building job daily and you will chase "
        "daily variance into a wrecked schedule. Match the loop period "
        "to the signal, not to how fast the data happens to arrive.",
        68, "  "))
    print()
    n, v, expl = resolution(0.04, 0.01, 4)
    print("     WORKED -- a supplier's on-time rate, gate 3")
    print("     sigma   4.0pp   quarter-to-quarter swing is noisy")
    print("     delta   1.0pp   a real improvement worth having")
    print("     n       {:.0f} quarters needed".format(n))
    print("     have    4")
    print()
    print(wrap(v + ". " + expl, 62, "     "))
    print()
    print(wrap(
        "So a claim like that fails gate 3. Even with a loop fast "
        "enough, four quarters could not have separated a 1pp "
        "improvement from ordinary delivery noise.", 62, "     "))
    print()
    print("  " + "-" * 70)
    print("  GATE 4 -- SURVIVABILITY. Is one failed cycle acceptable?")
    print("  " + "-" * 70)
    print()
    print(wrap(SURVIVABILITY, 68, "  "))
    print()
    print("  " + "-" * 70)
    print(wrap(
        "ALL FOUR MUST PASS for 'go and measure' to be the right "
        "advice. Any one failing sends you back to the model -- and "
        "gate 4 overrides gate 1 outright, because a fast loop is not "
        "the same as an affordable one.", 70, "  "))
    print()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
