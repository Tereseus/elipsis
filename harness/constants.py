#!/usr/bin/env python3
"""
constants.py -- the published regularities, with their scope conditions.

WHY THIS FILE EXISTS. A theory can sit in one of three slots and they
need completely different proof:

  SLOT 1  STRUCTURE GENERATOR   tells you what the steps ARE.
          Predicts nothing, does not need to. Feed those steps to
          chain.py.

  SLOT 2  ESTIMATOR             gives a number with an interval.
          THIS FILE. Very few things qualify.

  SLOT 3  MEASUREMENT           gives the input values, ideally with
          their own uncertainty. CHES, ParlGov, MARPOR, V-Dem. Not
          in here; they are data, not constants.

THE ERROR THIS FILE EXISTS TO PREVENT is using a slot-1 theory as a
slot-2 estimator. Any number that comes out of that was fabricated by
the reader, not the paper.

THE THREE FILTERS for admission to slot 2:
  1. a published effect size WITH an interval
  2. an out-of-sample test somebody other than the author ran
  3. a public dataset that operationalises the inputs

Fail any one and it belongs in slot 1 or 3. grade() runs the filters.

WHAT EVERY ENTRY CARRIES, and the last field is the important one:
  value / interval   the number and its honest range
  paper / worked     standard notation, then the same thing with
                     numbers substituted in
  legend             every symbol in plain English
  n                  what it was measured on
  scope              where it has been shown to hold
  out_of_scope       where it has NOT, including sign flips
  misuse             the specific wrong way it gets used. A constant
                     applied outside its scope is worse than no
                     constant, because it arrives wearing a citation.

Run:  python harness/constants.py
      python harness/constants.py cost_of_ruling
"""

import math
import sys

# --------------------------------------------------------------------
# slot 2: estimators
# --------------------------------------------------------------------

