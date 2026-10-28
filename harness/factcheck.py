"""Has this claim already been fact-checked?

Searches published fact checks (PolitiFact, AFP, Full Fact, Snopes and the
other outlets that mark up their articles with schema.org ClaimReview) for a
claim, so a check can start from what professional fact-checkers already
found instead of from nothing.

Two sources, no key needed for the first:
  1. A local copy of Google's public ClaimReview feed, published by Data
     Commons and refreshed daily (one JSON file, about 200 MB). `fetch`
     downloads it and builds a full-text index (SQLite FTS5, standard
     library); the JSON is deleted afterwards. The copy is refreshed when it
     is more than a week old.
  2. Google's Fact Check Tools API, live, only when GOOGLE_FACTCHECK_KEY is
     set. Nothing but the search words is sent.

A lookup, not a calculation: it reports what others concluded and when.
Their verdicts use their own scales ("False", "Pants on Fire", "Missing
context"), quoted as written.

    python harness/factcheck.py fetch [--force]
    python harness/factcheck.py search "nord stream still working"
    python harness/factcheck.py build FILE.json     (index a local copy)
"""
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402

FEED = "https://storage.googleapis.com/datacommons-feeds/claimreview/latest/data.json"
API = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
DB = paths.data("factchecks.db")
MAX_AGE_DAYS = 7
UA = {"User-Agent": "elipsis-factcheck/1.0"}

STOP = set("""a an and are as at be been but by did do does for from had has have he her his
how i if in into is it its me my no not of on or our she so than that the their them then
there these they this to was we were what when where which who why will with you your""".split())


# ------------------------------------------------------------- the feed ---

def _items(fh, chunk=1 << 20):
    """Yield each element of the feed's dataFeedElement array, reading the
    file a chunk at a time so a 200 MB feed never sits in memory whole. A
    truncated last element is dropped silently."""
    dec = json.JSONDecoder()
    buf = fh.read(chunk)
    start = buf.find('"dataFeedElement"')
    if start < 0:
        raise ValueError("not a ClaimReview DataFeed: no dataFeedElement")
    i = buf.index("[", start) + 1
    while True:
        while True:
            while i < len(buf) and buf[i] in " \t\r\n,":
                i += 1
            if i < len(buf):
                break
            more = fh.read(chunk)
            if not more:
                return
            buf, i = buf[i:] + more, 0
        if buf[i] == "]":
            return
        while True:
            try:
                obj, j = dec.raw_decode(buf, i)
                break
            except json.JSONDecodeError:
                more = fh.read(chunk)
                if not more:
                    return
                buf, i = buf[i:] + more, 0
        yield obj
        i = j
        if i > chunk:
            buf, i = buf[i:], 0


def _name(x):
    if isinstance(x, list):
        x = x[0] if x else {}
    return (x or {}).get("name", "") if isinstance(x, dict) else str(x or "")


def _rows(element):
    """One row per ClaimReview inside a feed element."""
    page = element.get("url", "")
    for r in element.get("item") or []:
        if not isinstance(r, dict) or not r.get("claimReviewed"):
            continue
        rated = r.get("reviewRating") or {}
        if isinstance(rated, list):
            rated = rated[0] if rated else {}
        claim = r.get("itemReviewed") or {}
        if isinstance(claim, list):
            claim = claim[0] if claim else {}
        yield (r["claimReviewed"].strip(),
               _name(claim.get("author")),
               _name(r.get("author")),
               str(rated.get("alternateName") or rated.get("ratingValue") or ""),
               str(rated.get("ratingExplanation") or "")[:400],
               str(r.get("datePublished") or "")[:10],
               page or str(r.get("url") or ""))


def build(src, db=DB):
    """Index a downloaded feed file into a fresh SQLite full-text table."""
    tmp = db + ".new"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    con.execute("CREATE VIRTUAL TABLE fc USING fts5(claim, claimant, publisher, rating, "
                "explanation UNINDEXED, reviewed UNINDEXED, url UNINDEXED, "
                "tokenize='unicode61 remove_diacritics 2')")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    n, batch = 0, []
    with open(src, encoding="utf-8") as fh:
        for el in _items(fh):
            for row in _rows(el):
                batch.append(row)
            if len(batch) >= 5000:
                con.executemany("INSERT INTO fc VALUES (?,?,?,?,?,?,?)", batch)
                n += len(batch)
                batch = []
    con.executemany("INSERT INTO fc VALUES (?,?,?,?,?,?,?)", batch)
    n += len(batch)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    con.executemany("INSERT INTO meta VALUES (?,?)",
                    [("built", stamp), ("reviews", str(n)), ("source", FEED)])
    con.commit()
    con.execute("INSERT INTO fc(fc) VALUES ('optimize')")
    con.commit()
    con.close()
    os.replace(tmp, db)
    return n


def _meta(db=DB):
    if not os.path.exists(db):
        return {}
    con = sqlite3.connect(db)
    try:
        return dict(con.execute("SELECT key, value FROM meta"))
    except sqlite3.Error:
        return {}
    finally:
        con.close()


