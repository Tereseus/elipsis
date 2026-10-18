"""Ten anti-ageing claims from a video, as claim rows: verdict, gap-map entry, and the chance
each line reaches people by 2030, 2035, 2040 and 2050. Case of 2026-10-17, rerun 2026-10-18
with two pieces of news the gap map had and the case missed (VITAL-H; the FDA at ARDD).

In place = approved by the FDA or the EMA for the row's milestone. Each row is one or more
routes (chains of steps), behind any shared steps every route needs:

  P(by Y) = S x (1 - product over routes of (1 - P_r)) x P(the steps finish before the end of Y)
  P_r     = product of the route's step chances

Step chances start from BIO, Informa and QLS, "Clinical Development Success Rates 2011-2020"
(2021): phase 1 to 2: 0.52; phase 2 to 3: 0.29; phase 3 to filing: 0.58; filing to approval:
0.91. Typical lengths: 2.3, 3.6, 3.3 and 1.3 years, each drawn from a lognormal (spread 0.45).
Every adjustment is written next to its step. The maths is in harness/claimrows.py.

    python ageing_milestones.py          print the table and each row's weakest step
    python ageing_milestones.py --save   also save the rows to the claim-row store
"""
import os
import sys


def _find_harness():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        d = os.path.dirname(d)
        if os.path.exists(os.path.join(d, "harness", "claimrows.py")):
            return os.path.join(d, "harness")
    sys.exit("claimrows.py not found: run this from inside an Elipsis folder")


sys.path.insert(0, _find_harness())
import claimrows as CR  # noqa: E402

NOW = 2026 + 290 / 365          # 18 October 2026
PH1, PH2, PH3, REVIEW = 2.3, 3.6, 3.3, 1.3
CASE = "2026-10-17_ageing-top-ten-video"
SRC = "YouTube video, a 'top ten' of anti-ageing discoveries"
BIO = "BIO/Informa/QLS 2021 base rate"


def step(stage, kind, p, median, done=0, why=""):
    return {"stage": stage, "kind": kind, "p": p, "median": median, "done": done, "why": why}


def row(n, claim, verdict, evidence, milestone, about=None, blocked_by=None, **chain):
    r = {"id": f"{CASE}#{n}", "case": f"cases/claims/{CASE}.md", "claim_no": n,
         "claim": claim, "source": SRC, "date": "2026-10-17", "field": "ageing",
         "about": about, "blocked_by": blocked_by, "evidence": evidence,
         "verdict": verdict, "milestone": milestone, "outcome": None}
    r.update(chain)
    return r


LTME = "long-term-multimorbidity-endpoints"
FPB = "faster-proxy-biomarkers"
CAIS = "combinatorial-aging-interventions-screening"
DIBM = "developing-immortal-biological-models"
TAME_START = {"stage": "TAME fully funded and started", "kind": "funding or start",
              "per_year": 0.077, "max_years": 10,
              "why": "gap map's count: 0 starts in 11 years since 2015; rule of succession "
                     "(0 + 1) / (11 + 2) = 0.077 a year, for at most 10 more years "
                     "(was a guessed 0.45 within about 2.5 years)"}
RAPA_BIOLOGY = step("rapamycin-type drugs slow ageing in people enough for a trial to show it",
                    "first effect in people", 0.40, 0,
                    why="guessed; strong in mice, PEARL (2025) missed its main goal; "
                        "both routes need it, so it is not counted twice")