CONSTANTS = [
    {
        "id": "cost_of_ruling",
        "name": "Cost of ruling",
        "status": "SOLID",
        "what": "Governing parties lose vote share just for having "
                "governed, regardless of how well they did.",
        "value": 2.25,
        "interval": (1.6, 2.5),
        "unit": "percentage points of vote share, per term in office",
        "paper": "E[Δv] = −c·f(t),  c ≈ 2.25, f increasing in t",
        "worked": "E[Δv] = −2.25 pp for one term in office",
        "legend": [
            ("Δv", "change in the governing party's vote share"),
            ("c", "the constant, 2.25 percentage points"),
            ("t", "terms served; the loss grows with tenure"),
        ],
        "n": "282 elections, 19 developed democracies, 1948-1997",
        "source": "Nannestad & Paldam, 'The Cost of Ruling'; revisited "
                  "in Acta Politica 2021, which calls it 'an unusually "
                  "stable constant'",
        "scope": [
            "national elections in developed parliamentary democracies",
            "the party or parties holding cabinet office",
        ],
        "out_of_scope": [
            "US-style candidate-centred races, where personal "
            "incumbency ADVANTAGE runs the other way -- the sign flips",
            "new or unconsolidated democracies",
            "subnational elections (weaker and noisier)",
        ],
        "misuse": "Reading a governing party's vote loss as a verdict "
                  "on its record without netting this out first. A "
                  "loss under about 2.25 points per term is the "
                  "ordinary price of office.",
    },
    {
        "id": "gamson",
        "name": "Gamson's Law",
        "status": "SOLID",
        "what": "In a coalition cabinet, a party's share of ministries "
                "tracks its share of the coalition's seats almost "
                "mechanically.",
        "value": 0.793,
        "interval": (0.75, 0.84),
        "unit": "slope: portfolio share per unit of seat share",
        "extra": {"intercept": 0.069, "r2": 0.89,
                  "through_origin": 0.93},
        "paper": "p̂ᵢ = α + βsᵢ,   α = 0.069,  β = 0.793,  R² = 0.89",
        "worked": "p̂ = 0.069 + 0.793(0.85) = 0.743  →  74 of every "
                  "100 ministries",
        "legend": [
            ("p̂ᵢ", "share of cabinet posts party i receives"),
            ("sᵢ", "party i's share of the COALITION's seats -- not "
                   "of parliament's"),
            ("α", "0.069, a small bonus for junior partners"),
            ("β", "0.793; forced through the origin it rises to 0.93"),
            ("R²", "0.89 -- seat contribution explains 89 in 100 of "
                   "the variation in who gets which ministry, and 11 "
                   "in 100 is something else"),
        ],
        "n": "post-war European coalition cabinets",
        "source": "Warwick & Druckman 2006, European Journal of "
                  "Political Research; called 'perhaps the strongest "
                  "empirical finding in political science'",
        "scope": [
            "parliamentary coalition governments",
            "counts ministries, one post one unit",
        ],
        "out_of_scope": [
            "presidential systems",
            "portfolio IMPORTANCE -- weighting finance above sport "
            "changes the picture and the slope is not for that",
        ],
        "misuse": "Using share of PARLIAMENT as s instead of share of "
                  "the coalition. A party with 30% of parliament in a "
                  "two-party coalition holding 55% of seats has s = "
                  "0.55, not 0.30, and the answer differs by more than "
                  "20 points.",
    },
    {
        "id": "economic_voting",
        "name": "Economic voting",
        "status": "SOLID BUT CONDITIONAL",
        "what": "Incumbents gain vote share when the economy grows -- "
                "but only as much as voters can tell who is "
                "responsible.",
        "value": 1.55,
        "interval": (1.4, 1.7),
        "unit": "pp of incumbent vote share per 1 pp of GDP growth",
        "extra": {"fragmented_government": 0.92},
        "paper": "Δv = β(C)·g,   β ≈ 1.4-1.7 clear,  ≈ 0.92 fragmented",
        "worked": "Δv = 1.55 × 2.0 = +3.1 pp for 2% growth under a "
                  "single-party majority; 1.8 pp under a fragmented "
                  "coalition",
        "legend": [
            ("Δv", "change in the incumbent's vote share"),
            ("g", "GDP growth, percentage points"),
            ("β(C)", "the response, which depends on C"),
            ("C", "clarity of responsibility -- how obvious it is to a "
                  "voter which party to blame. High for a single-party "
                  "majority, low for a fragmented coalition"),
        ],
        "n": "595 elections, 70 countries, 1960-2020",
        "source": "cross-national economic-voting literature; the "
                  "clarity-of-responsibility conditioning is Powell & "
                  "Whitten 1993",
        "scope": [
            "national elections with an identifiable incumbent",
            "peak growth during the term matters more than average",
        ],
        "out_of_scope": [
            "symmetric use -- the response is stronger on the way "
            "down than on the way up",
            "quoting the high coefficient for a fragmented coalition; "
            "it is roughly halved",
        ],
        "misuse": "Taking 1.55 as universal. The whole point of the "
                  "finding is that it is conditional -- in a "
                  "fragmented government it is 0.92, and using 1.55 "
                  "there overstates by about 70%.",
    },
    {
        "id": "effective_parties",
        "name": "Effective number of parties",
        "status": "ARITHMETIC -- no theory risk",
        "what": "How many parties there really are, once you stop "
                "counting the ones with 0.4% of the vote as equal to "
                "the ones with 30%.",
        "value": None,
        "interval": None,
        "unit": "a count, usually between 2 and 7",
        "paper": "N = 1 / Σ pᵢ²",
        "worked": "shares 0.30, 0.25, 0.20, 0.15, 0.10  →  "
                  "N = 1/0.2250 = 4.44",
        "legend": [
            ("N", "effective number of parties"),
            ("pᵢ", "party i's share of the vote, or of the seats -- "
                   "say which, they differ"),
            ("Σ", "add up over every party"),
        ],
        "n": "definitional",
        "source": "Laakso & Taagepera 1979",
        "scope": ["any party system, any level"],
        "out_of_scope": [],
        "misuse": "Quoting it without saying whether it is computed on "
                  "votes or on seats. The gap between the two IS the "
                  "electoral system's effect, so conflating them "
                  "hides exactly what you were measuring.",
    },
    {
        "id": "volatility",
        "name": "Electoral volatility (Pedersen index)",
        "status": "ARITHMETIC -- no theory risk",
        "what": "How much of the electorate moved between parties "
                "since last time.",
        "value": None,
        "interval": None,
        "unit": "percentage points of the electorate that switched",
        "paper": "V = ½ Σ |pᵢ,ₜ − pᵢ,ₜ₋₁|",
        "worked": "a party up 8, another down 5, another down 3  →  "
                  "V = ½(8+5+3) = 8.0",
        "legend": [
            ("V", "volatility, in percentage points"),
            ("pᵢ,ₜ", "party i's share at this election"),
            ("pᵢ,ₜ₋₁", "party i's share at the previous one"),
            ("½", "halved because every vote that leaves one party "
                  "arrives at another, so the raw sum counts each "
                  "switch twice"),
        ],
        "n": "definitional",
        "source": "Pedersen 1979",
        "scope": ["consecutive elections in the same system"],
        "out_of_scope": [
            "systems where parties split, merge or rename between "
            "elections -- you must decide what counts as the same "
            "party first, and that decision drives the answer",
        ],
        "misuse": "Reporting a jump in volatility as evidence of "
                  "realignment when a large party simply renamed "
                  "itself.",
    },
    {
        "id": "disproportionality",
        "name": "Gallagher index",
        "status": "ARITHMETIC -- no theory risk",
        "what": "How badly the seat shares match the vote shares.",
        "value": None,
        "interval": None,
        "unit": "index, 0 = perfect, over 10 = severe",
        "paper": "LSq = √( ½ Σ (vᵢ − sᵢ)² )",
        "worked": "one party +6 seats over votes, another −4, another "
                  "−2  →  LSq = √(½(36+16+4)) = √28 = 5.29",
        "legend": [
            ("LSq", "least-squares disproportionality index"),
            ("vᵢ", "party i's vote share, in percent"),
            ("sᵢ", "party i's seat share, in percent"),
        ],
        "n": "definitional",
        "source": "Gallagher 1991",
        "scope": ["any election with both vote and seat shares"],
        "out_of_scope": [],
        "misuse": "Treating a high value as unfairness. A high value "
                  "is what majoritarian systems are FOR; it is a "
                  "description of the rules, not a verdict on them.",
    },
    {
        "id": "seat_allocation",
        "name": "D'Hondt / Sainte-Lague seat allocation",
        "status": "ARITHMETIC -- no theory risk",
        "what": "Turns vote shares into actual seats. This is the step "
                "that decides whether 'polling at 30%' means power or "
                "not.",
        "value": None,
        "interval": None,
        "unit": "seats",
        "paper": "qᵢⱼ = vᵢ / dⱼ,   dⱼ = 1,2,3,… (D'Hondt)  or  "
                 "1,3,5,… (Sainte-Lague)",
        "worked": "see dhondt() -- allocates one seat at a time to "
                  "whichever party currently has the largest quotient",
        "legend": [
            ("qᵢⱼ", "party i's quotient when competing for its j-th "
                   "seat"),
            ("vᵢ", "party i's votes"),
            ("dⱼ", "the divisor sequence; D'Hondt favours large "
                  "parties, Sainte-Lague is kinder to small ones"),
        ],
        "n": "definitional",
        "source": "standard apportionment arithmetic",
        "scope": ["list PR systems"],
        "out_of_scope": [
            "the threshold. A 5% bar is applied BEFORE this runs and "
            "usually matters more than the divisor choice",
        ],
        "misuse": "Reading a national poll share as a national seat "
                  "share. Allocation happens per district, and doing "
                  "it once nationally gives the wrong answer wherever "
                  "district magnitude is small.",
    },
    {
        "id": "duverger",
        "name": "Duverger's Law / Cox's M+1 rule",
        "status": "DIRECTIONAL ONLY -- no point estimate",
        "what": "Electoral rules cap how many parties are viable in a "
                "district.",
        "value": None,
        "interval": None,
        "unit": "viable candidates per district",
        "paper": "n* → M + 1",
        "worked": "single-member district: M = 1, so n* → 2",
        "legend": [
            ("n*", "the number of candidates that stay viable once "
                   "voters stop wasting votes"),
            ("M", "district magnitude -- how many seats that district "
                  "elects"),
        ],
        "n": "wide comparative support at district level",
        "source": "Duverger 1954; Cox 1997 for the M+1 generalisation",
        "scope": ["the DISTRICT. This is where it holds"],
        "out_of_scope": [
            "the nation. National party counts depend on whether "
            "districts coordinate, and often they do not -- Canada "
            "and India have single-member districts and many parties",
        ],
        "misuse": "Predicting a national two-party system from "
                  "single-member districts. It is a district-level "
                  "regularity and there is no published coefficient "
                  "for the national jump, so this entry gets no "
                  "number.",
    },
    {
        "id": "pitf",
        "name": "PITF instability model",
        "status": "RANK ONLY -- see harness/pitf.py",
        "what": "Four variables, case-control design, outputs where a "
                "country sits relative to others.",
        "value": None,
        "interval": None,
        "unit": "percentile rank",
        "paper": "logit(rank) = Σ βₖxₖ,  intercept NOT published",
        "worked": "see harness/pitf.py -- a score is placed in the "
                  "world ranking, and the top fifth is flagged",
        "legend": [
            ("βₖ", "the published coefficients"),
            ("xₖ", "the four regime and conflict variables"),
            ("intercept", "deliberately absent. Case-control sampling "
                          "at 1:3 makes any intercept meaningless, so "
                          "the model cannot produce a probability"),
        ],
        "n": "case-control, 1:3; Table 2 out-of-sample",
        "source": "Goldstone et al. 2010, AJPS 54(1):190-208",
        "scope": ["cross-country comparison of relative risk"],
        "out_of_scope": [
            "ANY absolute probability. Of 251 country-years the model "
            "flagged out of sample, 18 had onsets -- 7.2%, which is "
            "the positive predictive value, not a forecast",
        ],
        "misuse": "Inventing an intercept to turn the rank into a yearly "
                  "probability for one country. The paper contains no "
                  "such number and cannot.",
    },
]
try:  # optional extra entries, loaded when present
    from private_examples import CONSTANTS_EXTRA
    CONSTANTS += CONSTANTS_EXTRA
