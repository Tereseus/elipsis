#!/usr/bin/env python3
"""
number_ledger.py -- forecasts of a number, scored by how close they land.

The claim ledger (ledger.py) scores yes/no questions with the Brier score. A
yes/no line throws away how far off a forecast was: "claims above 205,000?"
scores the same whether the figure came in at 194,000 or at 150,000. When the
question is really about a number, forecast the number.

A forecast is a MEDIAN (the single best guess: half the chance below, half
above) and, if you can, a LOW and HIGH (the 10th and 90th percentiles, so the
truth should land between them 8 times in 10). Every forecast carries a
BASELINE value, the dumb answer (last month's figure, the consensus), and the
score asks whether you beat it. A median that differs from the baseline needs a
written "departure": what this case has that the usual week or month lacks.
Moving away from the dumb answer without a reason is where overconfidence
shows (ledger.py scores the same rule for yes/no questions).

Scores, all of which reward reporting what you actually believe:
  absolute error   |median - actual|; the best single number to give under this
                   score is your median.
  vs the baseline  ratio r = your error / the baseline's error. Below 1 means you
                   beat it. Ratios from different units can be compared, so the
                   record averages them (geometric mean, each clipped to 0.1-10)
                   across questions.
  quantile loss    for LOW, MEDIAN and HIGH: rho_t(u) = u (t - [u < 0]),
                   u = actual - guess, averaged over the three. It rewards a
                   range that is narrow and still right (Gneiting and Raftery 2007).
  coverage         how often the actual fell between LOW and HIGH; should be
                   about 80 in 100.

Nothing is overwritten: the store is append-only, like the ledger's.

SETTLING ITSELF. A forecast may carry a machine-checkable "source", the
forecasting version of a proof checker: if the data source returns the figure,
the forecast resolves itself, with no judgement. Supported:
  {"type": "bls", "series": "LNS14000000", "period": "2026-M10", "transform": "value"}
  {"type": "bls", "series": "CES0000000001", "period": "2026-M10", "transform": "change"}
(US Bureau of Labor Statistics public API, no key; "change" is the period minus
the period before.)
  {"type": "fred", "series": "ICSA", "date": "2026-10-31"}
(a FRED series from its keyless CSV download; "date" is the observation date
as FRED lists it, for weekly jobless claims the Saturday the week ends. Run
the morning after release, FRED still holds the first published figure.)
{"type": "manual", "where": "..."} says where to look by hand.
The free daily run (gapwatch.py) calls autoresolve() every morning.

Run:  python harness/number_ledger.py                  -- open forecasts, due first
      python harness/number_ledger.py add <file.json>  -- log one (no file: template)
      python harness/number_ledger.py resolve <id> <actual> ["note"] [--early "why"]
      python harness/number_ledger.py setsource <id> <source.json> -- give an open forecast
                                                     a source it lacks (once)
      python harness/number_ledger.py link <id> <ledger_id> <op> <threshold>
                                                  -- the number also closes a yes/no
                                                     question in ledger.py (op: > >= < <=)
      python harness/number_ledger.py auto              -- settle what the sources can
      python harness/number_ledger.py score            -- the record
Standard library only.
"""
import json
import math
import os
import sys
import urllib.request
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths  # noqa: E402

STORE = paths.data("ledger", "numbers.json")
REQUIRED = ("id", "claim", "resolves", "median", "resolution_criteria", "baseline", "reasoning")
TEMPLATE = {
    "id": "short-unique-id",
    "claim": "What number, measured how, published when.",
    "resolves": "YYYY-MM-DD",
    "median": 0.0, "low": None, "high": None, "unit": "",
    "resolution_criteria": "Which release, which figure (first print or revised).",
    "baseline": {"value": 0.0, "what": "Last value, or the published consensus."},
    "departure": "Needed only if the median differs from the baseline: why.",
    "reasoning": "Why this median and range. Written before looking at any consensus.",
}


def load():
    if not os.path.exists(STORE):
        return {"forecasts": []}
    with open(STORE, encoding="utf-8") as f:
        return json.load(f)


