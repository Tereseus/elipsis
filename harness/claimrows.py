"""claimrows.py -- one row per checked claim, so that claims can be counted, not just read.

A case checks a claim in prose. Prose cannot be counted. This keeps, for every
checked claim, the same fields: what was claimed and where, the gap-map entry it
belongs to and the one that blocks it, the evidence it rested on, the verdict, the
odds that it reaches people by given years, the chain of steps behind those odds,
and later what actually happened.

Two things are computed, never typed in:

  ODDS BY YEAR   each row is one or more ROUTES (chains of steps) to a milestone,
                 optionally behind SHARED steps that every route needs. A step
                 succeeds with chance p and takes a random time around its typical
                 length. Many timelines are simulated and counted.
  WEAKEST STEP   the step whose improvement is worth the most to the whole row:
                 dP/dp_j = P / p_j for a single chain, adjusted for other routes.

Across many rows, the weakest steps are grouped by kind ("first effect in people",
"regulator", ...) and by the gap-map entry that blocks them. That count is where
known approaches get stuck. It ranks known options; it does not invent new ones.

    python harness/claimrows.py list [ENTRY]
    python harness/claimrows.py show ID
    python harness/claimrows.py sticking [FIELD]
    python harness/claimrows.py add ROWS.json      (a row or a list of rows)

Standard library only. Rows are saved in rows/claims.json in the data folder.
"""
import datetime
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import paths  # noqa: E402

FILE = paths.data("rows", "claims.json")

YEARS = (2030, 2035, 2040, 2050)   # read as "by the end of that year"
SIMS = 200_000
SPREAD = 0.45                      # spread of each step's length, on the log scale
FLOOR = 0.2                        # years a step always takes, at least

VERDICTS = ("holds", "partly", "wrong")
EVIDENCE = ("cells", "animals", "people, observational", "people, small trial",
            "people, large trial", "approved")
KINDS = ("funding or start", "safety in people", "first effect in people",
         "confirmation", "regulator", "no route yet")


def _now():
    d = datetime.date.today()
    return d.year + (d.timetuple().tm_yday - 1) / 365


# ---------------------------------------------------------------- the maths

def step_p(s):
    """Chance a step ever succeeds. A step is either a fixed chance (p) or a yearly
    chance (per_year) that has to come up within max_years."""
    if "per_year" in s:
        return 1 - (1 - s["per_year"]) ** s["max_years"]
    return s["p"]


def route_p(r):
    return math.prod(step_p(s) for s in r["stages"])


def ever(row):
    """P = (product of shared steps) x (1 - product over routes of (1 - route chance))."""
    shared = math.prod(step_p(s) for s in row.get("shared", []))
    none = math.prod(1 - route_p(r) for r in row["routes"])
    return shared * (1 - none)


def _draw_time(s, rng):
    """Years the step takes, or None if it fails."""
    if "per_year" in s:
        t = math.log(1 - rng.random()) / math.log(1 - s["per_year"])
        return t if t <= s["max_years"] else None
    if rng.random() >= s["p"]:
        return None
    if s.get("median", 0) <= 0:
        return 0.0
    return max(FLOOR, s["median"] * math.exp(rng.gauss(0, SPREAD)) - s.get("done", 0))


def simulate(row, now=None, years=YEARS, sims=SIMS, seed=20261017):
    """Chance the milestone is reached by the end of each year, from simulated timelines."""
    now = _now() if now is None else now
    rng = random.Random(seed)
    hits = [0] * len(years)
    for _ in range(sims):
        t0, ok = 0.0, True
        for s in row.get("shared", []):
            t = _draw_time(s, rng)
            if t is None:
                ok = False
                break
            t0 += t
        if not ok:
            continue
        best = None
        for r in row["routes"]:
            t = t0
            for s in r["stages"]:
                d = _draw_time(s, rng)
                if d is None:
                    t = None
                    break
                t += d
            if t is not None and (best is None or t < best):
                best = t
        if best is None:
            continue
        for i, y in enumerate(years):
            if now + best <= y + 1:
                hits[i] += 1
    return {str(y): round(100 * h / sims, 1) for y, h in zip(years, hits)}


