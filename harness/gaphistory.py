#!/usr/bin/env python3
"""
gaphistory.py -- the history database: past attempts and how they ended.

Base rates need a record of earlier "runs": what was tried, when, and
whether it worked. Medicine is the one field where that record already
exists in public, so it comes first:

  trials     every study registered on ClinicalTrials.gov (about 600,000,
             2000 onward): phase, conditions, interventions, sponsor, and
             how it ended (completed, terminated, withdrawn) and why
  approvals  every FDA drug application with an approval (Drugs@FDA via
             openFDA, back to the 1930s): ingredient, brand, date

Joining the two gives the question the gap map keeps asking: of earlier
attempts like this one, how many finished, and how many led to an
approved drug? Other fields have no registry like this; for them the
plan is resolved forecasting questions (Manifold, Polymarket), grants with
end dates (NIH, NSF, DOE), and archived pages (the Wayback Machine).

Run:  python harness/gaphistory.py fetch-trials    -- resumable; about 20 to
                                                      40 minutes for all of it
      python harness/gaphistory.py fetch-approvals  -- one download from openFDA
      python harness/gaphistory.py status           -- what is in the database
      python harness/gaphistory.py rates "<condition words>" [--drug "<names>"]
                                                    -- how earlier trials ended,
                                                       by phase
      python harness/gaphistory.py markets "<words>"  -- resolved Manifold questions
                                                       (any field) and their share yes
      python harness/gaphistory.py wayback <url>     -- one archived copy per year

Stored in gapmap/history.db (SQLite, standard library only).
"""

import io
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(HERE), "gapmap", "history.db")
UA = {"User-Agent": "elipsis-gapmap/0.1"}
CT_FIELDS = ("NCTId,BriefTitle,Phase,StudyType,OverallStatus,WhyStopped,StartDate,"
             "PrimaryCompletionDate,StudyFirstPostDate,HasResults,LeadSponsorName,"
             "LeadSponsorClass,Condition,InterventionName,InterventionType,EnrollmentCount")
ENDED = ("COMPLETED", "TERMINATED", "WITHDRAWN", "SUSPENDED")


