#!/usr/bin/env python3
"""
ancestry.py -- where each module in this toolkit already existed.

WHY THIS FILE EXISTS, AND IT IS AN ADMISSION.

Almost every module here has an ancestor in intelligence analysis
tradecraft, most of them decades old, all of them public. They were
not consulted while building this. They were reconstructed, without
attribution, by a model that was near-certainly trained on them --
Heuer's `Psychology of Intelligence Analysis` is published by the CIA
on its own website, ICD 203 is public, Kent's 1964 paper is in the CIA
reading room, Tetlock's results are in bestselling books.

Reconstructing a known framework and not citing it is worse than
either inventing it or citing it. It reads as originality, it is not,
and it costs the reader the ability to go and read the original, which
is better than the reconstruction.

This project already tags NUMBERS by provenance -- MEASURED, EXTENDED,
MINE, in constants.py. It was not tagging IDEAS. This file is that
tag.

THE ONE EMPTY ROW IS THE POINT. Eight modules have ancestors. `ledger`
does not, and the reason is structural rather than an oversight:
classification prevents a public calibration score, because scoring a
classified estimate discloses what was estimated. Their own forecasting
tournament found that tracked, scored, publicly-compared forecasting
was what separated the best forecasters from intelligence officers
holding clearances. The one column they cannot fill is the one their
own experiment identified as decisive.

Run:  python harness/ancestry.py
"""

import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import router as R  # noqa: E402


ANCESTRY = [
    {
        "ours": "causal_rivals (router shape)",
        "theirs": "Analysis of Competing Hypotheses (ACH)",
        "who": "Richards J. Heuer Jr., 45-year CIA veteran",
        "when": "1970s; published in Psychology of Intelligence "
                "Analysis, 1999",
        "same": "Weigh several explanations against the same evidence "
                "rather than building a case for one. Heuer's version "
                "is a matrix; ours is Bayes in odds form. Identical "
                "purpose.",
        "different": "ACH scores evidence for DIAGNOSTICITY -- how well "
                     "it discriminates between hypotheses -- and "
                     "explicitly seeks to DISCONFIRM rather than "
                     "confirm. Ours groups correlated evidence before "
                     "multiplying, which ACH does not formalise. Both "
                     "moves are worth having and neither has both.",
        "read": "https://www.cia.gov/ -- Psychology of Intelligence "
                "Analysis is published in full",
    },
    {
        "ours": "percentages stated both directions",
        "theirs": "Words of Estimative Probability (WEP)",
        "who": "Sherman Kent, founder of the Office of National "
               "Estimates",
        "when": "1964",
        "same": "Kent found National Intelligence Estimates using "
                "'probable' where different readers understood "
                "anything from 25% to 90%. He split analysts into "
                "'poets' and 'mathematicians' and built a table "
                "binding estimative words to numeric ranges. That is "
                "this project's rule, sixty years earlier.",
        "different": "Kent standardised the WORDS. This project "
                     "standardises the DIRECTION -- '7 in 100 yes, 93 "
                     "in 100 no' -- which attacks a different failure: "
                     "a reader who takes 7% as small without noticing "
                     "what the other 93% contains.",
        "read": "CIA reading room, CIA-RDP93T01132R000100020036-3",
    },
    {
        "ours": "SHOW_WORK (the standing rules on every tool)",
        "theirs": "ICD 203, Intelligence Community Analytic Standards",
        "who": "Office of the Director of National Intelligence",
        "when": "2007, revised 2015",
        "same": "Nine tradecraft standards including: properly "
                "describe quality and credibility of sources, properly "
                "express uncertainties, distinguish underlying "
                "intelligence from assumptions, incorporate analysis "
                "of alternatives, be logically argued. That is most of "
                "SHOW_WORK.",
        "different": "ICD 203 does not require the formula, the "
                     "substitution and the legend. It requires "
                     "uncertainty be expressed, not that the "
                     "derivation be reproducible by the reader.",
        "read": "https://www.intelligence.gov/assets/documents/"
                "intelligence-community-directives/ICD_203.pdf",
    },
    {
        "ours": "MEASURED / EXTENDED / MINE provenance tags",
        "theirs": "ICD 203 standards 2 and 3",
        "who": "ODNI",
        "when": "2007",
        "same": "'Properly describes quality and credibility of "
                "underlying sources' and 'properly distinguishes "
                "between underlying intelligence and analysts' "
                "assumptions and judgments'. Same three-way split, "
                "same reason.",
        "different": "Ours names the specific failure -- a constant "
                     "used outside the population it was measured on "
                     "-- and refuses to print the number without the "
                     "warning attached.",
        "read": "same ICD 203",
    },
    {
        "ours": "mirror.py (audit your own correction)",
        "theirs": "Red Cell, Team B, devil's advocacy",
        "who": "CIA and successors",
        "when": "1970s onward; Red Cell formalised after 2001",
        "same": "Somebody adversarially attacks the finished product "
                "before it ships.",
        "different": "Theirs is a SEPARATE TEAM attacking your work. "
                     "Ours is the same analyst turning the same "
                     "instrument on themselves, which is weaker -- a "
                     "second team is better and this project has no "
                     "way to field one. Ours is also PUBLISHED with "
                     "the finding, which theirs is not.",
        "read": "widely documented; see the 9/11 Commission and the "
                "2005 WMD Commission reports",
    },
    {
        "ours": "steelman.py",
        "theirs": "alternative analysis / 'analysis of alternatives'",
        "who": "ODNI, mandated in ICD 203",
        "when": "2007",
        "same": "Consider the strongest competing account before "
                "settling.",
        "different": "Theirs is about alternative HYPOTHESES for the "
                     "world. Ours is about the strongest reading of a "
                     "PERSON'S CLAIM, which is a different target. The "
                     "`what_you_supplied` requirement -- list every "
                     "word you added -- is not in the IC version and "
                     "is the part that makes it auditable.",
        "read": "same ICD 203",
    },
    {
        "ours": "denominator and window_shopping sweeps",
        "theirs": "Key Assumptions Check; Quality of Information Check",
        "who": "Heuer & Pherson, Structured Analytic Techniques",
        "when": "formalised 2010",
        "same": "Surface the choices that were made silently and test "
                "whether the conclusion survives them.",
        "different": "The academic lineage is closer here than the "
                     "intelligence one -- specification curve analysis "
                     "(Simonsohn, Simmons & Nelson 2020) and multiverse "
                     "analysis (Steegen, Tuerlinckx, Gelman & "
                     "Vanpaemel 2016) do it quantitatively, which the "
                     "SAT version does not.",
        "read": "Heuer & Pherson, Structured Analytic Techniques for "
                "Intelligence Analysis",
    },
    {
        "ours": "instability_score (pitf.py)",
        "theirs": "Political Instability Task Force",
        "who": "US government-funded, Goldstone et al.",
        "when": "1994 onward; the model used here is 2010",
        "same": "IT IS THEIRS. Not an ancestor -- the actual thing, "
                "imported. The only module in this toolkit that is a "
                "direct copy rather than a reconstruction.",
        "different": "Nothing. This project's contribution was "
                     "refusing to invent the intercept the paper does "
                     "not publish.",
        "read": "Goldstone et al. 2010, AJPS 54(1):190-208",
    },
    {
        "ours": "ledger.py -- published calibration record",
        "theirs": None,
        "who": None,
        "when": None,
        "same": None,
        "different": "THERE IS NO ANCESTOR, and the reason is "
                     "structural rather than cultural. A running "
                     "public calibration score on classified estimates "
                     "would disclose what was estimated. Their major "
                     "postmortems -- Iraq WMD 2005, the 9/11 "
                     "Commission -- were forced by catastrophe, not "
                     "run as routine.\n\nAnd their own tournament "
                     "found this was the decisive variable. IARPA's "
                     "Aggregative Contingent Estimation programme ran "
                     "2011-2015: 500 questions, over a million "
                     "forecasts. The Good Judgment Project won, and "
                     "its top forecasters were reported about 30% "
                     "better than intelligence officers holding "
                     "clearances. What separated them was tracked, "
                     "scored, publicly-compared forecasting with the "
                     "errors visible.\n\nThe one column they cannot "
                     "fill is the one their own experiment identified "
                     "as decisive. That is the whole argument for this "
                     "being public rather than a product.",
        "read": "IARPA ACE; Tetlock & Gardner, Superforecasting",
    },
]


