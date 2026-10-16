#!/usr/bin/env python3
"""
gapsources.py -- every public source the gap map can read without a key,
across fields and languages, into one store of items to be judged.

A keyword search misses what it doesn't name, and a paper index misses
news, money and regulators. So each node has two kinds of search:

  topic    its subject, in several languages
  watches  the named things that decide its odds: programmes, trials,
           regulators, funders

and runs them against every source that fits. Items land in
gapmap/items.db unjudged. A model (the scheduled job, or a person) then
reads each one and records whether it is on topic and whether it moves the
node's odds up or down, and why. Keyword matching finds candidates; the
reading decides.

Sources (all keyless):
  europepmc   papers and preprints, life sciences, includes PubMed
  openalex    papers in every field and language (engineering, computing,
              energy, social science); filters by language
  arxiv       preprints, physics, computing, engineering, quantitative biology
  ctgov       ClinicalTrials.gov registrations
  gnews       Google News, per language and region, with date windows
  fedreg      the US Federal Register: FDA, DOE, EPA and every other agency
  nih         NIH RePORTER grants
  nsf         NSF awards (engineering, computing, physical and social science)
  osti        DOE OSTI reports (energy, engineering)
  jstage      J-STAGE, Japanese journals
Not usable from a script: CNKI and ChiCTR (no public access; they block
scripts, and their protections are not bypassed), GDELT (rate-limited from
this machine), Semantic Scholar (rate-limited without a key), WHO ICTRP
(web form only).

Run:  python harness/gapsources.py collect [<slug>] [--since YYYY-MM-DD] [--until YYYY-MM-DD]
      python harness/gapsources.py queue <slug> [n] [--json]  -- unjudged items to read
      python harness/gapsources.py judge <item_id> on|off up|down|none "why"
      python harness/gapsources.py judge-file <file.json>    -- many at once (optional "strength": strong|context; see judge_file):
                                                  [{"id": 12, "on": "on", "effect": "up", "note": "why"}]
      python harness/gapsources.py counts                -- items by node and source
"""

import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
GAPMAP = os.path.join(os.path.dirname(HERE), "gapmap")
NODES = os.path.join(GAPMAP, "nodes")
DB = os.path.join(GAPMAP, "items.db")
UA = {"User-Agent": "elipsis-gapmap/0.1"}
GNEWS_LOCALES = {"en": ("en-US", "US", "US:en"), "zh": ("zh-CN", "CN", "CN:zh-Hans"),
                 "ja": ("ja", "JP", "JP:ja"), "de": ("de", "DE", "DE:de"), "fr": ("fr", "FR", "FR:fr"),
                 "es": ("es-419", "MX", "MX:es-419"), "ko": ("ko", "KR", "KR:ko"),
                 "ru": ("ru", "RU", "RU:ru"), "pt": ("pt-BR", "BR", "BR:pt-419")}


def _get(url, data=None, headers=None, raw=False):
    h = dict(UA)
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=40) as r:
        b = r.read()
    return b if raw else json.loads(b)


def q(s):
    return urllib.parse.quote(s)


# -- one function per source: (terms, since, until, lang) -> [item] ----------
# An item: {source, kind, date, title, url, lang, ext_id}

def s_europepmc(terms, since, until, lang):
    qq = f"({terms}) AND FIRST_PDATE:[{since} TO {until}]"
    r = _get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
        {"query": qq, "format": "json", "pageSize": 100, "sort": "FIRST_PDATE_D desc", "resultType": "lite"}))
    return [{"kind": "paper" if x.get("source") != "PPR" else "preprint", "date": x.get("firstPublicationDate"),
             "title": x.get("title", ""), "lang": "en" if x.get("language", "eng") == "eng" else x.get("language"),
             "url": f"https://europepmc.org/article/{x.get('source')}/{x.get('id')}",
             "ext_id": f"{x.get('source')}:{x.get('id')}"} for x in r["resultList"]["result"]]


def s_openalex(terms, since, until, lang):
    f = f"from_publication_date:{since},to_publication_date:{until}"
    if lang and lang != "en":
        f += f",language:{lang}"
    # The free-text search= matches almost anything for long OR strings;
    # the title-and-abstract filter is much tighter.
    f += f",title_and_abstract.search:{terms.replace(',', ' ')}"
    # Articles only: otherwise self-published repository compilations and
    # essays come through.
    f += ",type:article,primary_location.source.type:journal"
    r = _get(f"https://api.openalex.org/works?filter={q(f)}&per-page=100&sort=publication_date:desc")
    return [{"kind": "paper", "date": x.get("publication_date"), "title": x.get("title") or "",
             "lang": x.get("language"), "url": x.get("doi") or x.get("id"),
             "ext_id": x.get("id")} for x in r["results"]]


