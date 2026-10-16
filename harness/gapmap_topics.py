#!/usr/bin/env python3
"""
gapmap_topics.py -- tag every Gap Map capability (fix) with OpenAlex research
topics, and test the tags against the papers the Gap Map itself lists.

Why: hand-written searches don't scale to 369 fixes, and automatic keyword
searches tend to find either nothing or mostly junk. OpenAlex already files every new paper under one of
4,516 topics, so the daily sweep can take every new paper in the topics a fix
touches, and matching happens on top of that.

How (cheap on purpose: OpenAlex's free, keyless allowance is about 1,000
credits a day, shared by everything on this machine's IP address; a list query
costs 1 credit, a group_by 10, the /text classifier 100):
  1. Topics from the fix's name: list up to 50 works from the last five years
     whose title or abstract contains the fix's key phrase (falling back to its
     key words when the phrase is rare), reading only their topics, and keep
     the topics that recur.
  2. Topics from known papers: resolve the fix's listed resources that are
     papers (a DOI or arXiv link, or a research or whitepaper title found
     exactly) to OpenAlex works.
  3. Recall test: of a fix's known papers, how many share a topic with the
     name-derived tags? That says whether name tagging alone would have caught
     the papers the Gap Map's experts listed.
  4. Final tags = name topics plus known-paper topics.
Every call checks the allowance left; below the reserve (default 300, kept for
the daily sweep) it saves its cache and stops. Run it again later to resume.

Data: gapmap/convergent/gapmap-data.json (Gap Map export, MIT licence).
In the export every capability's own "gaps" list is empty; the links run from
gaps (foundationalCapabilities), so they are rebuilt from that side.

Run:  python harness/gapmap_topics.py tag [--reserve 300]   -- resumable
      python harness/gapmap_topics.py summary
      python harness/gapmap_topics.py volume [YYYY-MM-DD]   -- new articles that day in the tagged topics
Output: gapmap/convergent/capability_topics.json; cache gapmap/convergent/topic_cache.json
Never sends an email address or any personal data to the API.
"""

import collections
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONV = os.path.join(os.path.dirname(HERE), "gapmap", "convergent")
DATA = os.path.join(CONV, "gapmap-data.json")
OUT = os.path.join(CONV, "capability_topics.json")
CACHE = os.path.join(CONV, "topic_cache.json")
UA = {"User-Agent": "elipsis-gapmap/0.2"}
PAPER_TYPES = {"Research and Reviews", "Whitepapers and Essays"}
STOP = set("""a an and the of for in on to with by from at as or into via toward towards across using based new novel
better improved scalable large scale high low next generation general purpose open infrastructure platform platforms
tools tool system systems methods method approach approaches technology technologies capability capabilities data
dataset datasets database databases framework frameworks mapping maps map model models modeling modelling measurement
measurements leverage modern rapidly""".split())
RESERVE = 300


class BudgetLow(Exception):
    pass