def db():
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS trials (
        nct TEXT PRIMARY KEY, title TEXT, phase TEXT, study_type TEXT, status TEXT,
        why_stopped TEXT, start TEXT, primary_completion TEXT, first_posted TEXT,
        has_results INTEGER, sponsor TEXT, sponsor_class TEXT, conditions TEXT,
        interventions TEXT, intervention_types TEXT, enrollment INTEGER);
    CREATE TABLE IF NOT EXISTS approvals (
        appl_no TEXT, sponsor TEXT, brand TEXT, ingredients TEXT,
        submission_type TEXT, status TEXT, date TEXT);
    CREATE INDEX IF NOT EXISTS ix_trials_status ON trials(status);
    CREATE INDEX IF NOT EXISTS ix_appr_ingr ON approvals(ingredients);
    """)
    return con


def _get(url, raw=False):
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                b = r.read()
            return b if raw else json.loads(b)
        except Exception:
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))


def fetch_trials():
    con = db()
    token = (con.execute("SELECT v FROM meta WHERE k='ct_token'").fetchone() or [None])[0]
    if token == "DONE":
        print("Trials already complete. Delete the ct_token row in meta to refetch.")
        return
    pages = 0
    while True:
        p = {"pageSize": 1000, "fields": CT_FIELDS, "format": "json"}
        if token:
            p["pageToken"] = token
        r = _get("https://clinicaltrials.gov/api/v2/studies?" + urllib.parse.urlencode(p))
        rows = []
        for s in r.get("studies", []):
            ps = s.get("protocolSection", {})
            idm, st, dm = ps.get("identificationModule", {}), ps.get("statusModule", {}), ps.get("designModule", {})
            sp = ps.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
            arms = ps.get("armsInterventionsModule", {}).get("interventions", [])
            rows.append((
                idm.get("nctId"), idm.get("briefTitle"), "|".join(dm.get("phases", []) or []),
                dm.get("studyType"), st.get("overallStatus"), st.get("whyStopped"),
                st.get("startDateStruct", {}).get("date"), st.get("primaryCompletionDateStruct", {}).get("date"),
                st.get("studyFirstPostDateStruct", {}).get("date"), 1 if s.get("hasResults") else 0,
                sp.get("name"), sp.get("class"),
                "|".join(ps.get("conditionsModule", {}).get("conditions", []) or []),
                "|".join(i.get("name", "") for i in arms), "|".join(i.get("type", "") for i in arms),
                (dm.get("enrollmentInfo") or {}).get("count")))
        con.executemany("INSERT OR REPLACE INTO trials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        token = r.get("nextPageToken")
        con.execute("INSERT OR REPLACE INTO meta VALUES ('ct_token', ?)", (token or "DONE",))
        con.commit()
        pages += 1
        if pages % 25 == 0:
            n = con.execute("SELECT COUNT(*) FROM trials").fetchone()[0]
            print(f"{n} trials stored", flush=True)
        if not token:
            break
    con.execute("INSERT OR REPLACE INTO meta VALUES ('ct_fetched', date('now'))")
    con.commit()
    print("Trials complete:", con.execute("SELECT COUNT(*) FROM trials").fetchone()[0])


def fetch_approvals():
    idx = _get("https://api.fda.gov/download.json")
    part = idx["results"]["drug"]["drugsfda"]["partitions"][0]["file"]
    z = zipfile.ZipFile(io.BytesIO(_get(part, raw=True)))
    data = json.load(z.open(z.namelist()[0]))
    con = db()
    con.execute("DELETE FROM approvals")
    rows = []
    for app in data["results"]:
        ingr = sorted({ai.get("name", "").upper() for p in app.get("products", [])
                       for ai in p.get("active_ingredients", []) if ai.get("name")})
        brands = sorted({p.get("brand_name", "") for p in app.get("products", []) if p.get("brand_name")})
        for sub in app.get("submissions", []):
            if sub.get("submission_status") == "AP":
                rows.append((app.get("application_number"), app.get("sponsor_name"), "|".join(brands),
                             "|".join(ingr), sub.get("submission_type"), sub.get("submission_status"),
                             sub.get("submission_status_date")))
    con.executemany("INSERT INTO approvals VALUES (?,?,?,?,?,?,?)", rows)
    con.execute("INSERT OR REPLACE INTO meta VALUES ('fda_fetched', date('now'))")
    con.commit()
    print(f"{len(rows)} approved submissions from {len(data['results'])} applications "
          f"(export {idx['results']['drug']['drugsfda'].get('export_date')})")


def status():
    con = db()
    for t in ("trials", "approvals"):
        print(t, con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
    for k, v in con.execute("SELECT k, v FROM meta"):
        print(" ", k, "=", v if len(str(v)) < 40 else str(v)[:40] + "...")


def rates(words, drugs=None):
    """How earlier interventional trials on these conditions ended, by phase."""
    import re
    con = db()
    # Whole words only: a plain LIKE '%ear%' also matches heart, year, research.
    pats = [re.compile(r"\b" + re.escape(w.strip().lower()) + r"\b") for w in words if w.strip()]
    con.create_function("wmatch", 1, lambda t: 1 if t and any(p.search(t.lower()) for p in pats) else 0)
    where = "AND (wmatch(conditions) OR wmatch(title))" if pats else ""
    sql = f"SELECT phase, status, why_stopped, interventions FROM trials WHERE study_type='INTERVENTIONAL' {where}"
    rows = con.execute(sql).fetchall()
    if drugs:
        rows = [r for r in rows if any(d.lower() in (r[3] or "").lower() for d in drugs)]
    print(f"{len(rows)} interventional trials match.")
    print(f"{'phase':<16}{'ended':>7}{'completed':>11}{'stopped early':>15}{'share stopped':>15}")
    by = {}
    for ph, stt, why, _ in rows:
        by.setdefault(ph or "none", []).append(stt)
    for ph in sorted(by):
        ended = [s for s in by[ph] if s in ENDED]
        if not ended:
            continue
        comp = sum(1 for s in ended if s == "COMPLETED")
        stop = len(ended) - comp
        print(f"{ph:<16}{len(ended):>7}{comp:>11}{stop:>15}{stop / len(ended):>15.2f}")
    return rows


def fetch_markets(term):
    """Resolved yes/no questions on Manifold matching the words: a record of
    past claims in every field (politics, technology, energy, science) and
    how they came out."""
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS markets (id TEXT PRIMARY KEY, question TEXT, created TEXT,
                   closed TEXT, resolution TEXT, last_p REAL, url TEXT, term TEXT)""")
    r = _get("https://api.manifold.markets/v0/search-markets?" + urllib.parse.urlencode(
        {"term": term, "filter": "resolved", "contractType": "BINARY", "limit": 1000}))
    rows = [(m["id"], m["question"], time.strftime("%Y-%m-%d", time.gmtime(m["createdTime"] / 1000)),
             time.strftime("%Y-%m-%d", time.gmtime((m.get("resolutionTime") or m.get("closeTime") or 0) / 1000)),
             m.get("resolution"), m.get("probability"), m.get("url"), term) for m in r]
    con.executemany("INSERT OR REPLACE INTO markets VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    yes = sum(1 for x in rows if x[4] == "YES")
    no = sum(1 for x in rows if x[4] == "NO")
    print(f"{len(rows)} resolved questions for '{term}': {yes} yes, {no} no, {len(rows) - yes - no} other "
          f"(cancelled or partial). Share yes among yes/no: {yes / max(yes + no, 1):.2f}")


def wayback(url):
    """One archived copy per year of a web page: what it said back then."""
    r = _get("http://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode(
        {"url": url, "output": "json", "fl": "timestamp,statuscode", "collapse": "timestamp:4",
         "filter": "statuscode:200"}))
    for ts, _ in r[1:]:
        print(f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}  https://web.archive.org/web/{ts}/{url}")
    print(f"{len(r) - 1} years with a saved copy")


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "fetch-trials":
        fetch_trials()
    elif a[0] == "fetch-approvals":
        fetch_approvals()
    elif a[0] == "status":
        status()
    elif a[0] == "markets" and len(a) > 1:
        fetch_markets(a[1])
    elif a[0] == "wayback" and len(a) > 1:
        wayback(a[1])
    elif a[0] == "rates" and len(a) > 1:
        drugs = a[a.index("--drug") + 1].split(",") if "--drug" in a else None
        rates(a[1].split(","), drugs)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