def s_arxiv(terms, since, until, lang):
    d1, d2 = since.replace("-", "") + "0000", until.replace("-", "") + "2359"
    url = ("http://export.arxiv.org/api/query?max_results=100&sortBy=submittedDate&sortOrder=descending"
           f"&search_query={q(f'all:({terms}) AND submittedDate:[{d1} TO {d2}]')}")
    root = ET.fromstring(_get(url, raw=True))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    return [{"kind": "preprint", "date": (e.findtext("a:published", "", ns) or "")[:10],
             "title": " ".join((e.findtext("a:title", "", ns) or "").split()), "lang": "en",
             "url": e.findtext("a:id", "", ns), "ext_id": e.findtext("a:id", "", ns)}
            for e in root.findall("a:entry", ns)]


def s_ctgov(terms, since, until, lang):
    r = _get("https://clinicaltrials.gov/api/v2/studies?" + urllib.parse.urlencode(
        {"query.term": terms, "pageSize": 100, "sort": "StudyFirstPostDate:desc",
         "filter.advanced": f"AREA[StudyFirstPostDate]RANGE[{since},{until}]",
         "fields": "NCTId,BriefTitle,StudyFirstPostDate,OverallStatus"}))
    out = []
    for s in r.get("studies", []):
        ps = s["protocolSection"]
        nct = ps["identificationModule"]["nctId"]
        out.append({"kind": "trial", "date": ps["statusModule"].get("studyFirstPostDateStruct", {}).get("date"),
                    "title": ps["identificationModule"]["briefTitle"], "lang": "en",
                    "url": "https://clinicaltrials.gov/study/" + nct, "ext_id": nct})
    return out


def s_gnews(terms, since, until, lang):
    hl, gl, ceid = GNEWS_LOCALES.get(lang or "en", GNEWS_LOCALES["en"])
    # Google's before: is exclusive, so add a day to keep the until date in.
    before = (date.fromisoformat(until) + timedelta(days=1)).isoformat()
    url = (f"https://news.google.com/rss/search?q={q(terms + f' after:{since} before:{before}')}"
           f"&hl={hl}&gl={gl}&ceid={ceid}")
    root = ET.fromstring(_get(url, raw=True))
    out = []
    for it in root.iter("item"):
        pub = it.findtext("pubDate") or ""
        try:
            d = time.strftime("%Y-%m-%d", time.strptime(pub[5:16], "%d %b %Y"))
        except ValueError:
            d = None
        out.append({"kind": "news", "date": d, "title": it.findtext("title") or "", "lang": lang or "en",
                    "url": it.findtext("link"), "ext_id": it.findtext("guid") or it.findtext("link")})
    return out


def s_fedreg(terms, since, until, lang):
    r = _get("https://www.federalregister.gov/api/v1/documents.json?" + urllib.parse.urlencode(
        {"per_page": 100, "order": "newest", "conditions[term]": terms,
         "conditions[publication_date][gte]": since, "conditions[publication_date][lte]": until}))
    return [{"kind": "regulator", "date": x.get("publication_date"), "title": x.get("title", ""), "lang": "en",
             "url": x.get("html_url"), "ext_id": x.get("document_number")} for x in r.get("results", [])]


def s_nih(terms, since, until, lang):
    body = {"criteria": {"advanced_text_search": {"operator": "advanced", "search_field": "projecttitle,abstracttext",
                                                  "search_text": terms},
                         "award_notice_date": {"from_date": since, "to_date": until}},
            "limit": 100, "sort_field": "award_notice_date", "sort_order": "desc"}
    r = _get("https://api.reporter.nih.gov/v2/projects/search", data=json.dumps(body).encode(),
             headers={"Content-Type": "application/json"})
    return [{"kind": "grant", "date": (x.get("award_notice_date") or "")[:10], "title": x.get("project_title", ""),
             "lang": "en", "url": f"https://reporter.nih.gov/project-details/{x.get('appl_id')}",
             "ext_id": str(x.get("appl_id"))} for x in r.get("results", [])]


