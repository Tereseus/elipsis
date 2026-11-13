"""
forecast_tiers.py -- sort forecasts into tiers by how hard they are to beat,
and show where the score is won and lost.

Every forecast is scored against a starting number (the baseline): a market
price, a count of past cases, "nothing changes", or a guess. How hard a
forecast is depends on three things, each put in a named bucket:

  RARITY   how lopsided the starting number is (b = baseline chance of yes)
           long shot   b under 0.10 or over 0.90. The event is rare (or near
                       certain). The crowd is usually right, there is little
                       to gain, and one surprise costs a lot.
           lean        b from 0.10 to 0.30, or 0.70 to 0.90.
           toss-up     b from 0.30 to 0.70. Most room to add something.

  HORIZON  days from the forecast to the answer
           days        30 or fewer
           months      31 to 180
           years       over 180

  FOOTING  where the starting number came from
           market, counted, persistence or guessed

They combine into one tier:

  Tier 1  simple      market or counted starting number, answer within 30
                      days. Little time for surprises; strong starting point.
  Tier 2  standard    market or counted, answer in 31 to 180 days.
  Tier 3  hard        guessed or persistence starting number, or an answer
                      more than 180 days away. Weak footing or a long wait.
  Tier 4  method      about this toolkit's own methods and tools (the ones
                      the worth test leaves out). Hardest to judge honestly.

A fourth dimension says WHOSE VIEW the forecast tests:

  owner's view      the owner stated a belief (a claim, a worry, an idea, or a
                    report of what someone said); the forecast checks whether
                    the facts bear it out. Each is recorded with the side
                    ("yes" or "no") the owner is on, so the report can count
                    how often the owner's view held, next to the forecast's.
  owner's question  the owner asked a question but took no side.
  scout             picked from public markets and news by the daily scout.
  method            about the toolkit itself (tier 4).
  analyst           the forecaster's own question, from a conversation or a
                    reading job.

Owner's views live in a small store of their own (views.json beside the
ledger), written only through the `view` command below, never by hand.

A long shot in any tier is flagged RARE, because there one surprise costs a
lot. The report shows whether the record actually loses there.

    python harness/forecast_tiers.py report      scored forecasts by tier and
                                                 by rarity: n, Brier, the
                                                 baseline's Brier, and points
                                                 won or lost against it
    python harness/forecast_tiers.py open        open forecasts with their tier
    python harness/forecast_tiers.py one <id>    one forecast's tier and why
    python harness/forecast_tiers.py view <id> <kind> <side> "<the owner's words>"
                                                 record that a forecast tests the
                                                 owner's view; kind is claim,
                                                 worry, idea, report or question;
                                                 side is yes, no, or - (question)
        [--group <belief>]                       parts of one belief share a group
    python harness/forecast_tiers.py fact <slug> <group> held|partly|failed "<evidence>" "<the owner's words>"
                                                 a part of a belief already settled
                                                 by evidence, with no forecast
    python harness/forecast_tiers.py views       the owner's beliefs, part by part:
                                                 how many parts held (partly = half),
                                                 and who set the direction: the
                                                 owner's view the forecast agreed
                                                 with, the owner's view it corrected,
                                                 or the owner's question

Standard library only. Reads the ledger; never writes it.
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ledger as LG  # noqa: E402

TIER_NAMES = {1: "simple", 2: "standard", 3: "hard", 4: "method"}
VIEWS = LG.paths.data("ledger", "views.json")
VIEW_KINDS = ("claim", "worry", "idea", "report", "question")


def load_views():
    try:
        with open(VIEWS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_view(cid, kind, side, words, group=None):
    v = load_views()
    old = v.get(cid, {})
    v[cid] = {"kind": kind, "side": None if side == "-" else side, "words": words,
              "group": group or old.get("group") or cid,
              "recorded": datetime.date.today().isoformat()}
    _write_views(v)


def save_fact(slug, group, outcome, evidence, words, kind="claim"):
    """A part of a view that is already settled by evidence, with no forecast
    behind it: outcome is held, failed or partly."""
    v = load_views()
    v["fact:" + slug] = {"kind": kind, "side": "yes", "words": words, "group": group,
                         "outcome": outcome, "evidence": evidence,
                         "recorded": datetime.date.today().isoformat()}
    _write_views(v)


def _write_views(v):
    os.makedirs(os.path.dirname(VIEWS), exist_ok=True)
    with open(VIEWS, "w", encoding="utf-8") as f:
        json.dump(v, f, indent=1, ensure_ascii=False)


def origin(c, left_out, views):
    root = c["id"].split("~")[0]
    if root in views:
        return "owner's view" if views[root]["kind"] != "question" else "owner's question"
    if left_out(c):
        return "method"
    if str(c.get("source", "")).startswith("scout"):
        return "scout"
    return "analyst"


def _target_left_out():
    """The worth test's leave-out rule, so 'self' matches what it excludes."""
    try:
        with open(LG.TARGET, encoding="utf-8") as f:
            lo = json.load(f).get("leave_out", {})
    except (OSError, ValueError):
        lo = {}

    def left_out(c):
        tags = set(c.get("mode", [])) | set(c.get("tags", []))
        top = c.get("topic", [])
        tops = set(top if isinstance(top, list) else [top])
        return bool(c["id"].split("~")[0] in lo.get("ids", [])
                    or tags & set(lo.get("modes", []))
                    or (tops | tags) & set(lo.get("topics", [])))
    return left_out