except ImportError:
    pass


# --------------------------------------------------------------------
# things that look like constants and are not
# --------------------------------------------------------------------

REJECTED = [
    ("Median voter theorem",
     "Parties are supposed to converge on the centre. In multiparty "
     "systems with entry they demonstrably do not. Useful as a "
     "teaching device, not as an estimator."),
    ("The cube law",
     "Seats varied as the cube of the vote ratio -- in mid-century "
     "two-party Britain. It was an artifact of that geography and "
     "that era, and it broke."),
    ("Anything producing 'X% chance' from a model that publishes a "
     "rank",
     "Named after the mistake in pitf above. If the paper has no "
     "intercept, there is no probability in it, and supplying one "
     "yourself means the number is yours, not the literature's."),
]


THREE_FILTERS = [
    "Is there a published effect size WITH an interval?",
    "Did somebody other than the author test it out of sample?",
    "Is there a public dataset that operationalises the inputs?",
]


# --------------------------------------------------------------------
# apply
# --------------------------------------------------------------------

def get(cid):
    for c in CONSTANTS:
        if c["id"] == cid:
            return c
    raise KeyError(cid)


def cost_of_ruling(terms=1.0, low=False, high=False):
    """Expected vote-share loss, in percentage points, for having
    governed. Positive number = points lost."""
    c = get("cost_of_ruling")
    v = c["interval"][0] if low else (c["interval"][1] if high
                                      else c["value"])
    return v * terms


