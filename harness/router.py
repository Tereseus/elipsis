#!/usr/bin/env python3
"""
router.py -- given a claim, which formula applies?

THE DESIGN DECISION, AND IT IS THE WHOLE FILE.

The obvious build is: hand the claim to a model, ask "what shape is
this", trust the answer. That is wrong here for the same reason it is
wrong everywhere else in this project. Shape classification done by a
model, unaudited, is one more place where a confident wrong answer
becomes a confident wrong formula becomes a confident wrong number, and
nobody can see where it went in.

So the split is the same one gaps.py uses and it is the oldest idea in
this project: THE CODE GENERATES THE QUESTIONS. A MODEL ANSWERS THEM.
Never the other way round.

Each question below is a yes/no a model can answer by reading the claim
alone -- no world knowledge, no forecasting, no judgement about whether
the claim is true. "Does this need several things to all happen" is a
grammar question. "Will they all happen" is not, and is not asked here.

A CLAIM CAN BE MORE THAN ONE SHAPE AND THAT IS NOT A BUG. Most
interesting claims are two or three. The router returns all matches, and
the reply runs each one, because a claim that is both a conjunction and
a growth forecast is hostage to both and showing only one hides half of
it.

Run:  python harness/router.py
"""

import sys


def wrap(s, w=70, ind="   "):
    out, line = [], ""
    for word in s.split():
        if len(line) + len(word) + 1 > w:
            out.append(ind + line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        out.append(ind + line)
    return "\n".join(out)


def say(s):
    print(wrap(s))


# Every entry: the question the code asks, the formula that applies if
# the answer is yes, what has to be extracted, and what the reply then
# shows. The QUESTION is the contract -- it must be answerable from the
# text of the claim and nothing else.
SHAPES = [
    {
        "id": "conjunction",
        "question":
            "Does the claim need several separate things to ALL be true? "
            "Look for 'and then', 'once X, then Y', or a described "
            "sequence. Count the things that could each fail on their own.",
        "paper": "P(A₁ ∩ … ∩ Aₙ) = ∏ P(Aᵢ | A₁,…,Aᵢ₋₁)",
        "plain": "P = P₁ × P₂ × … × Pₙ",
        "extract": "the list of steps, in order",
        "then": "Frechet bounds, leave-one-out, and the word-drop "
                "cascade. This is the richest shape.",
        "why": "A common error: stating a "
               "chain of conditions with the confidence of its strongest "
               "link.",
    },
    {
        "id": "union",
        "question":
            "Does the claim say that SOMETHING from a list will happen, "
            "without committing to which? Look for 'one of these', "
            "'something's going to give', or a list of separate risks.",
        "paper": "P(A₁ ∪ … ∪ Aₙ) = 1 − ∏ (1 − pᵢ)",
        "plain": "P(at least one) = 1 − (1−P₁)(1−P₂)…",
        "extract": "the list of events, each priced separately",
        "then": "Poisson-binomial for HOW MANY will land, not just "
                "whether one does. That distribution is usually the more "
                "surprising output.",
        "why": "The mirror of the conjunction error. A list of individually "
               "unlikely things reads as 'probably nothing happens' and "
               "usually is not.",
    },
    {
        "id": "growth",
        "question":
            "Is a quantity claimed to change by some multiple over some "
            "period? A price, a share, a headcount, a market size. Needs "
            "a start, an end and a time.",
        "paper": "CAGR = (FV / PV)^(1/n) − 1",
        "plain": "rate = (end / start) ** (1/years) - 1",
        "extract": "start value, end value, number of years",
        "then": "For anything priced by a market, decompose: "
                "FV/PV = (E₁/E₀) × (M₁/M₀). Growth times multiple change, "
                "and nothing else. Usually the multiple is doing the work "
                "and nobody said so.",
        "why": "'It'll 10x' sounds like one claim and is two: the business "
               "grows, AND the market keeps paying the same premium.",
    },
    {
        "id": "accuracy_stat",
        "question":
            "Does the claim quote an accuracy, hit rate, or detection "
            "rate? '80% accurate', 'catches 9 in 10', 'the model "
            "predicted it'.",
        "paper": "PPV = TP / (TP + FP)",
        "plain": "of the ones it flagged, what share were real",
        "extract": "the quoted rate, and the base rate of the thing",
        "then": "Show the 2x2 table. Sensitivity and positive predictive "
                "value come out of the same four cells and only one of "
                "them ever gets quoted.",
        "why": "'80% accurate two years out' and '7 in 100 of what it "
               "flags happens' are the same fact. The first is the "
               "flattering half.",
    },
    {
        "id": "causal_rivals",
        "question":
            "Does the claim assert one explanation over another for the "
            "same events? 'It's not X, it's Y'. Look for a named cause "
            "competing with an implied alternative.",
        "paper": "O(H₁:H₂ | E) = O(H₁:H₂) × ∏ Lᵢ",
        "plain": "odds after = odds before × L₁ × L₂ × …",
        "extract": "the two rival explanations, and each piece of "
                   "evidence with how much likelier it is under one",
        "then": "GROUP CORRELATED EVIDENCE BEFORE MULTIPLYING. Three "
                "facts about the same observation are one L, not three. "
                "Forgetting that inflates the ratio many times over.",
        "why": "Competing explanations are testable against each other "
               "even when neither can be proved, and the evidence usually "
               "discriminates much less than the arguer thinks.",
    },
    {
        "id": "comparison",
        "question":
            "Does the claim recommend one option over others? 'We should "
            "do X instead of Y'. Needs at least two courses of action.",
        "paper": "E[X] = Σ pᵢ xᵢ     and     minₐ maxₛ R(a,s)",
        "plain": "expected value, then worst-case regret",
        "extract": "the options, the outcomes, the scenario weights",
        "then": "Run BOTH. Expected value needs probabilities; minimax "
                "regret needs none. When they disagree, that disagreement "
                "is the finding -- expected value is right over many "
                "similar bets and strange for one irreversible choice.",
        "why": "Most recommendations hide an unstated scenario weighting. "
               "An unweighted average across scenarios IS a weighting: it "
               "says each is equally likely.",
    },
    {
        "id": "stock_vs_flow",
        "question":
            "Is a LEVEL being confused with a RATE OF CHANGE, or the "
            "reverse? 'Unemployment is at record levels' -- the number "
            "out of work, or the number losing jobs this year? 'Debt is "
            "exploding' -- the total owed, or this year's borrowing?",
        "paper": "S(t) = S(0) + ∫₀ᵗ [ f_in(τ) − f_out(τ) ] dτ",
        "plain": "level now = level then + everything in - everything out",
        "extract": "which one the claim means, and what the other is doing",
        "then": "Show both series. A stock at a record while the flow "
                "falls is the commonest shape in political statistics and "
                "the two support opposite conclusions.",
        "why": "Missing from the first seven and it should not have been. "
               "For claims about debt, crime and housing it is "
               "more often the hostage choice than the denominator is.",
    },
    {
        "id": "window_shopping",
        "question":
            "Does the claim depend on where the time window starts or "
            "ends? Any 'since 20XX', 'over the past N years', or a trend "
            "with a stated beginning.",
        "paper": "Δ(t₀,t₁) = x(t₁) − x(t₀),  swept over all defensible t₀",
        "plain": "same series, every sensible start date, side by side",
        "extract": "the series, and the range of defensible start points",
        "then": "Plot the claim's value against start date. If it flips "
                "sign anywhere in the defensible range, the start date IS "
                "the argument. This is the denominator sweep in the time "
                "dimension and it is just as cheap.",
        "why": "Nearly free to check, works on any trend claim, and needs "
               "no forecast at all.",
    },
    {
        "id": "survivorship",
        "question":
            "Is the claim built from cases that are visible BECAUSE they "
            "succeeded or failed? 'Every great founder dropped out.' "
            "'Everyone who tried this went bust.'",
        "paper": "P(S | O) ≠ P(S),  where O = 'observed at all'",
        "plain": "the ones you can see are not the ones that happened",
        "extract": "what the full population would have been",
        "then": "Ask for the denominator that was never counted. Usually "
                "nobody has it, and saying so IS the finding -- the claim "
                "cannot be assessed, which is different from being wrong.",
        "why": "Turns an unanswerable claim into a specific, answerable "
               "request: name the population.",
    },
    {
        "id": "correlation_causal",
        "question":
            "Does the claim move from 'these move together' to 'this "
            "causes that'? Look for a statistic followed by a mechanism "
            "nobody measured.",
        "paper": "P(Y | do(X)) ≠ P(Y | X)",
        "plain": "what happens if you INTERVENE is not what you see when "
                 "you just LOOK",
        "extract": "the third thing that could drive both",
        "then": "Name a confounder and ask what would separate them. The "
                "do-operator is Pearl's, and the gap between the two "
                "sides of that inequality is the whole of the claim.",
        "why": "Extremely common and usually decidable by naming one "
               "plausible confounder out loud.",
    },
    {
        "id": "denominator",
        "question":
            "Could the claim be measured more than one defensible way, "
            "with different answers? Any share, rate, ratio, or the word "
            "'most', 'majority', 'dominant'.",
        "paper": "no formula — a sweep over the denominator",
        "plain": "same claim, N ways of counting it, side by side",
        "extract": "the plausible denominators",
        "then": "Report the spread and the ratio between highest and "
                "lowest. If it is wide, the measure IS the argument and "
                "no further analysis is needed to say so.",
        "why": "The cheapest and most durable move available. It needs no "
               "ground truth, no forecast, and cannot be argued with, "
               "because every number in it is the claimant's own claim "
               "measured honestly.",
    },
]


# WHAT EACH FORMULA IS CALLED AND WHERE IT COMES FROM.
#
# This was missing and it should not have been. A reply that shows
# notation without naming the method asks the reader to take the
# notation on trust, which is the opposite of the point. Naming it
# means they can go and check whether it was the right tool before
# they argue about the arithmetic -- and several of these names are
# the thing a reader can usefully search for afterwards.
#
# Two of the eleven share a source on purpose. The denominator sweep
# and the start-date sweep are the same manoeuvre run over different
# axes, and the literature calls both of them specification curve or
# multiverse analysis.
NAMED = {
    "conjunction": (
        "Chain rule for conjunctions",
        "standard probability; the multiplication rule"),
    "union": (
        "Complement rule for a union",
        "standard probability; P(at least one) = 1 - P(none)"),
    "growth": (
        "Compound annual growth rate",
        "standard compounding"),
    "accuracy_stat": (
        "Positive predictive value from the 2x2",
        "standard diagnostic-test arithmetic"),
    "causal_rivals": (
        "Bayes' theorem in odds form",
        "Bayes 1763; the odds form is the one that composes"),
    "comparison": (
        "Expected value, and minimax regret",
        "von Neumann & Morgenstern 1944; Savage 1951 for regret"),
    "stock_vs_flow": (
        "Stock-flow accounting identity",
        "an identity, not an estimate -- it cannot be wrong, only "
        "misread"),
    "window_shopping": (
        "Start-date sensitivity sweep",
        "specification curve analysis: Simonsohn, Simmons & Nelson "
        "2020; Steegen, Tuerlinckx, Gelman & Vanpaemel 2016"),
    "survivorship": (
        "Selection on the observed set",
        "Wald 1943, the aircraft-armour memo"),
    "correlation_causal": (
        "Pearl's do-operator",
        "Pearl 1995; seeing is not intervening"),
    "denominator": (
        "Reference-class sweep",
        "specification curve analysis: Steegen, Tuerlinckx, Gelman & "
        "Vanpaemel 2016; Simonsohn, Simmons & Nelson 2020"),
}

# --------------------------------------------------------------------
# WHAT KIND OF OBJECT EACH SHAPE ACTUALLY IS
#
# The eleven were assembled as one list and they are not one thing.
# Sorted properly they fall into four categories that need different
# detection questions and produce different outputs. Conflating them
# is why the partition always felt arbitrary.
# --------------------------------------------------------------------

CATEGORIES = {
    "failure_mode": {
        "what": "A defect in how the claim was built. A choice was "
                "made and not declared.",
        "detect": "Did they pick something here without saying so?",
        "output": "Sweep it. Show the answer under every defensible "
                  "choice and report the spread.",
        "visible": "IN THE CLAIM'S TEXT. You can see a share, a date "
                   "or a population without being told the reasoning, "
                   "which is why these fire most.",
        "ours": "This category is genuinely this project's own, with "
                "specification curve analysis as its ancestor.",
    },
    "argument_scheme": {
        "what": "A pattern of inference from premises to conclusion.",
        "detect": "What shape is the reasoning?",
        "output": "The critical questions attached to that pattern.",
        "visible": "ONLY IF THE REASONING IS STATED. Most claims "
                   "assert a conclusion and never show the argument, "
                   "which is why these fire far less often than "
                   "failure modes and has nothing to do with the "
                   "topic.",
        "ours": "Walton, Reed & Macagno catalogued 65 of these in "
                "2008, each with its own critical questions. Ours are "
                "three of them, reinvented. `conjunction` is his "
                "slippery slope with the arithmetic done.",
    },
    "method": {
        "what": "A procedure you run once you know what you are "
                "computing. Not a defect and not a reasoning pattern "
                "-- a tool.",
        "detect": "What quantity is being produced?",
        "output": "The formula, substituted, with the legend.",
        "visible": "When a number is quoted whose derivation is "
                   "standard.",
        "ours": "Operations research has had these for decades. "
                "Nothing original here and nothing needs to be.",
    },
    "operation": {
        "what": "What kind of finding-out is being attempted. A task, "
                "not a defect, pattern or tool.",
        "detect": "What are they trying to work out?",
        "output": "Which of the other three catalogues to open.",
        "visible": "Usually from the question rather than the claim.",
        "ours": "THE MISSING FRONT DOOR. Walton has the schemes, "
                "operations research has the methods, the failure-mode "
                "literature is scattered but real. A clean index of "
                "'what kind of finding-out is this' does not exist in "
                "one place. Exactly ONE of the eleven is an operation, "
                "and it has been hiding in here as though it were the "
                "same kind of thing as the others.",
    },
}

CATEGORY = {
    "denominator": "failure_mode",
    "window_shopping": "failure_mode",
    "survivorship": "failure_mode",
    "correlation_causal": "failure_mode",
    "stock_vs_flow": "failure_mode",

    "conjunction": "argument_scheme",
    "union": "argument_scheme",
    "causal_rivals": "argument_scheme",

    "growth": "method",
    "accuracy_stat": "method",

    "comparison": "operation",
}

# How often each shape fired on a measured sample of claims. Zero
# until a sample has been run.
FIRED = {
    "denominator": 0, "causal_rivals": 0, "correlation_causal": 0,
    "accuracy_stat": 0, "window_shopping": 0, "survivorship": 0,
    "comparison": 0, "stock_vs_flow": 0,
    "conjunction": 0, "union": 0, "growth": 0,
}
try:  # optional measured counts, loaded when present
    from private_examples import ROUTER_FIRED
    FIRED.update(ROUTER_FIRED)
except ImportError:
    pass

for _s in SHAPES:
    _s["formula_name"], _s["source"] = NAMED[_s["id"]]
    _s["category"] = CATEGORY[_s["id"]]
    _s["fired"] = FIRED[_s["id"]]


def by_category(cat=None):
    """Shapes grouped by what kind of object they are."""
    if cat:
        return [s for s in SHAPES if s["category"] == cat]
    return dict((c, [s for s in SHAPES if s["category"] == c])
                for c in CATEGORIES)


def category_counts():
    """(category, how many shapes, how many times they fired)."""
    out = []
    for c in CATEGORIES:
        ss = by_category(c)
        out.append((c, len(ss), sum(s["fired"] for s in ss)))
    return sorted(out, key=lambda x: -x[2])


def split_report():
    total = sum(FIRED.values())
    print("=" * 74)
    print("  THE ELEVEN ARE NOT ONE THING")
    print("=" * 74)
    print()
    print(wrap(
        "They were assembled as a flat list of 'shapes'. Sorted by "
        "what kind of object each actually is, they fall into four "
        "categories that need different detection questions and "
        "produce different outputs.", 70, "  "))
    print()
    print("  {:<20}{:>8}{:>10}{:>12}".format(
        "category", "shapes", "fires", "share"))
    print("  " + "-" * 50)
    for c, n, f in category_counts():
        print("  {:<20}{:>8}{:>10}{:>11.0f}%".format(
            c.replace("_", " "), n, f, 100.0 * f / max(total, 1)))
    print("  " + "-" * 50)
    print("  {:<20}{:>8}{:>10}".format("total", len(SHAPES), total))
    print()
    for c, meta in CATEGORIES.items():
        ss = by_category(c)
        print("=" * 74)
        print("  {}   ({} of 11, {} fires)".format(
            c.upper().replace("_", " "), len(ss),
            sum(s["fired"] for s in ss)))
        print("=" * 74)
        print()
        print(wrap(meta["what"], 66, "   "))
        print()
        print("   DETECT BY ASKING")
        print(wrap(meta["detect"], 64, "     "))
        print("   AND THE OUTPUT IS")
        print(wrap(meta["output"], 64, "     "))
        print()
        print("   WHEN IT IS VISIBLE")
        print(wrap(meta["visible"], 64, "     "))
        print()
        print("   WHOSE IT IS")
        print(wrap(meta["ours"], 64, "     "))
        print()
        print("   SHAPES")
        for s in sorted(ss, key=lambda x: -x["fired"]):
            print("     {:<24}{:>4} fires".format(s["id"], s["fired"]))
        print()
    print("=" * 74)
    print("  WHAT THE SPLIT EXPLAINS")
    print("=" * 74)
    print()
    print(wrap(
        "THE REASON IS STRUCTURAL. A failure mode is visible in "
        "the CLAIM -- you can see a share, a start date, a population, "
        "without being told anything about the reasoning. An argument "
        "scheme is only visible if the REASONING IS STATED, and most "
        "claims assert a conclusion and stop. So failure modes will "
        "out-fire schemes on any corpus of "
        "assertions, whatever the subject.", 70, "  "))
    print()
    print(wrap(
        "AND THE PROPER ORDER IS NOT FLAT. Operation first (what kind "
        "of finding-out is this), then scheme (how is it justified), "
        "then method (what gets computed), then failure mode (which "
        "defects are live, which depends on the first three). The flat "
        "eleven is the DEGENERATE CASE of that pipeline -- what you "
        "run when all you have is a conclusion, which for "
        "fact-checking is most of the time.", 70, "  "))
    print()


# THE MARKS PEOPLE CANNOT READ, AND WHAT EACH ONE DOES.
#
# WHY THIS EXISTS. A legend can define every NAMED QUANTITY in a
# formula while silently skipping the operators -- the integral sign,
# its limits, the dummy variable, the dtau -- which is exactly
# backwards: the named quantities are the part a reader can usually
# guess.
#
# So the definitions live in the code and get checked against the
# legend, because "remember to explain the integral sign" is not a
# rule, it is a hope. Each is written as what the mark DOES, never
# what it is called.
NOTATION = {
    "∫": "the integral sign. It means 'add up something that "
              "keeps changing'. A plain + adds fixed amounts; this "
              "adds up a RATE that is different at every moment. The "
              "small marks below and above it say where the adding-up "
              "starts and stops.",
    "Σ": "add all of these up, one for each item in the list.",
    "∏": "multiply all of these together, one for each item.",
    "√": "the square root: the number that, multiplied by "
              "itself, gives what is under the sign.",
    "max(": "take whichever of these is largest.",
    "min(": "take whichever of these is smallest.",
    "∑": "add all of these up, one for each item in the list.",
    "dτ": "a sliver of time. It tells you the adding-up runs over "
              "time rather than over anything else, and it closes the "
              "integral the way a bracket closes a bracket.",
    "τ": "a placeholder meaning 'each moment in between'. It is "
              "the thing that moves while you add up, and it exists "
              "only inside the integral -- you would never measure it.",
    "^(1/": "a fractional power, which is a root: the number that, "
            "multiplied by itself that many times, gives the base.",
    "|": "the bars mean 'the size of this, ignoring whether it is "
         "positive or negative'.",
    "∩": "the things inside must ALL happen.",
    "∪": "at least one of the things inside must happen.",
    "∈": "'is in' -- this item is a member of that set.",
    "≤": "is less than or equal to.",
    "≥": "is greater than or equal to.",
    "≠": "is not equal to.",
    "→": "leads to, or tends toward.",
    "Δ": "the change in something, end minus start.",
    "δ̂": "the little hat means this is an ESTIMATE of the "
                    "thing, not the thing itself.",
    "E[": "the expected value: the average you would get over many "
          "tries, weighting each outcome by how likely it is.",
    "P(": "the probability of what is inside the brackets.",
    "|A": "the vertical bar inside a probability means 'given that' -- "
          "everything after it is already assumed to have happened.",
}


def check_legend(paper, legend):
    """Every mark in the formula must appear in the legend.

    Returns the list of marks that were skipped. The caller decides
    whether that is fatal; block() treats it as fatal, because a
    legend that covers the easy symbols and skips the integral sign
    is worse than no legend -- it looks complete.
    """
    covered = " ".join(s for s, _ in legend)
    missing = []
    for mark in NOTATION:
        if mark in paper and mark not in covered:
            missing.append(mark)
    return missing


def by_id(sid):
    for s in SHAPES:
        if s["id"] == sid:
            return s
    raise KeyError(sid)


def block(sid, subbed, legend, checking, measures,
          paper=None, name=None, source=None):
    """Render one formula the way every reply must carry it.

    SIX PARTS, ALWAYS, IN THIS ORDER:
      1. CHECKING   the claim being tested, quoted IN FULL, with who
                    said it. Never a shorthand reference.
      2. MEASURES   what the number means, in words, before any
                    arithmetic happens.
      3. the formula's name and where it comes from
      4. the notation
      5. the notation with the numbers substituted
      6. every symbol defined by what it DOES

    WHY 1 AND 2 ARE REQUIRED ARGUMENTS AND NOT OPTIONAL. A reply that
    reports a count without listing the items, names a prediction by
    shorthand, or quotes a figure without stating the claim it came
    from is unreadable to anybody who has not seen the source.
    The test a reply has to pass is that SOMEONE WHO NEVER SAW THE
    ORIGINAL CAN FOLLOW ALL OF IT. Making these positional arguments
    means the format cannot silently drop them.

    If you report a count, the items belong in `subbed` or in the
    surrounding prose. A ratio whose numerator and denominator are
    never enumerated is a demand to be trusted, not an argument.

    `sid` is a router shape id. For a constant from constants.py that
    is not one of the eleven shapes, pass name/source/paper directly
    and leave sid None.
    """
    for label, val in (("checking", checking), ("measures", measures)):
        if not val or not str(val).strip():
            raise ValueError(
                "block() needs `{}`: a reply nobody outside the "
                "conversation can read persuades nobody and cannot be "
                "checked.".format(label))
    if sid is not None:
        s = by_id(sid)
        name = name or s["formula_name"]
        source = source or s["source"]
        paper = paper or s["paper"]
    skipped = check_legend(paper, legend)
    if skipped:
        raise ValueError(
            "legend skips {} mark(s) in the formula: {}\n\n"
            "These are usually the marks a reader most needs and the "
            "ones easiest to forget, because they have no name. "
            "Definitions you can paste:\n\n{}".format(
                len(skipped), "  ".join(skipped),
                "\n\n".join("   {}\n{}".format(m, wrap(NOTATION[m], 60,
                                                       "      "))
                            for m in skipped)))
    out = ["CHECKING THIS CLAIM",
           wrap(checking, 64, "   "),
           "",
           "WHAT THE NUMBER MEASURES",
           wrap(measures, 64, "   "),
           "",
           "FORMULA: " + name,
           wrap(source, 64, "   "),
           "",
           "ON PAPER",
           "   " + paper,
           "",
           "WITH THE NUMBERS IN"]
    for line in (subbed if isinstance(subbed, list) else [subbed]):
        out.append("   " + line)
    out += ["", "WHAT EVERY SYMBOL DOES"]
    for sym, mean in legend:
        body = wrap(mean, 52, "").split("\n")
        out.append("   {:<8} {}".format(sym, body[0].strip()))
        for x in body[1:]:
            out.append("   {:<8} {}".format("", x.strip()))
    return "\n".join(out)


def main():
    print("=" * 74)
    print("  THE ROUTER -- code asks, model answers")
    print("=" * 74)
    print()
    say("Seven questions. Each is answerable from the TEXT of the claim "
        "alone -- no world knowledge, no forecast, no view on whether the "
        "claim is true. That constraint is what keeps the router from "
        "being one more place a model can be confidently wrong "
        "invisibly.")
    print()
    say("Ask all seven of every claim. Multiple yeses is the normal case, "
        "not an error -- run every shape that matches.")
    print()

    for i, s in enumerate(SHAPES, 1):
        print("=" * 74)
        print("  {}. {}".format(i, s["id"].upper().replace("_", " ")))
        print("=" * 74)
        print()
        print("   ASK:")
        print(wrap(s["question"], 66, "      "))
        print()
        print("   IF YES, THE FORMULA IS")
        print("      on paper    " + s["paper"])
        print("      in code     " + s["plain"])
        print()
        print("   EXTRACT: " + s["extract"])
        print()
        print("   THEN ALSO SHOW:")
        print(wrap(s["then"], 66, "      "))
        print()
        print("   WHY THIS SHAPE MATTERS:")
        print(wrap(s["why"], 66, "      "))
        print()

    print("=" * 74)
    print("  THE STAGE THAT MUST NOT BE AUTOMATED")
    print("=" * 74)
    print()
    say("Stages 1, 2, 4 and 5 -- classify, extract, compute, render -- "
        "are all safe to automate. Stage 3, PRICING the parts, is not, "
        "and it is the one that decides the answer.")
    print()
    say("Every Pᵢ has to come from real research. A bot inventing "
        "those numbers would be guessing at speed and in public.")
    print()
    print("   THREE WAYS TO HANDLE STAGE 3, WEAKEST FIRST")
    print("   " + "-" * 66)
    print()
    for name, body in [
        ("BOT PRICES THEM  -- weakest",
         "Fast and scalable, and only as good as the bot's calibration, "
         "which is unscored until its forecasts resolve. Only viable if "
         "every number is labelled a guess and the "
         "rebuttal loop is genuinely live."),
        ("BOT LEAVES THEM BLANK  -- strongest, and nearly free",
         "Extract the structure, show the formula, and hand it back "
         "empty: 'your claim has three steps, here is what they multiply "
         "to, put your own numbers in.' It requires NO forecasting at "
         "all, so the calibration problem disappears entirely. It is "
         "unanswerable, because the only numbers in it are theirs. And it "
         "is the version that scales, because stage 3 stops existing."),
        ("HUMAN PRICES THEM  -- best output, does not scale",
         "Several searches per "
         "number, and errors caught by reading the working. Right "
         "for a summon-only bot where someone asked and is waiting; wrong "
         "for anything that replies at volume."),
    ]:
        print("   " + name)
        print(wrap(body, 64, "      "))
        print()

    print("=" * 74)
    print("  WHAT TO BUILD, IN ORDER")
    print("=" * 74)
    print()
    for i, (what, why) in enumerate([
        ("The seven questions as a prompt, run against 100 real claims. "
         "Record which shapes fire and how often.",
         "This is a measurement, not a build, and it decides everything "
         "after it. If 80 of 100 are conjunctions, build the conjunction "
         "path properly and ignore the rest for now."),
        ("The blank-structure reply. Extract steps, show formula, leave "
         "the numbers empty.",
         "Needs stages 1, 2 and 5 only. No pricing, no forecasting, no "
         "calibration exposure. Shippable, and already most of the value."),
        ("Agreement check: run the router twice on the same 100 claims "
         "and see how often it picks the same shapes.",
         "If it disagrees with itself, no downstream number means "
         "anything. Cheap to run and it is the thing that would silently "
         "rot."),
        ("Only then, pricing -- and only for summon-only replies where "
         "somebody asked.",
         "The only one where spending "
         "real research time per answer makes sense."),
    ], 1):
        print("   {}. {}".format(i, what))
        print(wrap("WHY: " + why, 64, "      "))
        print()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