def wrap(t, w=66, ind="   "):
    return R.wrap(t, w, ind)


def main():
    print("=" * 74)
    print("  ANCESTRY -- where each of these already existed")
    print("=" * 74)
    print()
    print(wrap(
        "None of these were consulted while building this toolkit. "
        "They were reconstructed without attribution by a model "
        "near-certainly trained on them, since all of it is public. "
        "That is worse than inventing or citing, because it reads as "
        "originality, is not, and costs you the better original.",
        70, "  "))
    print()
    print("  {:<38}{:<34}".format("OURS", "THEIRS"))
    print("  " + "-" * 70)
    for a in ANCESTRY:
        t = a["theirs"] or "*** NOTHING ***"
        print("  {:<38}{:<34}".format(a["ours"][:36], t[:32]))
        if a["when"]:
            print("  {:<38}{:<34}".format("", a["when"][:32]))
    print()
    for a in ANCESTRY:
        print("=" * 74)
        print("  " + a["ours"].upper())
        print("=" * 74)
        print()
        if a["theirs"]:
            print("   THEIRS:  " + a["theirs"])
            print("   WHO:     " + a["who"])
            print("   WHEN:    " + a["when"])
            print()
            print("   THE SAME BECAUSE")
            print(wrap(a["same"], 66, "     "))
            print()
            print("   DIFFERENT BECAUSE")
            print(wrap(a["different"], 66, "     "))
            print()
            print("   READ THE ORIGINAL")
            print(wrap(a["read"], 66, "     "))
        else:
            print("   THEIRS:  NOTHING. This is the only one.")
            print()
            for para in a["different"].split("\n\n"):
                print(wrap(para, 66, "     "))
                print()
            print("   READ")
            print(wrap(a["read"], 66, "     "))
        print()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