def net_of_ruling(observed_gap, terms=1.0):
    """Net the ordinary cost of ruling out of an observed vote gap.

    Some of the gap may be the strategy. Some is just that governing
    parties lose votes. This separates them.

    Returns (net_effect, low, high). A net effect at or below zero
    means the strategy explains nothing.
    """
    return (observed_gap - cost_of_ruling(terms),
            observed_gap - cost_of_ruling(terms, high=True),
            observed_gap - cost_of_ruling(terms, low=True))


def gamson(coalition_seat_share, through_origin=False):
    """Predicted share of cabinet posts.

    coalition_seat_share is the party's share of THE COALITION's
    seats, not of parliament. Passing the parliamentary share is the
    standard way this gets used wrong.
    """
    s = float(coalition_seat_share)
    if not 0.0 <= s <= 1.0:
        raise ValueError(
            "seat share must be a fraction of the COALITION's seats, "
            "between 0 and 1; got {}".format(s))
    c = get("gamson")
    if through_origin:
        return c["extra"]["through_origin"] * s
    return c["extra"]["intercept"] + c["value"] * s


def economic_vote(growth_pp, clarity="high"):
    """Expected change in incumbent vote share from GDP growth."""
    c = get("economic_voting")
    if clarity == "low":
        b = c["extra"]["fragmented_government"]
    elif clarity == "high":
        b = c["value"]
    else:
        raise ValueError("clarity must be 'high' or 'low'")
    return b * float(growth_pp)


