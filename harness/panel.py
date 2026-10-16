#!/usr/bin/env python3
"""
panel.py -- run the same question past several authors and MEASURE the
            shared-author bias instead of assuming it.

THE POINT

decide.py carries one number it cannot justify: b, the shared-author term.
It exists because channels are not independent draws from the world -- one
mind sets every range in one sitting, and if that mind is tilted, every
channel tilts the same way and the tilt never averages out. Without it,
confidence is manufactured by counting channels.

b was set to 0.35 by assertion. That is the weakest link in the whole
system, and it is the one thing a panel can fix.

Hand the blank elicitation sheet to several authors who cannot see each
other's answers. The disagreement between them IS b. It stops being a
guess and becomes a measurement.

    for author a and channel i:
        z(a,i) = [ mu(a,i) - mean_a mu(a,i) ] / mean_a sigma(a,i)

        how far this author put this channel from the panel's centre,
        in units of the channel's own spread

    B(a) = mean_i [ z(a,i) * dir(i) ]

        that author's overall tilt, direction-aligned so that pushing
        costs up and benefits down counts as ONE tilt rather than
        cancelling out

    b = sd across authors of B(a)

WHAT MATTERS IS INDEPENDENCE, NOT INTELLIGENCE

Averaging two authors whose judgements correlate at rho gives an effective
bias of b*sqrt((1+rho)/2). At rho = 1 -- two minds that agree about
everything -- you get NO reduction at all, however capable they are. At
rho = 0 the variance halves.

So a very strong model that shares your priors reduces b less than a
weaker one that genuinely disagrees. For this job, diversity beats
capability. Models from the same family share training lineage and will
correlate highly; that is worth knowing before reading too much into their
agreement.

AND THE OMISSIONS MATTER MORE THAN THE NUMBERS

Splitting a channel does not move the mean. Omitting one does. So the
`missing` field of each sheet is worth more than all four numbers in it,
and this script reports those first.

Layout:  harness/panels/<question>/<author>.json
Run:     python harness/panel.py <question>
"""

import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402  (sits next to this file)
sys.path.insert(0, HERE)
import decide as D                                        # noqa: E402
import chain as CH                                        # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PANELS = paths.data("panels")


def tri_mean(c):
    lo, hi, m = c["low"], c["high"], c.get("mode")
    return (lo + hi + m) / 3.0 if m is not None else (lo + hi) / 2.0


def tri_sd(c):
    lo, hi, m = c["low"], c["high"], c.get("mode")
    if hi <= lo:
        return 0.0
    if m is None:
        return (hi - lo) / math.sqrt(12.0)
    v = (lo * lo + hi * hi + m * m - lo * hi - lo * m - hi * m) / 18.0
    return math.sqrt(max(0.0, v))


def load_panel(name, extra=None):
    """Sheets from disk, plus any passed in directly.

    The inline path exists for callers that should not have to write
    files to ask a question -- an agent holding four filled sheets in
    memory has no business creating a directory to get them read. Sheets
    from disk come first so a saved panel is never shadowed by an
    inline one with the same author name.
    """
    d = D.load(name)
    folder = os.path.join(PANELS, name)
    authors = []
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if not fn.endswith(".json"):
                continue
            with io.open(os.path.join(folder, fn), encoding="utf-8") as f:
                a = json.load(f)
            a.setdefault("author", fn[:-5])
            authors.append(a)
    for i, a in enumerate(extra or [], 1):
        a = dict(a)
        a.setdefault("author", f"inline-{i}")
        authors.append(a)
    return d, authors


