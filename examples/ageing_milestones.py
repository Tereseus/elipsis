"""Chance that each of ten ageing interventions is in place by 2030, 2035, 2040 and 2050.
Case: ten anti-ageing claims from a video, Round 2 (2026-10-17).

In place = approved by the FDA or the EMA for an ageing-related use in people, unless the row says
otherwise. Each row is a chain of the stages still ahead: the chance all succeed, times the chance
the time they take fits before the year.

  P(in place by Y) = p_1 x p_2 x ... x p_k x P(T_1 + ... + T_k <= Y - now)

Stage success rates start from BIO, Informa and QLS, "Clinical Development Success Rates 2011-2020"
(2021): phase 1 to 2: 0.52; phase 2 to 3: 0.29; phase 3 to filing: 0.58; filing to approval: 0.91.
Median stage times from the same report: phase 1: 2.3 years, phase 2: 3.6, phase 3: 3.3, review: 1.3.
Each stage time is drawn from a lognormal around its median (spread 0.45 on the log scale).
Adjustments to the base rates are written next to each row. Standard library only.
"""
import math
import random

NOW = 2026 + 290 / 365          # 17 October 2026
YEARS = (2030, 2035, 2040, 2050)  # read as "by the end of that year"
SIMS = 200_000
SPREAD = 0.45

PH1, PH2, PH3, REVIEW = 2.3, 3.6, 3.3, 1.3
# (name, milestone, [(stage, chance of success, median years, years already spent)])
ROWS = [
    ("1 Yamanaka partial reprogramming", "approved for an eye disease (glaucoma or NAION)",
     [("phase 1", 0.50, PH1, 0.35), ("phase 2", 0.25, PH2, 0), ("phase 3", 0.55, PH3, 0), ("review", 0.90, REVIEW, 0)]),
    ("3 Senolytics", "any senolytic approved for an age-related disease",
     [("phase 2", 0.35, PH2, 2.0), ("phase 3", 0.55, PH3, 0), ("review", 0.90, REVIEW, 0)]),
    ("4 Young blood / plasma exchange", "approved for an age-related disease (e.g. Alzheimer's)",
     [("a pivotal trial starts", 0.35, 2.5, 0), ("phase 3", 0.25, PH3, 0), ("review", 0.85, REVIEW, 0)]),
    ("5 NAD+ boosters, as a drug", "an NAD+ drug approved for an age-related condition",
     [("phase 2", 0.25, PH2, 2.0), ("phase 3", 0.50, PH3, 0), ("a sponsor pays for it", 0.60, 0.01, 0), ("review", 0.90, REVIEW, 0)]),
    ("6a Metformin: TAME result", "TAME reports a positive primary result",
     [("fully funded and started", 0.45, 2.5, 0), ("the trial", 0.30, 6.0, 0)]),
    ("6b Metformin: ageing label", "the FDA approves metformin for an ageing-related use",
     [("fully funded and started", 0.45, 2.5, 0), ("the trial", 0.30, 6.0, 0), ("review of a new kind of label", 0.60, 1.5, 0)]),
    ("7 Rapamycin / mTOR inhibitors", "an mTOR inhibitor approved for an age-related use",
     [("phase 2", 0.25, PH2, 1.0), ("phase 3", 0.50, PH3, 0), ("review", 0.90, REVIEW, 0)]),
    ("8 Telomerase therapy", "a telomerase therapy approved for an age-related use",
     [("a regulated trial opens", 0.50, 3.0, 0), ("phase 1", 0.50, PH1, 0), ("phase 2", 0.25, PH2, 0), ("phase 3", 0.50, PH3, 0), ("review", 0.90, REVIEW, 0)]),
    ("10 daf-2 / insulin-IGF-1 drugs", "a drug lowering this signal approved for ageing",
     [("a trial for ageing opens", 0.30, 3.0, 0), ("phase 1", 0.50, PH1, 0), ("phase 2", 0.25, PH2, 0), ("phase 3", 0.50, PH3, 0), ("review", 0.90, REVIEW, 0)]),
]
# Not chained (no pipeline to chain); guessed directly, chance in 100 by 2030, 2035, 2040, 2050.
GUESSED = [
    ("2 Epigenetic clock as an accepted endpoint", "the FDA accepts an ageing clock as a trial endpoint", (2, 7, 15, 30)),
    ("5 NAD+ boosters, as supplements", "on sale legally in the US", (100, 100, 100, 100)),
    ("9 Jellyfish (Turritopsis) biology", "any human therapy derived from it", (0, 0, 0, 1)),
]


def run(stages, rng):
    p_all = math.prod(p for _, p, _, _ in stages)
    hits = [0] * len(YEARS)
    for _ in range(SIMS):
        t = 0.0
        for _, _, med, done in stages:
            t += max(0.2, med * math.exp(rng.gauss(0, SPREAD)) - done)
        for i, y in enumerate(YEARS):
            if NOW + t <= y + 1:
                hits[i] += 1
    return p_all, [p_all * h / SIMS for h in hits]


def main():
    rng = random.Random(20261017)
    print(f"{'':36s} {'all succeed':>11s}   " + "  ".join(f"by {y}" for y in YEARS))
    rows = []
    for name, what, stages in ROWS:
        p_all, by = run(stages, rng)
        rows.append((name, by))
        chain = " x ".join(f"{p:.2f}" for _, p, _, _ in stages)
        print(f"{name:36s} {100 * p_all:9.1f}    " + "  ".join(f"{100 * b:7.1f}" for b in by) + f"   [{chain}]")
    for name, what, g in GUESSED:
        print(f"{name:36s} {'guessed':>11s}   " + "  ".join(f"{v:7.0f}" for v in g))
    # at least one of the drug chains (rows 1, 3, 4, 5, 6b, 7, 8, 10), if they were independent
    keep = [r for r in rows if not r[0].startswith("6a")]
    for i, y in enumerate(YEARS):
        none = math.prod(1 - b[i] for _, b in keep)
        print(f"at least one approved by {y}, if independent: {100 * (1 - none):.1f} in 100")


if __name__ == "__main__":
    main()
