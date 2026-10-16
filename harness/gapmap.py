#!/usr/bin/env python3
"""
gapmap.py -- a plain, scored gap map, one node at a time.

Convergent Research's Gap Map (gap-map.org, MIT licence) lists research
bottlenecks and the capabilities that would fix them. It has no numbers:
no status, no odds, no record of what has worked. This adds four things
to a node, and keeps them in plain files that people and AI assistants
can read without a website:

  1. A SUCCESS LINE, written before looking, the way a trial registers
     its main outcome first.
  2. A TESTED SEARCH. A raw hit count is mostly noise, so each query
     carries its precision
     on a judged sample of 20 and its recall on papers known to belong.
  3. A COUNTED BASE RATE: s successes out of n attempts, from a named
     source, with the rule of succession (s + 1) / (n + 2).
  4. A LEDGER FORECAST that resolves within months, so the map's own
     odds get scored.

Files:
  gapmap/nodes/<slug>.json   the source of truth for a node (hand-edited:
                             success line, queries, judged samples, base rate)
  gapmap/nodes/<slug>.md     rendered from the JSON plus the ledger
  gapmap/README.md           the index
  gapmap/gapmap.json         every node and its forecasts in one file

Run:  python harness/gapmap.py refresh          -- new counts and the newest
                                                   papers and trials per node
      python harness/gapmap.py build            -- rewrite the .md files, the
                                                   index and gapmap.json
      python harness/gapmap.py sample <slug> [papers|trials]
                                                -- the newest 20 results, for
                                                   judging precision by hand
      python harness/gapmap.py recall <slug>    -- which known papers the
                                                   papers query finds

Sources need no key: Europe PMC (papers) and ClinicalTrials.gov API v2
(trials). Precision is judged by a person or a model reading titles and
is recorded with the sample, so anyone can re-judge it.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402  (sits next to this file)
ROOT = os.path.dirname(HERE)
GAPMAP = os.path.join(ROOT, "gapmap")
NODES = os.path.join(GAPMAP, "nodes")
LEDGER = paths.data("ledger", "claims.json")
UA = {"User-Agent": "elipsis-gapmap/0.1"}
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
CTGOV = "https://clinicaltrials.gov/api/v2/studies?"
ACTIVE = "RECRUITING|ACTIVE_NOT_RECRUITING|NOT_YET_RECRUITING|ENROLLING_BY_INVITATION"
WINDOW_DAYS = 90


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def epmc(query, size=20, sort="FIRST_PDATE_D desc"):
    p = {"query": query, "format": "json", "pageSize": size, "resultType": "lite"}
    if sort:
        p["sort"] = sort
    r = _get(EPMC + urllib.parse.urlencode(p))
    return r["hitCount"], r["resultList"]["result"]


def ctgov(params):
    return _get(CTGOV + urllib.parse.urlencode(params))


def load_nodes():
    out = []
    for name in sorted(os.listdir(NODES)):
        if name.endswith(".json"):
            with open(os.path.join(NODES, name), encoding="utf-8") as f:
                out.append(json.load(f))
    return out


def save_node(n):
    path = os.path.join(NODES, n["slug"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(n, f, ensure_ascii=False, indent=1)
        f.write("\n")


def find_node(slug):
    for n in load_nodes():
        if n["slug"] == slug:
            return n
    sys.exit(f"No node '{slug}'. Nodes: " + ", ".join(x["slug"] for x in load_nodes()))


def load_ledger():
    if not os.path.exists(LEDGER):
        return {}
    with open(LEDGER, encoding="utf-8") as f:
        claims = json.load(f)["claims"]
    return {c["id"]: c for c in claims}


# -- refresh -----------------------------------------------------------------

def refresh_node(n, today):
    since = today - timedelta(days=WINDOW_DAYS)
    latest = {"refreshed": today.isoformat(), "window_days": WINDOW_DAYS}
    q = n["queries"].get("papers")
    if q:
        qq = f"({q['query']}) AND FIRST_PDATE:[{since.isoformat()} TO {today.isoformat()}] AND SRC:MED"
        hits, res = epmc(qq, size=5)
        prec = q.get("tests", {}).get("precision", {}).get("rate")
        latest["papers"] = {
            "count": hits,
            "estimated_on_topic": round(hits * prec) if prec is not None else None,
            "newest": [{"title": x.get("title", ""), "date": x.get("firstPublicationDate"),
                        "pmid": x.get("pmid"),
                        "url": f"https://europepmc.org/article/MED/{x.get('pmid')}" if x.get("pmid") else None}
                       for x in res],
        }
    t = n["queries"].get("trials")
    if t:
        active = ctgov({"query.term": t["query"], "filter.overallStatus": ACTIVE,
                        "filter.advanced": "AREA[StudyType]INTERVENTIONAL",
                        "countTotal": "true", "pageSize": 1})
        recent = ctgov({"query.term": t["query"],
                        "filter.advanced": f"AREA[StudyFirstPostDate]RANGE[{since.isoformat()},MAX] AND AREA[StudyType]INTERVENTIONAL",
                        "countTotal": "true", "pageSize": 5, "sort": "StudyFirstPostDate:desc",
                        "fields": "NCTId,BriefTitle,OverallStatus,StudyFirstPostDate"})
        latest["trials"] = {
            "active_interventional": active.get("totalCount"),
            "first_posted_in_window": recent.get("totalCount"),
            "newest": [{"title": s["protocolSection"]["identificationModule"]["briefTitle"],
                        "nct": s["protocolSection"]["identificationModule"]["nctId"],
                        "status": s["protocolSection"]["statusModule"].get("overallStatus"),
                        "date": s["protocolSection"]["statusModule"].get("studyFirstPostDateStruct", {}).get("date"),
                        "url": "https://clinicaltrials.gov/study/" + s["protocolSection"]["identificationModule"]["nctId"]}
                       for s in recent.get("studies", [])],
        }
    n["latest"] = latest
    return n


def refresh():
    today = date.today()
    for n in load_nodes():
        try:
            save_node(refresh_node(n, today))
            print(f"refreshed {n['slug']}")
        except Exception as e:  # one dead source should not stop the rest
            print(f"FAILED {n['slug']}: {type(e).__name__}: {e}")


# -- sample and recall (the query tests) --------------------------------------

def sample(slug, kind="papers"):
    n = find_node(slug)
    q = n["queries"].get(kind)
    if not q:
        sys.exit(f"{slug} has no {kind} query.")
    if kind == "papers":
        y = date.today().year
        hits, res = epmc(f"({q['query']}) AND (PUB_YEAR:[{y - 1} TO {y}]) AND SRC:MED")
        print(f"{hits} papers {y - 1}-{y}. Newest 20, judge each on topic or not:")
        for i, x in enumerate(res, 1):
            print(f"  {i:>2}. {x.get('title', '')}")
    else:
        r = ctgov({"query.term": q["query"], "filter.advanced": "AREA[StudyType]INTERVENTIONAL",
                   "countTotal": "true", "pageSize": 20, "sort": "StudyFirstPostDate:desc",
                   "fields": "NCTId,BriefTitle"})
        print(f"{r.get('totalCount')} interventional trials. Newest 20, judge each on topic or not:")
        for i, s in enumerate(r.get("studies", []), 1):
            m = s["protocolSection"]["identificationModule"]
            print(f"  {i:>2}. {m['nctId']}  {m['briefTitle']}")


def recall(slug):
    n = find_node(slug)
    q = n["queries"]["papers"]
    known = q.get("tests", {}).get("recall", {}).get("known", [])
    found = 0
    for k in known:
        c, _ = epmc(f"({q['query']}) AND EXT_ID:{k['pmid']} AND SRC:MED", size=1, sort="")
        found += 1 if c else 0
        print(f"  {'FOUND ' if c else 'missed'}  PMID {k['pmid']}  {k.get('title', '')}")
    print(f"recall {found} of {len(known)}")


# -- build (the plain files) --------------------------------------------------

def pct(p):
    return f"{round(p * 100)} in 100 ({100 - round(p * 100)} in 100 not)"


def forecast_rows(n, ledger):
    rows = []
    for fid in n.get("forecasts", []):
        fam = [c for c in ledger.values() if c["id"] == fid or c.get("revises") == fid]
        if not fam:
            rows.append({"id": fid, "missing": True})
            continue
        cur = max(fam, key=lambda c: (c.get("made", ""), c["id"]))
        res = cur.get("resolved")
        rows.append({"id": fid, "latest_id": cur["id"], "claim": cur["claim"],
                     "probability": cur["probability"], "baseline": cur["baseline"]["probability"],
                     "resolves": cur["resolves"],
                     "resolved": None if not res else ("unresolvable" if res.get("outcome") is None
                                                      else ("yes" if res["outcome"] else "no"))})
    return rows


def judged_items(slug):
    """Counts and odds-moving items from gapsources.py's store, if it exists."""
    path = os.path.join(GAPMAP, "items.db")
    if not os.path.exists(path):
        return None
    import sqlite3
    con = sqlite3.connect(path)
    since = (date.today() - timedelta(days=WINDOW_DAYS)).isoformat()
    row = con.execute("SELECT COUNT(*), COUNT(DISTINCT source), COUNT(DISTINCT lang), SUM(judged IS NOT NULL), "
                      "SUM(on_topic='on') FROM items WHERE node=? AND found>=?", (slug, since)).fetchone()
    if not row[0]:
        return None
    moved = con.execute("SELECT date, effect, title, url, note FROM items WHERE node=? AND effect IN ('up','down') "
                        "ORDER BY date DESC LIMIT 10", (slug,)).fetchall()
    return {"found": row[0], "sources": row[1], "langs": row[2], "judged": row[3] or 0, "on": row[4] or 0,
            "moved": moved}