def get(url, tries=3):
    """GET JSON; stop the run when the shared daily allowance runs low."""
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                left = r.headers.get("X-RateLimit-Remaining")
                body = json.loads(r.read())
            if left is not None and int(left) < RESERVE:
                raise BudgetLow(left)
            return body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429:
                raise BudgetLow("429")
            time.sleep(2 * (i + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 * (i + 1))
    return None


def load_cache():
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {"name": {}, "work": {}}


def save_cache(c):
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(c, f)


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def key_words(name):
    return [w for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]+", name) if w.lower() not in STOP]


def tid(t):
    return t["id"].rsplit("/", 1)[-1]


def topics_of(work):
    return [{"id": tid(t), "name": t["display_name"], "subfield": t["subfield"]["display_name"],
             "field": t["field"]["display_name"]} for t in (work.get("topics") or [])]


def name_topics(name, cache):
    """Topics that recur among recent works naming the fix's key phrase (1 to 2 credits)."""
    if name in cache["name"]:
        return cache["name"][name]
    kw = key_words(name)
    since = (datetime.date.today() - datetime.timedelta(days=5 * 365)).isoformat()
    tried = []
    works = []
    for mode, terms in (("phrase", '"' + " ".join(kw[:4]) + '"'), ("words", " ".join(kw[:5]))):
        if not kw:
            break
        f = f"title_and_abstract.search:{terms.replace(',', ' ')},from_publication_date:{since}"
        r = get("https://api.openalex.org/works?" + urllib.parse.urlencode(
            {"filter": f, "per-page": 50, "select": "id,topics"}))
        time.sleep(0.12)
        works = (r or {}).get("results", [])
        tried.append({"mode": mode, "terms": terms, "hits": (r or {}).get("meta", {}).get("count", 0)})
        if len(works) >= 10:
            break
    tally, info = collections.Counter(), {}
    for w in works:
        for t in topics_of(w):
            tally[t["id"]] += 1
            info[t["id"]] = t
    keep = [dict(info[k], count=n) for k, n in tally.most_common(4) if n >= max(3, 0.15 * len(works))]
    cache["name"][name] = {"tried": tried, "n_works": len(works), "topics": keep,
                           "phrases": [" ".join(kw[:4]).lower()] if kw else []}
    return cache["name"][name]


def resolve(res, cache):
    """A Gap Map resource -> OpenAlex work topics, or None (1 credit, cached)."""
    rid = res["id"]
    if rid in cache["work"]:
        return cache["work"][rid]
    url, title = res.get("url") or "", res.get("title") or ""
    types = res.get("types") or []
    if isinstance(types, str):
        types = re.findall(r"'([^']+)'", types)
    w, how = None, None
    m = re.search(r"(10\.\d{4,9}/[^\s?#]+)", url)
    a = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})", url)
    if m:
        doi = m.group(1).rstrip(".").removesuffix(".pdf")
        w, how = get("https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(doi, safe="/")), "doi"
    elif a:
        w, how = get("https://api.openalex.org/works/https://doi.org/10.48550/arxiv." + a.group(1)), "arxiv"
    elif set(types) & PAPER_TYPES and len(norm(title).split()) >= 4:
        r = get("https://api.openalex.org/works?" + urllib.parse.urlencode(
            {"search": title, "per-page": 3, "select": "id,title,topics"}))
        how = "title"
        for cand in (r or {}).get("results", []):
            if norm(cand.get("title")) == norm(title):
                w = cand
                break
    else:
        cache["work"][rid] = None
        return None
    time.sleep(0.12)
    cache["work"][rid] = ({"work": w["id"].rsplit("/", 1)[-1], "how": how, "title": w.get("title"),
                           "topics": topics_of(w)} if w and w.get("topics") else None)
    return cache["work"][rid]


def gap_links(D):
    cap_gaps, cap_fields = {}, {}
    for g in D["gaps"]:
        fld = g.get("field")
        if isinstance(fld, str):
            mm = re.search(r"'name': '([^']+)'", fld)
            fld = mm.group(1) if mm else fld
        elif isinstance(fld, dict):
            fld = fld.get("name")
        caps = g.get("foundationalCapabilities") or []
        if isinstance(caps, str):
            caps = re.findall(r"'([^']+)'", caps)
        for cid in caps:
            cap_gaps.setdefault(cid, []).append({"id": g["id"], "name": g["name"], "slug": g.get("slug")})
            if fld:
                cap_fields.setdefault(cid, set()).add(fld)
    return cap_gaps, cap_fields


def tag():
    with open(DATA, encoding="utf-8") as f:
        D = json.load(f)
    res_by_id = {r["id"]: r for r in D["resources"]}
    cap_gaps, cap_fields = gap_links(D)
    cache = load_cache()
    out, done = [], 0
    try:
        for c in D["capabilities"]:
            nt = name_topics(c["name"], cache)
            papers = [w for w in (resolve(res_by_id[r], cache) for r in (c.get("resources") or []) if r in res_by_id) if w]
            done += 1
            if done % 10 == 0:
                save_cache(cache)
    except BudgetLow as e:
        save_cache(cache)
        print(f"Stopped to keep the shared OpenAlex allowance (left: {e}); {done} of {len(D['capabilities'])} "
              f"fixes processed this run. Run again after midnight UTC to resume.")
    save_cache(cache)
    # Write whatever is complete so far.
    for c in D["capabilities"]:
        if c["name"] not in cache["name"]:
            continue
        rids = [r for r in (c.get("resources") or []) if r in res_by_id]
        if any(r not in cache["work"] for r in rids):
            continue
        nt = cache["name"][c["name"]]
        papers = [cache["work"][r] for r in rids if cache["work"][r]]
        name_ids = {t["id"] for t in nt["topics"]}
        hit = [p for p in papers if name_ids & {t["id"] for t in p["topics"]}]
        final = {t["id"]: {k: t[k] for k in ("id", "name", "subfield", "field")} for t in nt["topics"]}
        for p in papers:
            for t in p["topics"]:
                final.setdefault(t["id"], t)
        out.append({"id": c["id"], "name": c["name"], "slug": c.get("slug"),
                    "gaps": cap_gaps.get(c["id"], []), "fields": sorted(cap_fields.get(c["id"], [])),
                    "name_topics": nt["topics"], "name_search": nt["tried"], "phrases": nt["phrases"],
                    "known_papers": [{"work": p["work"], "how": p["how"], "title": p["title"]} for p in papers],
                    "recall": {"found": len(hit), "of": len(papers)}, "topics": list(final.values())})
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"source": "Gap Map export " + D["metadata"]["exportDate"], "made": time.strftime("%Y-%m-%d"),
                   "complete": len(out) == len(D["capabilities"]), "capabilities": out}, f, ensure_ascii=False, indent=1)
    summary(out, len(D["capabilities"]))