def save(d):
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    with open(STORE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def find(d, fid):
    return next((f for f in d["forecasts"] if f["id"] == fid), None)


def pinball(actual, guess, t):
    u = actual - guess
    return u * (t - (1.0 if u < 0 else 0.0))


def scores(f):
    """Scores of one resolved forecast."""
    y, m, b = f["resolved"]["actual"], f["median"], f["baseline"]["value"]
    err, berr = abs(m - y), abs(b - y)
    out = {"error": err, "baseline_error": berr}
    if berr > 0:
        out["ratio"] = err / berr
    elif err == 0:
        out["ratio"] = 1.0
    if f.get("low") is not None and f.get("high") is not None:
        out["quantile_loss"] = (pinball(y, f["low"], 0.1) + pinball(y, m, 0.5)
                                + pinball(y, f["high"], 0.9)) / 3
        out["covered"] = f["low"] <= y <= f["high"]
    return out


def add(d, f):
    for k in REQUIRED:
        if k not in f:
            return False, f"Missing required field '{k}'."
    if find(d, f["id"]):
        return False, f"A forecast with id '{f['id']}' already exists."
    if "value" not in f["baseline"]:
        return False, "The baseline needs a value."
    lo, hi = f.get("low"), f.get("high")
    if (lo is None) != (hi is None):
        return False, "Give both low and high, or neither."
    if lo is not None and not lo <= f["median"] <= hi:
        return False, "Need low <= median <= high."
    if f["median"] != f["baseline"]["value"] and not f.get("departure"):
        return False, (f"The median {f['median']} differs from the baseline "
                       f"{f['baseline']['value']}. Give 'departure': what this case "
                       f"has that the usual one lacks, or use the baseline as the median.")
    f.setdefault("made", date.today().isoformat())
    f["resolved"] = None
    d["forecasts"].append(f)
    save(d)
    rng = f" (80 in 100 range {lo} to {hi})" if lo is not None else ""
    return True, (f"Logged [{f['id']}]: median {f['median']}{rng} against a baseline of "
                  f"{f['baseline']['value']}, resolving {f['resolves']}.")


def resolve(d, fid, actual, note, early=None):
    f = find(d, fid)
    if f is None:
        return False, f"No forecast with id '{fid}'."
    if f.get("resolved"):
        return False, "Already resolved."
    on = date.today().isoformat()
    if on < f["resolves"] and not early:
        return False, f"Not due until {f['resolves']}; pass --early \"why\" if the figure is already out."
    f["resolved"] = {"actual": actual, "on": on, "note": note, **({"early": early} if early else {})}
    save(d)
    s = scores(f)
    msg = (f"[{fid}] actual {actual}. Your median {f['median']}: off by {s['error']:g}; "
           f"baseline {f['baseline']['value']}: off by {s['baseline_error']:g}.")
    if "ratio" in s:
        msg += f" Ratio {s['ratio']:.2f} ({'beat' if s['ratio'] < 1 else 'did not beat'} the baseline)."
    if "covered" in s:
        msg += f" {'Inside' if s['covered'] else 'Outside'} the 80 in 100 range."
    return True, msg


BLS_API = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


def bls_fetch(series):
    """{series: {"2026-M10": value}} from the BLS public API (keyless: a few queries a day)."""
    body = json.dumps({"seriesid": sorted(series)}).encode()
    req = urllib.request.Request(BLS_API, data=body, headers={
        "Content-Type": "application/json", "User-Agent": "Elipsis (keyless)"})
    d = json.loads(urllib.request.urlopen(req, timeout=40).read())
    if d.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS: {d.get('status')} {d.get('message')}")
    out = {}
    for s in d["Results"]["series"]:
        # "-" marks a month that was never published (a shutdown, for example).
        out[s["seriesID"]] = {f"{r['year']}-{r['period']}": float(r["value"])
                              for r in s["data"]
                              if r["period"].startswith("M") and r["value"] not in ("-", "")}
    return out


FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="


def fred_fetch(series):
    """{series: {"2026-10-24": value}} from FRED's keyless CSV download."""
    out = {}
    for sid in sorted(series):
        # FRED resets connections from some bare user agents; a browser-style one works.
        req = urllib.request.Request(FRED_CSV + sid,
                                     headers={"User-Agent": "Mozilla/5.0 (Elipsis keyless)"})
        text = urllib.request.urlopen(req, timeout=40).read().decode("utf-8")
        vals = {}
        for line in text.splitlines()[1:]:
            day, _, v = line.partition(",")
            if v.strip() not in ("", "."):
                vals[day.strip()] = float(v)
        out[sid] = vals
    return out


def _prev_month(period):
    y, m = int(period[:4]), int(period[-2:])
    y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return f"{y}-M{m:02d}"


def autoresolve(d, fetch=bls_fetch, on=None, fred=fred_fetch):
    """Settle every due forecast whose source can answer. Returns lines saying what happened."""
    on = on or date.today().isoformat()
    out = _fred_resolve(d, fred, on)
    due = [f for f in d["forecasts"] if not f.get("resolved") and f["resolves"] <= on
           and (f.get("source") or {}).get("type") == "bls"]
    if not due:
        return out
    data = fetch({f["source"]["series"] for f in due})
    for f in due:
        src = f["source"]
        vals = data.get(src["series"], {})
        if src["period"] not in vals:
            late = date.fromisoformat(on) - date.fromisoformat(f["resolves"]) > timedelta(days=25)
            out.append(f"[{f['id']}] {src['series']} {src['period']} not published yet"
                       + (" (25+ days late: check by hand)" if late else ""))
            continue
        y = vals[src["period"]]
        if src.get("transform") == "change":
            p0 = _prev_month(src["period"])
            if p0 not in vals:
                out.append(f"[{f['id']}] previous month {p0} missing")
                continue
            y = round(y - vals[p0], 3)
        note = f"auto: BLS {src['series']} {src['period']} ({src.get('transform', 'value')}) = {y:g}, fetched {on}"
        ok, msg = resolve(d, f["id"], y, note)
        out.append(msg)
        if ok:
            out += settle_links(f, y, note)
    return out


def _fred_resolve(d, fetch, on):
    due = [f for f in d["forecasts"] if not f.get("resolved") and f["resolves"] <= on
           and (f.get("source") or {}).get("type") == "fred"]
    if not due:
        return []
    try:
        data = fetch({f["source"]["series"] for f in due})
    except Exception as e:  # a FRED outage must not stop the BLS forecasts settling
        return [f"FRED fetch failed ({e}); {len(due)} forecast(s) left for the next run"]
    out = []
    for f in due:
        src = f["source"]
        vals = data.get(src["series"], {})
        if src["date"] not in vals:
            out.append(f"[{f['id']}] FRED {src['series']} {src['date']} not published yet")
            continue
        y = vals[src["date"]]
        note = f"auto: FRED {src['series']} {src['date']} = {y:g}, fetched {on}"
        ok, msg = resolve(d, f["id"], y, note)
        out.append(msg)
        if ok:
            out += settle_links(f, y, note)
    return out


OPS = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
       "<": lambda a, b: a < b, "<=": lambda a, b: a <= b}