def effective_parties(shares):
    """Laakso-Taagepera. Pass vote shares or seat shares as fractions
    and say which when you report it."""
    tot = float(sum(shares))
    if tot <= 0:
        raise ValueError("shares must sum to something positive")
    p = [s / tot for s in shares]
    return 1.0 / sum(x * x for x in p)


def volatility(prev, curr):
    """Pedersen index. Both dicts of party -> share in PERCENT."""
    keys = set(prev) | set(curr)
    return 0.5 * sum(abs(curr.get(k, 0.0) - prev.get(k, 0.0))
                     for k in keys)


def disproportionality(votes, seats):
    """Gallagher LSq. Both dicts of party -> share in PERCENT."""
    keys = set(votes) | set(seats)
    return math.sqrt(0.5 * sum(
        (votes.get(k, 0.0) - seats.get(k, 0.0)) ** 2 for k in keys))


def dhondt(votes, total_seats, threshold=0.0, sainte_lague=False):
    """Allocate seats. votes is a dict of party -> votes (or shares).

    threshold is applied first, as a fraction of the total, because in
    practice it decides more outcomes than the divisor does.
    """
    tot = float(sum(votes.values()))
    live = dict((k, v) for k, v in votes.items()
                if tot > 0 and v / tot >= threshold)
    seats = dict((k, 0) for k in votes)
    for _ in range(int(total_seats)):
        best, bq = None, -1.0
        for k, v in live.items():
            d = (2 * seats[k] + 1) if sainte_lague else (seats[k] + 1)
            q = v / float(d)
            if q > bq:
                best, bq = k, q
        if best is None:
            break
        seats[best] += 1
    return seats


def _fmt(cid, paper, subbed, legend, answer, extra=None):
    """Every computed answer comes out in the same shape, because the
    server's standing rule wants notation, substitution and legend
    every time -- and because the misuse warning is welded to the
    number so you cannot get one without the other."""
    c = get(cid)
    o = ["", "=" * 66, "  COMPUTED: " + c["name"].upper(), "=" * 66, "",
         "   ON PAPER", "     " + paper, "",
         "   WITH YOUR NUMBERS IN", "     " + subbed, "",
         "   WHAT EVERY SYMBOL MEANS"]
    for sym, mean in legend:
        body = wrap(mean, 52, "").split("\n")
        o.append("     {:<11} {}".format(sym, body[0].strip()))
        for x in body[1:]:
            o.append("     {:<11} {}".format("", x.strip()))
    o += ["", "   ANSWER", "     " + answer]
    for line in (extra or []):
        o.append("     " + line)
    o += ["", "   BEFORE YOU USE THIS NUMBER", wrap(c["misuse"], 62, "     "),
          ""]
    if c["value"] is not None and c["interval"]:
        o += ["   The constant itself ranges {} to {}. If your conclusion "
              "flips".format(*c["interval"]),
              "   inside that range, the conclusion is the range, not the "
              "point.", ""]
    return "\n".join(o)


