#!/usr/bin/env python3
"""
gapmap_daily.py -- the daily sweep over every Gap Map fix, and one feed per gap.

It runs every day over every fix on the Gap Map, with updates people can
subscribe to. OpenAlex files every new paper under one of 4,516 topics; gapmap_topics.py
tagged each of the 369 fixes with the topics it touches. This script takes
every new article and preprint in those topics, matches each one to the fixes
it could serve, and stores the matches for the daily reading to judge. Only
matches judged on topic reach the feeds, so a feed is never raw keyword noise.

The search is the cheap part; matching and judging are the hard parts. A
match here is only a candidate: it shares a topic with the fix and names at
least one of the fix's key phrases. The model's reading decides.

Run:  python harness/gapmap_daily.py sweep [--days 10]   -- fetch new works, store candidate matches
      python harness/gapmap_daily.py queue [n] [--json]  -- best unjudged matches to read (default 150)
      python harness/gapmap_daily.py judge-file <file>   -- [{"id": 3, "on": "on"|"off", "effect": "up"|"down"|"none", "note": "...", "strength": "strong"|"context"}]
      python harness/gapmap_daily.py feeds               -- write gapmap/feeds/<gap>.xml and index.md
      python harness/gapmap_daily.py stats               -- counts by day
Store: gapmap/sweep.db (works seen, matches, judgements). Keyless; no personal data is sent.
"""

import datetime
import html
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
GAPMAP = os.path.join(os.path.dirname(HERE), "gapmap")
TAGS = os.path.join(GAPMAP, "convergent", "capability_topics.json")
DB = os.path.join(GAPMAP, "sweep.db")
FEEDS = os.path.join(GAPMAP, "feeds")
UA = {"User-Agent": "elipsis-gapmap/0.2"}
STOP = set("""a an and the of for in on to with by from at as or into via toward towards across using based new novel
better improved scalable large scale high low next generation general purpose open infrastructure platform platforms
tools tool system systems methods method approach approaches technology technologies capability capabilities data
dataset datasets database databases framework frameworks mapping maps map model models modeling modelling measurement
measurements development research analysis""".split())


RESERVE = 50   # OpenAlex credits left untouched for other jobs (free keyless allowance: about 1,000 a day per IP)


