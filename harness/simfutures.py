#!/usr/bin/env python3
"""
simfutures.py -- simulate many futures from the histories of similar cases,
then count.

The method is copied from Epic's Curiosity model ("Generative Medical Event
Models Improve with Scale", arXiv 2508.12104, Epic, Microsoft Research and
Yale, 2025). Curiosity reads a patient's record as a sequence of events,
writes the next event, then the next, many times over, and answers any
question by the share of simulated futures in which the event happens. It
learns the next-event step with a large model trained on 118 million
patients. Here the step is drawn straight from counted histories of similar
cases, so every number traces back to named public records and nothing is
trained.

First use: drug development. A drug's history is the trial phases it
reached (ClinicalTrials.gov) and its first FDA approval (Drugs@FDA), both in
gapmap/history.db, built by gaphistory.py.

Stages:  1 = phase 1 or early phase 1;  2 = phase 2 or phase 1/2;
         3 = phase 3 or phase 2/3;      A = first FDA approval (the end).

One simulated future: start at a stage, with some years already spent
there. Draw one similar drug that also spent at least that long at that
stage, and copy what it did next and how long it took. If it moved on in
time, move on and draw again from the new stage. If its record simply runs
out (no next event yet), we only learn that nothing happened for that long,
so draw again from drugs that waited longer. Stop at the horizon.

Built-in check: the plain count of drugs that reached the same stage long
enough ago to see the whole horizon, and how many were approved inside it.
If simulation and plain count disagree a lot, trust neither.

Known misses: trials often name a drug by a code (MK-3475) and the FDA by
its generic name (pembrolizumab), so some approvals are not linked and the
approval share is too low. Drugs first approved before their first
registered trial are left out (they are old drugs being retested).

Run:  python harness/simfutures.py drugs "<condition words>" [--stage 3]
          [--years-in 0] [--horizon 10] [--drug NAME] [--sims 5000] [--seed 1]
          [--industry yes|no] [--since 2005]
"""

import os
import random
import re
import sqlite3
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(HERE), "gapmap", "history.db")
MIN_N = 30          # fewer similar histories than this at a stage: fall back to all drugs
NOT_DRUGS = ("PLACEBO", "SALINE", "STANDARD", "VEHICLE", "SHAM", "USUAL CARE",
             "SUPPORTIVE CARE", "CONTROL", "NO INTERVENTION", "BEST AVAILABLE")
SALTS = {"HYDROCHLORIDE", "DIHYDROCHLORIDE", "HCL", "MESYLATE", "SODIUM", "POTASSIUM", "CALCIUM",
         "SULFATE", "MALEATE", "TARTRATE", "CITRATE", "ACETATE", "PHOSPHATE", "FUMARATE", "SUCCINATE",
         "BESYLATE", "TOSYLATE", "BROMIDE", "MONOHYDRATE", "HYDRATE", "DISODIUM", "MAGNESIUM"}
STAGE_NAME = {1: "phase 1", 2: "phase 2", 3: "phase 3", "A": "approved"}