def rarity(b):
    if b < 0.10 or b > 0.90:
        return "long shot"
    if b < 0.30 or b > 0.70:
        return "lean"
    return "toss-up"


def _days(c):
    try:
        a = datetime.date.fromisoformat(c["made"][:10])
        z = datetime.date.fromisoformat(c["resolves"][:10])
        return max((z - a).days, 0)
    except (KeyError, ValueError):
        return None


def horizon(c):
    n = _days(c)
    if n is None:
        return "unknown"
    return "days" if n <= 30 else "months" if n <= 180 else "years"


def classify(c, left_out=None):
    """(tier, rarity, horizon, footing, reason) for one forecast."""
    left_out = left_out or _target_left_out()
    b = LG.base_p(c)
    r, h, f = rarity(b), horizon(c), LG.baseline_kind(c)
    if left_out(c):
        t, why = 4, "about Elipsis's own methods"
    elif f in ("guessed", "persistence"):
        t, why = 3, f"starting number is {f}, not a market or a count"
    elif h == "years":
        t, why = 3, f"answer is {_days(c)} days away"
    elif h == "days":
        t, why = 1, f"{f} starting number, answer within {_days(c)} days"
    else:
        t, why = 2, f"{f} starting number, answer in {_days(c)} days"
    if r == "long shot":
        why += f"; RARE: starting chance {b:.2f}"
    return t, r, h, f, why


def _table(title, groups):
    print(f"\n  {title}")
    print("  " + "-" * 74)
    print(f"  {'bucket':<22}{'n':>4}{'yours':>9}{'baseline':>10}{'skill':>8}{'points':>10}")
    for name, cs in groups:
        if not cs:
            continue
        mine = sum(LG.brier(c["probability"], c["resolved"]["outcome"]) for c in cs)
        base = sum(LG.brier(LG.base_p(c), c["resolved"]["outcome"]) for c in cs)
        skill = 1 - mine / base if base > 0 else 0.0
        print(f"  {name:<22}{len(cs):>4}{mine / len(cs):>9.3f}{base / len(cs):>10.3f}"
              f"{skill:>+8.2f}{base - mine:>+10.3f}")
    print("  points = the baseline's total Brier minus yours: above 0 won, below 0 lost.")