class BudgetLow(Exception):
    pass


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                left = r.headers.get("X-RateLimit-Remaining")
                body = json.loads(r.read())
            if left is not None and int(left) < RESERVE:
                raise BudgetLow(left)
            return body
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise BudgetLow("429")
            time.sleep(2 * (i + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 * (i + 1))
    return None


def db():
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS works (work TEXT PRIMARY KEY, date TEXT, title TEXT, url TEXT, venue TEXT,
        type TEXT, topics TEXT, seen TEXT);
    CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY, work TEXT, cap TEXT, score REAL, hits TEXT,
        found TEXT, on_topic TEXT, effect TEXT, note TEXT, judged TEXT, UNIQUE(work, cap));
    CREATE TABLE IF NOT EXISTS runs (at TEXT, since TEXT, until TEXT, fetched INTEGER, new INTEGER, matches INTEGER);
    """)
    if "strength" not in [r[1] for r in con.execute("PRAGMA table_info(matches)")]:
        con.execute("ALTER TABLE matches ADD COLUMN strength TEXT")   # strong | context; null = not graded
    return con


def load_caps():
    with open(TAGS, encoding="utf-8") as f:
        caps = json.load(f)["capabilities"]
    for c in caps:
        words = [w for w in re.findall(r"[a-z][a-z0-9\-]+", c["name"].lower()) if w not in STOP and len(w) > 2]
        # Key phrase from the name, plus each pair of neighbouring key words.
        phrases = {k.lower() for k in c.get("phrases", []) if len(k) > 3}
        phrases |= {f"{a} {b}" for a, b in zip(words, words[1:])}
        c["_words"], c["_phrases"] = words, phrases
        c["_topics"] = {t["id"] for t in c["topics"]}
    return caps


def abstract(inv):
    if not inv:
        return ""
    pos = sorted((p, w) for w, ps in inv.items() for p in ps)
    return " ".join(w for _, w in pos)


def score(cap, text):
    """Candidate strength: key phrases named (2 each) plus share of name words present."""
    hits = [p for p in cap["_phrases"] if p in text]
    share = sum(1 for w in cap["_words"] if w in text) / max(len(cap["_words"]), 1)
    return 2 * len(hits) + share, hits, share


def sweep(days=10):
    caps = load_caps()
    by_topic = {}
    for c in caps:
        for t in c["_topics"]:
            by_topic.setdefault(t, []).append(c)
    ids = sorted(by_topic)
    until = datetime.date.today()
    since = until - datetime.timedelta(days=days)
    con = db()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    fetched = new = nmatch = 0
    sel = "id,title,publication_date,doi,type,topics,abstract_inverted_index,primary_location"
    stopped = None
    for k in range(0, len(ids), 50):
        if stopped:
            break
        f = (f"from_publication_date:{since},to_publication_date:{until},type:article|preprint,"
             f"topics.id:{'|'.join(ids[k:k + 50])}")
        cursor = "*"
        while cursor:
            try:
                r = get("https://api.openalex.org/works?" + urllib.parse.urlencode(
                    {"filter": f, "per-page": 200, "cursor": cursor, "select": sel}))
            except BudgetLow as e:
                stopped = f"allowance low ({e} credits left) at topic chunk {k // 50 + 1} of {(len(ids) + 49) // 50}"
                break
            if not r:
                break
            for w in r["results"]:
                fetched += 1
                wid = w["id"].rsplit("/", 1)[-1]
                if con.execute("SELECT 1 FROM works WHERE work=?", (wid,)).fetchone():
                    continue
                new += 1
                wt = [t["id"].rsplit("/", 1)[-1] for t in (w.get("topics") or [])]
                loc = w.get("primary_location") or {}
                venue = ((loc.get("source") or {}).get("display_name")) or ""
                con.execute("INSERT INTO works VALUES (?,?,?,?,?,?,?,?)",
                            (wid, w.get("publication_date"), w.get("title") or "", w.get("doi") or w["id"],
                             venue, w.get("type"), json.dumps(wt), now))
                text = ((w.get("title") or "") + " " + abstract(w.get("abstract_inverted_index"))).lower()
                for c in {id(c): c for t in wt for c in by_topic.get(t, [])}.values():
                    s, hits, share = score(c, text)
                    if hits or share >= 0.6:
                        con.execute("INSERT OR IGNORE INTO matches (work, cap, score, hits, found) VALUES (?,?,?,?,?)",
                                    (wid, c["id"], round(s, 3), json.dumps(hits), now))
                        nmatch += 1
            cursor = r.get("meta", {}).get("next_cursor")
            time.sleep(0.12)
        con.commit()
    con.execute("INSERT INTO runs VALUES (?,?,?,?,?,?)", (now, str(since), str(until), fetched, new, nmatch))
    con.commit()
    print(f"window {since} to {until}: {fetched} works fetched, {new} new, {nmatch} candidate matches "
          f"across {len(ids)} topics and {len(caps)} fixes" + (f"; STOPPED EARLY: {stopped}" if stopped else ""))


def queue(n=150, as_json=False):
    caps = {c["id"]: c for c in load_caps()}
    con = db()
    rows = con.execute("""SELECT m.id, m.cap, m.score, m.hits, w.title, w.url, w.date, w.venue, w.type
                          FROM matches m JOIN works w ON w.work = m.work
                          WHERE m.judged IS NULL ORDER BY m.score DESC LIMIT ?""", (n,)).fetchall()
    out = [{"id": r[0], "fix": caps[r[1]]["name"] if r[1] in caps else r[1],
            "gaps": [g["name"] for g in caps.get(r[1], {}).get("gaps", [])], "score": r[2],
            "phrases": json.loads(r[3]), "title": r[4], "url": r[5], "date": r[6], "venue": r[7], "type": r[8]}
           for r in rows]
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("GRADING: when judging, give every on-topic match \"strength\": strong (a regulator, trial or standards step, "
              "or a new measure checked against outcomes) or context (on topic, background only). Never drop an on-topic match.")
        for o in out:
            print(f"[{o['id']}] {o['score']:.1f} {o['fix'][:50]} <- {o['title'][:90]} ({o['date']})")
        left = con.execute("SELECT COUNT(*) FROM matches WHERE judged IS NULL").fetchone()[0]
        print(f"{left} unjudged matches in total")


def judge_file(path):
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    con = db()
    now = datetime.datetime.utcnow().isoformat(timespec="seconds")   # UTC, as the feeds say
    for it in items:
        con.execute("UPDATE matches SET on_topic=?, effect=?, note=?, strength=?, judged=? WHERE id=?",
                    (it["on"], it.get("effect", "none"), it.get("note", ""), it.get("strength"), now, it["id"]))
    con.commit()
    print(f"{len(items)} matches judged")


def feeds(max_items=50):
    """One Atom feed per gap: matches judged on topic for any fix under that gap."""
    caps = load_caps()
    gaps = {}
    for c in caps:
        for g in c["gaps"]:
            gaps.setdefault(g["slug"] or g["id"], {"name": g["name"], "caps": set()})["caps"].add(c["id"])
    capname = {c["id"]: c["name"] for c in caps}
    con = db()
    os.makedirs(FEEDS, exist_ok=True)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    index = ["# Gap map feeds", "", f"Updated {now[:10]}. One feed per Gap Map gap: new work judged on topic for any of its fixes.", "",
             "| Gap | Items | Feed |", "|---|---|---|"]
    for slug, g in sorted(gaps.items(), key=lambda kv: kv[1]["name"]):
        qm = ",".join("?" * len(g["caps"]))
        rows = con.execute(f"""SELECT m.cap, m.effect, m.note, m.judged, w.title, w.url, w.date, w.work
                               FROM matches m JOIN works w ON w.work = m.work
                               WHERE m.on_topic='on' AND m.cap IN ({qm})
                               ORDER BY m.judged DESC LIMIT ?""", (*g["caps"], max_items)).fetchall()
        entries = []
        for cap, eff, note, judged, title, url, d, wid in rows:
            mark = {"up": "Moves the odds up. ", "down": "Moves the odds down. "}.get(eff, "")
            entries.append(f"""  <entry>
    <title>{html.escape(title)}</title>
    <link href="{html.escape(url or '')}"/>
    <id>urn:elipsis:gapmap:{slug}:{wid}</id>
    <updated>{(judged or now)[:19]}Z</updated>
    <summary>{html.escape(mark + 'For: ' + capname.get(cap, cap) + '. ' + (note or ''))}</summary>
  </entry>""")
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Elipsis gap map: {html.escape(g['name'])}</title>
  <id>urn:elipsis:gapmap:{slug}</id>
  <updated>{now}</updated>
{chr(10).join(entries)}
</feed>
"""
        with open(os.path.join(FEEDS, f"{slug}.xml"), "w", encoding="utf-8") as f:
            f.write(xml)
        index.append(f"| {g['name']} | {len(rows)} | {slug}.xml |")
    with open(os.path.join(FEEDS, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")
    print(f"{len(gaps)} gap feeds written to gapmap/feeds/")


def stats():
    con = db()
    for r in con.execute("SELECT at, since, until, fetched, new, matches FROM runs ORDER BY at"):
        print(r)
    print(con.execute("SELECT COUNT(*), SUM(judged IS NOT NULL), SUM(on_topic='on') FROM matches").fetchone())


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "stats"
    if cmd == "sweep":
        sweep(int(a[a.index("--days") + 1]) if "--days" in a else 10)
    elif cmd == "queue":
        nums = [x for x in a[1:] if x.isdigit()]
        queue(int(nums[0]) if nums else 150, "--json" in a)
    elif cmd == "judge-file":
        judge_file(a[1])
    elif cmd == "feeds":
        feeds()
    else:
        stats()
