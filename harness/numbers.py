#!/usr/bin/env python3
"""
numbers.py -- forecasts of a number, scored by how close they land.

The claim ledger (ledger.py) scores yes/no questions with the Brier score. A
yes/no line throws away how far off a forecast was: "claims above 205,000?"
scores the same whether the figure came in at 194,000 or at 150,000. When the
question is really about a number, forecast the number.

A forecast is a MEDIAN (the single best guess: half the chance below, half
above) and, if you can, a LOW and HIGH (the 10th and 90th percentiles, so the
truth should land between them 8 times in 10). Every forecast carries a
BASELINE value, the dumb answer (last month's figure, the consensus), and the
score asks whether you beat it.

Scores, all of which reward reporting what you actually believe:
  absolute error   |median - actual|; the best single number to give under this
                   score is your median.
  vs the baseline  ratio r = your error / the baseline's error. Below 1 means you
                   beat it. Ratios from different units can be compared, so the
                   record averages them (geometric mean) across questions.
  quantile loss    for LOW, MEDIAN and HIGH: rho_t(u) = u (t - [u < 0]),
                   u = actual - guess, averaged over the three. It rewards a
                   range that is narrow and still right (Gneiting and Raftery 2007).
  coverage         how often the actual fell between LOW and HIGH; should be
                   about 80 in 100.

Nothing is overwritten: the store is append-only, like the ledger's.

Run:  python harness/numbers.py                  -- open forecasts, due first
      python harness/numbers.py add <file.json>  -- log one (no file: template)
      python harness/numbers.py resolve <id> <actual> ["note"] [--early "why"]
      python harness/numbers.py score            -- the record
Standard library only.
"""
import json
import math
import os
import sys
from datetime import date

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
        g = math.exp(sum(math.log(max(r, 1e-6)) for r in rs) / len(rs))
        beat = sum(1 for r in rs if r < 1)
        print(f"Beat the baseline on {beat} of {len(rs)}. Typical ratio (geometric mean) {g:.2f}: "
              f"{'better' if g < 1 else 'no better'} than the baseline.")
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
            print('usage: numbers.py resolve <id> <actual> ["note"] [--early "why"]')
            return
        ok, msg = resolve(d, rest[0], float(rest[1]), rest[2] if len(rest) > 2 else "", early)
        print(msg)
    elif cmd == "score":
        score(d)
    else:
        show_open(d)


if __name__ == "__main__":
    main(sys.argv[1:])
