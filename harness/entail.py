#!/usr/bin/env python3
"""
entail.py -- does the evidence support THIS claim, or a weaker neighbour of it?

The lineage checker answers "how many independent sources?" It will happily
return INDEPENDENT on six excellent sources that establish something adjacent
to what you said.

WHAT THIS TOOL DOES NOT DO: it does not read your sources. It cannot tell
whether a paper says what you think it says. That is language work, and it
belongs to whatever model you are talking to.

WHAT IT DOES: it forces you to write down, separately, (a) the structure of
your claim and (b) what each piece of evidence actually establishes -- and
then checks whether the second covers the first. The value is in being made
to write both down. The gaps become visible the moment they sit side by side,
which is why nobody does it voluntarily.

The nine gap types:

  SCOPE          evidence is instances; claim is systematic
  QUANTITY       evidence measures a neighbour of what you claimed
  MISSING VAR    the claim turns on a variable the evidence doesn't contain
  POPULATION     evidence from A, claim about B
  MECHANISM      evidence shows an outcome; claim asserts intent or cause
  COMPOSITION    marginals multiplied into a joint, independence unstated
  TARGET         the thing measured is not the thing claimed
  TEMPORAL       evidence from one era, claim about another
  DIRECTION      the evidence is equally consistent with the reverse

Run:  python harness/entail.py            -- check all
      python harness/entail.py <name>     -- check one
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402  (sits next to this file)
ENTAIL = paths.data("entail")


def load(name):
    p = os.path.join(ENTAIL, name if name.endswith(".json") else name + ".json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class Gap:
    def __init__(self, kind, detail, weakens_to=None):
        self.kind = kind
        self.detail = detail
        self.weakens_to = weakens_to


# ---------------------------------------------------------------- checks ---

def check(d):
    c = d["claim_structure"]
    ev = d["evidence"]
    gaps = []

    # SCOPE -- "systematic" needs more than a handful of instances.
    if c.get("scope") == "systematic":
        n_designed = sum(1 for e in ev if e.get("designed"))
        distinct = {e.get("actor") for e in ev if e.get("actor")}
        if n_designed < 3 or len(distinct) < 3:
            gaps.append(Gap("SCOPE",
                f"the claim is systematic, but the evidence is "
                f"{n_designed} designed instance(s) across {len(distinct)} "
                f"actor(s). Instances do not establish a practice.",
                "these specific actors did this on these specific occasions"))

    # QUANTITY -- is the thing you claimed the thing anyone measured?
    want = (c.get("quantity") or "").lower()
    measured = [e.get("quantity", "") for e in ev if e.get("quantity")]
    if want and not any(want in m.lower() or m.lower() in want for m in measured):
        gaps.append(Gap("QUANTITY SUBSTITUTION",
            f"you claim something about '{c['quantity']}'. Nothing here "
            f"measures that. What was measured: "
            + "; ".join(f"'{m}'" for m in measured) + ".",
            f"the claim about {measured[0]}" if measured else None))

    # MISSING VARIABLE -- the claim turns on something the evidence lacks.
    need = set(v.lower() for v in c.get("turns_on", []))
    have = set()
    for e in ev:
        have |= set(v.lower() for v in e.get("contains_variables", []))
    absent = sorted(need - have)
    if absent:
        gaps.append(Gap("MISSING VARIABLE",
            f"the claim turns on {', '.join(absent)}. No evidence item "
            f"contains {'it' if len(absent) == 1 else 'them'}. The claim is "
            f"not wrong here -- it is untestable with what you have.",
            "a claim that does not depend on " + ", ".join(absent)))

    # MECHANISM -- outcome observed is not intent demonstrated.
    if c.get("asserts_mechanism"):
        shown = [e["id"] for e in ev if e.get("mechanism_shown")]
        if not shown:
            obs = [e["id"] for e in ev if not e.get("designed")]
            gaps.append(Gap("MECHANISM ASSUMED",
                f"the claim asserts {c['asserts_mechanism']}. No evidence "
                f"item establishes it; "
                + (f"{len(obs)} are observational" if obs else "none show intent")
                + ". An outcome is not a purpose.",
                "that the outcome occurred, with the purpose left open"))

    # POPULATION
    cp = (c.get("population") or "").lower()
    if cp:
        pops = [e.get("population", "") for e in ev if e.get("population")]
        if pops and not any(cp in p.lower() or p.lower() in cp for p in pops):
            gaps.append(Gap("POPULATION",
                f"the claim is about '{c['population']}'. The evidence is "
                f"drawn from: " + "; ".join(f"'{p}'" for p in pops) + ".",
                f"the claim restricted to {pops[0]}"))

    # TEMPORAL
    cper = c.get("period")
    if cper:
        spans = [e["period"] for e in ev if e.get("period")]
        if spans:
            lo = min(s[0] for s in spans)
            hi = max(s[1] for s in spans)
            if cper[0] < lo or cper[1] > hi:
                gaps.append(Gap("TEMPORAL",
                    f"the claim covers {cper[0]}-{cper[1]}. The evidence "
                    f"covers {lo}-{hi}. The uncovered years are asserted, "
                    f"not shown.",
                    f"the claim restricted to {lo}-{hi}"))

    # COMPOSITION
    if c.get("is_joint_of"):
        parts = c["is_joint_of"]
        if not c.get("independence_established"):
            gaps.append(Gap("COMPOSITION",
                f"this is a joint probability built from {len(parts)} "
                f"marginals ({', '.join(parts)}) and independence is not "
                f"established. If the parts correlate, the product is wrong "
                f"in a knowable direction.",
                "the individual marginal rates, reported separately"))

    # TARGET
    for e in ev:
        if e.get("target_is_derived"):
            gaps.append(Gap("TARGET SUBSTITUTION",
                f"'{e['id']}' was scored against a target that was itself "
                f"produced by a model. Agreement with it measures agreement "
                f"between two models, not contact with the world.",
                "that the two models agree"))

    # DIRECTION
    if c.get("causal") and not c.get("direction_established"):
        alt = c.get("plausible_reverse", "the reverse")
        gaps.append(Gap("DIRECTION",
            f"the claim is causal, and the evidence is equally consistent "
            f"with {alt}. Nothing here distinguishes them.",
            "that the two are associated"))

    return gaps


def strongest_supported(d, gaps):
    """The claim you are actually entitled to make. This is the useful output --
    not 'you are wrong' but 'here is the version that survives'."""
    fallbacks = [g.weakens_to for g in gaps if g.weakens_to]
    if not fallbacks:
        return d["claim"]
    return d.get("weakened_form") or (
        "the conjunction of: " + "; and ".join(fallbacks))


# --------------------------------------------------------------- report ----

def report(name, d):
    gaps = check(d)
    print("=" * 74)
    print(f"CLAIM: {d['claim']}")
    print("=" * 74)
    print(f"  evidence items: {len(d['evidence'])}")
    print()

    if not gaps:
        print("  ENTAILED")
        print("  Every structural element of the claim is covered by the")
        print("  evidence as declared. The claim does not overreach its support.")
        print()
        return "ENTAILED"

    print(f"  {len(gaps)} GAP(S) BETWEEN EVIDENCE AND CLAIM")
    print("  " + "-" * 68)
    for g in gaps:
        print(f"  {g.kind}")
        for line in wrap(g.detail, 66):
            print(f"      {line}")
        print()

    print("  STRONGEST CLAIM THE EVIDENCE ACTUALLY SUPPORTS")
    print("  " + "-" * 68)
    for line in wrap(strongest_supported(d, gaps), 66):
        print(f"    {line}")
    print()
    return f"{len(gaps)} GAP(S)"


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
    files = sorted(f for f in os.listdir(ENTAIL) if f.endswith(".json"))
    if want:
        files = [f for f in files if want in f]
    if not files:
        print("no claims found"); return

    tally = {}
    for fn in files:
        tally[fn[:-5]] = report(fn[:-5], load(fn))

    if len(files) > 1:
        print("=" * 74)
        print("SUMMARY")
        print("=" * 74)
        for k, v in tally.items():
            print(f"  {k:<24} {v}")
        print()
        print("  Lineage asks whether the sources are independent.")
        print("  This asks whether they are about what you said.")
        print("  A claim can pass the first and fail this one badly.")


if __name__ == "__main__":
    main()