def apply(cid, **kw):
    """Compute with a constant. Returns a formatted block."""
    c = get(cid)

    if cid == "cost_of_ruling":
        if "observed_gap" in kw:
            gap = float(kw["observed_gap"])
            t = float(kw.get("terms", 1.0))
            net, lo, hi = net_of_ruling(gap, t)
            verdict = ("the strategy explains NOTHING -- this is the "
                       "ordinary price of office" if net <= 0 else
                       "about {:.2f} pp is left for the strategy to "
                       "explain".format(net))
            return _fmt(
                cid, "δ̂ = Δ_obs − c·t",
                "δ̂ = {:.2f} − 2.25×{:g} = {:.2f}".format(gap, t, net),
                [("δ̂", "the part of the gap the strategy actually "
                        "caused"),
                 ("Δ_obs", "the gap you observed, percentage points"),
                 ("c", "2.25, the average loss per term in office"),
                 ("t", "terms in office")],
                "{:.2f} pp  —  {}".format(net, verdict),
                ["using the low end c=1.6:  {:.2f} pp".format(hi),
                 "using the high end c=2.5: {:.2f} pp".format(lo)])
        t = float(kw.get("terms", 1.0))
        v = cost_of_ruling(t)
        return _fmt(
            cid, "E[Δv] = −c·t", "E[Δv] = −2.25 × {:g} = −{:.2f}".format(t, v),
            [("Δv", "change in the governing party's vote share"),
             ("c", "2.25 percentage points per term"),
             ("t", "terms served")],
            "expect a loss of {:.2f} pp".format(v),
            ["range {:.2f} to {:.2f} pp".format(
                cost_of_ruling(t, low=True), cost_of_ruling(t, high=True))])

    if cid == "gamson":
        s = float(kw["coalition_seat_share"])
        p = gamson(s)
        po = gamson(s, through_origin=True)
        return _fmt(
            cid, "p̂ = α + βs = 0.069 + 0.793s",
            "p̂ = 0.069 + 0.793({:.3f}) = {:.3f}".format(s, p),
            [("p̂", "share of cabinet posts the party gets"),
             ("s", "its share of the COALITION's seats, NOT of "
                   "parliament"),
             ("α", "0.069, a small bonus for junior partners"),
             ("β", "0.793, the slope")],
            "{:.0f} of every 100 ministries; the other {:.0f} go to the "
            "rest".format(100 * p, 100 * (1 - p)),
            ["forced through the origin instead: {:.0f} in 100".format(
                100 * po),
             "R² = 0.89, so 89 in 100 of the variation in who gets "
             "which",
             "ministry is explained by seats and 11 in 100 is not"])

    if cid == "economic_voting":
        g = float(kw["growth_pp"])
        cl = kw.get("clarity", "high")
        v = economic_vote(g, cl)
        b = 1.55 if cl == "high" else 0.92
        return _fmt(
            cid, "Δv = β(C)·g",
            "Δv = {:.2f} × {:g} = {:+.2f}".format(b, g, v),
            [("Δv", "change in the incumbent's vote share"),
             ("g", "GDP growth, percentage points"),
             ("β(C)", "1.55 where responsibility is clear, 0.92 where "
                      "it is fragmented"),
             ("C", "how obvious it is to a voter who to blame")],
            "{:+.2f} pp for the incumbent".format(v),
            ["the other clarity setting would give {:+.2f} pp".format(
                economic_vote(g, "low" if cl == "high" else "high")),
             "the response is stronger on the way DOWN than up"])

    if cid == "effective_parties":
        sh = [float(x) for x in kw["shares"]]
        n = effective_parties(sh)
        tot = sum(sh)
        sq = sum((x / tot) ** 2 for x in sh)
        return _fmt(
            cid, "N = 1 / Σ pᵢ²",
            "N = 1 / {:.4f} = {:.2f}".format(sq, n),
            [("N", "effective number of parties"),
             ("pᵢ", "party i's share, as a fraction"),
             ("Σ", "add these up over every party")],
            "{:.2f} effective parties out of {} listed".format(n, len(sh)))

    if cid == "volatility":
        v = volatility(kw["prev"], kw["curr"])
        return _fmt(
            cid, "V = ½ Σ |pᵢ,ₜ − pᵢ,ₜ₋₁|",
            "V = ½ × {:.1f} = {:.2f}".format(2 * v, v),
            [("V", "volatility in percentage points"),
             ("pᵢ,ₜ", "party i's share now"),
             ("pᵢ,ₜ₋₁", "its share last time"),
             ("½", "halved because every vote that leaves one party "
                   "arrives at another")],
            "{:.2f} pp of the electorate switched party".format(v))

    if cid == "disproportionality":
        d = disproportionality(kw["votes"], kw["seats"])
        sev = ("severe" if d > 10 else "moderate" if d > 5 else "mild")
        return _fmt(
            cid, "LSq = √( ½ Σ (vᵢ − sᵢ)² )",
            "LSq = √({:.2f}) = {:.2f}".format(d * d, d),
            [("LSq", "least-squares disproportionality"),
             ("vᵢ", "party i's vote share, percent"),
             ("sᵢ", "party i's seat share, percent")],
            "{:.2f}  —  {} disproportionality".format(d, sev))

    if cid == "seat_allocation":
        votes = kw["votes"]
        tot_s = int(kw["total_seats"])
        th = float(kw.get("threshold", 0.0))
        sl = bool(kw.get("sainte_lague", False))
        seats = dhondt(votes, tot_s, th, sl)
        tv = float(sum(votes.values()))
        rows = []
        for p, s in sorted(seats.items(), key=lambda x: -x[1]):
            vs = 100.0 * votes[p] / tv
            ss = 100.0 * s / tot_s
            cut = "  (below threshold)" if tv and votes[p] / tv < th else ""
            rows.append("{:<14}{:>6.1f}% votes {:>5} seats {:>6.1f}%{}"
                        .format(p, vs, s, ss, cut))
        top = max(seats.items(), key=lambda x: x[1])
        maj = "YES" if top[1] > tot_s / 2.0 else "no"
        return _fmt(
            cid, "qᵢⱼ = vᵢ / dⱼ,  dⱼ = " +
            ("1,3,5,…" if sl else "1,2,3,…"),
            "one seat at a time to the largest quotient, {} seats, "
            "threshold {:.0%}".format(tot_s, th),
            [("qᵢⱼ", "party i's quotient for its j-th seat"),
             ("vᵢ", "party i's votes"),
             ("dⱼ", "the divisor sequence -- " +
                   ("Sainte-Lague, kinder to small parties" if sl
                    else "D'Hondt, favours large parties"))],
            "largest party {} takes {} of {} seats; majority: {}".format(
                top[0], top[1], tot_s, maj),
            [""] + rows)

    if cid == "duverger":
        m = int(kw["magnitude"])
        return _fmt(
            cid, "n* → M + 1", "n* → {} + 1 = {}".format(m, m + 1),
            [("n*", "viable candidates once voters stop wasting votes"),
             ("M", "district magnitude -- seats that district elects")],
            "about {} viable candidates IN THAT DISTRICT".format(m + 1),
            ["this says nothing about the national party count"])

    if cid == "autocratization_outcome":
        return _fmt(
            cid, "P(breakdown) = k / n",
            "P(breakdown) = 41 / 49 = 0.84",
            [("k", "episodes that ended in democratic breakdown"),
             ("n", "autocratization episodes, 1994-2023")],
            "84 of every 100 episodes broke down; 16 in 100 did not",
            ["the U-turn figure is NOT usable -- see the warning below"])

    if cid == "pitf":
        return ("\nPITF is not computed here. Call the `instability_score` "
                "tool, which carries the model card and refuses to emit a "
                "probability.\n")

    raise KeyError("no apply() for '{}'".format(cid))