def fetch(force=False, db=DB):
    """Download the feed and rebuild the index, unless the copy is under a week old."""
    if not force and os.path.exists(db) and \
            time.time() - os.path.getmtime(db) < MAX_AGE_DAYS * 86400:
        m = _meta(db)
        return "up to date: %s reviews, built %s" % (m.get("reviews", "?"), m.get("built", "?"))
    part = db + ".feed.part"
    with urllib.request.urlopen(urllib.request.Request(FEED, headers=UA), timeout=120) as r, \
            open(part, "wb") as out:
        while True:
            block = r.read(1 << 20)
            if not block:
                break
            out.write(block)
    try:
        n = build(part, db)
    finally:
        os.remove(part)
    return "built: %d reviews" % n


# ------------------------------------------------------------- searching ---

def _words(query):
    w = [t for t in re.findall(r"\w+", query.lower()) if t not in STOP and len(t) > 1]
    return w or re.findall(r"\w+", query.lower())


def search_local(query, limit=10, db=DB):
    """Every word first; if that finds too little, any word, best matches first."""
    words = _words(query)
    if not words or not os.path.exists(db):
        return []
    con = sqlite3.connect(db)
    try:
        seen, out = set(), []
        for joiner in (" ", " OR "):
            q = joiner.join('"%s"' % w.replace('"', "") for w in words)
            for row in con.execute(
                    "SELECT claim, claimant, publisher, rating, explanation, reviewed, url "
                    "FROM fc WHERE fc MATCH ? ORDER BY bm25(fc, 4.0, 1.0, 0.5, 0.2) LIMIT ?",
                    (q, limit)):
                if row[6] + row[0] not in seen:
                    seen.add(row[6] + row[0])
                    out.append(row)
            if len(out) >= limit or len(words) == 1:
                break
        return out[:limit]
    finally:
        con.close()


def search_api(query, limit=10, key=None):
    """Google's live API. Only the search words and the key are sent."""
    key = key or os.environ.get("GOOGLE_FACTCHECK_KEY")
    if not key:
        return []
    url = API + "?" + urllib.parse.urlencode({"query": query, "pageSize": limit, "key": key})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        data = json.load(r)
    out = []
    for c in data.get("claims", []):
        for rv in c.get("claimReview", [])[:1]:
            out.append((c.get("text", ""), c.get("claimant", ""),
                        (rv.get("publisher") or {}).get("name", ""),
                        rv.get("textualRating", ""), "",
                        (rv.get("reviewDate") or "")[:10], rv.get("url", "")))
    return out


def report(query, limit=10, db=DB):
    query = (query or "").strip()
    if not query:
        raise ValueError("give `query`: the claim, or its key words")
    limit = max(1, min(int(limit or 10), 30))
    m = _meta(db)
    rows = search_local(query, limit, db)
    live = []
    try:
        live = search_api(query, limit)
    except Exception as e:  # the live API is optional; say it failed, keep the local result
        live_err = str(e)
    else:
        live_err = ""
    lines = ["FACT-CHECK LOOKUP: has this claim already been checked?",
             "This is a lookup, not a calculation: it reports what published fact checks "
             "concluded, on their own rating scales, quoted as written.", "",
             "Searched for: %s (words used: %s)" % (query, ", ".join(_words(query)))]
    if m:
        lines.append("Local copy: %s published fact checks, built %s from Google's public "
                     "ClaimReview feed (Data Commons)." % (m.get("reviews", "?"), m.get("built", "?")))
    else:
        lines.append("No local copy yet. Build it once with: python harness/factcheck.py fetch "
                     "(downloads about 200 MB, keeps an index).")
    if os.environ.get("GOOGLE_FACTCHECK_KEY"):
        lines.append("Live Google API: %s." % ("failed, " + live_err if live_err
                                               else "%d result(s)" % len(live)))
    seen, merged = set(), []
    for r in live + rows:
        k = r[6] or r[0]
        if k not in seen:
            seen.add(k)
            merged.append(r)
    merged = merged[:limit]
    lines += ["", "Found %d matching fact check(s)%s." % (
        len(merged), ", listed below" if merged else "")]
    for i, (claim, who, pub, rating, why, when, url) in enumerate(merged, 1):
        lines.append("")
        lines.append("%d. %s, %s: rated \"%s\"" % (i, pub or "unknown outlet", when or "no date",
                                                    rating or "no rating given"))
        lines.append("   Claim checked: %s" % (claim[:300] + ("..." if len(claim) > 300 else "")))
        if who:
            lines.append("   Said by: %s" % who)
        if why:
            lines.append("   Their reason: %s" % why[:300])
        lines.append("   %s" % url)
    lines += ["", "HOW TO USE THIS: a match is a lead, not a verdict. Check that the claim "
              "checked is the same claim (same numbers, same place, same date) before "
              "citing it, and read the article: a rating like \"Missing context\" can mean "
              "the facts are right. No match means no indexed fact check, not that the "
              "claim is true."]
    return "\n".join(lines)


def main(argv):
    if len(argv) >= 2 and argv[1] == "fetch":
        print(fetch(force="--force" in argv))
    elif len(argv) >= 3 and argv[1] == "build":
        print("built: %d reviews" % build(argv[2]))
    elif len(argv) >= 3 and argv[1] == "search":
        print(report(" ".join(argv[2:])))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