def summary(out, total=369):
    tested = [c for c in out if c["recall"]["of"]]
    found = sum(c["recall"]["found"] for c in tested)
    of = sum(c["recall"]["of"] for c in tested)
    any_hit = sum(1 for c in tested if c["recall"]["found"])
    all_topics = {t["id"] for c in out for t in c["topics"]}
    name_topics_ = {t["id"] for c in out for t in c["name_topics"]}
    print(f"\n{len(out)} of {total} fixes tagged; {sum(1 for c in out if c['name_topics'])} got topics from their name; "
          f"{sum(1 for c in out if not c['topics'])} have no topic at all; {sum(1 for c in out if c['gaps'])} linked to a gap")
    print(f"known papers resolved: {of} across {len(tested)} fixes")
    if of:
        print(f"recall of name tags against known papers: {found} of {of} papers ({100 * found / of:.0f} in 100); "
              f"fixes with at least one known paper caught: {any_hit} of {len(tested)}")
    print(f"distinct topics: from names {len(name_topics_)}, final {len(all_topics)} (of 4,516)")


def volume(day=None):
    """New articles published on one day in all tagged topics (OR in chunks of 50)."""
    day = day or (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
    with open(OUT, encoding="utf-8") as f:
        caps = json.load(f)["capabilities"]
    ids = sorted({t["id"] for c in caps for t in c["topics"]})
    total = 0
    for k in range(0, len(ids), 50):
        f = f"publication_date:{day},type:article,topics.id:{'|'.join(ids[k:k + 50])}"
        r = get("https://api.openalex.org/works?" + urllib.parse.urlencode({"filter": f, "per-page": 1}))
        total += (r or {}).get("meta", {}).get("count", 0)
        time.sleep(0.12)
    print(f"{day}: about {total} new articles in the {len(ids)} tagged topics (chunks may double-count a little)")
    return total


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--reserve" in a:
        RESERVE = int(a[a.index("--reserve") + 1])
    cmd = a[0] if a else "tag"
    if cmd == "tag":
        tag()
    elif cmd == "volume":
        volume(a[1] if len(a) > 1 and not a[1].startswith("--") else None)
    else:
        with open(OUT, encoding="utf-8") as f:
            d = json.load(f)
        summary(d["capabilities"])