def report(d):
    rs = LG.scored(d)
    lo = _target_left_out()
    info = [(c, classify(c, lo)) for c in rs]
    print("=" * 76)
    print(f"FORECAST TIERS  --  {len(rs)} scored")
    print("=" * 76)
    _table("BY TIER", [(f"{t} {TIER_NAMES[t]}", [c for c, k in info if k[0] == t]) for t in (1, 2, 3, 4)])
    _table("BY RARITY", [(r, [c for c, k in info if k[1] == r]) for r in ("long shot", "lean", "toss-up")])
    _table("BY HORIZON", [(h, [c for c, k in info if k[2] == h]) for h in ("days", "months", "years")])
    views = load_views()
    _table("BY WHOSE VIEW", [(o, [c for c in rs if origin(c, lo, views) == o])
                             for o in ("scout", "analyst", "owner's view", "owner's question", "method")])
    worst = sorted(info, key=lambda ck: LG.brier(LG.base_p(ck[0]), ck[0]["resolved"]["outcome"])
                   - LG.brier(ck[0]["probability"], ck[0]["resolved"]["outcome"]))[:5]
    print("\n  BIGGEST LOSSES AGAINST THE BASELINE")
    print("  " + "-" * 74)
    for c, k in worst:
        o = c["resolved"]["outcome"]
        lost = LG.brier(c["probability"], o) - LG.brier(LG.base_p(c), o)
        print(f"  {c['id'][:38]:<40}tier {k[0]} {k[1]:<10} said {c['probability']:.2f} "
              f"vs {LG.base_p(c):.2f}, {'yes' if o else 'no'}: -{lost:.2f}")


def show_open(d):
    lo = _target_left_out()
    for c in sorted(LG.open_claims(d), key=lambda c: c["resolves"]):
        if "~" in c["id"]:
            continue
        t, r, h, f, why = classify(c, lo)
        print(f"  {c['resolves']}  tier {t} {TIER_NAMES[t]:<9}{c['id'][:44]:<46}{why}")


PART_SCORE = {"held": 1.0, "partly": 0.5, "failed": 0.0}


def _part_state(d, cid, v):
    """(settled?, score of the owner's side 0-1 or None, forecast p or None, line)."""
    if cid.startswith("fact:"):
        o = v["outcome"]
        return True, PART_SCORE[o], None, f"already settled by evidence: {o.upper()} ({v['evidence'][:70]})"
    c = LG.find(d, cid)
    if not c:
        return False, None, None, "forecast missing"
    fam = [x for x in d["claims"] if x["id"].split("~")[0] == cid]
    p = max(fam, key=lambda x: x["made"])["probability"]
    side = v.get("side")
    if c.get("resolved") and c["resolved"].get("outcome") is not None:
        o = c["resolved"]["outcome"]
        if not side:
            return True, None, p, f"settled {'yes' if o else 'no'} (a question, no side)"
        ok = (side == "yes") == o
        return True, 1.0 if ok else 0.0, p, f"settled {'yes' if o else 'no'}: the owner's side {'HELD' if ok else 'failed'}"
    if not side:
        return False, None, p, f"open, forecast {p:.2f} for yes"
    agree = (p >= 0.5) == (side == "yes")
    return False, None, p, f"open, owner says {side}, forecast {p:.2f}: {'agrees' if agree else 'leans against'}"


def direction_of(d, cid, v):
    """Who set the direction: the owner's view the forecast agrees with, the
    owner's view the forecast corrects, or the owner's question."""
    if not v.get("side"):
        return "owner's question: forecast sets the direction"
    if cid.startswith("fact:"):
        return "owner's view: settled by evidence"
    fam = [x for x in d["claims"] if x["id"].split("~")[0] == cid]
    if not fam:
        return "owner's view"
    p = max(fam, key=lambda x: x["made"])["probability"]
    return ("owner's view: forecast agrees" if (p >= 0.5) == (v["side"] == "yes")
            else "owner's view: forecast corrects it")