def report(name, extra=None):
    d, authors = load_panel(name, extra)
    ids = [u["id"] for u in d["uncertainties"]]
    dirs = D.bias_dirs(d)

    print("=" * 74)
    print(f"PANEL: {d['decision']}")
    print("=" * 74)

    # The house model counts as one author, named honestly.
    house = {"author": "house (the model that built the file)",
             "channels": {u["id"]: {"low": u["low"], "high": u["high"],
                                    "mode": u.get("mode"),
                                    "k": (u.get("history") or {}).get(
                                        "transfer_error",
                                        D.DEFAULT_TRANSFER_ERROR)}
                          for u in d["uncertainties"]},
             "missing": [], "objections": []}
    all_a = [house] + authors

    if not authors:
        print()
        D.para("No independent sheets yet, so b cannot be measured and the "
               f"assumed value of {D.bias_sd(d):.2f} still stands. Generate "
               f"a blank sheet with:")
        print()
        print(f"      python harness/decide.py {name} --elicit")
        print()
        D.para("Give it to a model that cannot see the existing numbers, "
               "save the reply under harness/panels/" + name + "/, and run "
               "this again. One independent sheet is enough to start; the "
               "estimate of b sharpens with each one. Callers going "
               "through the MCP can pass filled sheets straight to "
               "`decide_panel` instead, without writing anything to disk.")
        print()
        D.para("Choose for DISAGREEMENT rather than for capability. Two "
               "authors who share a prior reduce b by almost nothing no "
               "matter how strong they are -- the reduction goes as "
               "sqrt((1+rho)/2), and rho is high within a model family.")
        return

    print(f"  {len(all_a)} authors: "
          + ", ".join(a["author"] for a in all_a))
    print()

    # ---- omissions first: the only thing that moves a mean ---------------
    print("  WHAT EACH AUTHOR SAYS IS MISSING")
    print("  " + "-" * 70)
    D.para("Reported before the numbers, because splitting a channel leaves "
           "the mean untouched and omitting one does not. A channel nobody "
           "thought of is the only error here that can reverse a verdict.")
    print()
    any_miss = False
    for a in all_a:
        for m in a.get("missing", []) + a.get("objections", []):
            any_miss = True
            print(f"   [{a['author']}]")
            for line in D.wrap(m, 66):
                print("      " + line)
    if not any_miss:
        print("   (none reported)")
    print()

    # ---- per-channel disagreement ---------------------------------------
    print("  DISAGREEMENT, CHANNEL BY CHANNEL")
    print("  " + "-" * 70)
    print("  {:<27}{:>9}{:>9}{:>9}{:>10}".format(
        "channel", "low", "high", "spread", "in σ"))
    zs = {a["author"]: {} for a in all_a}
    for cid in ids:
        ms, ss = [], []
        for a in all_a:
            c = a["channels"].get(cid)
            if not c:
                continue
            ms.append((a["author"], tri_mean(c)))
            ss.append(tri_sd(c))
        if len(ms) < 2:
            continue
        vals = [v for _, v in ms]
        centre = sum(vals) / len(vals)
        sig = sum(ss) / len(ss) or 1.0
        span = max(vals) - min(vals)
        print("  {:<27}{:>9,.0f}{:>9,.0f}{:>9,.0f}{:>9.2f}σ".format(
            cid, min(vals), max(vals), span, span / sig))
        for au, v in ms:
            zs[au][cid] = (v - centre) / sig
    priced = {c for a in all_a for c in a.get("channels", {})}
    thin = [c for c in ids
            if sum(1 for a in all_a if a.get("channels", {}).get(c)) < 2]
    print()
    if thin:
        print("  NOT PRICED BY ENOUGH AUTHORS -- absent from the table above")
        print("  " + "-" * 70)
        for c in thin:
            who = [a["author"] for a in all_a if a.get("channels", {}).get(c)]
            print(f"   {c}")
            print(f"      priced by {len(who)} of {len(all_a)}: "
                  + (", ".join(x[:40] for x in who) or "nobody"))
        print()
        D.para("These are EXCLUDED FROM b, because a disagreement needs two "
               "authors to exist. That is arithmetically unavoidable and it "
               "is also the most dangerous line in this report: a channel "
               "added to the model after the sheets were filled disappears "
               "from the comparison without changing any number, so the "
               "panel keeps reporting the same b while silently covering "
               "less of the model. Re-elicit rather than assume the old "
               "sheets still cover it.")
        print()

    # ---- b, measured -----------------------------------------------------
    print("  b, MEASURED RATHER THAN ASSUMED")
    print("  " + "-" * 70)
    D.maths("THE FORMULA",
            ["z(a,i) = [ μ(a,i) - mean_a μ(a,i) ] / mean_a σ(a,i)",
             "B(a)   = mean_i [ z(a,i) · dir(i) ]",
             "b      = sd across authors of B(a)",
             "",
             "dir(i) is +1 for a benefit channel and -1 for a cost, so an",
             "author who inflates every cost AND deflates every benefit",
             "registers as one large tilt instead of cancelling to zero."],
            legend=["μ", "σ", "Δ", "a, b"], d=d)
    Bs = []
    for a in all_a:
        z = zs[a["author"]]
        if not z:
            continue
        B = sum(z[c] * dirs[c] for c in z) / len(z)
        Bs.append((a["author"], B))
        print("   {:<44}B = {:>+7.3f}".format(a["author"], B))
    print()
    if len(Bs) >= 2:
        mb = sum(b for _, b in Bs) / len(Bs)
        var = sum((b - mb) ** 2 for _, b in Bs) / (len(Bs) - 1)
        b_meas = math.sqrt(var)
        assumed = D.bias_sd(d)
        print(f"   b (measured) = {b_meas:.3f}     "
              f"b (assumed)  = {assumed:.3f}")
        print()
        if b_meas > assumed * 1.3:
            D.para("The authors disagree MORE than the assumed b allowed "
                   "for. Every confidence figure produced with the assumed "
                   "value is too high. Set elicitor_bias.sd to the measured "
                   "number and rerun.")
        elif b_meas < assumed * 0.7:
            D.para("The authors agree more closely than assumed. Before "
                   "treating that as reassurance, check whether they are "
                   "independent: models from one family share training "
                   "lineage, and correlated authors agree without adding "
                   "information. Agreement between near-copies measures "
                   "nothing.")
        else:
            D.para("The measured value sits close to the assumed one, which "
                   "is mild support for the assumption and nothing more.")
        print()
        if len(Bs) < 3:
            D.para(f"Caveat with teeth: an sd from {len(Bs)} authors is "
                   f"barely an estimate. Treat it as an order of magnitude "
                   f"until there are four or five, and prefer authors who "
                   f"disagree with each other over authors that are strong.")
    print()

    # ---- what the verdict does under each author -------------------------
    print("  THE VERDICT UNDER EACH AUTHOR")
    print("  " + "-" * 70)
    borrowed = {}
    for a in all_a:
        d2 = json.loads(json.dumps(d))
        ok = True
        for u in d2["uncertainties"]:
            c = a["channels"].get(u["id"])
            if not c:
                ok = False
                borrowed.setdefault(a["author"], []).append(u["id"])
                continue
            u["low"], u["high"] = c["low"], c["high"]
            u["mode"] = c.get("mode")
            if u.get("history") is not None and c.get("k") is not None:
                u["history"]["transfer_error"] = c["k"]
        evs = D.simulate(d2)
        names = list(evs)
        w = {n: 0 for n in names}
        for i in range(D.N_DRAWS):
            w[max(names, key=lambda n: evs[n][i])] += 1
        top = max(names, key=lambda n: D.mean(evs[n]))
        print("   {:<40}{:<20}{:>6.0%}{}".format(
            a["author"][:39], top, w[top] / D.N_DRAWS,
            "" if ok else "  (incomplete sheet)"))
    print()
    if borrowed:
        print("  WHOSE NUMBERS THOSE ROWS ACTUALLY USED")
        print("  " + "-" * 70)
        for au, cs in borrowed.items():
            print(f"   {au[:60]}")
            print(f"      did not price {len(cs)}: " + ", ".join(cs))
        print()
        D.para("A channel an author did not price FALLS BACK TO THE HOUSE "
               "VALUE, so the row above is that author's numbers wherever "
               "they gave one and mine everywhere else. It is still worth "
               "printing -- the alternative is dropping the author "
               "entirely -- but a row marked incomplete is a hybrid, not "
               "an independent verdict, and it agrees with the house "
               "partly by construction.")
        print()
    D.para("If the authors pick the same winner, the verdict survives "
           "independent elicitation, which is the strongest thing this "
           "system can say about any answer. If they pick different "
           "winners, the honest output is that the question is not settled "
           "and the disagreement is where the work is.")



