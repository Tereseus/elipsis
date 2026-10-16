#!/usr/bin/env python3
"""
frame.py -- the question harness.

You state a question. It gets forced into six slots, and then it gets CHECKED.
The checks are the point: each one catches a specific way that questions about
"is X good or bad" go wrong, and each was found by walking into it.

    1 VERDICT WORD    which evaluative word is doing the work
    2 IS IT CONTESTED does anyone actually argue the opposite value?
    3 CLAIMS          the countable statements hiding inside the verdict word
    4 COMPARED TO     alternatives that really existed. never an ideal.
    5 MEASURES        one countable thing per claim
    6 WHERE IT SITS   (produced by the run, not written by hand)

Run:  python harness/frame.py                 -- check every frame
      python harness/frame.py <name>          -- check one
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402  (sits next to this file)
FRAMES = paths.data("frames")

# A measure has to be a COUNT of something, not a quality someone assigns.
COUNTABLE_UNITS = {
    "count", "rate", "share", "years", "months", "days",
    "currency", "persons", "deaths", "ratio", "index_of_counts",
}

# Slot 4 language that means somebody is comparing reality to a daydream.
NIRVANA_PATTERNS = [
    r"\bproper(ly)?\b", r"\bfair\b", r"\bideal\b", r"\bwell[- ]run\b",
    r"\bgood\b", r"\bbetter\b", r"\bno\s+\w+ation\b", r"\bwithout\b",
    r"\bif .* had\b", r"\bcorrect(ly)?\b", r"\bethical\b",
]

BOUNDABLE_KINDS = {"record.administrative", "physical.archaeological",
                   "physical.scientific", "dataset.coded"}


class Result:
    def __init__(self):
        self.fail, self.warn, self.ok = [], [], []

    def f(self, code, msg):   self.fail.append((code, msg))
    def w(self, code, msg):   self.warn.append((code, msg))
    def o(self, code, msg):   self.ok.append((code, msg))

    @property
    def verdict(self):
        if self.fail: return "UNANSWERABLE"
        if self.warn: return "ANSWERABLE WITH CAVEATS"
        return "WELL FORMED"


def check(fr):
    r = Result()
    claims   = fr.get("claims", [])
    alts     = fr.get("compared_to", [])
    measures = fr.get("measures", [])
    mids     = {m["id"] for m in measures}

    # --- slot 1 -----------------------------------------------------------
    if not fr.get("verdict_word"):
        r.f("no-verdict", "No verdict word identified. If nothing evaluative is "
                          "being asked, this isn't a good-or-bad question and "
                          "belongs in a different shape.")
    else:
        r.o("verdict", f"Verdict word is “{fr['verdict_word']}”.")

    # --- slot 2 -----------------------------------------------------------
    c = fr.get("contested")
    if c is None:
        r.f("no-contest-check", "Nobody said whether the underlying value is "
                                "actually disputed. That determines whether this "
                                "is a factual question or a political one.")
    elif c["answer"]:
        r.w("contested", "The value here IS disputed, so no single verdict is "
                         "permitted. The run must report one answer per value "
                         "position and let the reader see the spread.")
    else:
        r.o("uncontested", f"Value is uncontested — {c['why']}. "
                           "So this is a FACTUAL question wearing value clothing, "
                           "and it can have one answer.")

    # --- slot 3 -----------------------------------------------------------
    if not claims:
        r.f("no-claims", "The verdict word was never unpacked into countable "
                         "statements. Nothing here can be measured.")
    for cl in claims:
        linked = [m for m in cl.get("measures", []) if m in mids]
        if not linked:
            r.f("claim-unmeasured",
                f"Claim “{cl['text']}” has no measure attached. "
                "It cannot be tested and must be dropped or given one.")
    if claims and not r.fail:
        r.o("claims", f"{len(claims)} claims, each attached to a measure.")

    # --- slot 4 : the slot that kills most questions ----------------------
    real = [a for a in alts if a.get("real")]
    if len(alts) < 2:
        r.f("empty-arm", "Fewer than two alternatives. There is nothing to "
                         "compare against, so no contrast can be computed. "
                         "The honest output is “no evidence”.")
    if len(real) < 2:
        r.f("empty-arm-real", f"Only {len(real)} of {len(alts)} alternatives "
                              "actually existed. You cannot contrast against "
                              "systems that were never tried.")
    for a in alts:
        name = a["system"].lower()
        if not a.get("real"):
            r.w("nirvana-flagged",
                f"“{a['system']}” is marked as never having existed. "
                "Kept for discussion, excluded from the arithmetic.")
        elif any(re.search(p, name) for p in NIRVANA_PATTERNS):
            r.w("nirvana-language",
                f"“{a['system']}” reads like an ideal rather than a "
                "real system. Comparing reality to a daydream always loses — "
                "name the actual case and period instead.")
        elif not a.get("period"):
            r.w("no-period", f"“{a['system']}” has no period. A system "
                             "without dates cannot be matched to sources.")
    if len(real) >= 2:
        r.o("arms", f"{len(real)} real alternatives to contrast against.")

    # --- slot 5 -----------------------------------------------------------
    if not measures:
        r.f("no-measures", "No measures at all.")
    boundable = 0
    for m in measures:
        if m.get("unit") not in COUNTABLE_UNITS:
            r.f("not-countable",
                f"Measure “{m['text']}” has unit “{m.get('unit')}”, "
                "which is not a count of anything. This is the failure mode where "
                "an abstract quality gets a number stuck on it and starts looking "
                "like evidence.")
        if not m.get("source_type"):
            r.f("no-source-type", f"Measure “{m['text']}” names no source type.")
        elif m["source_type"] in BOUNDABLE_KINDS:
            boundable += 1
    if measures and boundable == 0:
        r.f("no-bounds", "Not one measure comes from a registry, an excavation, "
                         "or a coded dataset. Every number would rest on somebody's "
                         "interpretation, with nothing physical constraining it.")
    elif boundable:
        r.o("bounds", f"{boundable} of {len(measures)} measures are bounded by "
                      "administrative or physical evidence.")

    # --- slot 5b : can each measure be OBSERVED for enough arms? ----------
    # A measure can be perfectly well defined and
    # still be recorded in only one of the systems you want to compare --
    # in which case it contrasts nothing, and you find out only after
    # building the grid. This fires first instead.
    alt_ids = {a.get("id", a["system"]) for a in alts}
    for m in measures:
        obs = m.get("observable_for")
        if obs is None:
            r.w("no-observability",
                f"Measure “{m['text']}” doesn't say which systems it can "
                "actually be observed for.")
            continue
        unknown = [o for o in obs if o not in alt_ids]
        if unknown:
            r.w("obs-unknown-system",
                f"Measure “{m['text']}” claims observability for "
                f"{unknown}, which aren't in the comparison set.")
        if len(obs) < 2:
            r.f("single-arm-measure",
                f"Measure “{m['text']}” is observable for only "
                f"{len(obs)} system(s). It cannot contrast anything, so the "
                "claim resting on it is untestable as posed. Find the trace "
                "the other systems DID leave, or drop the claim.")

    # --- instrument continuity -------------------------------------------
    brk = fr.get("instrument_break")
    if brk:
        r.w("instrument-break",
            f"The measuring instrument changes at {brk['where']}: "
            f"{brk['why']} Trends WITHIN one instrument are the strong claim; "
            "comparisons ACROSS the break are a weaker separate inference and "
            "must be reported as such.")

    return r


def report(name, fr, r):
    line = "=" * 74
    print(line)
    print(f"FRAME: {name}")
    print(line)
    print(f'ASKED   "{fr["asked"]}"')
    print()
    print(f"1 VERDICT WORD   {fr.get('verdict_word', '—')}")
    cc = fr.get("contested")
    print(f"2 CONTESTED      {'yes' if cc and cc['answer'] else 'no'}"
          f"{'  (' + cc['why'] + ')' if cc else ''}")
    print(f"3 CLAIMS         {len(fr.get('claims', []))}")
    for cl in fr.get("claims", []):
        print(f"                 · {cl['text']}")
    print(f"4 COMPARED TO    {len(fr.get('compared_to', []))}")
    for a in fr.get("compared_to", []):
        tag = "" if a.get("real") else "   [NEVER EXISTED]"
        print(f"                 · {a['system']} ({a.get('period','no period')}){tag}")
    print(f"5 MEASURES       {len(fr.get('measures', []))}")
    for m in fr.get("measures", []):
        print(f"                 · {m['text']}  [{m.get('unit')} / {m.get('source_type')}]")
    print()
    print(f"VERDICT: {r.verdict}")
    print("-" * 74)
    for code, msg in r.fail:
        print(f"  FAIL  {msg}")
    for code, msg in r.warn:
        print(f"  WARN  {msg}")
    for code, msg in r.ok:
        print(f"  ok    {msg}")
    print()


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else None
    files = sorted(f for f in os.listdir(FRAMES) if f.endswith(".json"))
    if want:
        files = [f for f in files if want in f]
    if not files:
        print("no frames found"); return

    tally = {}
    for fn in files:
        with open(os.path.join(FRAMES, fn), encoding="utf-8") as f:
            fr = json.load(f)
        r = check(fr)
        report(fn[:-5], fr, r)
        tally[fn[:-5]] = r.verdict

    if len(files) > 1:
        print("=" * 74)
        print("SUMMARY")
        print("=" * 74)
        for k, v in tally.items():
            print(f"  {k:<28} {v}")
        print()
        print("  A question that fails here has not been answered badly.")
        print("  It has been shown to be unanswerable as asked — which is")
        print("  the single most useful thing this harness does, because it")
        print("  happens BEFORE anyone spends a year coding episodes.")


if __name__ == "__main__":
    main()