def s_nsf(terms, since, until, lang):
    d1, d2 = (time.strftime("%m/%d/%Y", time.strptime(d, "%Y-%m-%d")) for d in (since, until))
    r = _get("https://api.nsf.gov/services/v1/awards.json?" + urllib.parse.urlencode(
        {"keyword": terms, "dateStart": d1, "dateEnd": d2, "printFields": "id,title,date"}))
    return [{"kind": "grant", "date": time.strftime("%Y-%m-%d", time.strptime(x["date"], "%m/%d/%Y")) if x.get("date") else None,
             "title": x.get("title", ""), "lang": "en",
             "url": f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={x.get('id')}", "ext_id": x.get("id")}
            for x in r.get("response", {}).get("award", [])]


def s_osti(terms, since, until, lang):
    r = _get(f"https://www.osti.gov/api/v1/records?rows=100&q={q(terms)}"
             f"&publication_date_start={q(time.strftime('%m/%d/%Y', time.strptime(since, '%Y-%m-%d')))}"
             f"&publication_date_end={q(time.strftime('%m/%d/%Y', time.strptime(until, '%Y-%m-%d')))}",
             headers={"Accept": "application/json"})
    return [{"kind": "report", "date": (x.get("publication_date") or "")[:10], "title": x.get("title", ""),
             "lang": "en", "url": x.get("links", [{}])[0].get("href") if x.get("links") else None,
             "ext_id": str(x.get("osti_id"))} for x in r]


def s_jstage(terms, since, until, lang):
    url = (f"https://api.jstage.jst.go.jp/searchapi/do?service=3&count=100&text={q(terms)}"
           f"&pubyearfrom={since[:4]}&pubyearto={until[:4]}")
    root = ET.fromstring(_get(url, raw=True))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in root.findall("a:entry", ns):
        t = e.find("a:article_title/a:ja", ns)
        t = t if t is not None and (t.text or "").strip() else e.find("a:article_title/a:en", ns)
        link = e.find("a:article_link/a:ja", ns)
        out.append({"kind": "paper", "date": e.findtext("a:pubyear", "", ns), "title": (t.text if t is not None else "") or "",
                    "lang": "ja", "url": link.text if link is not None else None, "ext_id": e.findtext("a:id", "", ns)})
    return out


SOURCES = {"europepmc": s_europepmc, "openalex": s_openalex, "arxiv": s_arxiv, "ctgov": s_ctgov,
           "gnews": s_gnews, "fedreg": s_fedreg, "nih": s_nih, "nsf": s_nsf, "osti": s_osti, "jstage": s_jstage}


# -- store --------------------------------------------------------------------

def db():
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY, node TEXT, source TEXT, kind TEXT, date TEXT, title TEXT,
        url TEXT, lang TEXT, ext_id TEXT, search TEXT, found TEXT,
        on_topic TEXT, effect TEXT, note TEXT, judged TEXT,
        UNIQUE(node, source, ext_id));
    CREATE TABLE IF NOT EXISTS runs (node TEXT, source TEXT, search TEXT, since TEXT, until TEXT,
        status TEXT, n INTEGER, at TEXT);
    """)
    if "strength" not in [r[1] for r in con.execute("PRAGMA table_info(items)")]:
        con.execute("ALTER TABLE items ADD COLUMN strength TEXT")   # strong | context; null = not graded
    return con


def load_nodes():
    out = []
    for name in sorted(os.listdir(NODES)):
        if name.endswith(".json"):
            with open(os.path.join(NODES, name), encoding="utf-8") as f:
                out.append(json.load(f))
    return out


def searches(node):
    """Every (label, source, terms, lang) a node asks for. A search may give
    "terms_by_source": {"nih": {"en": ...}} where one source needs its own
    syntax or a stricter query (for example when NIH returns unrelated grants
    for the plain topic words)."""
    for s in node.get("searches", []):
        for src in s["sources"]:
            for lang, terms in s.get("terms_by_source", {}).get(src, s["terms"]).items():
                # OpenAlex matches unrelated works for non-English terms,
                # so other languages go to news and J-STAGE only.
                if lang == "en" or src == "gnews" or (src == "jstage" and lang == "ja"):
                    # A node's precision-tested papers query beats a looser topic string.
                    if src == "europepmc" and s.get("kind") == "topic" and node.get("queries", {}).get("papers"):
                        terms = node["queries"]["papers"]["query"]
                    yield s["label"], src, terms, lang


def collect(slug=None, since=None, until=None, quiet=False):
    until = until or date.today().isoformat()
    since = since or (date.fromisoformat(until) - timedelta(days=7)).isoformat()
    con = db()
    total = 0
    for node in load_nodes():
        if slug and node["slug"] != slug:
            continue
        for label, src, terms, lang in searches(node):
            if src == "jstage" and lang != "ja":
                continue
            try:
                items = SOURCES[src](terms, since, until, lang)
                status = "ok"
            except Exception as e:
                items, status = [], f"{type(e).__name__}: {str(e)[:60]}"
            new = 0
            for it in items:
                cur = con.execute("INSERT OR IGNORE INTO items (node, source, kind, date, title, url, lang, ext_id, search, found) "
                                  "VALUES (?,?,?,?,?,?,?,?,?,date('now'))",
                                  (node["slug"], src, it["kind"], it["date"], it["title"], it["url"],
                                   it["lang"], it["ext_id"], f"{label} [{lang}]"))
                new += cur.rowcount
            con.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,datetime('now'))",
                        (node["slug"], src, f"{label} [{lang}]", since, until, status, len(items)))
            total += new
            if not quiet:
                print(f"{node['slug'][:24]:<25}{src:<10}{lang:<3} {label[:34]:<35} {status:<6} {len(items):>3} found, {new:>3} new")
            time.sleep(0.4)
    con.commit()
    return total


GRADING = ("when judging, give every on-topic item \"strength\": strong (a regulator, trial or standards step, "
           "or a new measure checked against outcomes) or context (on topic, background only). Never drop an on-topic item.")


def queue(slug, n=30, as_json=False):
    con = db()
    rows = con.execute("SELECT id, date, source, kind, lang, title, url, search FROM items WHERE node=? AND judged IS NULL "
                       "ORDER BY date DESC LIMIT ?", (slug, n)).fetchall()
    if as_json:
        print(json.dumps([dict(zip(("id", "date", "source", "kind", "lang", "title", "url", "search"), r))
                          for r in rows], ensure_ascii=False, indent=1))
        return
    print("GRADING: " + GRADING)
    for row in rows:
        print(f"[{row[0]}] {row[1]} {row[2]}/{row[3]} ({row[4]}) {row[5]}\n      {row[6]}")


def judge(item_id, on, effect, note):
    if on not in ("on", "off") or effect not in ("up", "down", "none"):
        sys.exit("judge takes on|off and up|down|none")
    con = db()
    con.execute("UPDATE items SET on_topic=?, effect=?, note=?, judged=date('now') WHERE id=?",
                (on, effect, note, item_id))
    con.commit()


def judge_file(path):
    """Apply many judgements at once: a JSON list of {id, on, effect, note}."""
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    bad = [r for r in rows if r.get("on") not in ("on", "off") or r.get("effect") not in ("up", "down", "none")]
    if bad:
        sys.exit(f"{len(bad)} entries need on|off and up|down|none, e.g. {bad[0]}")
    con = db()
    # "strength" (optional): strong = reports a regulator, trial or standards step, or a new measure checked
    # against outcomes; context = on topic but only background (kept, never dropped, shown after strong).
    con.executemany("UPDATE items SET on_topic=?, effect=?, note=?, strength=?, judged=date('now') WHERE id=?",
                    [(r["on"], r["effect"], r.get("note", ""), r.get("strength"), r["id"]) for r in rows])
    con.commit()
    print(f"{len(rows)} judgements recorded")


def counts():
    con = db()
    for row in con.execute("SELECT node, source, COUNT(*), SUM(judged IS NOT NULL), SUM(on_topic='on') "
                           "FROM items GROUP BY node, source ORDER BY node, source"):
        print(f"{row[0][:30]:<31}{row[1]:<10}{row[2]:>6} items  {row[3] or 0:>5} judged  {row[4] or 0:>5} on topic")


def main():
    a = sys.argv[1:]
    def opt(k):
        return a[a.index(k) + 1] if k in a else None
    if not a:
        print(__doc__)
    elif a[0] == "collect":
        slug = a[1] if len(a) > 1 and not a[1].startswith("--") else None
        print(collect(slug, opt("--since"), opt("--until")), "new items")
    elif a[0] == "queue" and len(a) > 1:
        n = int(a[2]) if len(a) > 2 and a[2].isdigit() else 30
        queue(a[1], n, "--json" in a)
    elif a[0] == "judge" and len(a) > 4:
        judge(int(a[1]), a[2], a[3], a[4])
    elif a[0] == "judge-file" and len(a) > 1:
        judge_file(a[1])
    elif a[0] == "counts":
        counts()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