def grade(has_interval, tested_out_of_sample, has_dataset):
    """Which slot does a candidate theory belong in?"""
    if has_interval and tested_out_of_sample and has_dataset:
        return ("SLOT 2 -- estimator",
                "It can produce a number. Add it here with its scope.")
    if has_dataset and not has_interval:
        return ("SLOT 3 -- measurement",
                "It supplies inputs, not predictions. Use the dataset; "
                "do not ask the theory for a number.")
    return ("SLOT 1 -- structure generator",
            "It tells you what the steps are. Feed those to chain.py "
            "and let a human price them. Do not invent parameters it "
            "does not have.")


# --------------------------------------------------------------------
# report
# --------------------------------------------------------------------

def wrap(s, w=68, ind="     "):
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


def show(c):
    print("=" * 74)
    print("  {}   [{}]".format(c["name"].upper(), c["status"]))
    print("=" * 74)
    print()
    print(wrap(c["what"], 68, "   "))
    print()
    if c["value"] is not None:
        lo, hi = c["interval"]
        print("   VALUE     {} {}".format(c["value"], c["unit"]))
        print("   RANGE     {} to {}".format(lo, hi))
    else:
        print("   VALUE     none -- {}".format(c["unit"]))
    print()
    print("   ON PAPER")
    print("     " + c["paper"])
    print()
    print("   WITH THE NUMBERS IN")
    print(wrap(c["worked"], 66, "     "))
    print()
    print("   WHAT EVERY SYMBOL MEANS")
    for sym, mean in c["legend"]:
        body = wrap(mean, 52, "").split("\n")
        print("     {:<11} {}".format(sym, body[0].strip()))
        for extra in body[1:]:
            print("     {:<11} {}".format("", extra.strip()))
    print()
    print("   MEASURED ON")
    print(wrap(c["n"], 66, "     "))
    print("   SOURCE")
    print(wrap(c["source"], 66, "     "))
    print()
    print("   HOLDS FOR")
    for s in c["scope"]:
        print(wrap("- " + s, 64, "     "))
    if c["out_of_scope"]:
        print()
        print("   DOES NOT HOLD FOR")
        for s in c["out_of_scope"]:
            print(wrap("- " + s, 64, "     "))
    print()
    print("   HOW IT GETS USED WRONG")
    print(wrap(c["misuse"], 66, "     "))
    print()