def settle_links(f, y, note):
    """A yes/no question in the claim ledger that this number decides
    ("unemployment 4.3 or higher?") closes with it."""
    out = []
    if not f.get("links"):
        return out
    import ledger as L
    d = L.load()
    for k in f["links"]:
        outcome = OPS[k["op"]](y, k["threshold"])
        closed = L.resolve(d, k["ledger_id"], outcome, f"{note}; {y:g} {k['op']} {k['threshold']:g} is {outcome}")
        out.append(f"  linked yes/no [{k['ledger_id']}]: {'closed ' + str(outcome) if closed else 'not closed'}")
    return out


def link(d, fid, ledger_id, op, threshold):
    f = find(d, fid)
    if f is None or f.get("resolved"):
        return False, "Only an open forecast can be linked."
    if op not in OPS:
        return False, f"op must be one of {sorted(OPS)}"
    f.setdefault("links", []).append({"ledger_id": ledger_id, "op": op, "threshold": threshold,
                                       "added": date.today().isoformat()})
    save(d)
    return True, f"[{fid}] will also close [{ledger_id}] as: actual {op} {threshold:g}."


def set_source(d, fid, src):
    f = find(d, fid)
    if f is None:
        return False, f"No forecast with id '{fid}'."
    if f.get("resolved") or f.get("source"):
        return False, "Only an open forecast without a source can be given one."
    f["source"] = src
    f["source_added"] = date.today().isoformat()
    save(d)
    return True, f"[{fid}] now settles from {src}."