def show_views(d):
    views = load_views()
    if not views:
        print("No owner's views recorded yet.")
        return
    groups = {}
    for cid, v in views.items():
        groups.setdefault(v.get("group") or cid, []).append((cid, v))
    print("=" * 76)
    print(f"THE OWNER'S VIEWS  --  {len(groups)} beliefs or questions, {len(views)} parts")
    print("=" * 76)
    tally = {}
    whole = []
    for g, parts in sorted(groups.items()):
        print(f"\n  {g}")
        got, n = 0.0, 0
        for cid, v in parts:
            settled, score, p, line = _part_state(d, cid, v)
            name = cid[5:] if cid.startswith("fact:") else cid
            print(f"    - {v['kind']:<8} {name[:40]:<42}{line}")
            print(f"        \"{v['words'][:92]}\"")
            if settled and score is not None:
                got += score
                n += 1
                key = direction_of(d, cid, v)
                ok_forecast = None if p is None else ((p >= 0.5) == (score >= 0.5))
                t = tally.setdefault(key, [0, 0, 0, 0])
                t[0] += 1
                t[1] += score
                if ok_forecast is not None:
                    t[2] += ok_forecast
                    t[3] += 1
        if n:
            print(f"    belief score: {got:g} of {n} settled parts held")
            whole.append((got, n))
    print("\n  WHO SET THE DIRECTION (settled parts only)")
    print("  " + "-" * 74)
    if not tally:
        print("  Nothing with a side has settled yet.")
    for key, (n, owner, fc, nf) in sorted(tally.items()):
        fpart = f"forecast's side right {fc} of {nf}" if nf else "no forecast behind these"
        print(f"  {key:<44} n={n:<3} owner's side held {owner:g}; {fpart}")
    if whole:
        g = sum(x for x, _ in whole)
        n = sum(y for _, y in whole)
        print(f"\n  Overall by part: the owner's side held in {g:g} of {n} settled parts "
              f"({100 * g / n:.0f} in 100, {100 - 100 * g / n:.0f} not).")
        avg = sum(x / y for x, y in whole) / len(whole)
        print(f"  Overall by belief (each belief counts once, whatever its number of parts): "
              f"{100 * avg:.0f} in 100 held across {len(whole)} beliefs.")
        for name, (lo_, hi_) in (("held", (1.0, 1.01)), ("partly", (0.25, 1.0)), ("failed", (-1, 0.25))):
            k = sum(1 for x, y in whole if lo_ <= x / y < hi_)
            print(f"    beliefs that {name:<7}{k}")


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    d = LG.load()
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if argv[0] == "report":
        report(d)
        return 0
    if argv[0] == "open":
        show_open(d)
        return 0
    if argv[0] == "views":
        show_views(d)
        return 0
    group = None
    if "--group" in argv:
        i = argv.index("--group")
        group = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if argv[0] == "fact" and len(argv) >= 6:
        slug, grp, outcome, evidence, words = argv[1], argv[2], argv[3], argv[4], " ".join(argv[5:])
        if outcome not in PART_SCORE:
            print("outcome must be held, partly or failed")
            return 1
        save_fact(slug, grp, outcome, evidence, words)
        print(f"Recorded fact part {slug} in {grp}: {outcome}")
        return 0
    if argv[0] == "view" and len(argv) >= 5:
        cid, kind, side, words = argv[1], argv[2], argv[3], " ".join(argv[4:])
        if not LG.find(d, cid):
            print(f"No forecast {cid}")
            return 1
        if kind not in VIEW_KINDS or side not in ("yes", "no", "-"):
            print(f"kind must be one of {VIEW_KINDS}; side yes, no or -")
            return 1
        if kind == "question" and side != "-":
            print("A question takes no side: use -")
            return 1
        save_view(cid, kind, side, words, group)
        print(f"Recorded: {cid} tests the owner's {kind}" + (f", side {side}" if side != "-" else ""))
        return 0
    if argv[0] == "one" and len(argv) > 1:
        c = LG.find(d, argv[1])
        if not c:
            print(f"No forecast {argv[1]}")
            return 1
        t, r, h, f, why = classify(c)
        o = origin(c, _target_left_out(), load_views())
        print(f"{c['id']}: tier {t} ({TIER_NAMES[t]}), rarity {r}, horizon {h}, footing {f}, "
              f"whose view {o}. Why: {why}.")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