def worth(row):
    """For every step: how much the whole row's chance rises per point added to that step.
    Shared step j:  dP/dp_j = P / p_j.
    Step j on route r:  dP/dp_j = S x (P_r / p_j) x product over other routes of (1 - P_s),
    where S is the product of the shared steps and P_r the route's own chance."""
    S = math.prod(step_p(s) for s in row.get("shared", []))
    P = ever(row)
    out = []
    for s in row.get("shared", []):
        out.append({"route": "shared", "stage": s["stage"], "kind": s["kind"],
                    "p": round(step_p(s), 3), "worth": round(P / step_p(s), 3)})
    for r in row["routes"]:
        others = math.prod(1 - route_p(q) for q in row["routes"] if q is not r)
        pr = route_p(r)
        for s in r["stages"]:
            out.append({"route": r["name"], "stage": s["stage"], "kind": s["kind"],
                        "p": round(step_p(s), 3),
                        "worth": round(S * pr / step_p(s) * others, 3)})
    return sorted(out, key=lambda x: -x["worth"])


# ---------------------------------------------------------------- the store

def load():
    if not os.path.exists(FILE):
        return []
    with open(FILE, encoding="utf-8") as f:
        return json.load(f)


def _save(rows):
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, FILE)


def check(row):
    need = ("id", "claim", "source", "date", "field", "evidence", "verdict", "milestone")
    miss = [k for k in need if not row.get(k)]
    if miss:
        raise ValueError(f"row {row.get('id', '?')}: missing {', '.join(miss)}")
    if row["verdict"] not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}")
    if row["evidence"] not in EVIDENCE:
        raise ValueError(f"evidence must be one of {EVIDENCE}")
    if not row.get("routes") and not row.get("guessed"):
        raise ValueError(f"row {row['id']}: give routes (chains of steps) or guessed odds")
    for r in row.get("routes", []):
        for s in row.get("shared", []) + r["stages"]:
            if s.get("kind") not in KINDS:
                raise ValueError(f"step '{s.get('stage')}': kind must be one of {KINDS}")
            p = step_p(s)
            if not 0 < p <= 1:
                raise ValueError(f"step '{s['stage']}': chance must be above 0 and at most 1")


def compute(row, now=None):
    row = dict(row)
    if row.get("routes"):
        row["p_ever"] = round(100 * ever(row), 1)
        # the simulated chance by a year can't exceed the exact chance of ever; any excess is
        # sampling noise
        row["odds"] = {y: min(v, row["p_ever"]) for y, v in simulate(row, now).items()}
        w = worth(row)
        row["weakest"] = w[0]
        row["steps_by_worth"] = w
    else:
        row["p_ever"] = None
        row["odds"] = {str(k): v for k, v in row["guessed"].items()}
        row["weakest"] = None
        row["steps_by_worth"] = []
    row["computed"] = datetime.date.today().isoformat()
    return row


def add(new_rows, reason=""):
    """Add or update rows. An update keeps the old odds in the row's history, with the reason."""
    if isinstance(new_rows, dict):
        new_rows = [new_rows]
    rows = {r["id"]: r for r in load()}
    msgs = []
    for nr in new_rows:
        check(nr)
        c = compute(nr)
        old = rows.get(c["id"])
        if old:
            c["history"] = old.get("history", []) + [{
                "until": c["computed"], "odds": old.get("odds"), "p_ever": old.get("p_ever"),
                "why_changed": reason or nr.get("why_changed", "")}]
            msgs.append(f"updated {c['id']}: {old.get('odds')} -> {c['odds']}")
        else:
            msgs.append(f"added {c['id']}: {c['odds']}")
        rows[c["id"]] = c
    _save(list(rows.values()))
    return "\n".join(msgs)


# ---------------------------------------------------------------- reports

def _odds(o):
    return ", ".join(f"{y}: {v:g}" for y, v in o.items())