def show_open(d):
    today = date.today().isoformat()
    rows = sorted((f for f in d["forecasts"] if not f.get("resolved")), key=lambda f: f["resolves"])
    if not rows:
        print("No open number forecasts.")
    for f in rows:
        due = "DUE  " if f["resolves"] <= today else "     "
        rng = f" [{f['low']} to {f['high']}]" if f.get("low") is not None else ""
        print(f"{due}{f['resolves']}  [{f['id']}]  median {f['median']}{rng} {f.get('unit', '')}"
              f"  baseline {f['baseline']['value']}")


def score(d):
    done = [f for f in d["forecasts"] if f.get("resolved")]
    print(f"NUMBER FORECASTS: {len(done)} resolved, "
          f"{sum(1 for f in d['forecasts'] if not f.get('resolved'))} open")
    if not done:
        return
    ss = [(f, scores(f)) for f in done]
    for f, s in ss:
        line = f"  [{f['id']}] actual {f['resolved']['actual']}, median {f['median']}, baseline {f['baseline']['value']}"
        if "ratio" in s:
            line += f", ratio {s['ratio']:.2f}"
        if "covered" in s:
            line += ", inside range" if s["covered"] else ", OUTSIDE range"
        print(line)
    rs = [s["ratio"] for _, s in ss if "ratio" in s]
    if rs:
        # Geometric mean of ratios clipped to 0.1..10, so one exact hit (ratio 0)
        # or one baseline that was spot on cannot swamp the record.
        g = math.exp(sum(math.log(min(max(r, 0.1), 10)) for r in rs) / len(rs))
        beat = sum(1 for r in rs if r < 1)
        print(f"Beat the baseline on {beat} of {len(rs)}. Typical ratio (geometric mean, each "
              f"clipped to 0.1-10) {g:.2f}: {'better' if g < 1 else 'no better'} than the baseline.")
    cov = [s["covered"] for _, s in ss if "covered" in s]
    if cov:
        print(f"Actual inside the 80 in 100 range: {sum(cov)} of {len(cov)} "
              f"({100 * sum(cov) / len(cov):.0f} in 100; about 80 is right, far more means ranges too wide).")


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    d = load()
    cmd = argv[0] if argv else ""
    if cmd == "add":
        if len(argv) < 2:
            print(json.dumps(TEMPLATE, indent=2))
            return
        ok, msg = add(d, json.load(open(argv[1], encoding="utf-8")))
        print(msg)
    elif cmd == "resolve":
        rest = argv[1:]
        early = None
        if "--early" in rest:
            i = rest.index("--early")
            early = rest[i + 1] if i + 1 < len(rest) else "no reason given"
            rest = rest[:i] + rest[i + 2:]
        if len(rest) < 2:
            print('usage: number_ledger.py resolve <id> <actual> ["note"] [--early "why"]')
            return
        ok, msg = resolve(d, rest[0], float(rest[1]), rest[2] if len(rest) > 2 else "", early)
        print(msg)
    elif cmd == "setsource":
        ok, msg = set_source(d, argv[1], json.load(open(argv[2], encoding="utf-8")))
        print(msg)
    elif cmd == "link":
        ok, msg = link(d, argv[1], argv[2], argv[3], float(argv[4]))
        print(msg)
    elif cmd == "auto":
        print("\n".join(autoresolve(d)) or "Nothing due with a source.")
    elif cmd == "score":
        score(d)
    else:
        show_open(d)


if __name__ == "__main__":
    main(sys.argv[1:])
