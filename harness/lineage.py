#!/usr/bin/env python3
"""
lineage.py -- how many sources does a claim ACTUALLY have?

Everyone counts citations. Nobody collapses echoes into origins.

Give it a claim and the sources that assert it. It walks the citation graph
backwards and answers one question: strip out everything that is repeating
someone else, and how many independent origins remain?

Then it looks at what those origins are. An origin that is fiction, or
retracted, or produced by a party that benefits from the claim, is not the
same as an origin that is a parish register.

Run:  python harness/lineage.py            -- check every claim
      python harness/lineage.py <name>     -- check one
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402  (sits next to this file)
CLAIMS = paths.data("claims")

# Origin kinds that should never quietly count as evidence. The claim may
# still be true -- but it is not true BECAUSE of a source of this kind, and
# anything downstream inherits the defect.
DISQUALIFYING = {
    "fiction":    "a work of fiction or satire",
    "retracted":  "a retracted or withdrawn publication",
    "fabricated": "shown to be methodologically fraudulent",
    "derived":    "an arithmetic construction, not a measurement",
}

# Origin kinds that are only as good as the interest behind them.
SELF_REPORTED = {"interested", "platform", "press_release", "marketing"}

# Origin kinds that hold up because producing them served some other purpose.
BOUNDING = {"registry", "census", "administrative", "archaeological",
            "physical", "instrument"}


class Source:
    def __init__(self, d):
        self.id = d["id"]
        self.year = d.get("year")
        self.kind = d.get("kind", "unknown")
        self.cites = list(d.get("cites", []))
        self.note = d.get("note", "")
        self.interested = bool(d.get("interested", False))
        self.who_benefits = d.get("who_benefits")


def load(name):
    p = os.path.join(CLAIMS, name if name.endswith(".json") else name + ".json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- graph ----

def trace(src_id, index, seen=None):
    """Walk back to the origins this source rests on.

    An ORIGIN is a source that asserts the claim and cites nothing else that
    asserts it -- i.e. the buck stops there. Everything else is an echo, no
    matter how respectable, how recent, or how many times it is repeated."""
    seen = seen or set()
    if src_id in seen:
        return set(), True                      # cycle
    seen = seen | {src_id}

    s = index.get(src_id)
    if s is None:
        return {src_id}, False                  # cited but not described
    upstream = [c for c in s.cites if c in index or c not in index]
    if not upstream:
        return {src_id}, False                  # terminal: an origin

    origins, cyclic = set(), False
    for c in s.cites:
        o, cy = trace(c, index, seen)
        origins |= o
        cyclic = cyclic or cy
    return origins, cyclic


def analyse(claim):
    index = {s["id"]: Source(s) for s in claim["sources"]}
    origins_of, any_cycle = {}, False

    for sid in index:
        o, cy = trace(sid, index)
        origins_of[sid] = o
        any_cycle = any_cycle or cy

    all_origins = set()
    for o in origins_of.values():
        all_origins |= o

    # How many sources collapse onto each origin — this is the echo count.
    echoes = {o: sum(1 for s, os_ in origins_of.items() if o in os_)
              for o in all_origins}

    return index, origins_of, all_origins, echoes, any_cycle


def verdict(index, all_origins, any_cycle):
    """The finding, and the reason for it."""
    n = len(all_origins)
    kinds = [index[o].kind if o in index else "undescribed" for o in all_origins]
    bad = [k for k in kinds if k in DISQUALIFYING]
    interested = [o for o in all_origins
                  if o in index and (index[o].interested
                                     or index[o].kind in SELF_REPORTED)]
    bounded = [k for k in kinds if k in BOUNDING]

    if any_cycle:
        return ("CIRCULAR",
                "sources cite each other in a loop. The chain never reaches "
                "evidence, so the claim rests on nothing outside itself.")
    if n == 0:
        return ("UNGROUNDED", "no origin could be identified.")
    if n == 1 and bad:
        return ("DISQUALIFIED ORIGIN",
                f"everything traces to one source, and it is "
                f"{DISQUALIFYING[kinds[0]]}. Repetition has not made it evidence.")
    if n == 1 and interested:
        who = index[list(all_origins)[0]].who_benefits or "the source itself"
        return ("SINGLE INTERESTED ORIGIN",
                f"everything traces to one source, and that source benefits "
                f"from the claim being believed ({who}). This is the most "
                f"common shape of a laundered statistic.")
    if n == 1:
        return ("SINGLE ORIGIN",
                "every citation collapses to one source. The claim may be "
                "true, but the apparent consensus is one voice with an echo.")
    if bad:
        return ("MIXED, ONE DISQUALIFIED",
                f"{n} origins, but {len(bad)} of them "
                f"({', '.join(sorted(set(bad)))}) cannot carry weight. "
                "Re-count without them before believing the total.")
    if n >= 3 and bounded:
        return ("INDEPENDENT",
                f"{n} genuinely separate origins, {len(bounded)} of them "
                "from records made for some other purpose. This is what "
                "corroboration actually looks like.")
    return ("INDEPENDENT",
            f"{n} separate origins with no shared ancestor.")


# --------------------------------------------------------------- report ----

def report(name, claim):
    index, origins_of, all_origins, echoes, cyc = analyse(claim)
    v, why = verdict(index, all_origins, cyc)

    print("=" * 74)
    print(f"CLAIM: {claim['claim']}")
    print("=" * 74)
    print(f"  cited by       {len(claim['sources'])} sources")
    print(f"  independent    {len(all_origins)} origin(s)")
    if len(claim["sources"]):
        ratio = len(all_origins) / len(claim["sources"])
        print(f"  collapse ratio {ratio:.2f}   "
              f"({len(claim['sources']) - len(all_origins)} sources are echoes)")
    print()
    print(f"  VERDICT: {v}")
    print(f"  {why}")
    print()

    print("  ORIGINS")
    for o in sorted(all_origins,
                    key=lambda x: (index[x].year if x in index and index[x].year
                                   else 9999)):
        s = index.get(o)
        if s is None:
            print(f"    · {o} — cited but never described")
            continue
        flags = []
        if s.kind in DISQUALIFYING:
            flags.append(DISQUALIFYING[s.kind].upper())
        if s.interested or s.kind in SELF_REPORTED:
            flags.append("INTERESTED")
        if s.kind in BOUNDING:
            flags.append("made for another purpose")
        tag = f"   [{' / '.join(flags)}]" if flags else ""
        print(f"    · {s.id} ({s.year}, {s.kind}){tag}")
        if s.note:
            print(f"        {s.note}")
        if s.who_benefits:
            print(f"        benefits: {s.who_benefits}")
        print(f"        {echoes[o]} of {len(claim['sources'])} sources rest on this")
    print()

    # The gap between when the thing happened and when the origin was written.
    ev = claim.get("event_year")
    if ev:
        for o in all_origins:
            s = index.get(o)
            if s and s.year:
                gap = s.year - ev
                if gap > 50:
                    print(f"  TEMPORAL GAP: {s.id} was written {gap} years "
                          f"after the events it describes.")
        print()
    return v


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else None
    files = sorted(f for f in os.listdir(CLAIMS) if f.endswith(".json"))
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
            print(f"  {k:<22} {v}")
        print()
        print("  Counting citations measures how often a claim was repeated.")
        print("  Counting origins measures how often it was independently found.")
        print("  Only the second one is evidence.")


if __name__ == "__main__":
    main()