def render_node(n, ledger):
    L = []
    gm = n["gap_map"]
    L.append(f"# {n['name']}")
    L.append("")
    L.append(f"Gap Map capability: [{gm['capability']}]({gm['url']}). Field: {gm.get('field') or 'not linked to a field in the Gap Map data'}.")
    L.append("")
    qn = n["question"]
    L.append("## The question")
    L.append(f"- **Problem:** {qn['problem']}")
    L.append(f"- **What is being tried:** {qn['tried']}")
    L.append(f"- **What counts as a result:** {qn['counts']}")
    L.append("")
    s = n["success_line"]
    L.append("## Success line (written before looking)")
    L.append(f"{s['text']}")
    L.append(f"- **Status on {s['checked']}:** {s['status']}")
    L.append("")
    b = n["base_rate"]
    L.append("## Base rate: what happened in similar cases")
    L.append(f"- **Count:** {b['s']} of {b['n']}, so {b['s'] / b['n']:.3f}. Rule of succession: ({b['s']} + 1) ÷ ({b['n']} + 2) = {(b['s'] + 1) / (b['n'] + 2):.3f}.")
    L.append(f"- **What was counted:** {b['what']}")
    L.append(f"- **Source:** [{b['source']}]({b['url']})")
    if b.get("caveat"):
        L.append(f"- **Caveat:** {b['caveat']}")
    L.append("")
    L.append("## Forecasts on the record (scored when they resolve)")
    rows = forecast_rows(n, ledger)
    if not rows:
        L.append("None yet.")
    for r in rows:
        if r.get("missing"):
            L.append(f"- `{r['id']}`: not found in the ledger.")
            continue
        state = f"resolved {r['resolved']}" if r["resolved"] else f"open, resolves {r['resolves']}"
        L.append(f"- `{r['latest_id']}`: {r['claim']} **{pct(r['probability'])}**, against a baseline of {pct(r['baseline'])}; {state}.")
    L.append("")
    L.append("## Searches, and how good they are")
    for kind, q in n["queries"].items():
        t = q.get("tests", {})
        L.append(f"### {kind.capitalize()} ({q['source']})")
        L.append(f"Query: `{q['query']}`")
        p = t.get("precision")
        if p:
            L.append(f"- **Precision** ({p['date']}, {p['basis']}): {p['on_topic']} of {p['sample']} on topic, so {p['rate']:.2f}. On topic means: {p['definition']}")
        rc = t.get("recall")
        if rc:
            L.append(f"- **Recall** ({rc['date']}): {rc['found']} of {len(rc['known'])} known papers found.")
            for k in rc["known"]:
                L.append(f"  - {'found' if k['found'] else 'missed'}: {k['title']} (PMID {k['pmid']})")
        for v in t.get("versions_tried", []):
            L.append(f"- Tried and dropped: {v}")
        L.append("")
    lt = n.get("latest")
    L.append("## Latest (refreshed by `harness/gapmap.py refresh`)")
    if not lt:
        L.append("Not refreshed yet.")
    else:
        L.append(f"Refreshed {lt['refreshed']}, window: the last {lt['window_days']} days.")
        if "papers" in lt:
            pp = lt["papers"]
            est = f", about {pp['estimated_on_topic']} on topic after precision" if pp.get("estimated_on_topic") is not None else ""
            L.append(f"- **Papers in the window:** {pp['count']}{est}. Newest:")
            for x in pp["newest"]:
                L.append(f"  - {x['date']}: [{x['title']}]({x['url']})")
        if "trials" in lt:
            tt = lt["trials"]
            L.append(f"- **Trials:** {tt['active_interventional']} interventional trials active or recruiting; {tt['first_posted_in_window']} first posted in the window. Newest:")
            for x in tt["newest"]:
                L.append(f"  - {x['date']}: [{x['title']}]({x['url']}) ({x['status']})")
    L.append("")
    jd = judged_items(n["slug"])
    if jd:
        L.append("## What the reading found (all sources, judged item by item)")
        L.append(f"- In the last {WINDOW_DAYS} days: {jd['found']} items collected from {jd['sources']} sources "
                 f"in {jd['langs']} languages; {jd['judged']} read and judged, {jd['on']} on topic.")
        if jd["moved"]:
            L.append("- **Items that move the odds:**")
            for d, eff, title, url, note in jd["moved"]:
                L.append(f"  - {d} ({'raises' if eff == 'up' else 'lowers'} the odds): [{title}]({url}). {note}")
        else:
            L.append("- No judged item has moved the odds yet.")
        L.append("")
    if n.get("notes"):
        L.append("## Notes")
        for x in n["notes"]:
            L.append(f"- {x}")
        L.append("")
    L.append("---")
    L.append(f"Source of truth: [{n['slug']}.json]({n['slug']}.json). Gap Map data © Convergent Research, MIT licence.")
    return "\n".join(L) + "\n"