def show(rid):
    r = next((x for x in load() if x["id"] == rid), None)
    if not r:
        return f"No row {rid}."
    out = [f"{r['id']}  ({r['verdict']}, evidence: {r['evidence']})",
           f"Claim: {r['claim']}", f"Source: {r['source']}, {r['date']}",
           f"Gap-map entry: {r.get('about') or 'none'}; blocked by: {r.get('blocked_by') or 'none'}",
           f"Milestone: {r['milestone']}",
           f"Chance in 100 by the end of {_odds(r['odds'])}"]
    if r.get("routes"):
        out.append(f"Chance it ever happens: {r['p_ever']:g} in 100 "
                   f"({100 - r['p_ever']:g} in 100 it never does)")
        for s in r.get("shared", []):
            out.append(f"  shared step: {s['stage']}, chance {step_p(s):.2f} ({s['kind']})")
        for rt in r["routes"]:
            out.append(f"  route: {rt['name']}")
            for s in rt["stages"]:
                out.append(f"    {s['stage']}: chance {step_p(s):.2f} ({s['kind']})"
                           + (f"; {s['why']}" if s.get("why") else ""))
        w = r["weakest"]
        out += ["Weakest step (the one worth most to improve):",
                f"  {w['stage']} ({w['kind']}), chance {w['p']:.2f}: each point added to it "
                f"adds {w['worth']:.2f} points to the whole row."]
    else:
        out.append("Odds guessed directly: no chain of steps to compute.")
    for h in r.get("history", []):
        out.append(f"Earlier, until {h['until']}: {_odds(h['odds'])}. Changed because: {h['why_changed']}")
    if r.get("outcome"):
        out.append(f"Outcome: {r['outcome']}")
    return "\n".join(out)


def listing(entry=None):
    rows = [r for r in load() if not entry or entry in (r.get("about"), r.get("blocked_by"))]
    if not rows:
        return "No claim rows" + (f" for {entry}." if entry else " yet.")
    out = [f"{len(rows)} claim rows" + (f" tied to {entry}" if entry else "") + ":"]
    for r in rows:
        out.append(f"- {r['id']}: {r['verdict']}; {r['milestone']}; chance in 100 by "
                   f"{_odds(r['odds'])}")
    return "\n".join(out)


def sticking(field=None):
    """Where known approaches get stuck: the weakest step of every chained row, grouped."""
    rows = [r for r in load() if r.get("weakest") and (not field or r["field"] == field)]
    if not rows:
        return "No chained claim rows" + (f" in {field}." if field else " yet.")
    by_kind, by_entry = {}, {}
    for r in rows:
        w = r["weakest"]
        by_kind.setdefault(w["kind"], []).append(f"{r['id']} ({w['stage']}, chance {w['p']:.2f})")
        by_entry.setdefault(r.get("blocked_by") or "no entry", []).append(r["id"])
    n = len(rows)
    out = [f"WHERE KNOWN APPROACHES GET STUCK: {n} chained claim rows"
           + (f" in {field}" if field else ""), "",
           "For each row, the weakest step is the one whose improvement is worth the most:",
           "  dP/dp_j = P / p_j",
           "  P: the chance the whole row succeeds",
           "  p_j: the chance step j succeeds",
           "  dP/dp_j: how much P rises for each point added to step j, other steps held fixed",
           "  /: divided by",
           "A derivative of a product: the weakest link always comes out on top. With other "
           "routes to the same goal, the gain is scaled down by the chance those fail too.", "",
           "Weakest step, by kind:"]
    for k, items in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        out.append(f"  {k}: {len(items)} of {n} ({round(100 * len(items) / n)} in 100)")
        out += [f"    - {i}" for i in items]
    out += ["", "Blocked by gap-map entry:"]
    for e, items in sorted(by_entry.items(), key=lambda kv: -len(kv[1])):
        out.append(f"  {e}: {len(items)} of {n}: " + ", ".join(items))
    out += ["", "This ranks known approaches. It cannot propose a new one, and it is only as "
            "good as the step chances behind it; check each row's steps before acting on it."]
    return "\n".join(out)


def main(argv):
    if not argv or argv[0] not in ("list", "show", "sticking", "add"):
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "list":
        print(listing(rest[0] if rest else None))
    elif cmd == "show":
        print(show(rest[0]))
    elif cmd == "sticking":
        print(sticking(rest[0] if rest else None))
    elif cmd == "add":
        with open(rest[0], encoding="utf-8") as f:
            print(add(json.load(f), " ".join(rest[1:])))


if __name__ == "__main__":
    main(sys.argv[1:])
