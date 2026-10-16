#!/usr/bin/env python3
"""
audit.py -- run a question through every check, cheapest first, and stop early.

The five tools were built in the order they were discovered. That is the wrong
order to USE them in. The right order is by cost, because the cheap checks kill
most questions and there is no point sourcing citations for a question that
cannot carry a model.

    1. BUDGET      does the sample support any model at all?      free
    2. FRAME       is the question well-posed?                    free
    3. LINEAGE     do the sources collapse to one origin?         minutes
    4. ENTAILMENT  does the evidence support THIS claim?          minutes
    5. LEDGER      write the prediction down before you check     seconds

The short-circuit is the point. A question that fails stage 1 dies in two
seconds, and you never write the other four sections. That is the workflow:
author one section, run it, and only write the next if the previous survived.

A question file is progressive -- it only needs the sections it got far
enough to need.

Run:  python harness/audit.py <name>     -- one question
      python harness/audit.py            -- all
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402  (sits next to this file)
sys.path.insert(0, HERE)
QUESTIONS = paths.data("questions")

import budget as B      # noqa: E402
import frame as F       # noqa: E402
import lineage as L     # noqa: E402
import entail as E      # noqa: E402

BAR = "=" * 74


def load(name):
    p = os.path.join(QUESTIONS, name if name.endswith(".json") else name + ".json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def stage(n, title, cost):
    print()
    print(BAR)
    print(f"STAGE {n} — {title}    [{cost}]")
    print(BAR)


def halt(n, why, saved):
    print()
    print("!" * 74)
    print(f"HALTED AT STAGE {n}")
    print("!" * 74)
    for line in E.wrap(why, 70):
        print(f"  {line}")
    print()
    print(f"  You did not need to write: {', '.join(saved)}.")
    print("  That is the saving. Most questions end here, and ending here")
    print("  costs seconds instead of months.")
    print()


def run(name, d):
    print(BAR)
    print(f"AUDIT: {d['question']}")
    print(BAR)

    # ---- 1. budget ----------------------------------------------------
    if "budget" in d:
        stage(1, "VARIABLE BUDGET", "free")
        a = B.analyse(d["budget"])
        v, why = B.verdict(a)
        print(f"  usable cases {a['n_use']}   independent groups {a['n_clu']}"
              f"   budget {a['budget_low']}-{a['budget_high']}")
        print(f"  VERDICT: {v}")
        for line in E.wrap(why, 70):
            print(f"    {line}")
        if v == "STOP":
            halt(1, why, ["a frame", "a source list", "an entailment breakdown"])
            return "STOPPED AT BUDGET"
        want = d["budget"].get("variables_wanted", [])
        if want and len(want) > a["budget_low"]:
            print(f"\n  Cut {len(want) - a['budget_low']} of your "
                  f"{len(want)} variables before proceeding.")
    else:
        print("\n  (no budget section — skipping the cheapest check, "
              "which is a mistake)")

    # ---- 2. frame -----------------------------------------------------
    if "frame" in d:
        stage(2, "QUESTION FRAME", "free")
        r = F.check(d["frame"])
        print(f"  VERDICT: {r.verdict}")
        for _, m in r.fail:
            for line in E.wrap("FAIL  " + m, 70):
                print(f"    {line}")
        for _, m in r.warn:
            for line in E.wrap("WARN  " + m, 70):
                print(f"    {line}")
        if r.fail:
            halt(2, "The question cannot be answered as posed. Fix the frame "
                    "before spending anything on sources.",
                 ["a source list", "an entailment breakdown"])
            return "STOPPED AT FRAME"

    # ---- 3. lineage ---------------------------------------------------
    worst = None
    if "lineage" in d:
        stage(3, "SOURCE LINEAGE", "minutes")
        for claim in d["lineage"]:
            idx, oo, origins, echoes, cyc = L.analyse(claim)
            lv, lwhy = L.verdict(idx, origins, cyc)
            print(f"  {len(claim['sources'])} sources -> "
                  f"{len(origins)} independent origin(s)")
            print(f"  VERDICT: {lv}")
            for line in E.wrap(lwhy, 70):
                print(f"    {line}")
            if lv != "INDEPENDENT":
                worst = lv
            print()

    # ---- 4. entailment ------------------------------------------------
    gaps = []
    if "entailment" in d:
        stage(4, "ENTAILMENT", "minutes")
        gaps = E.check(d["entailment"])
        if not gaps:
            print("  ENTAILED — the claim does not overreach its support.")
        else:
            print(f"  {len(gaps)} gap(s): "
                  + ", ".join(sorted({g.kind for g in gaps})))
            print()
            print("  STRONGEST CLAIM THE EVIDENCE SUPPORTS")
            for line in E.wrap(E.strongest_supported(d["entailment"], gaps), 68):
                print(f"    {line}")

    # ---- 5. ledger ----------------------------------------------------
    stage(5, "LEDGER", "seconds")
    p = d.get("prediction")
    if p:
        print(f"  claim      {p['claim']}")
        print(f"  p          {p['probability']:.2f}")
        print(f"  baseline   {p['baseline']['probability']:.2f}  "
              f"({p['baseline']['what']})")
        print(f"  resolves   {p['resolves']}")
        print(f"\n  Append to harness/ledger/claims.json, then check on the date.")
    else:
        print("  No prediction recorded. If you are going to act on this,")
        print("  write down what you expect first — it is the only stage")
        print("  that can ever tell you whether any of the others help.")

    print()
    print(BAR)
    if worst and gaps:
        out = f"CLEARED WITH WARNINGS — {worst}, {len(gaps)} entailment gap(s)"
    elif worst:
        out = f"CLEARED WITH WARNINGS — {worst}"
    elif gaps:
        out = f"CLEARED WITH WARNINGS — {len(gaps)} entailment gap(s)"
    else:
        out = "CLEARED"
    print(f"RESULT: {out}")
    print(BAR)
    return out


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else None
    files = sorted(f for f in os.listdir(QUESTIONS) if f.endswith(".json"))
    if want:
        files = [f for f in files if want in f]
    if not files:
        print("no questions found"); return
    tally = {}
    for fn in files:
        tally[fn[:-5]] = run(fn[:-5], load(fn))
        print()
    if len(files) > 1:
        print(BAR)
        print("SUMMARY")
        print(BAR)
        for k, v in tally.items():
            print(f"  {k:<22} {v}")


if __name__ == "__main__":
    main()
