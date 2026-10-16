#!/usr/bin/env python3
"""
operations.py -- what kind of finding-out is this?

THE FRONT DOOR. Sorting the router's eleven shapes by what kind of
object each actually is left four categories, and exactly ONE of the
eleven turned out to be an operation -- `comparison`, sitting in the
list as though it were the same kind of thing as `denominator`.

That gap is the reason the pipeline felt arbitrary. The proper order
is not flat:

    operation  ->  scheme  ->  method  ->  failure mode
    what kind      how is      what gets     which defects
    of finding-    it being    computed      are live, which
    out is this    justified                 depends on the
                                             first three

Walton, Reed & Macagno catalogued 65 argument schemes. Operations
research has had the methods for decades. The failure modes are this
project's own, with specification curve analysis behind them. Nobody
has built a clean index of the OPERATIONS, and it is the one that
tells you which of the other three to open.

WHY THE CONSTRUCTION EXAMPLES. Every operation here is illustrated
with a building-site question, because the index is worthless if it
only works on geopolitics. If it cannot tell a foreman which formula
to reach for, it is a philosophy paper.

Run:  python harness/operations.py
      python harness/operations.py estimate
"""

import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import router as R  # noqa: E402


OPERATIONS = [
    {
        "id": "estimate",
        "asks": "How many, how much, how long? A quantity you cannot "
                "count directly.",
        "methods": "Fermi decomposition (split into factors you can "
                   "each bound) | PERT three-point | Wright's "
                   "learning curve for anything repeated | reference "
                   "class forecasting",
        "worst_failure": "Optimism. Estimating the job in front of "
                         "you instead of looking at how long the last "
                         "fifty like it took. Flyvbjerg built "
                         "reference class forecasting specifically "
                         "for this and it is the single highest-yield "
                         "fix in the index.",
        "site": "'How long will this take?' Do not estimate it. Find "
                "eight comparable jobs you finished and put yourself "
                "in that distribution.",
        "loop": "fast -- you find out in days",
    },
    {
        "id": "bound",
        "asks": "What is the most and least this could be, when a "
                "point estimate is not available?",
        "methods": "Frechet bounds for chains | rule of three for "
                   "zero observations | GRADE against a decision "
                   "threshold",
        "worst_failure": "Reporting a point where only a range is "
                         "supported. And its mirror: reporting a "
                         "range as useless when it sits entirely on "
                         "one side of the threshold and therefore "
                         "decides the question.",
        "site": "'Could this beam fail?' You may not get a number. "
                "You can often get 'the worst case is still inside "
                "spec', which settles it.",
        "loop": "n/a -- bounding is what you do when the loop is too "
                "slow to help",
    },
    {
        "id": "compare",
        "asks": "Which of these options? A choice between at least "
                "two courses of action.",
        "methods": "Expected value | minimax regret (needs no "
                   "probabilities) | break-even analysis",
        "worst_failure": "An unstated scenario weighting. An "
                         "unweighted average across scenarios IS a "
                         "weighting -- it says each is equally "
                         "likely, and nobody defends that.",
        "site": "'Subcontract this or do it in-house?' Run expected "
                "value AND minimax regret. When they disagree, that "
                "disagreement is the finding.",
        "loop": "medium -- you learn after the job",
    },
    {
        "id": "diagnose",
        "asks": "What is causing this? Working backwards from an "
                "effect to a mechanism.",
        "methods": "Analysis of Competing Hypotheses | Bayes in odds "
                   "form | fault tree",
        "worst_failure": "Stopping at the first plausible cause. ACH "
                         "exists because analysts confirm rather than "
                         "discriminate -- the question is not 'does "
                         "this fit' but 'what would this rule OUT'.",
        "site": "'Why does this wall keep cracking?' List every cause "
                "that fits, then find the observation that separates "
                "them. Settlement, thermal and moisture all crack a "
                "wall; they crack it in different patterns.",
        "loop": "fast -- you can open the wall",
    },
    {
        "id": "attribute",
        "asks": "Who or what is responsible? Same machinery as "
                "diagnose, different output -- diagnose tells you "
                "what to fix, attribute tells you who pays.",
        "methods": "Bayes in odds form | counterfactual: would it "
                   "have happened anyway?",
        "worst_failure": "Attributing to the most visible actor. The "
                         "cost-of-ruling constant exists because "
                         "governing parties lose votes for no reason "
                         "at all, and the visible cause takes the "
                         "blame.",
        "site": "'Whose delay is this?' The subcontractor who missed "
                "the date is visible. Ask what the schedule would "
                "have done if they had hit it.",
        "loop": "slow -- and it is adversarial, which slows it more",
    },
    {
        "id": "predict",
        "asks": "What happens next? Forward in time, or outside the "
                "range you have observed.",
        "methods": "Base rate from a reference class FIRST | chain "
                   "rule for compound events | outside view before "
                   "inside view",
        "worst_failure": "No reference class. If you cannot name the "
                         "set of comparable cases, you are not "
                         "predicting, you are imagining -- and with "
                         "n=0 the rule of three returns nothing at "
                         "all.",
        "site": "'Will this supplier deliver on time?' Their last "
                "twenty deliveries are the answer. Their promise is "
                "not evidence about their promise.",
        "loop": "varies -- and this is the one that decides "
                "everything, see the note at the end",
    },
    {
        "id": "detect",
        "asks": "Is it present at all? A yes-or-no on presence, "
                "usually with an imperfect test.",
        "methods": "The 2x2 table | positive predictive value | "
                   "sensitivity and specificity",
        "worst_failure": "Ignoring the base rate. A 99%-accurate test "
                         "for something present in 1 in 10,000 "
                         "produces about 99 false alarms for every "
                         "true one. The quoted accuracy is the "
                         "flattering half of the same four cells.",
        "site": "'Is there asbestos here?' The test's accuracy is not "
                "the chance you have it. What era the building is "
                "from sets the base rate and the base rate does most "
                "of the work.",
        "loop": "fast -- you can retest",
    },
    {
        "id": "classify",
        "asks": "Which kind of thing is this?",
        "methods": "Confusion matrix | explicit category boundaries "
                   "declared BEFORE looking",
        "worst_failure": "Undeclared categories. Whoever draws the "
                         "boundary decides the answer -- which is the "
                         "denominator problem wearing different "
                         "clothes.",
        "site": "'Is this defect structural or cosmetic?' Write the "
                "boundary down before you inspect, or you will draw "
                "it where the answer is convenient.",
        "loop": "fast",
    },
    {
        "id": "aggregate",
        "asks": "Several sources say different things. What do they "
                "jointly say?",
        "methods": "Weighted mean | the correlation correction: "
                   "sd_n/sd_1 = sqrt((1 + (n-1)rho)/n)",
        "worst_failure": "Treating correlated sources as independent. "
                         "At rho = 1 there is NO variance reduction "
                         "however many you add.",
        "site": "'Three quotes, three prices.' If all three priced it "
                "off the same drawings, they are one estimate with "
                "three signatures.",
        "loop": "fast",
    },
    {
        "id": "allocate",
        "asks": "How do I split something limited across competing "
                "uses?",
        "methods": "Equalise marginal return | shadow price | "
                   "constraint identification",
        "worst_failure": "Splitting equally by default. Equal "
                         "division is a decision and almost never the "
                         "right one; the right answer puts the next "
                         "unit wherever it does most, until that "
                         "stops being true.",
        "site": "'Three sites, one crew.' Not a third each -- "
                "wherever the next day of labour removes the most "
                "delay.",
        "loop": "fast, and reallocation is cheap, which is the point",
    },
    {
        "id": "sequence",
        "asks": "What order should these go in, and which one is "
                "holding everything else up?",
        "methods": "Critical path | Little's Law (L = lambda x W) for "
                   "throughput | theory of constraints",
        "worst_failure": "Optimising a task that is not on the "
                         "critical path. Speeding up anything with "
                         "slack changes the finish date by exactly "
                         "zero, and it feels like progress.",
        "site": "'What do we do first?' Find the chain with no slack. "
                "Every hour saved anywhere else is an hour you did "
                "not save.",
        "loop": "fast",
    },
    {
        "id": "measure",
        "asks": "What is this value, and how much do I trust the "
                "instrument?",
        "methods": "Repeatability | instrument error | significant "
                   "figures that match the tool",
        "worst_failure": "Precision beyond the instrument. Reporting "
                         "four decimals from a tool good to one is a "
                         "claim about the tool, not the world.",
        "site": "'How level is this floor?' Measure it three times. "
                "The spread between your own readings is the smallest "
                "difference you are entitled to report.",
        "loop": "immediate",
    },
    {
        "id": "cause",
        "asks": "Did this change make that happen? The effect of a "
                "policy or action, against what would have happened "
                "without it.",
        "methods": "Difference-in-differences (the change where it was "
                   "done minus the change where it was not) | natural "
                   "experiments | randomised trials | synthetic control",
        "worst_failure": "Before-and-after with no comparison group. "
                         "Crime fell after the law; it also fell in "
                         "every town that never passed it.",
        "site": "'Did the new curing blanket stop the cracking?' "
                "Compare this season's slabs with the slabs poured the "
                "same weeks without it, not with last year's.",
        "loop": "slow -- you need the untreated cases to run alongside",
    },
    {
        "id": "strategize",
        "asks": "What will the other side do, given that they are "
                "choosing too?",
        "methods": "Game theory: payoff tables | best responses | "
                   "equilibrium (no side gains by changing alone) | "
                   "repeated games and reputation",
        "worst_failure": "Treating a rival as weather. People respond "
                         "to your move; a forecast that assumes they "
                         "will not is wrong the moment you act on it.",
        "site": "'Bid low on this tender?' The other three bidders "
                "read the same drawings. Ask what they bid if they "
                "expect you to go low.",
        "loop": "medium -- you see their move, rarely their reasons",
    },
    {
        "id": "simulate",
        "asks": "What range of outcomes do all these uncertainties "
                "add up to?",
        "methods": "Monte Carlo (draw every uncertain input at random "
                   "thousands of times and count the outcomes) | "
                   "agent-based models | sensitivity runs",
        "worst_failure": "Inputs made up to look precise. A thousand "
                         "runs of invented numbers is one invented "
                         "number with error bars.",
        "site": "'Will we finish by March?' Draw each task's length "
                "from its own spread, run the schedule 10,000 times, "
                "and read off how many runs finish in time.",
        "loop": "fast to run, slow to check -- the world runs once",
    },
    {
        "id": "trend",
        "asks": "Is this changing over time, and is the change real or "
                "noise?",
        "methods": "Time series: moving averages | seasonal adjustment "
                   "| breakpoint tests | exponential smoothing",
        "worst_failure": "Calling a turn from the last two points. "
                         "Most monthly wiggles are noise; a trend is "
                         "what survives the season and the revision.",
        "site": "'Are callbacks rising?' Twelve months against the "
                "same months last year, not this month against last.",
        "loop": "medium -- each new point tests the last call",
    },
    {
        "id": "connect",
        "asks": "Who links to whom, and how does something spread "
                "through those links?",
        "methods": "Networks: degree and centrality (who sits in the "
                   "middle) | paths | contagion models (each contact "
                   "passes it on with some chance)",
        "worst_failure": "Counting people instead of links. One "
                         "well-connected node can matter more than a "
                         "hundred isolated ones.",
        "site": "'Why did the wrong spec reach every crew?' Trace who "
                "forwarded the drawing to whom; one office was in "
                "every path.",
        "loop": "medium",
    },
    {
        "id": "optimize",
        "asks": "What is the best plan, given all the limits at once?",
        "methods": "Linear programming | constraints and objective "
                   "written down | shadow prices (what one more unit "
                   "of a limit is worth)",
        "worst_failure": "Optimising the wrong objective. The cheapest "
                         "plan that fails the safety limit is not "
                         "optimal, it is illegal.",
        "site": "'Which mix of crews and plant finishes cheapest without "
                "missing the deadline?' Write the cost, the deadline "
                "and the crew limits as equations and solve them "
                "together.",
        "loop": "fast -- the plan either fits the limits or it does not",
    },
]