ROWS = [
    row("10", "one gene change made a worm live '10 times longer'", "wrong", "animals",
        "a drug lowering the insulin/IGF-1 signal approved for ageing", blocked_by=LTME,
        routes=[{"name": "usual trials", "stages": [
            step("a trial for ageing opens", "funding or start", 0.30, 3.0, why="none exists"),
            step("phase 1", "safety in people", 0.50, PH1, why="0.52 " + BIO),
            step("phase 2", "first effect in people", 0.25, PH2, why="0.29 " + BIO + ", lowered"),
            step("phase 3", "confirmation", 0.50, PH3, why="0.58 " + BIO + ", lowered"),
            step("review", "regulator", 0.90, REVIEW, why="0.91 " + BIO)]}]),
    row("9", "the jellyfish reverts to its earliest stage 'an unlimited number of times'",
        "holds", "animals", "any human therapy derived from it", about=DIBM,
        guessed={2030: 0, 2035: 0, 2040: 0, 2050: 1}),
    row("8", "switching telomerase on made mice younger and longer-lived without cancer",
        "holds", "animals", "a telomerase therapy approved for an age-related use",
        blocked_by=LTME,
        routes=[{"name": "usual trials", "stages": [
            step("a regulated trial opens", "funding or start", 0.50, 3.0,
                 why="only a pay-to-enrol study in Colombia exists"),
            step("phase 1", "safety in people", 0.50, PH1),
            step("phase 2", "first effect in people", 0.25, PH2),
            step("phase 3", "confirmation", 0.50, PH3),
            step("review", "regulator", 0.90, REVIEW)]}]),
    row("7", "rapamycin raised mouse lifespan 'up to 14%'", "holds", "animals",
        "a rapamycin-type drug approved for an age-related use", about=CAIS, blocked_by=LTME,
        shared=[RAPA_BIOLOGY],
        routes=[
            {"name": "a new mTOR drug through the usual trials", "stages": [
                step("phase 2", "first effect in people", 0.625, PH2, done=1.0,
                     why="0.25 overall = 0.40 shared x 0.625"),
                step("phase 3", "confirmation", 0.50, PH3),
                step("review", "regulator", 0.90, REVIEW)]},
            {"name": "VITAL-H (ARPA-H, up to $38 million, 726 people in their 60s)", "stages": [
                step("enrols", "funding or start", 0.85, 0.8,
                     why="funded February 2026; enrolment expected late 2026 or 2027"),
                step("the rapamycin arm beats placebo on intrinsic capacity",
                     "first effect in people", 0.75, 4.5,
                     why="0.30 overall = 0.40 shared x 0.75; five-year contract"),
                step("FDA approves an ageing-related label", "regulator", 0.50, 1.5,
                     why="an FDA official outlined intrinsic capacity as one of two possible "
                         "approaches (October 2026), not yet accepted; generic drug, no sponsor")]}]),
    row("6a", "metformin users outlived healthy people; TAME 'officially reclassified aging'",
        "wrong", "people, observational", "TAME reports a positive primary result",
        blocked_by=LTME,
        routes=[{"name": "TAME", "stages": [
            TAME_START,
            step("the trial is positive", "first effect in people", 0.30, 6.0,
                 why="the 2022 twin study weakened the case")]}]),
    row("6b", "metformin users outlived healthy people; TAME 'officially reclassified aging'",
        "wrong", "people, observational", "metformin approved for an ageing-related use",
        blocked_by=LTME,
        routes=[{"name": "TAME", "stages": [
            TAME_START,
            step("the trial is positive", "first effect in people", 0.30, 6.0),
            step("FDA approves a new kind of label", "regulator", 0.70, 1.5,
                 why="was 0.60; raised because an FDA office said in October 2026 that it "
                     "is responsible for ageing as an indication and asked for protocols")]}]),
    row("5a", "NAD+ has 'fallen by 50%' by middle age; boosters restore it", "partly",
        "people, small trial", "NAD+ boosters on sale legally as US supplements",
        guessed={2030: 100, 2035: 100, 2040: 100, 2050: 100}),
    row("5b", "NAD+ has 'fallen by 50%' by middle age; boosters restore it", "partly",
        "people, small trial", "an NAD+ drug approved for an age-related condition",
        routes=[{"name": "usual trials", "stages": [
            step("phase 2", "first effect in people", 0.25, PH2, done=2.0),
            step("phase 3", "confirmation", 0.50, PH3),
            step("a company pays for it", "funding or start", 0.60, 0.01,
                 why="it sells cheaply as a supplement"),
            step("review", "regulator", 0.90, REVIEW)]}]),
    row("4", "young blood made old mice younger; GDF11 alone rejuvenated them", "partly",
        "animals", "plasma exchange approved for an age-related disease", about=FPB,
        routes=[{"name": "usual trials", "stages": [
            step("a large trial starts", "funding or start", 0.35, 2.5,
                 why="one 42-person trial (2025) so far"),
            step("it shows a clinical effect (Alzheimer's)", "first effect in people", 0.25, PH3),
            step("review", "regulator", 0.85, REVIEW)]}]),
    row("3", "clearing 'zombie' cells extended mouse life; arthritis trials under way",
        "partly", "animals", "a senolytic approved for an age-related disease", about=CAIS,
        routes=[{"name": "usual trials", "stages": [
            step("phase 2", "first effect in people", 0.35, PH2, done=2.0,
                 why="0.29 " + BIO + ", raised: several drugs tested at once"),
            step("phase 3", "confirmation", 0.55, PH3),
            step("review", "regulator", 0.90, REVIEW)]}]),
    row("2", "ageing is corrupted epigenetic software, 'a primary reason we age'", "partly",
        "people, observational", "the FDA accepts an ageing clock as a trial endpoint",
        about=FPB, blocked_by=FPB, guessed={2030: 2, 2035: 7, 2040: 15, 2050: 30}),
    row("1", "four factors reset cells; a short dose restored sight in old mice", "holds",
        "animals", "partial reprogramming approved for an eye disease",
        routes=[{"name": "ER-100 and successors", "stages": [
            step("phase 1", "safety in people", 0.50, PH1, done=0.35,
                 why="first person dosed June 2026"),
            step("phase 2", "first effect in people", 0.25, PH2,
                 why="0.29 " + BIO + ", lowered: first of its kind, tumour risk"),
            step("phase 3", "confirmation", 0.55, PH3),
            step("review", "regulator", 0.90, REVIEW)]}]),
]


def main():
    computed = [CR.compute(r, NOW) for r in ROWS]
    print(f"{'':6s}{'ever':>6s}  " + "  ".join(f"{y:>5d}" for y in CR.YEARS) + "   weakest step")
    for c in computed:
        o = c["odds"]
        ev = f"{c['p_ever']:6.1f}" if c["p_ever"] is not None else " guess"
        w = c["weakest"]
        tail = f"   {w['stage']} ({w['p']:.2f}, worth {w['worth']:.2f})" if w else ""
        print(f"{c['claim_no']:6s}{ev}  " + "  ".join(f"{o[str(y)]:5.1f}" for y in CR.YEARS) + tail)
    # at least one drug approved: every chained row except 6a (a trial result, not an approval)
    drugs = [c for c in computed if c.get("routes") and c["claim_no"] != "6a"]
    for y in CR.YEARS:
        none = 1.0
        for c in drugs:
            none *= 1 - c["odds"][str(y)] / 100
        print(f"at least one drug approved by {y}, if independent: {100 * (1 - none):.1f} in 100")
    if "--save" in sys.argv:
        print(CR.add(ROWS, "rerun 2026-10-18: VITAL-H route; TAME start from the gap map's "
                           "count; FDA label step 0.60 to 0.70"))


if __name__ == "__main__":
    main()