# ---------------------------------------------------------------------
# CHAINS.
#
# The decision panel measures b, the shared-author tilt, and feeds it back
# into a confidence figure. A chain has no b to feed anywhere -- it has no
# simulation and no confidence percentage. What it has instead is a single
# number, and the useful thing a panel does to a single number is show how
# far it moves when somebody else writes it.
#
# So this reports the SPREAD OF THE ANSWER ACROSS AUTHORS rather than a
# bias coefficient. If three authors produce three different answers, the
# honest report of the claim is that range, and the file's own third significant
# figure was never real. That is a more useful output than a correction
# factor, because a reader can act on it without understanding the method.
#
# And the omissions come first, before any number, because splitting a
# link does not move the answer and leaving out a route does.
# ---------------------------------------------------------------------


def load_chain_panel(name, extra=None):
    d = CH.load(name)
    folder = os.path.join(PANELS, name)
    authors = []
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if not fn.endswith(".json"):
                continue
            with io.open(os.path.join(folder, fn), encoding="utf-8") as f:
                a = json.load(f)
            a.setdefault("author", fn[:-5])
            authors.append(a)
    for i, a in enumerate(extra or [], 1):
        a = dict(a)
        a.setdefault("author", f"inline-{i}")
        authors.append(a)
    return d, authors