def wrap(t, w=66, ind="   "):
    return R.wrap(t, w, ind)


def by_id(oid):
    for o in OPERATIONS:
        if o["id"] == oid:
            return o
    raise KeyError(oid)


def show(o):
    print("=" * 74)
    print("  " + o["id"].upper())
    print("=" * 74)
    print()
    print("   ASKS")
    print(wrap(o["asks"], 64, "     "))
    print()
    print("   METHODS TO OPEN")
    for m in o["methods"].split(" | "):
        print(wrap("- " + m, 62, "     "))
    print()
    print("   THE FAILURE THAT BITES HARDEST")
    print(wrap(o["worst_failure"], 64, "     "))
    print()
    print("   ON A BUILDING SITE")
    print(wrap(o["site"], 64, "     "))
    print()
    print("   FEEDBACK LOOP: " + o["loop"])
    print()


def main():
    if len(sys.argv) > 1:
        try:
            show(by_id(sys.argv[1]))
        except KeyError:
            print("No operation '{}'. The eighteen are: {}".format(
                sys.argv[1], ", ".join(o["id"] for o in OPERATIONS)))
        return

    print("=" * 74)
    print("  OPERATIONS -- what kind of finding-out is this?")
    print("=" * 74)
    print()
    print(wrap(
        "The front door. Answer this first and it tells you which "
        "catalogue to open: Walton's 65 argument schemes, the "
        "operations-research methods, or the failure modes. Nobody "
        "has built this index, and exactly one of the router's eleven "
        "shapes turned out to be an operation hiding among ten things "
        "of other kinds.", 70, "  "))
    print()
    print("  {:<12}{:<44}{:<14}".format("operation", "asks", "loop"))
    print("  " + "-" * 70)
    for o in OPERATIONS:
        print("  {:<12}{:<44}{:<14}".format(
            o["id"], o["asks"][:42], o["loop"].split(" --")[0][:12]))
    print()
    for o in OPERATIONS:
        show(o)
    print("=" * 74)
    print("  THE LOOP IS WORTH MORE THAN THE MODEL")
    print("=" * 74)
    print()
    print(wrap(
        "Most of these operations have a FAST feedback loop. You "
        "estimate the job, you do the job, you find out. That matters "
        "more than any formula in the index, because a fast loop "
        "substitutes for a good model -- a thermostat holds a room at "
        "20 degrees with no theory of thermodynamics whatsoever, "
        "because it measures and corrects.", 70, "  "))
    print()
    print("     on paper      the loop wins when   T_loop < T_change")
    print()
    print("     T_loop     how long until you find out you were wrong")
    print("     T_change   how fast the thing you are watching moves")
    print("     <          'is shorter than'")
    print()
    print(wrap(
        "On a building site T_loop is days and T_change is weeks, so "
        "the loop wins and you barely need the model -- check, "
        "correct, check again. In geopolitics T_loop is YEARS and "
        "T_change is months, so the loop loses and you need a model "
        "you cannot have.", 70, "  "))
    print()
    print(wrap(
        "THAT IS WHY THE HARD QUESTIONS ARE HARD. Not complexity. The "
        "feedback loop is slower than the thing it is watching, so "
        "you never get to correct. Every genuinely difficult question "
        "-- will there be war, will the policy work -- fails on T_loop, not on "
        "maths.", 70, "  "))
    print()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