def table():
    """The catalogue, the filters and the rejected list. No worked
    examples -- those are in main()."""
    print("=" * 74)
    print("  THE CONSTANTS FILE -- published regularities with scope")
    print("=" * 74)
    print()
    print(wrap("Slot 2 only: things that produce a number. "
               "Classification schemes are slot 1 -- they "
               "generate the steps of a chain and predict nothing, "
               "which is not a criticism, it is what a classification "
               "scheme is for.", 70, "  "))
    print()

    print("  {:<26}{:>10}  {:<28}".format("constant", "value", "status"))
    print("  " + "-" * 70)
    for c in CONSTANTS:
        v = "--" if c["value"] is None else "{:.3f}".format(c["value"])
        st = c["status"]
        st = st if len(st) <= 30 else st.split(" -- ")[0] + " *"
        print("  {:<26}{:>10}  {:<30}".format(c["id"], v, st))
    print()
    print("     * see the entry for the caveat: "
          "python harness/constants.py <id>")
    print()

    print("  " + "-" * 70)
    print("  THE THREE FILTERS FOR ADMISSION")
    print("  " + "-" * 70)
    for i, q in enumerate(THREE_FILTERS, 1):
        print("   {}. {}".format(i, q))
    print()
    print(wrap("Fail any one and it is slot 1 or slot 3. grade() "
               "returns which.", 68, "   "))
    print()

    print("  " + "-" * 70)
    print("  REJECTED -- look like constants, are not")
    print("  " + "-" * 70)
    print()
    for name, why in REJECTED:
        print("   " + name)
        print(wrap(why, 64, "      "))
        print()


def main():
    if len(sys.argv) > 1:
        show(get(sys.argv[1]))
        return

    table()

    print("=" * 74)
    print("  WORKED: GAMSON'S LAW, SEATS TO MINISTRIES")
    print("=" * 74)
    print()
    print("     on paper      p̂ = α + βs = 0.069 + 0.793s")
    print()
    print("   {:<34}{:>14}".format(
        "share of the COALITION's seats", "ministries"))
    print("   " + "-" * 50)
    for s in (0.20, 0.35, 0.50, 0.65, 0.85):
        print("   {:<34.0%}{:>13.0%}".format(s, gamson(s)))
    print()
    print(wrap("R² = 0.89, so this explains 89 in 100 of the variation "
               "in who gets which ministry and 11 in 100 is something "
               "else. Portfolios track seats almost mechanically.",
               70, "   "))
    print()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