def _house_sheet(d):
    """The file's own numbers, entered as one author and named honestly.
    It is not a neutral participant -- it is the prior every other sheet
    exists to be independent of -- but leaving it out would hide the thing
    being tested."""
    rg = d.get("regimes")
    out = {"author": "house (the model that wrote the file)",
           "links": {}, "missing_routes": [], "dependencies": [],
           "objections": []}
    if rg:
        out["q"] = {"low": rg.get("q_low", rg["q"]),
                    "high": rg.get("q_high", rg["q"]), "mode": rg["q"]}
        names = rg.get("names", ["crisis", "calm"])
        for l in d["links"]:
            br = l.get("p_by_regime") or {}
            out["links"][l["id"]] = {
                n: {"low": br.get(n, l["p"]), "high": br.get(n, l["p"]),
                    "mode": br.get(n, l["p"])} for n in names}
    else:
        for l in d["links"]:
            out["links"][l["id"]] = {
                "low": l.get("low", l["p"]), "high": l.get("high", l["p"]),
                "mode": l["p"]}
    return out


def _author_answer(d, a):
    """What the claim comes to under one author's numbers."""
    rg = d.get("regimes")
    ids = [l["id"] for l in d["links"]]
    if rg:
        names = rg.get("names", ["crisis", "calm"])
        hi, lo = names[0], names[1]
        q = tri_mean(a["q"]) if a.get("q") else rg["q"]
        ph, pl = 1.0, 1.0
        for i in ids:
            cell = a["links"].get(i)
            if not cell:
                return None
            ph *= tri_mean(cell[hi])
            pl *= tri_mean(cell[lo])
        return q * ph + (1 - q) * pl
    prod = 1.0
    for i in ids:
        cell = a["links"].get(i)
        if not cell:
            return None
        prod *= tri_mean(cell)
    return prod



