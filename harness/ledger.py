#!/usr/bin/env python3
"""
ledger.py -- the claim ledger. Write down what you expect, before you find out.

The lineage checker audits other people's claims. This audits yours.

It is the one piece of the original design that works at N=1, because you are
the only subject you have complete data on. And it is the piece with an actual
theorem behind it: score forecasts with a proper rule, weight sources by their
track record, and the ensemble provably stays close to the best single source
in hindsight -- without anyone having to know in advance which one that is.

Five disciplines it enforces:

  1. RESOLUTION CRITERIA ARE WRITTEN FIRST. If you decide afterwards what
     would have counted, you will decide you were right.

  2. EVERY CLAIM CARRIES A BASELINE. If you do not beat the
     dumb answer, you have no skill, however confident you felt. Where a
     market prices the question, the market IS the baseline.

  3. REASONING IS TAGGED, MODE AND TOPIC SEPARATELY. Being wrong on average
     is useless information. Being wrong *when reasoning from memory* and
     right *when checking first* is actionable, and you cannot see it without
     the tags.
     One more tag describes the QUESTION, not the reasoning: "conditional"
     marks a question about what follows from an action already taken or
     announced. The report scores those apart from "will it happen at all".

  4. THE RECORD CORRECTS THE NEXT FORECAST. Every new forecast is also stored
     pulled toward its baseline by k, the share of your own departure the
     record says to keep. k is fitted on everything resolved so far, and the
     raw and corrected numbers are scored side by side, so the ledger shows
     whether correcting helps rather than assuming it.

  5. NOTHING IS OVERWRITTEN. A rerun on new information is a new dated
     forecast that points at the one it revises. Overwrite, and you can always
     "update" to the answer the day before it resolves and look brilliant.

Run:  python harness/ledger.py                  -- open claims and what's due
      python harness/ledger.py score            -- calibration report
      python harness/ledger.py calibrate        -- how k is fitted, and the honest test
      python harness/ledger.py due              -- only what needs resolving
      python harness/ledger.py stale [n] [--all] -- open questions DUE FOR A LOOK, most
                                                    overdue first (--all: every one)
      python harness/ledger.py checked <id> ["note"] -- a look that changed nothing, so
                                                    the question moves to the back
      python harness/ledger.py add <file.json>  -- log a forecast (no file: template)
      python harness/ledger.py rerun <id> <p> "reasoning" [<baseline_p> "what it is"]
      python harness/ledger.py resolve <id> yes|no|unresolvable ["note"]
                                                [--early "why"] [--force]
      python harness/ledger.py export [path]    -- JSON snapshot for the report page

A question cannot be closed before its date unless --early says why (a settled
market, or an event that has plainly happened). A question about what the research
says (literature-check, replication-forecast, search-prediction) is never SCORED
before its date, even then, unless --force: new studies can change the answer.
"""

import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402  (sits next to this file)
STORE = paths.data("ledger", "claims.json")
# Looks that changed nothing. Kept apart from the claims so the record of
# forecasts stays append-only.
CHECKS = paths.data("ledger", "checks.json")

BUCKETS = [(0.0, 0.10), (0.10, 0.30), (0.30, 0.50),
           (0.50, 0.70), (0.70, 0.90), (0.90, 1.01)]

# Reasoning modes. Anything else in a claim's tags is a topic, or a flag.
MODES = {
    "commit-then-check", "search-prediction", "model-inference",
    "literature-check", "replication-forecast", "extrapolation",
    "omission", "recall", "secondhand", "verdict", "elicitation",
    "own-design", "own-output", "own-parameter", "institutional-adoption",
    "reference-class",   # a world event, from a named base rate plus specifics
}
FLAGS = {
    "user-claim",
    # A question about what FOLLOWS from an action already taken or announced
    # ("given this plan, will X happen?"), as opposed to "will it happen at
    # all?". The report scores the two apart. It describes the
    # question, not the reasoning, so it is a flag and not a mode.
    "conditional",
}

# Questions about what the research says. They are never scored before their
# date, even when the answer looks settled, because new studies can change it.
PROTECTED_EARLY = {"literature-check", "replication-forecast", "search-prediction"}

# Correction toward the baseline. On a short record k leans on a prior --
# keep half of every move away from the baseline -- and the fitted value takes
# over as resolved forecasts accumulate, weighted n against PRIOR_WEIGHT.
PRIOR_K = 0.5
PRIOR_WEIGHT = 10
K_FLOOR, K_CEIL = 0.0, 1.5   # never bet against yourself; allow extra trust
MODE_MIN = 20                # a mode gets its own k only after this many

REQUIRED = ("id", "claim", "resolves", "probability",
            "resolution_criteria", "baseline", "reasoning")


