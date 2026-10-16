#!/usr/bin/env python3
"""
gapmap_tools.py -- three read-only lookups over the gap map, for the Elipsis tool server.

  whats_new_for_gap  new papers judged on topic for a gap since the last look
  will_this_work     a fix's odds: counted base rate, forecast on the record, what is known
  gaps_moving        gaps ranked by recent judged-on-topic activity

Standard library only. Reads gapmap/sweep.db (daily sweep), gapmap/items.db (hand-built
nodes), gapmap/nodes/*.json, gapmap/convergent/capability_topics.json and
harness/ledger/claims.json. Never calls a network. gapmap/history.db is used for
base rates only if it exists (rebuild: gaphistory.py fetch-trials, fetch-approvals).
The only write is gapmap/looks.json, and only when mark_seen is set.

Coverage is partial and the tools say so: only the fixes tagged with OpenAlex
topics (capability_topics.json) are swept, and only matches the daily reading
has judged count as on topic.
"""

import datetime
import glob
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402  (sits next to this file)
GAPMAP = os.path.join(os.path.dirname(HERE), "gapmap")
LEDGER = paths.data("ledger", "claims.json")
LOOKS = os.path.join(GAPMAP, "looks.json")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _caps():
    d = _load(os.path.join(GAPMAP, "convergent", "capability_topics.json"))
    return d["capabilities"], d.get("complete")


def _nodes():
    return [_load(p) for p in sorted(glob.glob(os.path.join(GAPMAP, "nodes", "*.json")))]


def _con(name):
    p = os.path.join(GAPMAP, name)
    if not os.path.exists(p):
        return None
    return sqlite3.connect(p)


def _today():
    return datetime.date.today().isoformat()


def _find_gap(query, caps):
    """Match a gap by id, slug or a fragment of its name. Returns (gap_name, set of fix ids) or None."""
    q = (query or "").strip().lower()
    gaps = {}
    for c in caps:
        for g in c.get("gaps", []):
            gaps.setdefault(g["id"], {"name": g["name"], "slug": g.get("slug") or "", "caps": set()})["caps"].add(c["id"])
    for gid, g in gaps.items():
        if q in (gid.lower(), g["slug"].lower(), g["name"].lower()):
            return g["name"], g["caps"]
    hits = [g for g in gaps.values() if q and (q in g["name"].lower() or q in g["slug"].lower())]
    if len(hits) == 1:
        return hits[0]["name"], hits[0]["caps"]
    if len(hits) > 1:
        return None, [h["name"] for h in hits]
    return None, sorted(g["name"] for g in gaps.values())


def _pilot(query):
    q = (query or "").strip().lower()
    for n in _nodes():
        if q and (q == n["slug"] or q in n["name"].lower() or q in n["slug"]):
            return n
    return None