def sheet_checks(d, a):
    """Quality flags for one sheet, computed WITHOUT reference to any
    other author's numbers.

    That constraint is the whole point. A panel exists to stop the file's
    author manufacturing agreement, so a filter that can reject a sheet
    for disagreeing would defeat it entirely. Every check below is
    internal to the sheet: it can fail while agreeing with the house and
    pass while contradicting it.

    Nothing is dropped. A flagged sheet stays in the spread and stays in
    the disagreement table. The flag is information for a reader, not a
    licence to ignore an answer you did not like.
    """
    out = []
    rg = d.get("regimes")
    names = rg.get("names", ["crisis", "calm"]) if rg else [None]
    hi, lo = (names[0], names[1]) if rg else (None, None)

    # 1. low <= mode <= high, which is arithmetic, not opinion
    bad = []
    for i, cell in (a.get("links") or {}).items():
        for nm in names:
            c = cell[nm] if nm else cell
            if not (c["low"] <= c.get("mode", c["low"]) <= c["high"]):
                bad.append(i + (f" [{nm}]" if nm else ""))
    if bad:
        out.append(("ordering", "low <= mode <= high is violated in "
                    + ", ".join(bad) + ". The range is not a range."))

    # 2. did it engage with the regime split, or apply one global rule?
    if rg:
        offs = []
        for i, cell in (a.get("links") or {}).items():
            offs.append(tri_mean(cell[hi]) - tri_mean(cell[lo]))
        if len(offs) > 2:
            spread = max(offs) - min(offs)
            same_sign = all(x >= 0 for x in offs) or all(x <= 0 for x in offs)
            if same_sign and spread < 0.12:
                out.append((
                    "one global rule",
                    f"Every link is shifted the same way by roughly the "
                    f"same amount ({min(offs):+.2f} to {max(offs):+.2f}). "
                    f"The sheet asked explicitly whether some steps get "
                    f"easier while others get harder, and this answers "
                    f"that they all move together. That may be the "
                    f"author's view; it is also what a sheet looks like "
                    f"when one sign was chosen and applied without "
                    f"reading the steps."))

    # 3. does the prose contradict the numbers?
    prose = " ".join(a.get("objections", []) + a.get("missing_routes", []) +
                     a.get("dependencies", [])).lower()
    doubt = any(w in prose for w in
                ("too optimistic", "excessively optimistic", "overly "
                 "optimistic", "unrealistic", "implausible", "unlikely "
                 "to happen", "not realistic"))
    if doubt:
        out.append(("prose vs numbers",
                    "The written comments call the claim too optimistic "
                    "or unrealistic. Check that against where this "
                    "author's numbers land in the table below -- if they "
                    "are the highest on the panel, the sheet contradicts "
                    "itself and one half of it is not considered."))

    # 4. did it answer the route question with a route?
    for r in a.get("missing_routes", []):
        rl = r.lower()
        if any(w in rl for w in ("prevents", "avoids", "stops ",
                                 "would not", "makes it less")):
            out.append(("route is not a route",
                        "A missing_routes entry describes something that "
                        "would PREVENT the claim rather than a different "
                        "way it could come true: '" + r[:90] + "'. That "
                        "is an answer to a different question."))
            break
    return out