def _years(d):
    """'2014-03' or '2014-03-27' -> 2014.17; None if unreadable."""
    if not d:
        return None
    m = re.match(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", d)
    if not m:
        return None
    y, mo, dy = int(m.group(1)), int(m.group(2) or 6), int(m.group(3) or 15)
    return y + (mo - 1) / 12 + (dy - 1) / 365


def _stage(phase):
    p = phase or ""
    if "PHASE3" in p:
        return 3
    if "PHASE2" in p:
        return 2
    if "PHASE1" in p:
        return 1
    return None             # phase 4 (after approval) or not applicable


def _norm(name):
    n = re.sub(r"\(.*?\)", " ", name.upper())
    n = re.sub(r"\b\d+(\.\d+)?\s*(MG|MCG|UG|G|ML|MG/KG|IU|%)\b.*", " ", n)
    n = re.sub(r"[^A-Z0-9 \-]", " ", n)
    n = re.sub(r"(MAB|CEPT|ASE)-[A-Z]{4}\b", r"\1", n)   # biologic four-letter suffix: LECANEMAB-IRMB
    return " ".join(w for w in n.split() if w not in SALTS)


def _approvals(con):
    """Normalised single-ingredient or brand name -> first original approval (years)."""
    first = {}
    for ingr, brand, typ, d in con.execute("SELECT ingredients, brand, submission_type, date FROM approvals"):
        if typ != "ORIG":
            continue
        t = _years("%s-%s-%s" % (d[:4], d[4:6], d[6:8])) if d and d.isdigit() else _years(d)
        if t is None:
            continue
        names = []
        if ingr and "|" not in ingr:
            names.append(ingr)
        names += [b for b in (brand or "").split("|") if b]
        for nm in names:
            k = _norm(nm)
            if k and (k not in first or t < first[k]):
                first[k] = t
    return first


_ALIAS = {}


def _aliases(con):
    """Trials often write 'Pembrolizumab (MK-3475)'. Join the name outside and inside the brackets
    so a code-named early trial and a generic-named approval count as one drug. Name -> group name."""
    if id(con) in _ALIAS:
        return _ALIAS[id(con)]
    code = re.compile(r"^[A-Z]{1,6}[- ]?\d{2,}[A-Z0-9-]*$")      # MK-3475, AMG 510, BAN2401
    word = re.compile(r"^[A-Z]{6,}$")                               # PEMBROLIZUMAB
    parent = {}

    def find(x):
        return parent.get(x, x)
    for (ivs,) in con.execute("SELECT interventions FROM trials WHERE interventions LIKE '%(%'"):
        for nm in (ivs or "").split("|"):
            m = re.match(r"\s*([^()]+?)\s*\(([^()]+)\)", nm)
            if not m:
                continue
            a, b = _norm(m.group(1)), _norm(m.group(2))
            if code.match(a) and word.match(b):
                a, b = b, a
            if not (word.match(a) and code.match(b)):
                continue            # only a code name paired with one generic name
            if b not in parent:     # first pairing wins; a code is not reused for a second drug
                parent[b] = a
    out = {k: find(k) for k in parent}
    _ALIAS[id(con)] = out
    return out


def timelines(con, words=None, industry=True, since=2005):
    """Drug name -> list of (time, stage) in order reached, approval last if linked."""
    pats = [re.compile(r"\b" + re.escape(w.lower()) + r"\b") for w in (words or []) if w.strip()]
    first = {}
    al = _aliases(con)
    sql = ("SELECT phase, start, conditions, title, interventions, intervention_types, sponsor_class "
           "FROM trials WHERE study_type='INTERVENTIONAL'")
    for ph, st, cond, title, ivs, typ, cls in con.execute(sql):
        s, t = _stage(ph), _years(st)
        if s is None or t is None or (industry and cls != "INDUSTRY"):
            continue
        if pats:
            text = ((cond or "") + " " + (title or "")).lower()
            if not any(p.search(text) for p in pats):
                continue
        names, types = (ivs or "").split("|"), (typ or "").split("|")
        for i, nm in enumerate(names):
            if i < len(types) and types[i] not in ("DRUG", "BIOLOGICAL"):
                continue
            k = _norm(nm)
            if len(k) < 4 or any(x in k for x in NOT_DRUGS):
                continue
            k = al.get(k, k)
            d = first.setdefault(k, {})
            if s not in d or t < d[s]:
                d[s] = t
    appr = _approvals(con)
    names = {}
    for k in appr:
        names.setdefault(al.get(k, k), []).append(appr[k])
    out = {}
    for k, d in first.items():
        t0 = min(d.values())
        a = min(names[k]) if k in names else None
        if a is not None and a < t0:
            continue        # approved before its first registered trial: an old drug retested
        if t0 < since:
            continue        # began before registration was required: its early history is missing
        seq, top = [], 0
        for t, s in sorted((t, s) for s, t in d.items()):
            if s > top:
                seq.append((t, s))
                top = s
        if a is not None:
            seq.append((max(a, seq[-1][0]), "A"))
        out[k] = seq
    return out


def transitions(tl, end):
    """History so far -> list of (next stage or None, years). None means the record ran out (censored).
    Keyed twice: by the full path of stages reached, e.g. (1, 2), and by the current stage alone, e.g. 2."""
    tr = {}
    for seq in tl.values():
        path = ()
        for i, (t, s) in enumerate(seq):
            if s == "A":
                break
            path += (s,)
            if i + 1 < len(seq):
                rec = (seq[i + 1][1], seq[i + 1][0] - t)
            else:
                rec = (None, max(0.0, end - t))
            tr.setdefault(path, []).append(rec)
            tr.setdefault(s, []).append(rec)
    return tr


def _pool(tr, path):
    """Histories with the same path if there are enough, else the same current stage."""
    p = tr.get(path, [])
    return p if len(p) >= MIN_N else tr.get(path[-1], [])


def simulate(tr, path, years_in, horizon, sims, rng):
    """Returns counts of where each future ended and the years to approval."""
    ends, to_appr, ran_out = {}, [], 0
    for _ in range(sims):
        pa, s, el, now = tuple(path), path[-1], years_in, 0.0
        while s != "A":
            pool = [r for r in _pool(tr, pa) if r[1] > el]
            if not pool:
                ran_out += 1
                break
            nxt, g = rng.choice(pool)
            if nxt is None:                     # nothing happened for g years; wait that long, redraw
                if now + (g - el) >= horizon:
                    break
                now, el = now + (g - el), g
                continue
            if now + (g - el) > horizon:
                break
            now, s, el = now + (g - el), nxt, 0.0
            if s != "A":
                pa += (s,)
        ends[s] = ends.get(s, 0) + 1
        if s == "A":
            to_appr.append(now)
    return ends, to_appr, ran_out


def plain_count(tl, path, horizon, end):
    """Drugs with the same path that reached its last stage at least `horizon` years before the data end,
    and how many were approved inside the horizon."""
    n = k = 0
    for seq in tl.values():
        st = [x for x in seq if x[1] != "A"]
        if len(st) < len(path) or tuple(x[1] for x in st[:len(path)]) != tuple(path):
            continue
        t = st[len(path) - 1][0]
        if end - t < horizon:
            continue
        n += 1
        a = next((ta for ta, s in seq if s == "A"), None)
        if a is not None and a - t <= horizon:
            k += 1
    return k, n


def _both(k, n):
    if not n:
        return "no cases"
    p = round(100 * k / n)
    return f"{k} of {n} ({p} in 100 yes, {100 - p} in 100 no)"


def _pname(path):
    return " then ".join(STAGE_NAME[x] for x in path)


def run_drugs(words, stage=3, years_in=0.0, horizon=10.0, drug=None, sims=5000, seed=1,
              industry=True, since=2005, db=DB):
    if not os.path.exists(db):
        return ("The history database is not on this machine (gapmap/history.db). Build it with "
                "gaphistory.py fetch-trials and fetch-approvals, then run this again.")
    con = sqlite3.connect(db)
    row = con.execute("SELECT v FROM meta WHERE k='ct_fetched'").fetchone()
    end = _years(row[0]) if row else _years(date.today().isoformat())
    lines = ["HOW ROUGH: counted from public registries, then simulated. The next step is copied from similar past drugs, "
             "not learned; approvals filed under a name the trials never used are missed, so the approval share runs low."]
    every = timelines(con, industry=industry, since=since)
    mine = timelines(con, words, industry=industry, since=since) if words else every
    path = tuple(range(1, stage + 1))          # default: came through every earlier phase
    if drug:
        k = _norm(drug)
        seq = timelines(con, industry=False, since=0).get(k)
        if not seq:
            return "\n".join(lines + [f"No drug named '{drug}' found in the trial records."])
        lines.append("HISTORY OF %s: %s" % (k, ", ".join("%s in %.1f" % (STAGE_NAME[s], t) for t, s in seq)))
        if seq[-1][1] == "A":
            return "\n".join(lines + ["Already approved: nothing to simulate."])
        path, years_in = tuple(s for _, s in seq), max(0.0, end - seq[-1][0])
    tr_all, tr_mine = transitions(every, end), transitions(mine, end)
    tr = dict(tr_all)
    used = []
    for key in set(tr_mine) | set(tr_all):
        if len(tr_mine.get(key, [])) >= MIN_N:
            tr[key] = tr_mine[key]
    for i in range(1, len(path) + 1):
        pa = path[:i]
        if len(tr_mine.get(pa, [])) >= MIN_N:
            used.append(f"{_pname(pa)}: {len(tr_mine[pa])} similar")
        elif len(tr_all.get(pa, [])) >= MIN_N:
            used.append(f"{_pname(pa)}: {len(tr_mine.get(pa, []))} similar, so all {len(tr_all[pa])} drugs with this path")
        else:
            used.append(f"{_pname(pa)}: too few with this path, so drugs at {STAGE_NAME[pa[-1]]} by any path")
    who = "industry-sponsored trials" if industry else "all trials"
    lines.append(f"SIMILAR MEANS: {who} whose conditions or title contain {', '.join(words) if words else '(anything)'}, "
                 f"drugs first registered in {since} or later; {len(mine)} drugs found.")
    lines.append("HISTORIES USED: " + "; ".join(used))
    rng = random.Random(seed)
    ends, ta, ran_out = simulate(tr, path, years_in, horizon, sims, rng)
    a = ends.get("A", 0)
    p = a / sims
    se = (p * (1 - p) / sims) ** 0.5
    lines += ["",
              f"START: {_pname(path)}, {years_in:.1f} years already at the last stage. HORIZON: {horizon:g} years.",
              f"SIMULATED FUTURES: {sims}. Approved within the horizon in {_both(a, sims)}.",
              f"  Simulation wobble: about plus or minus {200 * se:.1f} in 100 (two standard errors, from the number of futures only).",
              "  Where the other futures ended: " + "; ".join(
                  f"still at {STAGE_NAME[s]} in {ends[s]}" for s in (1, 2, 3) if ends.get(s))]
    if ta:
        ta.sort()
        lines.append(f"  Among approved futures, typical (median) time to approval: {ta[len(ta) // 2]:.1f} years.")
    if ran_out:
        lines.append(f"  {ran_out} futures ran past the longest similar record and were stopped where they stood.")
    if years_in == 0:
        k, n = plain_count(mine, path, horizon, end)
        lines.append(f"PLAIN-COUNT CHECK: of similar drugs with the same path that reached {STAGE_NAME[path[-1]]} at least "
                     f"{horizon:g} years before the data end, approved within {horizon:g} years: {_both(k, n)}.")
    return "\n".join(lines)


def tool(args):
    """MCP entry point."""
    words = [w for w in re.split(r"[,;]", args.get("conditions", "")) if w.strip()]
    return run_drugs(words, stage=int(args.get("stage", 3)), years_in=float(args.get("years_in", 0)),
                     horizon=float(args.get("horizon", 10)), drug=args.get("drug"),
                     sims=int(args.get("sims", 5000)), seed=int(args.get("seed", 1)),
                     industry=bool(args.get("industry", True)), since=int(args.get("since", 2005)))


def main():
    a = sys.argv[1:]
    if len(a) < 1 or a[0] != "drugs":
        print(__doc__)
        return
    words, opts, i = [], {}, 1
    while i < len(a):
        if a[i].startswith("--"):
            opts[a[i][2:].replace("-", "_")] = a[i + 1]
            i += 2
        else:
            words += [w for w in re.split(r"[,;]", a[i]) if w.strip()]
            i += 1
    print(run_drugs(words, stage=int(opts.get("stage", 3)), years_in=float(opts.get("years_in", 0)),
                    horizon=float(opts.get("horizon", 10)), drug=opts.get("drug"),
                    sims=int(opts.get("sims", 5000)), seed=int(opts.get("seed", 1)),
                    industry=opts.get("industry", "yes") != "no", since=int(opts.get("since", 2005))))


if __name__ == "__main__":
    main()