def whats_new_for_gap(args):
    caps, complete = _caps()
    gap = args.get("gap", "")
    days = int(args.get("days", 14))
    limit = int(args.get("limit", 20))
    looks = _load(LOOKS) if os.path.exists(LOOKS) else {}
    pilot = _pilot(gap)
    if pilot:
        name, ids = pilot["name"], set()
    else:
        name, ids = _find_gap(gap, caps)
        if name is None:
            return "No single gap matched '%s'. Choose one of: %s" % (gap, "; ".join(sorted(ids)))
    key = pilot["slug"] if pilot else name
    since = args.get("since") or looks.get(key) or (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    out, pending = [], 0
    if pilot:
        con = _con("items.db")
        if con:
            for r in con.execute("""SELECT title, url, date, effect, note, source, strength FROM items
                                    WHERE node=? AND on_topic='on' AND date>=?
                                    ORDER BY (strength='strong') DESC, date DESC LIMIT ?""",
                                 (pilot["slug"], since, limit)):
                out.append(dict(zip(("title", "url", "date", "effect", "note", "source", "strength"), r)))
            pending = con.execute("SELECT COUNT(*) FROM items WHERE node=? AND judged IS NULL", (pilot["slug"],)).fetchone()[0]
    else:
        con = _con("sweep.db")
        if con:
            qm = ",".join("?" * len(ids))
            for r in con.execute(f"""SELECT w.title, w.url, w.date, m.effect, m.note, m.cap FROM matches m
                                     JOIN works w ON w.work=m.work
                                     WHERE m.on_topic='on' AND m.cap IN ({qm}) AND w.date>=?
                                     ORDER BY w.date DESC LIMIT ?""", (*ids, since, limit)):
                out.append(dict(zip(("title", "url", "date", "effect", "note", "fix_id"), r)))
            pending = con.execute(f"SELECT COUNT(*) FROM matches WHERE judged IS NULL AND cap IN ({qm})", tuple(ids)).fetchone()[0]
    if args.get("mark_seen"):
        looks[key] = _today()
        with open(LOOKS, "w", encoding="utf-8") as f:
            json.dump(looks, f, indent=1)
    lines = [f"GAP: {key}", f"HOW ROUGH: counted from the daily sweep; 'on topic' is the daily reading's judgement of a title and abstract, not a measured fact.",
             f"SINCE: {since} (publication date). Found {len(out)} judged on topic (showing up to {limit}); {pending} further candidates not yet read.",
             "TIERS: nothing on topic is dropped. STRONG = a regulator, trial or standards step, or a new measure checked against outcomes; context = on topic background, listed after the strong ones.",
             "COVERAGE: only %s of the Gap Map's fixes are tagged for the sweep; a gap with no tagged fix returns nothing, which is not the same as no news."
             % (str(len(caps)) if complete is False else "all tagged")]
    for o in out:
        eff = {"up": "moves the odds up", "down": "moves the odds down"}.get(o.get("effect"), "no change to odds")
        tier = {"strong": "STRONG", "context": "context"}.get(o.get("strength"), "ungraded")
        lines.append(f"- {o['date']} {tier}: {o['title']} [{eff}] {o['url']}\n    {o.get('note') or ''}")
    return "\n".join(lines)


def _ledger_forecast(ids):
    """Latest logged entry per forecast id (reruns are stored as id~date)."""
    if not os.path.exists(LEDGER):
        return []
    claims = _load(LEDGER).get("claims", [])
    claims = claims.values() if isinstance(claims, dict) else claims
    out = []
    for base in ids:
        rel = [c for c in claims if c.get("id") == base or str(c.get("id", "")).startswith(base + "~")]
        if rel:
            out.append(sorted(rel, key=lambda c: str(c.get("id")))[-1])
    return out


def will_this_work(args):
    fix = args.get("fix", "")
    n = _pilot(fix)
    lines = ["HOW ROUGH: the base rate is counted (s of n from a named source); the forecast is my estimate logged before looking at prices; "
             "neither is a measured chance for this specific fix."]
    if n:
        b = n["base_rate"]
        s, t = b["s"], b["n"]
        rs = (s + 1) / (t + 2)
        lines += [f"FIX: {n['name']}", f"SUCCESS LINE: {n['success_line']['text']}", f"STATUS: {n['success_line']['status']}",
                  "",
                  f"BASE RATE: {s} of {t} similar attempts succeeded ({s} in {t}; {t - s} did not). Rule of succession: (s + 1) / (n + 2) = ({s} + 1) / ({t} + 2) = {rs:.2f}, "
                  f"i.e. {round(rs * 100)} in 100 succeed, {100 - round(rs * 100)} in 100 do not.",
                  "  s = similar attempts that succeeded; n = similar attempts counted; the +1 and +2 stop a small count from claiming 0 or 100.",
                  f"  What was counted: {b['what']}", f"  Source: {b['source']} {b['url']}", f"  Caveat: {b['caveat']}"]
        fc = _ledger_forecast(set(n.get("forecasts", [])))
        for c in fc:
            p = c.get("probability")
            lines.append(f"NEAR-TERM FORECAST ON THE RECORD: {c.get('claim', '')} -- {round(p * 100)} in 100 yes, {100 - round(p * 100)} in 100 no; resolves {c.get('resolves', '?')}.")
        if not fc and n.get("forecasts"):
            lines.append("NEAR-TERM FORECAST ids: " + ", ".join(n["forecasts"]) + " (not found in the ledger file).")
        lat = n.get("latest", {}).get("papers", {})
        if lat:
            lines.append(f"WHAT IS KNOWN: {lat.get('count')} papers in the last {n['latest'].get('window_days')} days "
                         f"(about {lat.get('estimated_on_topic')} on topic), refreshed {n['latest'].get('refreshed')}.")
        for note in n.get("notes", []):
            lines.append("  note: " + note)
        h = _con("history.db")
        try:
            nt = h.execute("SELECT COUNT(*) FROM trials").fetchone()[0] if h else 0
        except sqlite3.Error:
            nt = 0
        lines.append("HISTORY DATABASE: %s" % ("holds %d trials; trial outcomes by phase are available through gaphistory.py." % nt if nt else
                     "empty here (not in the repository), so no trial or approval base rate was used beyond the counted one above."))
        return "\n".join(lines)
    caps, _ = _caps()
    q = fix.strip().lower()
    hits = [c for c in caps if q and q in c["name"].lower()]
    if len(hits) != 1:
        names = [c["name"] for c in (hits or caps)]
        return "No single fix matched '%s'. Fixes with counted odds: %s. Fixes in the sweep only: %s" % (
            fix, "; ".join(x["name"] for x in _nodes()), "; ".join(names))
    c = hits[0]
    con = _con("sweep.db")
    on = tot = 0
    if con:
        on, tot = con.execute("SELECT SUM(on_topic='on'), SUM(judged IS NOT NULL) FROM matches WHERE cap=?", (c["id"],)).fetchone()
    lines += [f"FIX: {c['name']}", "ODDS: none. No success line, counted base rate or forecast exists for this fix, so any number would be a guess.",
              f"WHAT IS KNOWN: the daily sweep has {on or 0} papers judged on topic out of {tot or 0} judged so far (activity only, not evidence it will work).",
              "To get odds: write a dated success line, count s of n similar past attempts from a named source, then log a forecast."]
    return "\n".join(lines)


def gaps_moving(args):
    caps, complete = _caps()
    days = int(args.get("days", 14))
    top = int(args.get("top", 10))
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    gaps = {}
    for c in caps:
        for g in c.get("gaps", []):
            gaps.setdefault(g["id"], {"name": g["name"], "caps": set()})["caps"].add(c["id"])
    rows = []
    con = _con("sweep.db")
    for g in gaps.values():
        on = judged = cand = 0
        if con:
            qm = ",".join("?" * len(g["caps"]))
            on, judged, cand = con.execute(f"""SELECT COALESCE(SUM(m.on_topic='on'),0), COALESCE(SUM(m.judged IS NOT NULL),0), COUNT(*)
                FROM matches m JOIN works w ON w.work=m.work WHERE m.cap IN ({qm}) AND w.date>=?""", (*g["caps"], since)).fetchone()
        rows.append((g["name"], on, judged, cand))
    icon = _con("items.db")
    if icon:
        for n in _nodes():
            on, judged, cand = icon.execute("""SELECT COALESCE(SUM(on_topic='on'),0), COALESCE(SUM(judged IS NOT NULL),0), COUNT(*)
                FROM items WHERE node=? AND date>=?""", (n["slug"], since)).fetchone()
            rows.append((n["name"] + " (hand-built node)", on, judged, cand))
    rows.sort(key=lambda r: (-r[1], -r[3]))
    lines = ["HOW ROUGH: counted. Activity is papers per window, not progress; a busy gap is not a gap about to be solved. "
             "Ranking is by papers the daily reading judged on topic; unjudged candidates are shown and not counted.",
             f"WINDOW: publication dates from {since} ({days} days). Only fixes tagged for the sweep are covered; "
             "there is no comparison with an earlier window, so this does not say 'speeding up' or 'slowing down'.",
             "RANK | GAP | on topic | judged | candidates"]
    for i, r in enumerate(rows[:top], 1):
        lines.append(f"{i} | {r[0]} | {r[1]} | {r[2]} | {r[3]}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    a = sys.argv[1:]
    f = {"new": whats_new_for_gap, "work": will_this_work, "moving": gaps_moving}[a[0]]
    print(f(json.loads(a[1]) if len(a) > 1 else {}))