def build():
    ledger = load_ledger()
    nodes = load_nodes()
    for n in nodes:
        with open(os.path.join(NODES, n["slug"] + ".md"), "w", encoding="utf-8") as f:
            f.write(render_node(n, ledger))
    allj = {"generated": date.today().isoformat(),
            "about": "A scored gap map: Gap Map capabilities with a success line, tested searches, a counted base rate and ledger forecasts.",
            "source_of_gaps": "https://www.gap-map.org/ (Convergent Research, MIT licence)",
            "nodes": [dict(n, forecasts_status=forecast_rows(n, ledger)) for n in nodes]}
    with open(os.path.join(GAPMAP, "gapmap.json"), "w", encoding="utf-8") as f:
        json.dump(allj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    L = ["# Elipsis gap map", "",
         "A plain, scored layer on top of Convergent Research's [Gap Map](https://www.gap-map.org/). "
         "The Gap Map lists research bottlenecks and the capabilities that would fix them, but carries no numbers. "
         "Each node here adds a success line written before looking, searches tested for precision and recall, "
         "a base rate counted from what happened in similar cases, and forecasts that are scored when they resolve.", "",
         "Machine-readable: [gapmap.json](gapmap.json). Each node also has its own JSON and Markdown file in [nodes/](nodes/).", "",
         "The base rate is for the long-run success line; the forecast is a near-term question that gets scored within months.", "",
         "| Node | Success line | Base rate (similar cases) | Near-term forecast on the record | Papers, last 90 days | Refreshed |",
         "|---|---|---|---|---|---|"]
    for n in nodes:
        b = n["base_rate"]
        rows = [r for r in forecast_rows(n, ledger) if not r.get("missing")]
        fc = "; ".join((f"resolved {r['resolved']}" if r["resolved"] else f"{pct(r['probability'])}, resolves {r['resolves']}")
                       for r in rows) or "none"
        lt = n.get("latest", {})
        pp = lt.get("papers", {})
        papers = f"{pp.get('count')} (about {pp.get('estimated_on_topic')} on topic)" if pp else "not refreshed"
        br = f"{b['s']} of {b['n']}; rule of succession {(b['s'] + 1) / (b['n'] + 2):.2f}"
        L.append(f"| [{n['name']}](nodes/{n['slug']}.md) | {n['success_line']['short']} | {br} | {fc} | {papers} | {lt.get('refreshed', 'never')} |")
    L += ["", "## How a node is built", "",
          "1. **Success line first**, with a date, like a trial's registered main outcome.",
          "2. **Tested searches.** Precision: the share of the newest 20 results that are on topic, judged by title and recorded. "
          "Recall: the share of papers known to belong that the query finds. A raw count is not a signal.",
          "3. **A counted base rate**: s successes of n attempts from a named source, and the rule of succession (s + 1) ÷ (n + 2), which keeps a small count from claiming 0 or 100.",
          "4. **A ledger forecast** that resolves within months, logged blind before any market price is seen, and scored when it resolves.", "",
          "Refresh with `python harness/gapmap.py refresh` and rebuild with `python harness/gapmap.py build`.", ""]
    with open(os.path.join(GAPMAP, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"built {len(nodes)} nodes, README.md and gapmap.json")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "refresh":
        refresh()
    elif cmd == "build":
        build()
    elif cmd == "sample" and len(sys.argv) >= 3:
        sample(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "papers")
    elif cmd == "recall" and len(sys.argv) >= 3:
        recall(sys.argv[2])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