def chain_report(name, extra=None):
    d, authors = load_chain_panel(name, extra)
    house = _house_sheet(d)
    rg = d.get("regimes")
    ids = [l["id"] for l in d["links"]]

    print("=" * 74)
    print("PANEL (CHAIN)")
    print("=" * 74)
    print()
    D.para(d["claim"], indent="  ")
    print()

    if not authors:
        D.para("NO INDEPENDENT SHEETS YET, so every number in this file "
               "still has one source. That is not a small caveat. More "
               "passes by the same author are the same prior "
               "re-expressed, not new evidence.")
        print()
        print(f"      python harness/chain.py {name} elicit")
        print()
        D.para("Give the sheet to a model that cannot see these numbers, "
               f"save the reply under harness/panels/{name}/, and run "
               "this again.")
        print()
        D.para("CHOOSE FOR DISAGREEMENT, NOT CAPABILITY. Averaging two "
               "authors whose judgements correlate at rho leaves you with "
               "sqrt((1+rho)/2) of the original tilt. At rho = 1 -- two "
               "minds that agree about everything -- you get no reduction "
               "at all, however capable they are. A weaker model that "
               "genuinely disagrees is worth more here than a stronger one "
               "that shares your priors, and models from one family share "
               "training lineage.")
        print()
        return

    all_a = [house] + authors

    # ---- omissions first, per the doctrine in this file's header -----
    print("  WHAT THE PANEL SAYS IS MISSING")
    print("  " + "-" * 70)
    D.para("Before any number. Splitting a link does not move the answer; "
           "leaving out a route does. Only independent authors are listed "
           "-- the house sheet has nothing to add here by construction.")
    print()
    any_note = False
    for a in authors:
        for key, lab in [("missing_routes", "ROUTE"),
                         ("dependencies", "DEPENDENCE"),
                         ("objections", "OBJECTION")]:
            for x in a.get(key, []):
                any_note = True
                print(f"   [{lab}] {a['author']}")
                for line in D.wrap(x, 66):
                    print("      " + line)
                print()
    if not any_note:
        print("   Nothing reported. Worth asking whether the sheet was")
        print("   filled in or merely completed.")
        print()

    # ---- sheet quality, before the numbers ---------------------------
    flags = {a["author"]: sheet_checks(d, a) for a in authors}
    if any(flags.values()):
        print("  SHEET QUALITY")
        print("  " + "-" * 70)
        D.para("Checks internal to each sheet -- none of them can see "
               "another author's numbers, so none can fail a sheet for "
               "disagreeing. NOTHING IS DROPPED: every flagged sheet stays "
               "in the spread below and in the disagreement table. A "
               "filter that removed answers the file's author disliked "
               "would defeat the only purpose a panel has.")
        print()
        for au, fl in flags.items():
            for nm, why in fl:
                print(f"   [{nm}] {au[:52]}")
                for line in D.wrap(why, 64):
                    print("      " + line)
                print()

    # ---- the answer under each author --------------------------------
    print("  WHAT THE CLAIM COMES TO, AUTHOR BY AUTHOR")
    print("  " + "-" * 70)
    print()
    vals = []
    for a in all_a:
        v = _author_answer(d, a)
        if v is None:
            print(f"   {a['author'][:44]:<46}  incomplete sheet")
            continue
        vals.append(v)
        print(f"   {a['author'][:44]:<46}{v:>8.4f}  = {v:>6.2%}")
    print()
    if len(vals) > 1:
        lo, hi = min(vals), max(vals)
        print("   " + "-" * 62)
        print(f"   {'spread across authors':<46}{lo:.2%} to {hi:.2%}")
        print()
        D.para(f"THAT RANGE IS THE ANSWER, not the midpoint of it. The "
               f"widest and narrowest authors differ by a factor of "
               f"{(hi/lo if lo else float('inf')):.1f}, and nothing in the "
               f"file's own working could have told you that, because the "
               f"file's working all came from one place. Report the claim "
               f"as {lo:.1%} to {hi:.1%} and say how many authors that "
               f"spans.")
        print()

    # ---- where they disagree most ------------------------------------
    print("  WHICH STEP THEY DISAGREE ABOUT MOST")
    print("  " + "-" * 70)
    print()
    names = (rg.get("names", ["crisis", "calm"]) if rg else [None])
    rows = []
    for i in ids:
        for nm in names:
            got = []
            for a in all_a:
                c = a["links"].get(i)
                if not c:
                    continue
                got.append(tri_mean(c[nm] if nm else c))
            if len(got) > 1:
                rows.append((max(got) - min(got), i, nm, min(got), max(got)))
    rows.sort(reverse=True)
    lab_w = 34
    print("   {:<{w}}{:>8}{:>8}{:>10}".format(
        "step", "lowest", "highest", "spread", w=lab_w))
    for sp, i, nm, mn, mx in rows:
        lab = i if not nm else f"{i} [{nm}]"
        print("   {:<{w}}{:>8.2f}{:>8.2f}{:>10.2f}".format(
            lab[:lab_w - 1], mn, mx, sp, w=lab_w))
    print()
    if rows:
        D.para(f"The panel is furthest apart on '{rows[0][1]}'"
               + (f" in the '{rows[0][2]}' world" if rows[0][2] else "")
               + ". That is where a further author is worth most, and it "
                 "is not necessarily the step the file's own leave-one-out "
                 "calls decisive -- disagreement and influence are "
                 "different things, and a step everyone agrees about "
                 "cannot be improved by asking again.")
        print()



def main():
    if len(sys.argv) < 2:
        qs = sorted(f[:-5] for f in os.listdir(D.DECISIONS)
                    if f.endswith(".json"))
        cs = sorted(f[:-5] for f in os.listdir(CH.CHAINS)
                    if f.endswith(".json"))
        print("usage: python harness/panel.py <question>")
        print("decisions:", ", ".join(qs))
        print("chains:   ", ", ".join(cs))
        return
    name = sys.argv[1]
    if os.path.exists(os.path.join(D.DECISIONS, name + ".json")):
        report(name)
    elif os.path.exists(os.path.join(CH.CHAINS, name + ".json")):
        chain_report(name)
    else:
        print(f"no decision or chain named '{name}'")


if __name__ == "__main__":
    main()
