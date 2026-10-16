#!/usr/bin/env python3
"""
budget.py -- how many variables are you allowed?

Everyone works in the wrong order. You list the variables you think matter,
then go hunting for data. This inverts it: count the data first, and let it
tell you how big a model you are permitted to build.

The number is not a matter of taste. With N observations you can estimate
roughly sqrt(N) parameters before you are fitting noise instead of signal.
Past that, every variable you add buys a better fit to this sample and a
worse prediction of the next one.

Two corrections matter more than the headline count:

  USABLE, NOT NOMINAL. Allcott had 111 trials and 61 of his 101 target sites
  fell outside the support of the rest. Cases that fail transport are not
  cases. Count what you can actually use.

  CLUSTERS, NOT CASES. Conley & Kelly: when units are spatially or
  institutionally correlated, effective sample size is far below the count.
  The true budget sits between the case count and the cluster count, and
  closer to the cluster count the more alike your cases are.

Run:  python harness/budget.py              -- all questions
      python harness/budget.py <name>       -- one
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402  (sits next to this file)
BUDGETS = paths.data("budgets")


def load(name):
    p = os.path.join(BUDGETS, name if name.endswith(".json") else name + ".json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def budgets_for(n):
    """Three rules, three numbers, and they are NOT interchangeable.

    sqrt(N)      -- general estimability heuristic. Applies to any method.
    log2(N)      -- configurational methods need N >= 2^k truth-table rows.
                    Also a general combinatorial ceiling.
    N / 15       -- the 'observations per predictor' guidance. This is a
                    REQUIREMENT OF REGRESSION SPECIFICALLY, not a general
                    budget. Below N=15 it returns 0, which does not mean
                    'no variables allowed' -- it means 'regression is not
                    an available method at this N'. Taking a blind minimum
                    across all three lets the most demanding method zero out
                    a sample that other methods could still use.
    """
    if n <= 0:
        return {"sqrt": 0, "configurational": 0, "regression": 0}
    return {
        "sqrt": int(math.sqrt(n)),
        "configurational": int(math.log2(n)) if n >= 2 else 0,
        "regression": n // 15,
    }


def binding(b, n):
    """The general budget is the tighter of the two method-agnostic rules.
    Regression is reported separately as an availability check."""
    if n <= 0:
        return 0
    return min(b["sqrt"], b["configurational"])


def analyse(d):
    cases = d.get("cases", [])
    usable = [c for c in cases if c.get("usable", True)]
    unusable = [c for c in cases if not c.get("usable", True)]
    clusters = sorted({c.get("cluster", c["id"]) for c in usable})

    n_nom = len(cases)
    n_use = len(usable)
    n_clu = len(clusters)

    b_case = budgets_for(n_use)
    b_clu = budgets_for(n_clu)

    # The honest budget is the conservative one. If your cases cluster hard,
    # the cluster count is the real sample size.
    binding_case = binding(b_case, n_use)
    binding_clu = binding(b_clu, n_clu)

    return dict(usable=usable, unusable=unusable, clusters=clusters,
                n_nom=n_nom, n_use=n_use, n_clu=n_clu,
                b_case=b_case, b_clu=b_clu,
                budget_high=binding_case, budget_low=binding_clu)


def verdict(a):
    hi, lo = a["budget_high"], a["budget_low"]
    if a["n_use"] < 2:
        return ("STOP", "Fewer than two usable cases. There is no comparison "
                "to make. No number you compute here will mean anything, and "
                "adding variables cannot help.")
    if hi == 0:
        return ("STOP", "The usable sample supports zero variables. You can "
                "describe these cases. You cannot model them.")
    if lo == 0 and hi <= 2:
        return ("SEVERELY CONSTRAINED",
                "You get at most one or two variables, and if your cases are "
                "as correlated as they look, zero. Pick the single variable "
                "you would defend to a hostile reader, use only that, and "
                "report it as description rather than inference.")
    if lo <= 3:
        return ("CONSTRAINED",
                f"Between {lo} and {hi} variables depending on how "
                f"independent your cases really are. Choose at the low end.")
    return ("PROCEED",
            f"{lo} to {hi} variables. This is a sample that can carry a model.")


def report(name, d):
    a = analyse(d)
    v, why = verdict(a)

    print("=" * 74)
    print(f"QUESTION: {d['question']}")
    print("=" * 74)
    print(f"  reference class: {d['reference_class']}")
    print()
    print(f"  cases named        {a['n_nom']}")
    print(f"  usable             {a['n_use']}")
    print(f"  independent groups {a['n_clu']}   ({', '.join(a['clusters'][:6])}"
          + (" ..." if len(a['clusters']) > 6 else "") + ")")
    print()

    if a["unusable"]:
        print("  EXCLUDED")
        for c in a["unusable"]:
            print(f"    · {c['id']} — {c.get('why_not','no reason given')}")
        print()

    print("  PARAMETER BUDGET")
    print(f"  {'rule':<22}{'by cases':>10}{'by groups':>12}")
    for k in ("sqrt", "configurational"):
        print(f"  {k:<22}{a['b_case'][k]:>10}{a['b_clu'][k]:>12}")
    print(f"  {'BINDING (general)':<22}{a['budget_high']:>10}{a['budget_low']:>12}")
    print()
    rg = a['b_case']['regression']
    if rg == 0:
        print(f"  regression: unavailable. Needs ~15 cases per predictor; "
              f"you have {a['n_use']}.")
    else:
        print(f"  regression: supports {rg} predictor(s) at 15 cases each.")
    print()

    print(f"  VERDICT: {v}")
    for line in wrap(why, 68):
        print(f"    {line}")
    print()

    want = d.get("variables_wanted", [])
    if want:
        allowed = a["budget_low"]
        print(f"  YOU LISTED {len(want)} VARIABLES")
        for w in want:
            print(f"    · {w}")
        if len(want) > allowed:
            print()
            print(f"  CUT {len(want) - allowed} OF THEM. You are allowed "
                  f"{allowed}.")
            print("  Not because the others do not matter. Because the sample")
            print("  cannot tell you whether they do.")
        else:
            print(f"\n  Within budget ({allowed} allowed).")
        print()
    return v


def wrap(s, w):
    out, line = [], ""
    for word in s.split():
        if len(line) + len(word) + 1 > w:
            out.append(line); line = word
        else:
            line = (line + " " + word).strip()
    if line:
        out.append(line)
    return out


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else None
    files = sorted(f for f in os.listdir(BUDGETS) if f.endswith(".json"))
    if want:
        files = [f for f in files if want in f]
    if not files:
        print("no questions found"); return

    tally = {}
    for fn in files:
        tally[fn[:-5]] = report(fn[:-5], load(fn))

    if len(files) > 1:
        print("=" * 74)
        print("SUMMARY")
        print("=" * 74)
        for k, v in tally.items():
            print(f"  {k:<26} {v}")
        print()
        print("  Run this BEFORE choosing variables, not after.")
        print("  It is the only check here that costs nothing and can save")
        print("  you a year.")


if __name__ == "__main__":
    main()