def load():
    if not os.path.exists(STORE):
        return {"claims": []}
    with open(STORE, encoding="utf-8") as f:
        return json.load(f)


def save(d):
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    with open(STORE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def today():
    return date.today().isoformat()


def brier(p, outcome):
    """Strictly proper: you minimise it by reporting what you actually believe."""
    return (p - (1.0 if outcome else 0.0)) ** 2


# ------------------------------------------------------------- selection ---

def resolved(d):
    """Closed claims, including any closed as unresolvable."""
    return [c for c in d["claims"] if c.get("resolved")]


def scored(d):
    """Closed with a yes/no outcome -- the only claims a score can use."""
    return [c for c in resolved(d) if c["resolved"].get("outcome") is not None]


def unresolvable(d):
    return [c for c in resolved(d) if c["resolved"].get("outcome") is None]


def open_claims(d):
    return [c for c in d["claims"] if not c.get("resolved")]


def find(d, cid):
    for c in d["claims"]:
        if c["id"] == cid:
            return c
    return None


def modes(c):
    m = c.get("mode")
    if m:
        return [m] if isinstance(m, str) else m
    return [t for t in c.get("tags", []) if t in MODES] or ["untagged"]


def qkind(c):
    """'conditional' if the question asks what follows from an action already
    taken or announced; otherwise 'unconditional' (will it happen at all).
    Read from the tags or the flags, so reruns inherit it from their parent."""
    marks = list(c.get("tags", [])) + list(c.get("flags", []))
    return ["conditional" if "conditional" in marks else "unconditional"]


def topics(c):
    # Some entries store topic as one string, not a list;
    # iterating a string would group by single letters.
    t = c.get("topic")
    if t:
        return [t] if isinstance(t, str) else t
    return [x for x in c.get("tags", [])
            if x not in MODES and x not in FLAGS] or ["no-topic"]


def sources(c):
    """Where the question came from: a conversation, or an automated feed."""
    return [c.get("source") or "conversation"]


def root_of(d, c):
    """Follow `revises` back to the first forecast on this question."""
    seen = set()
    while c.get("revises") and c["id"] not in seen:
        seen.add(c["id"])
        parent = find(d, c["revises"])
        if parent is None:
            break
        c = parent
    return c["id"]


def family(d, cid):
    """A forecast and every rerun of the same question."""
    c = find(d, cid)
    if c is None:
        return []
    r = root_of(d, c)
    return [x for x in d["claims"] if root_of(d, x) == r]


def placeholder_baseline(c):
    """A coin flip standing in for a baseline nobody looked up."""
    b = c.get("baseline", {})
    what = (b.get("what") or "").lower()
    return b.get("probability") == 0.5 and (
        not what or "uninformative" in what or "placeholder" in what
        or "coin flip" in what)


# ------------------------------------------------------------ correction ---

def base_p(c):
    return c.get("baseline", {}).get("probability", 0.5)


def outcome01(c):
    return 1.0 if c["resolved"]["outcome"] else 0.0


def rows_of(cs):
    return [(c["probability"], base_p(c), outcome01(c)) for c in cs]


def fit_k(rows):
    """The k that would have minimised the Brier score on (p, b, o) rows.
    Setting the derivative of sum (b + k(p - b) - o)^2 to zero gives
    k* = sum (o - b)(p - b) / sum (p - b)^2."""
    num = sum((o - b) * (p - b) for p, b, o in rows)
    den = sum((p - b) ** 2 for p, b, o in rows)
    return (num / den) if den > 0 else None


def blend_k(fit, n):
    """Clamp the fitted k, then shrink it toward the prior by record length."""
    if fit is None or n == 0:
        return PRIOR_K
    f = max(K_FLOOR, min(K_CEIL, fit))
    return (PRIOR_WEIGHT * PRIOR_K + n * f) / (PRIOR_WEIGHT + n)


def current_k(d, mode=None):
    """(k to apply, raw fitted k*, forecasts it was fitted on, scope)."""
    rs = scored(d)
    if mode:
        ms = [c for c in rs if mode in modes(c)]
        if len(ms) >= MODE_MIN:
            f = fit_k(rows_of(ms))
            return blend_k(f, len(ms)), f, len(ms), mode
    f = fit_k(rows_of(rs))
    return blend_k(f, len(rs)), f, len(rs), "all"


def k_for(d, c):
    """The most specific k the record supports for this forecast's modes."""
    best = None
    for m in modes(c):
        got = current_k(d, m)
        if got[3] != "all" and (best is None or got[2] > best[2]):
            best = got
    return best or current_k(d)


def calibrate_new(d, c):
    """Store the corrected probability alongside the raw one. Never replaces it."""
    k, _, n, scope = k_for(d, c)
    b, p = base_p(c), c["probability"]
    c["calibrated"] = {"p": round(b + k * (p - b), 4), "k": round(k, 4),
                       "fitted_on": n, "scope": scope, "on": today()}
    return c["calibrated"]


def loo(d):
    """Leave-one-out: correct each scored forecast with a k fitted on all the
    others, as if it had been logged last. It never sees its own answer, so
    this is the honest test of whether correcting would have helped."""
    rs = scored(d)
    if len(rs) < 3:
        return None
    total = 0.0
    for i, c in enumerate(rs):
        others = rs[:i] + rs[i + 1:]
        k = blend_k(fit_k(rows_of(others)), len(others))
        b, p = base_p(c), c["probability"]
        total += brier(b + k * (p - b), c["resolved"]["outcome"])
    return total / len(rs)


# --------------------------------------------------------------- reports ---

def show_open(d, only_due=False):
    now = today()
    op = open_claims(d)
    if not op:
        print("No open claims.")
        return 0
    due = [c for c in op if c["resolves"] <= now]
    later = [c for c in op if c["resolves"] > now]

    if due:
        print(f"DUE NOW ({len(due)})")
        print("-" * 74)
        for c in sorted(due, key=lambda x: x["resolves"]):
            print(f"  [{c['id']}]  resolved by {c['resolves']}  p={c['probability']:.2f}")
            print(f"    {c['claim']}")
            print(f"    counts as true if: {c['resolution_criteria']}")
            print(f"    → python harness/ledger.py resolve {c['id']} yes|no|unresolvable")
            print()
    elif only_due:
        print("Nothing is due.")

    if later and not only_due:
        print(f"PENDING ({len(later)})")
        print("-" * 74)
        for c in sorted(later, key=lambda x: x["resolves"]):
            cal = c.get("calibrated")
            ps = f"p={c['probability']:.2f}" + (f" → {cal['p']:.2f}" if cal else "      ")
            rv = "  (rerun)" if c.get("revises") else ""
            print(f"  [{c['id']}]  {c['resolves']}  {ps}  {c['claim'][:40]}{rv}")
        print()
    return len(due)


def load_checks():
    """{root_id: [{"when": date, "note": text}, ...]} -- looks that changed nothing."""
    if not os.path.exists(CHECKS):
        return {}
    with open(CHECKS, encoding="utf-8") as f:
        return json.load(f)


def save_checks(ch):
    os.makedirs(os.path.dirname(CHECKS), exist_ok=True)
    with open(CHECKS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(ch, f, indent=2, ensure_ascii=False)


def mark_checked(d, cid, note=""):
    """Record that someone looked at an open question and nothing moved, so it
    goes to the back of the queue instead of coming up again tomorrow."""
    c = find(d, cid)
    if c is None:
        print(f"No claim with id '{cid}'.")
        return False
    if c.get("resolved"):
        print(f"[{cid}] is already resolved.")
        return False
    root = root_of(d, c)
    ch = load_checks()
    ch.setdefault(root, []).append({"when": today(), "note": note})
    save_checks(ch)
    print(f"[{root}] marked as looked at on {today()}. It comes back up when it is due.")
    return True


def review_interval(root_claims, on):
    """Days between looks. A question tied to a market gets a look every day,
    because its price moves daily. Any other question gets about ten looks
    between now and its date: never more often than daily, never less often
    than monthly. (A slow research question cannot move overnight.)"""
    if any(x.get("market") for x in root_claims):
        return 1.0
    latest = max(root_claims, key=lambda x: (x.get("made", ""), x["id"]))
    try:
        left = (date.fromisoformat(latest["resolves"]) - on).days
    except ValueError:
        left = 0
    return min(30.0, max(1.0, left / 10.0))


def stalest(d, n=None, everything=False):
    """Open questions that are DUE FOR A LOOK, most overdue first. Each
    question appears once, as its most recent forecast. 'Touched' is the later
    of its latest forecast and its latest recorded look; a question is due once
    it has sat untouched for its review interval. everything=True lists all."""
    on = date.today()
    checks = load_checks()
    fams = {}
    for c in open_claims(d):
        fams.setdefault(root_of(d, c), []).append(c)
    rows = []
    for root, cs in fams.items():
        latest = max(cs, key=lambda x: (x.get("made", ""), x["id"]))
        touched = max([latest.get("made", "")] +
                      [x["when"] for x in checks.get(root, [])])
        try:
            idle = (on - date.fromisoformat(touched)).days
        except ValueError:
            idle = 9999
        gap = review_interval(cs, on)
        if not everything and idle < gap:
            continue
        rows.append((idle / gap, touched, root, latest))
    rows.sort(key=lambda r: (-r[0], r[1], r[2]))
    rows = [(touched, root, c) for _, touched, root, c in rows]
    return rows[:n] if n else rows


def show_stale(d, n=None, everything=False):
    rows = stalest(d, n, everything)
    if not rows:
        print("Nothing is due for a look today.")
        return
    print(f"OPEN QUESTIONS DUE FOR A LOOK, MOST OVERDUE FIRST ({len(rows)})")
    print("-" * 74)
    for touched, root, c in rows:
        cal = c.get("calibrated")
        ps = f"p={c['probability']:.2f}" + (f" → {cal['p']:.2f}" if cal else "")
        tie = "  [market-tied]" if c.get("market") else ""
        print(f"  last touched {touched}  [{c['id']}]  resolves {c['resolves']}  {ps}{tie}")
        print(f"    {c['claim']}")
        print(f"    baseline {base_p(c):.2f}: {c.get('baseline', {}).get('what', '')[:90]}")
        print(f"    → moved: python harness/ledger.py rerun {c['id']} <p> \"reasoning\" "
              f"[<baseline_p> \"what\"]")
        print(f"    → nothing moved: python harness/ledger.py checked {c['id']} \"why\"")
        print()


def _group_table(title, rs, key):
    groups = {}
    for c in rs:
        for g in key(c):
            groups.setdefault(g, []).append(c)
    if not groups:
        return []
    print(f"  {title}")
    print("  " + "-" * 60)
    rows = []
    for g, cs in groups.items():
        b = sum(brier(c["probability"], c["resolved"]["outcome"]) for c in cs) / len(cs)
        dr = sum(c["probability"] - outcome01(c) for c in cs) / len(cs)
        rows.append((b, g, len(cs), dr))
    for b, g, n, dr in sorted(rows):
        verdict = "reliable" if b < 0.15 else ("mixed" if b < 0.25 else "UNRELIABLE")
        print(f"  {g:<22} n={n:<3}  Brier {b:.3f}  bias {dr:+.2f}   {verdict}")
    print()
    return rows


def score(d):
    rs = scored(d)
    if len(rs) < 2:
        print(f"Only {len(rs)} scored claim(s). Calibration needs more.")
        return

    mine = sum(brier(c["probability"], c["resolved"]["outcome"]) for c in rs) / len(rs)
    base = sum(brier(base_p(c), c["resolved"]["outcome"]) for c in rs) / len(rs)
    always_half = 0.25

    print("=" * 74)
    print(f"CALIBRATION  —  {len(rs)} scored claims")
    print("=" * 74)
    aside = []
    if unresolvable(d):
        aside.append(f"{len(unresolvable(d))} closed as unresolvable")
    if d.get("voided"):
        aside.append(f"{len(d['voided'])} voided")
    if aside:
        print(f"  ({', '.join(aside)} -- not scored)")
    print(f"  your Brier score          {mine:.3f}")
    print(f"  the baseline's Brier      {base:.3f}")
    print(f"  always saying 50%         {always_half:.3f}")
    print()

    # The headline. Everything else is detail.
    if mine < base:
        print(f"  YOU BEAT THE BASELINE by {base - mine:.3f}. That is skill.")
    elif abs(mine - base) < 0.01:
        print("  YOU TIED THE BASELINE. Your reasoning added nothing measurable.")
    else:
        print(f"  THE BASELINE BEAT YOU by {mine - base:.3f}.")
        print("  Your effort made the forecasts worse than the dumb answer.")
    print()

    # Reruns make some questions count several times; show the fair view too.
    fams = {}
    for c in rs:
        fams.setdefault(root_of(d, c), []).append(c)
    if len(fams) < len(rs):
        q = sum(sum(brier(c["probability"], c["resolved"]["outcome"]) for c in cs)
                / len(cs) for cs in fams.values()) / len(fams)
        print(f"  {len(rs)} forecasts on {len(fams)} questions. "
              f"Weighting each question once: Brier {q:.3f}")
        print()

    # Directional bias.
    drift = sum(c["probability"] - outcome01(c) for c in rs) / len(rs)
    print(f"  DIRECTIONAL BIAS  {drift:+.3f}")
    if drift > 0.08:
        print("  You are systematically too confident that things are TRUE.")
    elif drift < -0.08:
        print("  You are systematically too confident that things are FALSE.")
    else:
        print("  No strong directional skew.")
    print()

    # Calibration table
    print("  WHEN YOU SAY...        n    you said   it happened    gap")
    print("  " + "-" * 60)
    for lo, hi in BUCKETS:
        b = [c for c in rs if lo <= c["probability"] < hi]
        if not b:
            continue
        said = sum(c["probability"] for c in b) / len(b)
        happened = sum(1 for c in b if c["resolved"]["outcome"]) / len(b)
        gap = said - happened
        flag = "   <-- overconfident" if gap > 0.15 else (
               "   <-- underconfident" if gap < -0.15 else "")
        print(f"  {int(lo*100):>3}-{int(hi*100):>3}%          {len(b):>4}"
              f"      {said:.2f}        {happened:.2f}      {gap:+.2f}{flag}")
    print()

    # Which of your reasoning modes is wrong -- and, separately, where.
    rows = _group_table("BY REASONING MODE", rs, modes)
    if rows:
        worst = max(rows)
        if worst[0] > 0.25 and worst[2] >= 2:
            print(f"  Your weakest mode is '{worst[1]}'. When you reason that way,")
            print("  you are worse than a coin flip. That is the finding to act on.")
            print()
    _group_table("BY TOPIC", rs, topics)
    _group_table("BY QUESTION KIND (conditional: what follows from an action "
                 "already taken; unconditional: will it happen at all)", rs, qkind)
    _group_table("BY SOURCE", rs, sources)

    # Correction: logged-with-correction results, and the retrospective test.
    print("  CORRECTING TOWARD THE BASELINE")
    print("  " + "-" * 60)
    cal = [c for c in rs if c.get("calibrated")]
    if cal:
        rb = sum(brier(c["probability"], c["resolved"]["outcome"]) for c in cal) / len(cal)
        cb = sum(brier(c["calibrated"]["p"], c["resolved"]["outcome"]) for c in cal) / len(cal)
        print(f"  resolved with a stored correction: {len(cal)}   "
              f"raw {rb:.3f}   corrected {cb:.3f}")
    else:
        print("  No forecast logged with a stored correction has resolved yet.")
    lo_o = loo(d)
    if lo_o is not None:
        print(f"  leave-one-out on all {len(rs)}: corrected {lo_o:.3f}  "
              f"(raw {mine:.3f}, baseline {base:.3f})")
    k, _, n, _ = current_k(d)
    print(f"  new forecasts are stored with k = {k:.3f}, fitted on {n}. "
          f"Working: `ledger.py calibrate`")
    print()

    print("  Brier: 0 is perfect, 0.25 is what you get by always saying 50%,")
    print("  1.0 is confidently wrong every time. Lower is better.")


def show_calibration(d):
    rs = scored(d)
    n = len(rs)
    if n < 3:
        print(f"Only {n} scored claim(s). Nothing to fit yet; new forecasts use "
              f"the prior k = {PRIOR_K}.")
        return
    rows = rows_of(rs)
    num = sum((o - b) * (p - b) for p, b, o in rows)
    den = sum((p - b) ** 2 for p, b, o in rows)
    fit = fit_k(rows)
    clamped = max(K_FLOOR, min(K_CEIL, fit))
    k = blend_k(fit, n)
    mine = sum(brier(p, o) for p, b, o in rows) / n
    base = sum(brier(b, o) for p, b, o in rows) / n

    print("=" * 74)
    print("HOW MUCH OF YOUR OWN JUDGMENT THE RECORD SAYS TO KEEP")
    print("=" * 74)
    print()
    print("  Every forecast is also stored corrected toward its baseline:")
    print()
    print("     q = b + k(p − b)")
    print()
    print("     q           the corrected probability, stored next to yours")
    print("     p           the probability you gave")
    print("     b           the baseline: the market price if one exists,")
    print("                 otherwise the base rate")
    print("     p − b       how far your judgment moved away from the baseline")
    print("     k(p − b)    k multiplied by that move; k is how much of it to")
    print("                 keep, 1 all of it, 0 none")
    print("     +           add the kept part back on to the baseline")
    print()
    print("  The k that would have scored best on the record so far:")
    print()
    print("     k* = Σ (o − b)(p − b) ÷ Σ (p − b)²")
    print(f"        = {num:.3f} ÷ {den:.3f} = {fit:+.3f}")
    print()
    print("     o           what happened: 1 if it came true, 0 if not")
    print("     Σ           add up over every scored forecast")
    print("     ( )( )      two brackets side by side are multiplied")
    print("     ÷           divided by;  ² squared")
    print()
    if fit < 0:
        print("  A negative k* means that when you moved away from the baseline,")
        print("  reality more often went the other way.")
        print()
    print(f"  That k* is limited to between {K_FLOOR:g} and {K_CEIL:g} -- never bet against")
    print("  yourself on a short record -- and pulled toward the prior:")
    print()
    print("     k = (w₀ × k₀ + n × k*) ÷ (w₀ + n)")
    print(f"       = ({PRIOR_WEIGHT} × {PRIOR_K} + {n} × {clamped:.3f}) ÷ "
          f"({PRIOR_WEIGHT} + {n}) = {k:.3f}")
    print()
    print(f"     k₀          the prior, {PRIOR_K}: keep half of every move until the")
    print("                 record says otherwise")
    print(f"     w₀          how many forecasts the prior counts as: {PRIOR_WEIGHT}")
    print(f"     n           resolved forecasts on the record: {n}")
    print("     ×           multiplied by")
    print()
    print("  WHAT EACH k WOULD HAVE SCORED ON THE RECORD  (in sample -- flatters)")
    print("  " + "-" * 60)
    for label, kk in (("trust yourself fully", 1.0), ("keep half", 0.5),
                      ("the k now in use", k), ("use the baseline only", 0.0)):
        bb = sum(brier(b + kk * (p - b), o) for p, b, o in rows) / n
        print(f"     k = {kk:5.3f}   {label:<24} Brier {bb:.3f}")
    print()
    lo_o = loo(d)
    print("  THE HONEST TEST -- leave one out")
    print("  " + "-" * 60)
    print(f"  Correct each forecast with a k fitted on the other {n - 1}, as if it")
    print("  were the newest, so it never sees its own answer:")
    print()
    print(f"     raw {mine:.3f}     corrected {lo_o:.3f}     baseline {base:.3f}")
    print()
    if lo_o < mine - 0.005:
        print(f"  Correcting would have cut your error by {mine - lo_o:.3f}.")
    else:
        print("  Correcting would not have helped.")
    if lo_o > base + 0.005:
        print(f"  The baseline on its own still wins, by {lo_o - base:.3f}.")
    print()
    ms = {}
    for c in rs:
        for m in modes(c):
            ms.setdefault(m, []).append(c)
    print(f"  PER MODE -- each gets its own k only at {MODE_MIN} scored forecasts")
    print("  " + "-" * 60)
    for m, cs in sorted(ms.items(), key=lambda kv: -len(kv[1])):
        f = fit_k(rows_of(cs)) if len(cs) >= 2 else None
        fs = f"k* {f:+.2f}" if f is not None else "k*   —  "
        use = "in use" if len(cs) >= MODE_MIN else f"needs {MODE_MIN - len(cs)} more"
        print(f"     {m:<22} n={len(cs):<3} {fs}   {use}")
    print()
    print(f"  NEW FORECASTS ARE STORED WITH k = {k:.3f}")


# ----------------------------------------------------------------- write ---

def add(d, c):
    """Validate, correct and append one forecast. Returns (ok, message)."""
    for k in REQUIRED:
        if k not in c:
            return False, (f"Missing required field '{k}'. Resolution criteria "
                           f"and a baseline are mandatory: decide afterwards what "
                           f"would have counted and you will decide you were right.")
    if find(d, c["id"]):
        return False, f"A claim with id '{c['id']}' already exists."
    if "probability" not in c["baseline"]:
        return False, "The baseline needs a probability."
    if not 0.0 <= c["probability"] <= 1.0:
        return False, "Probability must be between 0 and 1."
    c.setdefault("made", today())
    for key in ("mode", "topic"):
        # A bare string would be split letter by letter into the tags below.
        if isinstance(c.get(key), str):
            c[key] = [c[key]]
    tags = c.get("tags", [])
    c.setdefault("mode", [t for t in tags if t in MODES] or ["untagged"])
    c.setdefault("topic", [t for t in tags if t not in MODES and t not in FLAGS]
                 or ["no-topic"])
    c.setdefault("tags", list(c["mode"]) + list(c["topic"]))
    c["resolved"] = None
    cal = calibrate_new(d, c)
    d["claims"].append(c)
    save(d)
    msg = [f"Logged [{c['id']}] at p={c['probability']:.2f} against a baseline "
           f"of {c['baseline']['probability']:.2f}, resolving {c['resolves']}.",
           f"Stored corrected: {cal['p']:.2f} (k={cal['k']:.2f}, fitted on "
           f"{cal['fitted_on']})."]
    if c["resolves"] <= c["made"]:
        msg.append("WARNING: this resolves on or before the day it was logged. A "
                   "forecast logged after its answer is public scores as a free "
                   "win -- check nothing has already settled it.")
    if placeholder_baseline(c):
        msg.append("WARNING: the baseline is a placeholder coin flip, so the "
                   "correction pulls this toward 50%. Find a market price or a "
                   "base rate.")
    return True, "\n".join(msg)


def rerun(d, cid, p, reasoning, baseline=None):
    """Log a fresh forecast on the same question. The original is untouched."""
    parent = find(d, cid)
    if parent is None:
        print(f"No claim with id '{cid}'.")
        return None
    if parent.get("resolved"):
        print(f"[{cid}] is already resolved. Nothing to rerun.")
        return None
    if not 0.0 <= p <= 1.0:
        print("Probability must be between 0 and 1.")
        return None
    root = root_of(d, parent)
    nid, i = f"{root}~{today()}", 2
    while find(d, nid):
        nid, i = f"{root}~{today()}-{i}", i + 1
    new = {
        "id": nid,
        "claim": parent["claim"],
        "made": today(),
        "resolves": parent["resolves"],
        "probability": p,
        "resolution_criteria": parent["resolution_criteria"],
        "baseline": dict(baseline) if baseline else dict(parent.get("baseline", {})),
        "reasoning": reasoning,
        "revises": cid,
        "mode": list(modes(parent)),
        "topic": list(topics(parent)),
        "tags": list(parent.get("tags", [])),
        "resolved": None,
    }
    if parent.get("flags"):
        new["flags"] = list(parent["flags"])
    cal = calibrate_new(d, new)
    d["claims"].append(new)
    save(d)
    print(f"[{nid}] logged as a rerun of [{cid}]: {parent['probability']:.2f} → "
          f"{p:.2f} (stored corrected {cal['p']:.2f}). The original stays on the record.")
    return new


def resolve(d, cid, outcome, note, early=None, force=False):
    """outcome: True, False, or None for unresolvable. Every rerun of the same
    question resolves with it.

    Before its date a question closes only if `early` says why (a market has
    settled it, or the event has plainly happened). A question about what the
    research says is not SCORED early even then, unless `force`: the answer can
    change when new studies appear. Returns True if it closed."""
    if find(d, cid) is None:
        print(f"No claim with id '{cid}'.")
        return False
    fam = [x for x in family(d, cid) if not x.get("resolved")]
    if not fam:
        print(f"[{cid}] already resolved.")
        return False
    not_due = sorted(x["resolves"] for x in fam if x["resolves"] > today())
    if not_due:
        if not early:
            print(f"[{cid}] is not due until {not_due[0]}, so it was left open. To "
                  f"close it sooner, say why: --early \"the market resolved YES\".")
            return False
        research = sorted({m for x in fam for m in modes(x) if m in PROTECTED_EARLY})
        if outcome is not None and research and not force:
            print(f"[{cid}] asks what the research says ({', '.join(research)}), so it "
                  f"is not scored before {not_due[0]} even if the answer looks settled: "
                  f"new studies can change it. It was left open. Close it as "
                  f"unresolvable if the question itself was badly set, or pass --force.")
            return False
        note = f"(closed early: {early}) {note}".strip()
    for x in fam:
        x["resolved"] = {"outcome": outcome, "when": today(), "note": note}
        if outcome is None:
            x["resolved"]["unresolvable"] = True
    save(d)
    if outcome is None:
        extra = f" with {len(fam) - 1} rerun(s)" if len(fam) > 1 else ""
        print(f"[{cid}] closed as UNRESOLVABLE{extra}. Not scored.")
        print("  A question that could not be settled was not a forecast. Next")
        print("  time, log the nearer claim the same belief implies.")
        return True
    for x in fam:
        b = brier(x["probability"], outcome)
        line = (f"[{x['id']}] resolved {'TRUE' if outcome else 'FALSE'}. "
                f"You said {x['probability']:.2f}. Brier {b:.3f}.")
        if x.get("calibrated"):
            line += (f"  Corrected {x['calibrated']['p']:.2f}: Brier "
                     f"{brier(x['calibrated']['p'], outcome):.3f}.")
        print(line)
    worst = max(fam, key=lambda x: brier(x["probability"], outcome))
    if brier(worst["probability"], outcome) > 0.4:
        print("  That is a bad miss. Worth reading back what you wrote.")
        print(f"  Your reasoning was: {worst.get('reasoning', '(none recorded)')}")
    return True


def export(d):
    """Snapshot for the report page: the score, the fit, and every forecast."""
    rs = scored(d)
    n = len(rs)
    k, fit, _, _ = current_k(d)
    summary = {"scored": n, "open": len(open_claims(d)),
               "unresolvable": len(unresolvable(d)),
               "voided": len(d.get("voided", [])), "k": round(k, 4),
               "k_fit": None if fit is None else round(fit, 4),
               "prior_k": PRIOR_K, "prior_weight": PRIOR_WEIGHT}
    if n:
        summary.update(
            brier=round(sum(brier(c["probability"], c["resolved"]["outcome"])
                            for c in rs) / n, 4),
            baseline_brier=round(sum(brier(base_p(c), c["resolved"]["outcome"])
                                     for c in rs) / n, 4),
            bias=round(sum(c["probability"] - outcome01(c) for c in rs) / n, 4),
            loo=None if loo(d) is None else round(loo(d), 4))
    buckets = []
    for lo, hi in BUCKETS:
        b = [c for c in rs if lo <= c["probability"] < hi]
        if b:
            buckets.append({"lo": lo, "hi": min(hi, 1.0), "n": len(b),
                            "said": round(sum(c["probability"] for c in b) / len(b), 4),
                            "happened": round(sum(outcome01(c) for c in b) / len(b), 4)})
    claims = []
    for c in d["claims"]:
        r = c.get("resolved")
        claims.append({
            "id": c["id"], "claim": c["claim"], "made": c.get("made"),
            "resolves": c["resolves"], "p": c["probability"],
            "baseline": base_p(c),
            "baseline_placeholder": placeholder_baseline(c),
            "corrected": (c.get("calibrated") or {}).get("p"),
            "mode": modes(c), "topic": topics(c), "revises": c.get("revises"),
            "status": ("open" if not r else
                       "unresolvable" if r.get("outcome") is None else
                       "true" if r["outcome"] else "false"),
        })
    return {"as_of": today(), "summary": summary, "buckets": buckets,
            "claims": claims}


TEMPLATE = """{
  "id": "short-slug",
  "claim": "what you think will happen, in one sentence",
  "made": "%s",
  "resolves": "YYYY-MM-DD",
  "probability": 0.70,
  "resolution_criteria": "EXACTLY what would count as this being true. Write it now. You will not be honest about it later.",
  "baseline": {
    "what": "the market price if one exists, else the base rate -- the dumb answer",
    "probability": 0.50
  },
  "reasoning": "why you think so. you will want this when you are wrong.",
  "mode": ["search-prediction"],
  "topic": ["geopolitics"]
}""" % date.today().isoformat()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    d = load()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "score":
        score(d)
    elif cmd == "calibrate":
        show_calibration(d)
    elif cmd == "due":
        show_open(d, only_due=True)
    elif cmd == "stale":
        nums = [a for a in sys.argv[2:] if a.isdigit()]
        show_stale(d, int(nums[0]) if nums else None, "--all" in sys.argv)
    elif cmd == "checked":
        if len(sys.argv) < 3:
            print('usage: ledger.py checked <id> ["note"]   -- a look that changed nothing')
            return
        mark_checked(d, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "add":
        if len(sys.argv) < 3:
            print("Save this as a .json file, fill it in, then run "
                  "`ledger.py add <file>`:\n")
            print(TEMPLATE)
            return
        src = sys.argv[2]
        text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
        ok, msg = add(d, json.loads(text))
        print(msg)
        if not ok:
            sys.exit(1)
    elif cmd == "rerun":
        if len(sys.argv) < 5:
            print('usage: ledger.py rerun <id> <p> "reasoning" '
                  '[<baseline_p> "what the baseline is"]')
            return
        base = None
        if len(sys.argv) > 5:
            base = {"probability": float(sys.argv[5]),
                    "what": sys.argv[6] if len(sys.argv) > 6 else ""}
        rerun(d, sys.argv[2], float(sys.argv[3]), sys.argv[4], base)
    elif cmd == "resolve":
        rest = sys.argv[2:]
        force, early = False, None
        if "--force" in rest:
            force = True
            rest.remove("--force")
        if "--early" in rest:
            i = rest.index("--early")
            early = rest[i + 1] if i + 1 < len(rest) else "no reason given"
            del rest[i:i + 2]
        if len(rest) < 2:
            print('usage: ledger.py resolve <id> yes|no|unresolvable ["note"] '
                  '[--early "why"] [--force]')
            return
        word = rest[1].lower()
        if word in ("unresolvable", "u", "void", "none"):
            out = None
        elif word in ("yes", "y", "true", "1"):
            out = True
        elif word in ("no", "n", "false", "0"):
            out = False
        else:
            print(f"'{rest[1]}' is not yes, no or unresolvable.")
            return
        ok = resolve(d, rest[0], out, rest[2] if len(rest) > 2 else "", early, force)
        if not ok:
            sys.exit(1)
    elif cmd == "export":
        snap = export(d)
        if len(sys.argv) > 2:
            with open(sys.argv[2], "w", encoding="utf-8", newline="\n") as f:
                json.dump(snap, f, indent=2, ensure_ascii=False)
            print(f"Wrote {sys.argv[2]}: {len(snap['claims'])} forecasts, "
                  f"as of {snap['as_of']}.")
        else:
            print(json.dumps(snap, indent=2, ensure_ascii=False))
    else:
        rs, op = resolved(d), open_claims(d)
        parts = [f"{len(scored(d))} scored"]
        if unresolvable(d):
            parts.append(f"{len(unresolvable(d))} unresolvable")
        parts.append(f"{len(op)} open")
        if d.get("voided"):
            parts.append(f"{len(d['voided'])} voided")
        print(f"{len(d['claims'])} claims — {', '.join(parts)}\n")
        show_open(d)
        if rs:
            print("Run `python harness/ledger.py score` for calibration.")


if __name__ == "__main__":
    main()
