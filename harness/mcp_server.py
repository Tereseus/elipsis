#!/usr/bin/env python3
"""
mcp_server.py -- Elipsis as an MCP tool server.

Zero dependencies. Standard library only, JSON-RPC 2.0 over stdio. Nothing is
hosted, nothing is billed, no key is required.

The division of labour is the whole reason this is a tool server rather than
a website. The model you are talking to does the language: shaping a loose
question into structure, reading sources. This process does only the parts that
must be deterministic and auditable -- the counting, the checks, the budget
arithmetic. You should never want a language model doing the arithmetic, and
never want deterministic code trying to understand a sentence.

Every tool takes inline objects, so a model can draft something and have it
checked before anything touches disk.

THE ORDER MATTERS. Run them cheapest-first:

check_budget     does the sample support any model?     free
check_frame      is the question well-posed?            free
check_lineage    how many independent origins?          minutes
check_entailment does the evidence support THIS?        minutes
ledger_add       write the prediction down first        seconds
ledger_rerun     new information? log it, never overwrite seconds

or call `audit` to run the whole sequence with short-circuiting.

THE DECIDE TOOLS ARE DIFFERENT IN KIND. Everything above is a checklist that
tells you whether a question can be answered. `decide` actually computes:
given options and beliefs held as ranges, it returns which option wins and
how confident that is, which beliefs cannot change the answer, where each
one would flip it, and what further research is worth.

It computes what the stated beliefs IMPLY. It does not discover them. No
tool here can look at a history of anything -- meals, symptoms, trades,
past choices -- and produce an effect size. Somebody supplies every range
and says where it came from, and the report states what share was guessed.
"""

import json
import os
import sys
import traceback
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import paths           # noqa: E402
import frame as F       # noqa: E402
import budget as B      # noqa: E402
import lineage as L     # noqa: E402
import entail as E      # noqa: E402
import gapmap_tools as GT  # noqa: E402
import simfutures as SF  # noqa: E402
import ledger as LG     # noqa: E402
import decide as DC     # noqa: E402
import trial as TR      # noqa: E402
import robust as RB     # noqa: E402
import gaps as GP       # noqa: E402
import publish as PB    # noqa: E402
import pitf as PF       # noqa: E402
import chain as CN      # noqa: E402
import panel as PN      # noqa: E402
import constants as KC  # noqa: E402
import router as RT     # noqa: E402
import steelman as SM   # noqa: E402
import mirror as MR     # noqa: E402
import ancestry as AN   # noqa: E402
import evidence as EV   # noqa: E402
import operations as OP # noqa: E402
import loop as LP       # noqa: E402
import reference_models as RM  # noqa: E402
import claimrows as CRW     # noqa: E402

OUT = os.path.join(HERE, "..", "web") if paths.DATA == HERE else paths.data("web")
PROTOCOL = "2024-11-05"


def _cap(fn, *a):
    """Run a reporter that prints, and capture what it printed."""
    import io as _io
    import contextlib
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a)
    return buf.getvalue()


# ----------------------------------------------------------------- tools ---

def t_check_budget(args):
    d = args["question"]
    a = B.analyse(d)
    v, why = B.verdict(a)
    want = d.get("variables_wanted", [])
    out = [f"QUESTION: {d.get('question','(unnamed)')}",
           f"reference class: {d.get('reference_class','(unnamed)')}", "",
           f"cases named        {a['n_nom']}",
           f"usable             {a['n_use']}",
           f"independent groups {a['n_clu']}", "",
           f"BUDGET  {a['budget_low']} to {a['budget_high']} variables", "",
           f"VERDICT: {v}", why]
    if want:
        allowed = a["budget_low"]
        out += ["", f"you listed {len(want)}; allowed {allowed}"]
        if len(want) > allowed:
            out.append(f"CUT {len(want)-allowed}. Not because the others do "
                       f"not matter -- because the sample cannot tell you "
                       f"whether they do.")
    return "\n".join(out)


def t_check_frame(args):
    fr = args["frame"]
    r = F.check(fr)
    out = [f'ASKED: "{fr["asked"]}"', "", f"VERDICT: {r.verdict}", ""]
    if r.fail:
        out.append("MUST FIX — the question cannot be answered as posed:")
        out += [f"  · {m}" for _, m in r.fail] + [""]
    if r.warn:
        out.append("CAVEATS — answerable, but constrained:")
        out += [f"  · {m}" for _, m in r.warn] + [""]
    if r.ok:
        out.append("PASSED:")
        out += [f"  · {m}" for _, m in r.ok]
    return "\n".join(out)


def t_check_lineage(args):
    c = args["claim"]
    idx, oo, origins, echoes, cyc = L.analyse(c)
    v, why = L.verdict(idx, origins, cyc)
    n = len(c["sources"])
    out = [f'CLAIM: {c["claim"]}', "",
           f"cited by {n} sources", f"independent origins: {len(origins)}",
           f"echoes: {n - len(origins)}", "", f"VERDICT: {v}", why, "", "ORIGINS"]
    for o in sorted(origins):
        s = idx.get(o)
        if not s:
            out.append(f"  · {o} — cited but never described"); continue
        flags = []
        if s.kind in L.DISQUALIFYING:
            flags.append(L.DISQUALIFYING[s.kind].upper())
        if s.interested or s.kind in L.SELF_REPORTED:
            flags.append("INTERESTED")
        if s.kind in L.BOUNDING:
            flags.append("made for another purpose")
        out.append(f"  · {s.id} ({s.year}, {s.kind})"
                   + (f"  [{' / '.join(flags)}]" if flags else ""))
        if s.note:
            out.append(f"      {s.note}")
    return "\n".join(out)


def t_check_entailment(args):
    d = args["claim"]
    gaps = E.check(d)
    out = [f'CLAIM: {d["claim"]}', ""]
    if not gaps:
        out += ["ENTAILED", "Every structural element of the claim is covered "
                "by the evidence as declared."]
        return "\n".join(out)
    out.append(f"{len(gaps)} GAP(S)")
    out.append("")
    for g in gaps:
        out += [g.kind, "    " + g.detail, ""]
    out += ["STRONGEST CLAIM THE EVIDENCE ACTUALLY SUPPORTS",
            "  " + E.strongest_supported(d, gaps)]
    return "\n".join(out)


def t_audit(args):
    import audit as A
    return _cap(A.run, args.get("name", "inline"), args["question"])


def t_ledger_status(args):
    d = LG.load()
    return _cap(LG.show_open, d) or "No open claims."


def t_ledger_score(args):
    return _cap(LG.score, LG.load())


def t_ledger_add(args):
    ok, msg = LG.add(LG.load(), args["claim"])
    return msg


def t_ledger_resolve(args):
    d = LG.load()
    if args.get("unresolvable"):
        outcome = None
    elif "outcome" in args:
        outcome = bool(args["outcome"])
    else:
        return "Give an outcome (true or false), or unresolvable: true."
    return _cap(LG.resolve, d, args["id"], outcome, args.get("note", ""),
                args.get("early"), bool(args.get("force")))


def t_ledger_rerun(args):
    return _cap(LG.rerun, LG.load(), args["id"], float(args["probability"]),
                args["reasoning"], args.get("baseline")) or "Nothing logged."


def t_ledger_calibrate(args):
    return _cap(LG.show_calibration, LG.load())


def t_ledger_due(args):
    return _cap(LG.show_open, LG.load(), True)


def _ledger_blurb():
    """The live record, read at start-up, so this description cannot go stale."""
    try:
        rs = LG.scored(LG.load())
        if len(rs) < 2:
            return "Too few forecasts have resolved to score yet."
        mine = sum(LG.brier(c["probability"], c["resolved"]["outcome"])
                   for c in rs) / len(rs)
        base = sum(LG.brier(LG.base_p(c), c["resolved"]["outcome"])
                   for c in rs) / len(rs)
        hi = [c for c in rs if c["probability"] >= 0.7]
        right = sum(1 for c in hi if c["resolved"]["outcome"])
        s = (f"On the ledger's own record ({len(rs)} resolved) it comes out at "
             f"{mine:.3f} against a {base:.3f} baseline")
        s += ", which is worse than the dumb answer." if mine > base else "."
        if hi:
            s += f" At 70% confidence or above, right {right} time(s) in {len(hi)}."
        return s
    except Exception:
        return "It reports the Brier score against the baseline."


def t_render_finding(args):
    title = args["title"]
    verdict = args["verdict"]
    charts = args.get("charts", [])
    refusals = args.get("refusals", [])
    fname = args.get("filename", "finding_generated.html")

    def bars(c):
        rows = sorted(c["data"].items(), key=lambda kv: -kv[1])
        return "".join(
            f'<div class=r><span class=n>{k}</span>'
            f'<span class=t><i style="width:{v*100:.0f}%"></i></span>'
            f'<span class=v>{v:.2f}</span></div>' for k, v in rows)

    html = f"""<title>{title}</title>\n<style>\n:root{{--p:#F2F1EF;--c:#FFF;--s:#E6E4E1;--i:#1A1A18;--i2:#4A4945;\n--m:#8A2B26;--r:#CFCCC7;--b:#2E4C6B}}\n@media(prefers-color-scheme:dark){{:root:not([data-theme=light]){{\n--p:#131312;--c:#1B1B19;--s:#0C0C0B;--i:#EDEBE7;--i2:#B6B3AC;\n--m:#E08079;--r:#312F2C;--b:#8FB4D6}}}}\n:root[data-theme=dark]{{--p:#131312;--c:#1B1B19;--s:#0C0C0B;--i:#EDEBE7;\n--i2:#B6B3AC;--m:#E08079;--r:#312F2C;--b:#8FB4D6}}\n*{{box-sizing:border-box}}\nbody{{margin:0;background:var(--p);color:var(--i);font:17px/1.6 Georgia,serif}}\n.w{{max-width:820px;margin:0 auto;padding:34px 22px 60px}}\nh1{{font-size:clamp(28px,5vw,46px);line-height:1.05;margin:0 0 18px}}\n.vd{{background:var(--c);border:1px solid var(--r);border-top:4px solid var(--m);\npadding:20px 22px;margin:0 0 30px;font-size:18px}}\nh2{{font-size:15px;letter-spacing:.12em;text-transform:uppercase;\ncolor:var(--i2);margin:32px 0 12px;font-family:system-ui,sans-serif}}\n.ch{{background:var(--c);border:1px solid var(--r);padding:18px 20px;margin-bottom:14px}}\n.ch h3{{font:600 15px system-ui,sans-serif;margin:0 0 14px}}\n.r{{display:grid;grid-template-columns:minmax(0,1fr);gap:3px;margin-bottom:9px}}\n@media(min-width:600px){{.r{{grid-template-columns:200px 1fr 48px;gap:12px;align-items:center}}}}\n.n{{font:14px system-ui,sans-serif;color:var(--i2);min-width:0}}\n.t{{display:block;height:18px;background:var(--s)}}\n.t i{{display:block;height:100%;background:var(--b)}}\n.v{{font:13px ui-monospace,monospace;text-align:right}}\n.rf{{background:var(--c);border:1px solid var(--r);padding:14px 20px;margin-bottom:10px}}\n.rf p{{margin:0 0 4px;font-size:16px}}\n.rf small{{color:var(--i2);font-size:14.5px;display:block}}\nfooter{{margin-top:34px;padding-top:18px;border-top:1px solid var(--r);\ncolor:var(--i2);font-size:14.5px}}\n</style>\n<div class=w>\n<h1>{title}</h1>\n<div class=vd>{verdict}</div>\n{"<h2>What could be measured</h2>" if charts else ""}\n{"".join(f'<div class=ch><h3>{c["title"]}</h3>{bars(c)}</div>' for c in charts)}\n{"<h2>What could not be measured</h2>" if refusals else ""}\n{"".join(f'<div class=rf><p>{r["claim"]}</p><small>{r["why"]}</small></div>' for r in refusals)}\n<footer>Levels are ordinal, not units. Unsourced cells are absent, never zero.</footer>\n</div>"""
    os.makedirs(OUT, exist_ok=True)
    path = os.path.abspath(os.path.join(OUT, fname))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return f"Wrote {path}"


OBJ = {"type": "object"}

def _load_decision(args):
    """A decision comes either inline or by saved name. Inline is the one\nanother agent will use: build the spec, get a number, discard it."""
    if args.get("decision"):
        return args["decision"]
    if args.get("name"):
        return DC.load(args["name"])
    raise ValueError("pass either `decision` (inline) or `name` (saved)")


def t_decide(args):
    d = _load_decision(args)
    txt = _cap(DC.report, d)
    if args.get("answer_only"):
        # everything above the second heading is the verdict block
        i = txt.find("=" * 74, txt.find("=" * 74, txt.find("THE ANSWER")) + 1)
        return txt[:i] if i > 0 else txt
    return txt


def t_decide_list(args):
    fs = sorted(f[:-5] for f in os.listdir(DC.DECISIONS) if f.endswith(".json"))
    return "saved decisions: " + (", ".join(fs) if fs else "(none)")


def t_decide_save(args):
    name = args["name"]
    if not name.replace("_", "").replace("-", "").isalnum():
        raise ValueError("name must be alphanumeric with _ or -")
    d = args["decision"]
    # MUST be captured. stdout is the JSON-RPC transport, and an
    # uncaptured reporter writes 70 lines of prose into the middle of the
    # protocol -- measured: 1 of 70 lines parsed as JSON. Validate by
    # rendering, but render into a buffer.
    _cap(DC.report, d)                 # fail loudly here rather than on disk
    p = os.path.join(DC.DECISIONS, name + ".json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    return f"saved to harness/decisions/{name}.json"


def t_decide_elicit(args):
    d = _load_decision(args)
    return _cap(DC.elicit, d, args.get("name", "adhoc"))



def t_trial_design(args):
    d = TR.design(float(args["sigma"]),
                  days=args.get("days"),
                  effect=args.get("effect"),
                  power=float(args.get("power", 0.80)),
                  unblind_bias=args.get("unblind_bias"))
    return _cap(TR.report, d) + "\n" + json.dumps(d, indent=2)


def t_trial_assign(args):
    if args.get("days"):
        rows = TR.schedule(args["trial_id"], int(args["days"]),
                           args.get("start"),
                           tuple(args.get("arms", ["A", "B"])))
        return json.dumps(rows, indent=2)
    day = args["day"]
    arm = TR.assign(args["trial_id"], day, tuple(args.get("arms", ["A", "B"])))
    return json.dumps({"trial_id": args["trial_id"], "day": day, "arm": arm,
                       "deterministic": True,
                       "note": "Recomputable by anyone. Re-running cannot "
                               "change it, which is the point."})


def t_trial_analyse(args):
    return json.dumps(TR.analyse(args["rows"], args.get("blinded")), indent=2)



def t_robust(args):
    d = _load_decision(args)
    return _cap(RB.report, d)



def t_find_gaps(args):
    if args.get("chain") or (args.get("decision") or {}).get("links"):
        d = args.get("chain") or args["decision"]
    elif args.get("name") and os.path.exists(
            os.path.join(CN.CHAINS, args["name"] + ".json")):
        d = CN.load(args["name"])
    else:
        d = _load_decision(args)
    # A chain fails differently and gets a different checklist: no
    # baseline and no options to be missing, but an independence
    # assumption and a decomposition depth, which a decision has not.
    fn = GP.chain_report if d.get("links") else GP.report
    out = _cap(fn, d)
    if args.get("findings"):
        n, fresh, seen = GP.log_pass(args.get("name", "adhoc"),
                                     args["findings"])
        out += ("\n\nPASS %d LOGGED: %d findings, %d new.\n"
                % (n, len(args["findings"]), len(fresh)))
        out += ("CONVERGED -- stop here.\n" if not fresh
                else "NOT CONVERGED -- run another pass.\n")
    return out


def t_publication_screen(args):
    text = args.get("question") or ""
    hits = PB.screen(text)
    if not hits:
        return "NO REFUSAL CLASS TRIGGERED.\n\n" + PB.ENCOURAGE
    out = ["DO NOT PUBLISH THIS ONE.", ""]
    for nm, why in hits:
        out += ["class: " + nm, why, ""]
    out.append("The objection is not that the answer is uncertain. It is "
               "that publishing the answer changes what the answer is for.")
    return "\n".join(out)



def t_evidence(args):
    """GRADE certainty against a decision threshold, plus severity."""
    lo, hi = args.get("low"), args.get("high")
    th = args.get("threshold")
    if lo is not None and hi is not None and th is not None:
        v, expl = EV.decides(float(lo), float(hi), float(th))
        out = ["CHECKING WHETHER THIS INTERVAL SETTLES THE DECISION", "",
               "   interval    {:.1%} to {:.1%}".format(float(lo),
                                                        float(hi)),
               "   threshold   {:.1%}".format(float(th)), "",
               "   " + v, EV.wrap(expl, 64, "   "), ""]
        if v == "STRADDLES":
            out += [EV.wrap(
                "Narrowing the estimate is worth paying for HERE and "
                "only here. In the decided cases, more precision buys "
                "nothing.", 64, "   "), ""]
        out += ["", _cap(EV.main)]
        return "\n".join(out)
    if args.get("worked"):
        return _cap(EV.worked)
    return _cap(EV.main)


def t_loop(args):
    """Can you just go and measure instead? The four gates."""
    if args.get('cases'):
        return _cap(LP.cases)
    tc = args.get('t_change')
    if tc is not None:
        tl = args.get('t_loop')
        out = [LP.check(tl, float(tc), args.get('unit', 'units')), '']
        sg = args.get('sigma'); dl = args.get('delta')
        av = args.get('cycles_available')
        if sg is not None and dl is not None and av is not None:
            n, v, ex = LP.resolution(float(sg), float(dl), float(av))
            out += ['', 'GATE 3 -- CAN A CYCLE TELL SIGNAL FROM NOISE?',
                    '', '   on paper       n = (sigma / delta)^2']
            if n is not None:
                out.append('   substituted    n = ({} / {})^2 = '
                           '{:.0f}'.format(sg, dl, n))
            out += ['',
                    '   LEGEND',
                    '     n       cycles needed to see a real change',
                    '     sigma   the spread of the noise, cycle to '
                    'cycle',
                    '     delta   the real movement you want to see',
                    '     /       divided by',
                    '     ^2      squared -- averaging n observations',
                    '             shrinks noise only by the square '
                    'root of n',
                    '', '   ' + v, LP.wrap(ex, 64, '   '), '']
        out += ['', _cap(LP.main)]
        return chr(10).join(out)
    return _cap(LP.main)


def t_operation(args):
    """Which of the eighteen operations is this, and what does it open?"""
    name = args.get("operation")
    if name:
        try:
            o = OP.by_id(name)
        except KeyError:
            return ("No operation '{}'. The eighteen are: {}".format(
                name, ", ".join(x["id"] for x in OP.OPERATIONS)))
        return _cap(lambda: OP.show(o))
    return _cap(OP.main)


def t_ancestry(args):
    """Where each module in this toolkit already existed."""
    return _cap(AN.main)


def t_steelman(args):
    """The seven questions to ask BEFORE the eleven."""
    name = args.get("case")
    if name and name in SM.CASES:
        return _cap(SM.report, name) + "\n" + SM.public_block(name)
    out = [_cap(SM.main)]
    if args.get("claim"):
        out += ["", "=" * 70,
                "  THE CLAIM YOU PASSED", "=" * 70, "",
                SM.wrap(args["claim"], 66, "   "), "",
                "Answer the seven above against it. The two that get "
                "skipped",
                "most often are `what_you_supplied` -- which is the "
                "only thing",
                "separating a steelman from a different claim of your "
                "own -- and",
                "`which_are_you_auditing`, which is where the switch "
                "happens.", ""]
    return "\n".join(out)


def t_mirror(args):
    """Run the eleven questions back on your own correction."""
    name = args.get("case")
    if name and name in MR.CASES:
        return _cap(MR.report, name) + "\n" + MR.public_block(name)
    return _cap(MR.main)


def t_route(args):
    """The eleven shape questions, with names and sources."""
    if args.get("split"):
        return _cap(RT.split_report)
    cat = args.get("category")
    if cat:
        if cat not in RT.CATEGORIES:
            return ("No category '%s'. The four are: %s"
                    % (cat, ", ".join(RT.CATEGORIES)))
        ss = RT.by_category(cat)
        m = RT.CATEGORIES[cat]
        out = [cat.upper().replace("_", " "), "",
               RT.wrap(m["what"], 66, "   "), "",
               "DETECT BY ASKING", RT.wrap(m["detect"], 64, "   "),
               "AND THE OUTPUT IS", RT.wrap(m["output"], 64, "   "), "",
               "WHEN IT IS VISIBLE", RT.wrap(m["visible"], 64, "   "), "",
               "WHOSE IT IS", RT.wrap(m["ours"], 64, "   "), "",
               "SHAPES"]
        for s in sorted(ss, key=lambda x: -x["fired"]):
            out.append("   {:<24}{:>4} fires".format(
                s["id"], s["fired"]))
        return "\n".join(out)
    sid = args.get("shape")
    if sid:
        try:
            s = RT.by_id(sid)
        except KeyError:
            return ("No shape '%s'. The eleven are: %s"
                    % (sid, ", ".join(x["id"] for x in RT.SHAPES)))
        return "\n".join([
            "SHAPE: " + s["id"],
            "", "ASK", RT.wrap(s["question"], 66, "   "),
            "", "FORMULA: " + s["formula_name"],
            RT.wrap(s["source"], 66, "   "),
            "", "ON PAPER", "   " + s["paper"],
            "", "EXTRACT: " + s["extract"],
            "", "THEN ALSO SHOW", RT.wrap(s["then"], 66, "   "),
            "", "WHY IT MATTERS", RT.wrap(s["why"], 66, "   "), ""])
    return _cap(RT.main)


def t_constant(args):
    """Published effect sizes, with the scope conditions welded on."""
    cid = args.get("id")
    if not cid:
        return _cap(KC.table)
    try:
        KC.get(cid)
    except KeyError:
        return ("No constant '%s'. The catalogue is: %s\n\nCall with no "
                "arguments for the full table, the three admission "
                "filters, and the rejected list."
                % (cid, ", ".join(c["id"] for c in KC.CONSTANTS)))
    out = _cap(KC.show, KC.get(cid))
    ap = args.get("apply")
    if ap:
        try:
            out += KC.apply(cid, **ap)
        except KeyError as e:
            out += "\nNo apply() for %s, or a required argument is " \
                   "missing: %s\n" % (cid, e)
        except (ValueError, TypeError) as e:
            out += "\nCANNOT COMPUTE: %s\n" % e
    return out


def t_theory_slot(args):
    """Which of the three slots does a candidate theory belong in?"""
    name = args.get("theory") or "(unnamed)"
    keys = ("has_interval", "tested_out_of_sample", "has_dataset")
    if any(args.get(k) is None for k in keys):
        return ("Answer all three before this can route anything. They "
                "are yes/no about the LITERATURE, not about the theory's "
                "plausibility:\n\n  1. %s\n  2. %s\n  3. %s\n\nIf you do "
                "not know, the answer is no -- a coefficient you cannot "
                "cite is one you would have to invent." % tuple(KC.THREE_FILTERS))
    a, b, c = (bool(args[k]) for k in keys)
    slot, why = KC.grade(a, b, c)
    o = ["THEORY: " + name, "", "   %-58s %s" % (KC.THREE_FILTERS[0],
                                                 "yes" if a else "NO"),
         "   %-58s %s" % (KC.THREE_FILTERS[1], "yes" if b else "NO"),
         "   %-58s %s" % (KC.THREE_FILTERS[2], "yes" if c else "NO"),
         "", "=" * 66, "  " + slot, "=" * 66, "", KC.wrap(why, 64, "   "),
         ""]
    if not slot.startswith("SLOT 2"):
        o += [KC.wrap(
            "It can still do real work -- a slot-1 theory decomposes a "
            "claim into the steps that must all hold, which is exactly "
            "what `chain` takes. What it must not do is hand you a "
            "number. Price the steps yourself and say you did.",
            64, "   "), ""]
    return "\n".join(o)


def t_instability_score(args):
    """PITF instability model. Named profile, or an inline one."""
    if args.get("card_only"):
        return _cap(PF.model_card)

    name = args.get("profile")
    if name and name in PF.PROFILES:
        return _cap(PF.model_card) + "\n" + _cap(PF.report, name)

    regime = args.get("regime")
    if not regime:
        return ("Pass either `profile` (one of: %s) or `regime` plus the "
                "other three variables.\n\nRegime categories: %s"
                % (", ".join(PF.PROFILES), ", ".join(PF.REGIME)))
    if regime not in PF.REGIME:
        return ("Unknown regime '%s'. The model's five categories are: %s\n"
                "Note it does NOT use the composite Polity score -- the "
                "categories come from the EXREC and PARCOMP components, and "
                "factionalism is PARCOMP=3."
                % (regime, ", ".join(PF.REGIME)))

    imr = args.get("imr_percentile")
    if imr is None:
        return ("`imr_percentile` is required: the country's position in the "
                "GLOBAL distribution of infant mortality, 0-100, where lower "
                "is safer. It is the second-largest term in the model and "
                "the one most applications leave out. Rich countries sit "
                "near 5-15; the world median is 50 by definition.")
    nb = int(args.get("neighbours_at_war", 0))
    di = bool(args.get("discrimination", False))

    dist = PF.ranking()
    z = PF.score(regime, imr, nb, di)
    rank = PF.percentile_of(z, dist)
    fl = PF.flagged(z, dist)
    r = PF.annual_risk(z, dist)
    b = PF.base_rates()

    out = [_cap(PF.model_card), ""]
    out += ["=" * 70,
            "  THIS PROFILE",
            "=" * 70, ""]
    out += ["   regime type           %s  (coef %+.3f, OR %.2f)"
            % (regime, PF.REGIME[regime][0], PF.REGIME[regime][1]),
            "   infant mortality      %gth percentile globally  (%+.3f)"
            % (imr, PF.IMR_COEF * PF.imr_scale(imr)),
            "   neighbours at war     %d  (%+.3f, threshold is 4)"
            % (nb, PF.NEIGHBOURS_COEF if nb >= 4 else 0.0),
            "   state discrimination  %s  (%+.3f)"
            % ("yes" if di else "no", PF.DISCRIM_COEF if di else 0.0),
            "   " + "-" * 60,
            "   risk score            %+.3f log-odds vs the reference" % z,
            ""]
    out += ["   world ranking         %.0fth percentile" % rank,
            "   top-quintile flag     %s" % ("INSIDE" if fl else "OUTSIDE"),
            "   cut sits at           %+.3f" % dist[int(0.80*len(dist))],
            ""]
    out += ["  THE ANSWER, BOTH DIRECTIONS", "  " + "-" * 60, ""]
    out += ["   About %.1f in 100 chance per year that an instability onset"
            % (r * 100),
            "   BEGINS -- a civil war, an ethnic war, or an adverse regime",
            "   change, and the model does not say which. Which is the same",
            "   as about %.1f in 100 that no onset begins in a given year."
            % ((1 - r) * 100),
            "",
            "   Against the world base rate of %.1f in 100 per country-year,"
            % (b["overall"] * 100),
            "   that is %.1f times an average country's risk."
            % (r / b["overall"]),
            ""]
    warns = PF.extrapolating(imr, regime, nb)
    if warns:
        out += ["  WHAT IS OUTSIDE THE FITTED RANGE", "  " + "-" * 60, ""]
        for w in warns:
            out += ["   " + ln for ln in DC.wrap(w, 66)] + [""]
    return "\n".join(out)



def _load_chain(args):
    """A chain comes either inline or by saved name, same as a decision."""
    if args.get("chain"):
        return args["chain"]
    if args.get("name"):
        return CN.load(args["name"])
    raise ValueError("pass either `chain` (inline) or `name` (saved)")


def t_claim_rows(args):
    act = args.get("action", "list")
    if act == "list":
        return CRW.listing(args.get("entry"))
    if act == "show":
        if not args.get("id"):
            raise ValueError("pass `id` to show one row")
        return CRW.show(args["id"])
    if act == "sticking":
        return CRW.sticking(args.get("field"))
    if act == "add":
        if not args.get("rows"):
            raise ValueError("pass `rows`: one row or a list of rows")
        return CRW.add(args["rows"], args.get("reason", ""))
    raise ValueError("action must be list, show, sticking or add")


def _needs_gapmap(fn):
    """The gap-map tools read data built on this machine; say so instead of failing."""
    def run(args):
        if not os.path.exists(os.path.join(GT.GAPMAP, "convergent", "capability_topics.json")):
            return ("The gap map has not been built on this machine (the gapmap/ folder is "
                    "empty). Build it with the gap-map scripts in harness/ (gapmap.py, "
                    "gapmap_topics.py, gapmap_daily.py), then run this again.")
        return fn(args)
    return run


def t_chain(args):
    return _cap(CN.report, _load_chain(args))


def t_plan_audit(args):
    gut = args.get("gut")
    if gut is not None and not 0.0 <= float(gut) <= 1.0:
        raise ValueError("`gut` is a probability between 0 and 1")
    return _cap(CN.plan_audit, _load_chain(args),
                float(gut) if gut is not None else None)


def t_trial_worth(args):
    d = _load_decision(args)
    rows = []

    def run():
        rows.extend(DC.test_value_report(
            d, args["belief"], float(args["outcome_sd"]), args.get("days"),
            args.get("cost_per_day"), float(args.get("fixed_cost") or 0.0),
            float(args.get("unblind_bias") or 0.0), args.get("horizon_days")))
    txt = _cap(run)
    return txt + ("\n" + json.dumps(rows, indent=2) if rows else "")


def t_chain_list(args):
    fs = sorted(f[:-5] for f in os.listdir(CN.CHAINS) if f.endswith(".json"))
    return "chains: " + ", ".join(fs)


def t_chain_save(args):
    name = args["name"]
    if not name.replace("_", "").replace("-", "").isalnum():
        raise ValueError("name must be alphanumeric with _ or -")
    d = args["chain"]
    _cap(CN.report, d)                 # fail here rather than on disk
    p = os.path.join(CN.CHAINS, name + ".json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    return f"saved to harness/chains/{name}.json"


def t_chain_elicit(args):
    d = _load_chain(args)
    return _cap(CN.elicit, d, args.get("name", "adhoc"))


def t_chain_panel(args):
    name = args.get("name")
    if not name:
        raise ValueError("`name` is required -- the panel reads the saved "
                         "chain to compare sheets against")
    return _cap(PN.chain_report, name, args.get("sheets") or [])



def t_decide_panel(args):
    name = args.get("name")
    if not name:
        raise ValueError("`name` is required -- the panel compares sheets "
                         "against the saved decision")
    return _cap(PN.report, name, args.get("sheets") or [])


# ---------------------------------------------------------------------
# THE STANDING RULE. Sent once, as the server's `instructions` in the
# initialize reply, and summarised in SHOW_WORK_SHORT at the head of every
# tool description, so a client that drops the instructions still sees the
# core of it. (It used to be prepended in full to all 47 descriptions:
# about 140,000 characters of the 200,000 in the tool list.) Set as an
# instruction to the caller rather than a feature of the code, because the
# code cannot make a model explain itself -- only the description can.
# ---------------------------------------------------------------------

SHOW_WORK = (
    "ALWAYS SHOW THE MATHS. This is a standing rule of this server and "
    "it applies to every tool in it, without exception and without being "
    "asked.\n\n"
    "Whenever you report a number that came out of this server:\n"
    "  1. SAY WHAT YOU ARE CHECKING. Quote the claim in full, name who "
    "said it and where, and state in words what the number measures -- "
    "all BEFORE any arithmetic. AND STATE THE STRONGEST VERSION, not "
    "just the wording: somebody's words are a lossy encoding of their "
    "argument, and auditing the encoding while reporting on the "
    "argument produces findings that are true about a point nobody was "
    "making. Call the `steelman` tool first, declare what you supplied "
    "to build the strong version, and say which version you are "
    "checking. If you refute the wording and the argument survives, "
    "that is a FAILURE STATE, not a finding. "
    "If you report a count, LIST THE ITEMS: "
    "'3 of 8' with the eight never shown is not an argument, it is a "
    "demand to be trusted. Never refer to something as though the "
    "reader already knows it. THE TEST IS THAT SOMEONE WHO NEVER SAW "
    "THE ORIGINAL CAN FOLLOW THE WHOLE REPLY. Length is not the "
    "constraint; being complete beats being short.\n"
    "  2. Write the formula in standard notation.\n"
    "  3. Write it again with the actual numbers substituted in.\n"
    "  4. Give a legend defining EVERY symbol in plain English, next to "
    "the formula and not in a block at the top that scrolls away. Define "
    "symbols by what they DO -- 'the capital sigma means add these up', "
    "'D is the gap between the top two options' -- not by their name.\n"
    "     EVERY SYMBOL INCLUDES THE OPERATORS, not just the quantities "
    "that have names. Go through the formula mark by mark, left to "
    "right. The integral sign, the sigma, the product sign, the root, "
    "the intersection and union, 'is in', the absolute-value bars, max "
    "and min, the limits above and below a sign, and any dummy variable "
    "that exists only inside an operator -- each needs a line. These "
    "are the marks a reader most needs and the easiest to skip, because "
    "having no name they read as punctuation. harness/router.py's "
    "NOTATION dict holds a plain-English definition for each and "
    "check_legend() will refuse to render a block that omits one.\n"
    "     AND IF THE OPERATOR IS DOING NO WORK, DROP IT. An integral is "
    "warranted only when the rate actually varies; if it is constant, "
    "write the multiplication and show no integral at all.\n"
    "  5. State every percentage BOTH WAYS and say what it measures. "
    "Never a bare percent. '7 in 100 of the countries it flags have an "
    "onset, 93 in 100 do not' -- not '7%'.\n"
    "  6. Say which parts are standard textbook method and which you "
    "improvised, because the improvised parts are where the errors "
    "actually are.\n\n"
    "IF THERE IS NO DERIVATION, SAY SO EXPLICITLY -- 'this is a lookup, "
    "not a calculation' is useful information. Do not silently omit the "
    "working section.\n\n"
    "WHY: the working is there so the reader can "
    "check the reasoning rather than trust the output. A formula nobody "
    "can read is worse than no formula, because it looks authoritative.\n")

SHOW_WORK_SHORT = (
    "STANDING RULE, ALWAYS SHOW THE MATHS (full text in this server's "
    "instructions): quote the claim in full and steelman it first; list "
    "the items behind any count; formula, then numbers substituted, then "
    "a legend for every symbol and operator; every percentage both ways; "
    "say what is standard and what is improvised; if there is no "
    "derivation, say so.\n\n---\n\n")


TOOLS = {
 "simulate_futures": (SF.tool,
   "SIMULATE MANY FUTURES FOR A DRUG, THEN COUNT (the method of Epic's "
   "Curiosity model, with the next step copied from similar past drugs "
   "instead of learned). Histories come from ClinicalTrials.gov phases and "
   "first FDA approvals in gapmap/history.db. Pass `conditions` (comma-"
   "separated words that define similar drugs, e.g. 'alzheimer'), `stage` "
   "(1, 2 or 3), `years_in` (years already spent at that stage), `horizon` "
   "(years), or `drug` (a name: its own history sets the start). Returns the "
   "share of simulated futures approved within the horizon, given both ways, "
   "where the rest ended, and a plain-count check. Approvals filed under a "
   "different name than the trial used are missed, so the share runs low.",
   {"type": "object", "properties": {
      "conditions": {"type": "string"}, "stage": {"type": "integer"},
      "years_in": {"type": "number"}, "horizon": {"type": "number"},
      "drug": {"type": "string"}, "sims": {"type": "integer"},
      "seed": {"type": "integer"}}}),

 "reference_models": (RM.tool,
   "THE STANDARD FORMAL MODEL FOR A TOPIC, so the steelman step has something "
   "real to hold a claim against. Call it AFTER `steelman` names the strongest "
   "version: it hands back the recognised equation for that topic, its legend, "
   "and the list of quantities the claim MUST supply, so the check becomes "
   "mechanical -- does the claim fill the terms or leave them empty. 26 models "
   "on ten shelves (war and escalation, terrorism and civil war, epidemics, "
   "collective behaviour, animal conflict, sex ratio and demography, economics "
   "and geography, adoption and technology, forecasting itself, and dose, "
   "feedback and learning), each marked "
   "[math] (substitute into it) or [logic] (establish its conditions). Pass "
   "`match` (words from the claim, e.g. 'will this spiral') to find the fitting "
   "model, `model` (an id) for the full entry with notation and needs, or "
   "`topic` (a shelf) to list one shelf. No argument lists all. It hands you "
   "the equation and what it needs; it does not fit parameters or decide the "
   "case.",
   {"type": "object", "properties": {
      "match": {"type": "string"}, "model": {"type": "string"},
      "topic": {"type": "string"}}}),

 "whats_new_for_gap": (_needs_gapmap(GT.whats_new_for_gap),
   "NEW PAPERS FOR ONE GAP MAP GAP, since the last look. Reads the daily sweep "
   "(papers matched to fixes and judged on topic by the daily reading). Pass "
   "`gap` (a gap name or fragment, or a pilot-node name); `since` (YYYY-MM-DD) or `days`; `mark_seen: true` to record "
   "today as the last look so the next call returns only newer papers. "
   "Counted, but 'on topic' is a judgement, and only fixes tagged for the "
   "sweep are covered.",
   {"type": "object", "properties": {
      "gap": {"type": "string"}, "since": {"type": "string"},
      "days": {"type": "integer"}, "limit": {"type": "integer"},
      "mark_seen": {"type": "boolean"}}, "required": ["gap"]}),

 "will_this_work": (_needs_gapmap(GT.will_this_work),
   "THE ODDS FOR ONE GAP MAP FIX: its counted base rate (s of n similar "
   "attempts and the rule of succession (s + 1) / (n + 2)), the forecast on "
   "the record for a near-term question, and what is known. For a fix with "
   "no counted base rate it says there are no odds rather than inventing "
   "them. Pass `fix` (a fix or pilot-node name or fragment).",
   {"type": "object", "properties": {"fix": {"type": "string"}}, "required": ["fix"]}),

 "claim_rows": (t_claim_rows,
   "ONE ROW PER CHECKED CLAIM, SO CLAIMS CAN BE COUNTED. A case checks a claim in "
   "prose; a row keeps the same fields for every claim: what was claimed and where, "
   "the gap-map entry it belongs to (`about`) and the one that blocks it "
   "(`blocked_by`), the evidence it rested on, the verdict (holds, partly, wrong), "
   "the milestone, and its routes: chains of steps, each with a chance `p`, a "
   "typical length `median` in years, years already `done`, a `kind` (funding or "
   "start, safety in people, first effect in people, confirmation, regulator) and "
   "`why`. A yearly-chance step uses `per_year` and `max_years` instead of p and "
   "median. Steps every route needs go in `shared`. Rows with no chain give "
   "`guessed` odds by year instead. The odds by 2030, 2035, 2040 and 2050 and the "
   "weakest step (dP/dp_j = P / p_j, the step worth most to improve) are computed, "
   "never typed in. An update keeps the old odds and the reason they changed.\n\n"
   "action `list` (optionally `entry`, a gap-map slug), `show` (`id`), `sticking` "
   "(optionally `field`): where known approaches get stuck, the weakest step of "
   "every row grouped by kind and by blocking gap-map entry, with every item "
   "listed. It ranks known options; it cannot invent new ones. `add` (`rows`, "
   "`reason`) saves or updates rows. Show the formula and its legend when you "
   "use the numbers.",
   {"type": "object", "properties": {
      "action": {"type": "string", "enum": ["list", "show", "sticking", "add"]},
      "id": {"type": "string"}, "entry": {"type": "string"},
      "field": {"type": "string"}, "reason": {"type": "string"},
      "rows": {}}}),

 "gaps_moving": (_needs_gapmap(GT.gaps_moving),
   "GAP MAP GAPS RANKED BY RECENT ACTIVITY: papers in the last `days` that "
   "the daily reading judged on topic, with the judged and unjudged "
   "counts beside them. Activity is not progress.",
   {"type": "object", "properties": {
      "days": {"type": "integer"}, "top": {"type": "integer"}}}),

 "decide_panel": (t_decide_panel,
   "READ BACK FILLED ELICITATION SHEETS FOR A DECISION and MEASURE the "
   "shared-author bias instead of assuming it.\n\n"
   "WHAT IT FIXES. `decide` carries one number it cannot justify: b, the "
   "shared-author term, set by assertion at 0.35. It exists because "
   "channels are not independent draws from the world -- one mind sets "
   "every range in one sitting, and if that mind is tilted every channel "
   "tilts the same way and the tilt never averages out. Without it, "
   "confidence is manufactured by counting channels. A panel is the only thing that turns b "
   "from a guess into a measurement:\n\n"
   "  z(a,i) = [ mu(a,i) - mean_a mu(a,i) ] / mean_a sigma(a,i)\n"
   "  B(a)   = mean_i [ z(a,i) * dir(i) ]\n"
   "  b      = sd across authors of B(a)\n\n"
   "dir(i) is +1 for a benefit and -1 for a cost, so an author who "
   "inflates every cost AND deflates every benefit registers as one "
   "large tilt rather than cancelling to zero.\n\n"
   "IF THE MEASURED b EXCEEDS THE ASSUMED ONE, every confidence figure "
   "the model has produced is too high, and the tool says so. If it "
   "comes in LOWER, that is not reassurance until you have checked the "
   "authors were independent -- agreement between near-copies measures "
   "nothing.\n\n"
   "OMISSIONS PRINT BEFORE ANY NUMBER. Splitting a channel leaves the "
   "mean untouched; omitting one is the only error here that can reverse "
   "a verdict.\n\n"
   "CHOOSE AUTHORS FOR DISAGREEMENT, NOT CAPABILITY. Averaging two "
   "authors correlated at rho leaves sqrt((1+rho)/2) of the tilt; at "
   "rho=1 there is no reduction at all however capable they are. Models "
   "from one family share training lineage and will correlate highly.\n\n"
   "An sd from two authors is barely an estimate -- treat it as an order "
   "of magnitude until there are four or five. Pass `sheets` to supply "
   "filled answers inline, or leave it empty to read "
   "harness/panels/<name>/. Generate blank sheets with `decide_elicit`.",
   {"type": "object", "properties": {
      "name": {"type": "string",
        "description": "Saved decision name. Required -- the panel "
                       "compares sheets against the saved decision."},
      "sheets": {"type": "array", "items": {"type": "object"},
        "description": "Filled sheets, inline. Each: {author, channels: "
                       "{<id>: {low, high, mode, k}}, missing[], "
                       "objections[]}."}},
    "required": ["name"]}),

 "chain": (t_chain,
   "USE THIS WHEN a claim needs several separate things to ALL go right -- 'X will happen, and then Y, and then Z'. People state compound claims with the confidence of their strongest link, and the size of that error is the whole reason this exists.\n\nPRICE A COMPOUND CLAIM -- something that happens only if several "
   "things all happen. Returns the product, which link kills it, how "
   "rough the whole thing is, and the near-term versions that can "
   "actually be scored.\n\n"
   "WHY THIS IS A DIFFERENT TOOL FROM `decide`. A decision compares "
   "options and its damaging error is double counting, which moves the "
   "mean. A chain multiplies conditional probabilities and its damaging "
   "error is the INDEPENDENCE ASSUMPTION, which nobody writes down.\n\n"
   "EVERY LINK AFTER THE FIRST MUST BE CONDITIONAL on the ones before "
   "it. Write the statement as 'Given X, ...'. A marginal multiplied as "
   "if conditional breaks the arithmetic invisibly, because both are "
   "decimals between 0 and 1.\n\n"
   "OPTIONAL BLOCKS worth having. `outside_view` prices a route the "
   "links do not describe, because an unlisted route is priced at zero "
   "silently while the product still looks complete. `regimes` names a "
   "common cause and prices every link twice, once in each of its "
   "worlds -- the only way to represent links that share a driver but "
   "respond to it with opposite signs, which a correlation coefficient "
   "cannot do. The arithmetic checks that regime values average back to "
   "the stated marginal, so a split cannot quietly revise a belief.\n\n"
   "THE OPPOSITE ERROR IS CHECKED TOO. Multiplying corrects "
   "overconfidence and, overdone, manufactures doom -- the multiple-stage "
   "fallacy (six 50% stages give 1.6%). A step can list other `routes` through it and a number "
   "of `attempts`, joined through a named `shared_block` {p, what} -- the "
   "one obstacle that would stop every route and retry at once -- so "
   "retries are not priced as fresh coins; the report prints both ends, "
   "all blocked by one thing and each failing for its own reasons. Every "
   "report ends with THE MULTIPLE-STAGE CHECK: stacked guessed middling "
   "steps, later steps that do not say what they assume, and no other "
   "way through anywhere.\n\n"
   "SHAPE: {claim, horizon_years, links:[{id, p, low, high, statement, "
   "basis, provenance, already_occurred?, p_by_regime?, attempts?, "
   "routes?:[{id, p, low?, high?, attempts?, statement?}], "
   "shared_block?:{p, what}}], outside_view?, regimes?, "
   "scoreable_version?}. See harness/chains/*.json.",
   {"type": "object", "properties": {
      "chain": {"type": "object", "description": "Inline chain spec."},
      "name": {"type": "string", "description": "Or a saved chain name."}}}),

 "plan_audit": (t_plan_audit,
   "USE THIS WHEN someone says a plan is nearly done, or 'it'll probably "
   "work', and you want to know how done it really is.\n\n"
   "HOW DONE IS THIS PLAN? Puts the person's own probability (`gut`) next "
   "to the product of the plan's steps, gives the spread with every step "
   "uncertain, names the step that swings the answer and the step to "
   "CHECK FIRST -- the one with the most to lose per unit of evidence "
   "behind it, its leave-one-out gain times the share of it that was not "
   "measured -- and says how far the gut number is from the steps, in "
   "odds as well as probability.\n\n"
   "IT ALSO RUNS THE MULTIPLE-STAGE CHECK, because an audit that only "
   "ever says 'less done than you think' is a pessimism machine, not an "
   "audit. It looks for Yudkowsky's three causes: stacked middling "
   "guesses (0.35-0.65 with nothing measured behind them, with the "
   "product recomputed at the top of their own ranges), later steps that "
   "do not say what they assume, and no other way through any step.\n\n"
   "SHAPE: the same chain as `chain`, inline or by saved name, plus an "
   "optional `gut` between 0 and 1. Use `chain` for the full working and "
   "`find_gaps` for the omission hunt.",
   {"type": "object", "properties": {
      "chain": {"type": "object", "description": "Inline chain spec."},
      "name": {"type": "string", "description": "Or a saved chain name."},
      "gut": {"type": "number",
        "description": "Your own probability that the plan comes off, "
                       "0 to 1, before seeing the steps."}}}),

 "chain_list": (t_chain_list,
   "List saved chains that can be rerun by name.",
   {"type": "object", "properties": {}}),

 "chain_save": (t_chain_save,
   "Save an inline chain so it can be rerun and revised. Renders it "
   "first, so a malformed chain fails here rather than on disk. Worth "
   "doing for anything you will revisit -- the point of saving is that "
   "when a link changes you rerun and see what moved, rather than "
   "re-arguing it from scratch.",
   {"type": "object", "properties": {
      "name": {"type": "string"}, "chain": {"type": "object"}},
    "required": ["name", "chain"]}),

 "chain_elicit": (t_chain_elicit,
   "EMIT A BLANK ELICITATION SHEET FOR A CHAIN. The statements with "
   "every number and every argument stripped out. Give it to a "
   "DIFFERENT model or person who has not seen the existing answer.\n\n"
   "This is not the decision sheet reworded. It forces the conditioning "
   "at every step, because an author who prices marginals when the "
   "model multiplies conditionals breaks the arithmetic without leaving "
   "a trace. It asks directly which links share a driver, because that "
   "is the chain-specific error and an author who prices four links "
   "without saying how they relate has answered the easy part. And it "
   "sends only the `statement` of each link, never the `basis` -- the "
   "basis is the argument for the number, and sending it hands the new "
   "author the old author's conclusion.\n\n"
   "WHY BOTHER: passes of a gaps run by the same author are the same "
   "prior re-expressed, not new evidence. This is the only thing that "
   "adds a genuinely separate source.\n\n"
   "CHOOSE FOR DISAGREEMENT, NOT CAPABILITY. Averaging two authors "
   "correlated at rho leaves sqrt((1+rho)/2) of the original tilt; at "
   "rho=1 there is no reduction at all however capable they are. A "
   "model from the same family shares training lineage and will "
   "correlate highly -- it will agree with you and the panel will "
   "report a false narrowing.",
   {"type": "object", "properties": {
      "chain": {"type": "object"}, "name": {"type": "string"}}}),

 "chain_panel": (t_chain_panel,
   "READ BACK FILLED ELICITATION SHEETS FOR A CHAIN and report what the "
   "claim comes to under each author.\n\n"
   "It reports a SPREAD, not a corrected number. A chain has no "
   "simulation and no confidence percentage, so there is no bias term "
   "to feed anywhere -- it has one number, and the useful thing a panel "
   "does to one number is show how far it moves when somebody else "
   "writes it. If three authors give 0.4%, 1.2% and 3%, the honest "
   "report of the claim is that range, and the file's third significant "
   "figure was never real.\n\n"
   "OMISSIONS PRINT BEFORE ANY NUMBER, because splitting a link does "
   "not move the answer and leaving out a route does. It also ranks "
   "which step the panel disagrees about most, which is NOT the same as "
   "which step the leave-one-out calls decisive: a step everyone agrees "
   "about cannot be improved by asking again.\n\n"
   "Pass `sheets` to supply filled answers inline, or leave it empty to "
   "read harness/panels/<name>/. The file's own numbers always appear "
   "as one author, named honestly, because leaving them out would hide "
   "the thing being tested.",
   {"type": "object", "properties": {
      "name": {"type": "string",
        "description": "Saved chain name. Required -- the panel compares "
                       "sheets against the saved chain."},
      "sheets": {"type": "array", "items": {"type": "object"},
        "description": "Filled sheets, inline. Each: {author, q?, links: "
                       "{<id>: {low,high,mode} or {<regime>: {low,high,"
                       "mode}}}, missing_routes[], dependencies[], "
                       "objections[]}."}},
    "required": ["name"]}),

 "instability_score": (t_instability_score,
   "USE THIS FOR ANY QUESTION ABOUT A COUNTRY COMING APART -- civil war, coup, collapse, a democracy sliding. It replaces a guess with published coefficients, and it is the only tool here whose numbers were measured by someone else rather than judged by whoever is asking.\n\nSCORE A COUNTRY ON THE PITF GLOBAL INSTABILITY MODEL -- Goldstone et "
   "al. (2010), AJPS 54(1):190-208, the model the CIA-convened Political "
   "Instability Task Force built. Four variables, fitted to 141 onsets "
   "across every country over 500,000 people, 1955-2003.\n\n"
   "THIS IS THE ONLY TOOL HERE WITH MEASURED COEFFICIENTS. Everything else "
   "computes over ranges somebody supplied. These are published numbers "
   "with published confidence intervals that can be checked against the "
   "paper.\n\n"
   "THE FOUR VARIABLES, and three of them get left out by people quoting "
   "this model:\n"
   "  regime type -- five categories, and partial democracy WITH "
   "factionalism carries an odds ratio of 36.91 against full autocracy. "
   "This is the one everybody quotes. Note the categories come from the "
   "Polity EXREC and PARCOMP components, NOT the composite Polity score; "
   "factionalism is PARCOMP=3. An argument that reaches a category via the "
   "headline Polity number has taken a road the model does not use.\n"
   "  infant mortality -- as a GLOBAL PERCENTILE, not a raw rate. OR 6.59 "
   "between the 75th and 25th percentiles. Second-largest term, and "
   "strongly protective for rich countries.\n"
   "  four or more bordering states at war -- OR 22.0. Off for most "
   "countries, which means a quarter of the model is inactive.\n"
   "  state-led discrimination -- OR 1.93. The smallest term.\n\n"
   "WHAT IT RETURNS IS A RANK, NOT A PROBABILITY, and that is the paper's "
   "design rather than a limitation of this implementation. The paper "
   "publishes no intercept and cannot: the design is case-control at one "
   "onset per three controls, so any fitted intercept describes a sample "
   "built at 25% instability rather than a world running at 1.7%. The "
   "authors rank countries and flag the top fifth. Absolute risk comes "
   "from their own out-of-sample table, and it is the same number for "
   "everyone on the same side of the cut.\n\n"
   "THE ACCURACY, BOTH WAYS. 'Right more than 80% of the time two years "
   "ahead' is true: 86% of onsets flagged, 81% of stable years cleared. "
   "From the same four cells: of the 251 country-years it FLAGGED, 18 had "
   "an onset -- 7 in 100, and 233 false alarms. A flag is a fourfold lift "
   "from a 1.7% base rate, not a prediction of collapse. Always report "
   "both.\n\n"
   "AN ONSET IS NOT A CIVIL WAR. Of 117 onsets, 65 began as civil war and "
   "49 as adverse regime change -- a significant move toward autocracy, "
   "not necessarily violent. Do not report a flag as a civil-war forecast."
   "\n\nPass `card_only` for the accuracy table alone.",
   {"type": "object", "properties": {
      "profile": {"type": "string",
        "description": "A saved profile name (call with no arguments to list "
                       "them). Or build one inline with the fields below."},
      "regime": {"type": "string",
        "description": "full_autocracy | partial_autocracy | "
                       "partial_dem_factional | partial_dem_nonfactional | "
                       "full_democracy. From Polity EXREC and PARCOMP, not "
                       "the composite score."},
      "imr_percentile": {"type": "number",
        "description": "Position in the GLOBAL infant-mortality "
                       "distribution, 0-100, lower is safer. Required for "
                       "an inline profile -- omitting it is the single most "
                       "common way this model gets misapplied."},
      "neighbours_at_war": {"type": "integer",
        "description": "Bordering states in major armed conflict. The "
                       "variable is a threshold at 4, not a count."},
      "discrimination": {"type": "boolean",
        "description": "State-led political or economic discrimination "
                       "against at least one minority, per Minorities at "
                       "Risk."},
      "card_only": {"type": "boolean",
        "description": "Return only the accuracy table."}}}),

 "find_gaps": (t_find_gaps,
   "USE THIS WHEN you are about to hand someone a number and you cannot say out loud what you left out of it.\n\nHUNT FOR WHAT IS MISSING AND WHAT IS IN THERE TWICE. Every other tool "
   "computes over what it is given; this is the only one that asks what is "
   "absent. Three passes:\n\n"
   "OVERLAP -- every pair of beliefs ranked by shared vocabulary, so the "
   "pairs that could plausibly be the same thing twice come first. Double "
   "counting moves the MEAN; correlation only moves the spread, so this is "
   "the more damaging of the two and the easier to miss.\n\n"
   "COUNTER -- for each belief, the strongest case its range is too high "
   "and too low. One-sided sourcing is invisible from inside a model.\n\n"
   "OMISSION -- eight error classes that have actually reversed an answer: "
   "a baseline that pays nothing, an option nobody listed, no wait option, "
   "someone bearing a cost with no term, two names for one thing, several "
   "beliefs from one source, the question not being the one asked, and what "
   "the opposite model looks like.\n\n"
   "THE CODE GENERATES THE QUESTIONS; A MODEL ANSWERS THEM. That direction "
   "matters: assigning probabilities is a calibration task and models are "
   "bad at it, while spotting that two paragraphs describe the same thing "
   "is recall, which fails differently. Pass `findings` back to log a pass "
   "and get told whether you have converged -- stop when a pass finds "
   "nothing new, not at a fixed depth.",
   {"type": "object", "properties": {
      "decision": {"type": "object"}, "chain": {"type": "object"},
      "name": {"type": "string"},
      "findings": {"type": "array", "items": {"type": "string"},
        "description": "What this pass found, to log and check convergence."}}}),

 "publication_screen": (t_publication_screen,
   "RUN THIS BEFORE PUBLISHING ANY ANSWER. Some questions get worse by "
   "being answered in public, and the test is not sensitivity -- it is "
   "whether a named party can MOVE THE INPUTS once they know the output.\n\n"
   "The clearest case is attribution. Publish a probability naming a "
   "suspect and you have published the scoring function an adversary needs "
   "in order to be misread; the model cannot detect a competent false flag "
   "because planted signals are exactly the signals it reads.\n\n"
   "Also screens target selection and probabilities attached to named "
   "private individuals. Everything else is cleared, and some questions get "
   "BETTER for being published: where several parties each run their own "
   "model, the disagreements separate a fight about facts from a fight "
   "about values, and only one of those is settleable.",
   {"type": "object", "properties": {
      "question": {"type": "string",
        "description": "The question or claim about to be published."}},
    "required": ["question"]}),

 "robust": (t_robust,
   "USE THIS WHEN someone says 'but you made those numbers up', or when you are about to act on a margin that looks comfortable. It answers the actual objection: how wrong could EVERY input be, at once, in the worst direction, before the answer flips. Report that number instead of the probability when talking to anyone sceptical.\n\nTHE CONCLUSIONS THAT DO NOT DEPEND ON THE WEIGHTS. Run this whenever "
   "someone doubts the numbers, which they should. Four standard analyses, "
   "each dropping an assumption the main report relies on:\n\n"
   "STOCHASTIC DOMINANCE -- if one option dominates another at first "
   "order, EVERY decision-maker who prefers more to less agrees, whatever "
   "their values and whatever their risk attitude. Second order is the "
   "same for risk-averse ones. No weight is consulted, so no weight being "
   "wrong can undo it. This is the strongest conclusion available.\n\n"
   "MINIMAX REGRET (Savage) -- drops probabilities entirely. Picks the "
   "option whose worst-case regret is smallest. When it disagrees with "
   "expected value, that disagreement is informative: expected value is "
   "right over many similar bets and strange for a single irreversible "
   "choice.\n\n"
   "ROBUSTNESS RADIUS -- how wrong can EVERY input be, at once, in the "
   "worst direction, before the answer flips. Exact under a linear "
   "payoff. Report this number rather than the probability when talking "
   "to someone sceptical, because it answers their actual objection.\n\n"
   "CHEAPEST ATTACK -- the minimum-effort change that reverses the "
   "verdict, solved in closed form. It names the belief an opponent "
   "should go after first.",
   {"type": "object", "properties": {
      "decision": {"type": "object"}, "name": {"type": "string"}}}),

 "trial_design": (t_trial_design,
   "DESIGN AN N-OF-1 TRIAL BEFORE RUNNING IT. Given the outcome's spread "
   "(sigma, in the outcome's own units) it returns the smallest effect the "
   "trial could detect, how many days a given effect would need, and the "
   "power you would actually have.\n\n"
   "Pass unblind_bias if the thing recording the outcome can tell which arm "
   "the day was in -- it reports that bias as a share of the smallest "
   "detectable effect. Above roughly half, the trial cannot separate a real "
   "minimum effect from the instrument leaning, and more days will not fix "
   "it: the bias does not shrink with n while the detectable effect does.",
   {"type": "object", "properties": {
      "sigma": {"type": "number",
        "description": "SD of the outcome measure, in its own units."},
      "days": {"type": "integer", "description": "Total days, both arms."},
      "effect": {"type": "number",
        "description": "Effect size worth detecting, same units as sigma."},
      "power": {"type": "number", "description": "Default 0.80."},
      "unblind_bias": {"type": "number",
        "description": "Suspected measurement bias if the outcome is not "
                       "blind to the assignment."}},
    "required": ["sigma"]}),

 "trial_worth": (t_trial_worth,
   "USE THIS WHEN someone is about to run a test to settle a decision and "
   "nobody has asked whether its answer could change the choice. A power "
   "calculation says whether a test can SEE an effect; this says whether "
   "seeing it is worth the days.\n\n"
   "IS THIS TEST WORTH RUNNING? Given a decision (inline or saved), the "
   "belief the test would measure, the daily outcome's SD, and how long "
   "the choice will last, it returns for several test lengths what the "
   "test is worth, what it costs, and the net:\n\n"
   "  SE       = sigma x sqrt(2 / (days/2))\n"
   "  worth(n) = EVSI(n) x periods left AFTER the test\n"
   "  net(n)   = worth(n) - fixed_cost - cost_per_day x n\n\n"
   "EVSI is `decide`'s own value of a noisy signal, with the noise set by "
   "the test instead of by history. By default a test day costs half the "
   "current gap between the top two options, because a two-arm test "
   "spends half its days on the one you would otherwise not pick. A "
   "belief that cannot change the choice has EVPI = 0 and gets 'don't "
   "run it for this decision'. An instrument that can see the arm adds a "
   "floor under the noise that more days cannot shrink.\n\n"
   "UNITS. If the decision's unit is a rate (per day, per year), pass "
   "`horizon_days`; otherwise the report warns and counts one period "
   "only. Long tests inside a short horizon lose, because the answer "
   "only pays once it has arrived. The net-benefit idea is ENBS, as in "
   "voiage (Apache-2.0).",
   {"type": "object", "properties": {
      "decision": {"type": "object", "description": "Inline decision."},
      "name": {"type": "string", "description": "Or a saved decision."},
      "belief": {"type": "string",
        "description": "Id of the belief the test would measure."},
      "outcome_sd": {"type": "number",
        "description": "SD of the daily outcome, in the belief's units."},
      "days": {"type": "array", "items": {"type": "integer"},
        "description": "Test lengths to price. Default 14, 28, 56, 112, "
                       "224."},
      "cost_per_day": {"type": "number",
        "description": "Cost of one test day in the decision's unit. "
                       "Default: half the gap between the top two "
                       "options."},
      "fixed_cost": {"type": "number", "description": "Default 0."},
      "unblind_bias": {"type": "number",
        "description": "Bias if the instrument can see the arm. Default 0."},
      "horizon_days": {"type": "number",
        "description": "Days from now the choice will apply for. Needed "
                       "when the decision's unit is a rate."}},
    "required": ["belief", "outcome_sd"]}),

 "trial_assign": (t_trial_assign,
   "GET THE ARM FOR A DAY, OR THE WHOLE SCHEDULE. Assignment is a hash of "
   "trial id and date, not a fresh coin.\n\n"
   "That is deliberate and it matters more than it sounds. A fresh random "
   "draw each morning leaves nothing to stop a re-roll after a bad night, "
   "and the person best placed to do that is the person the trial is about. "
   "A hash means the entire schedule exists before day one, anyone can "
   "recompute it, and re-running returns the same answer.\n\n"
   "The assignment may be as visible as you like. The OUTCOME is what has "
   "to be blind.",
   {"type": "object", "properties": {
      "trial_id": {"type": "string"},
      "day": {"type": "string", "description": "ISO date, for one day."},
      "days": {"type": "integer",
        "description": "Or a count, for the whole schedule."},
      "start": {"type": "string", "description": "ISO start date."},
      "arms": {"type": "array", "items": {"type": "string"}}},
    "required": ["trial_id"]}),

 "trial_analyse": (t_trial_analyse,
   "ANALYSE A FINISHED OR RUNNING TRIAL. Takes rows of {arm, outcome} and "
   "returns the difference in means, its standard error and confidence "
   "interval, the observed sigma, and the smallest effect the trial could "
   "have detected.\n\n"
   "ALWAYS PASS `blinded`. If the instrument recording the outcome could "
   "see the assignment, say so -- the result is then an upper bound on the "
   "real effect rather than an estimate of it, and the tool says so in the "
   "output. Randomising protects the assignment; only blinding protects "
   "the measurement. They are different guarantees.",
   {"type": "object", "properties": {
      "rows": {"type": "array", "items": {"type": "object"},
        "description": "[{\"arm\": \"A\", \"outcome\": 3.0}, ...]"},
      "blinded": {"type": "boolean",
        "description": "Could the thing recording the outcome tell which "
                       "arm the day was in? false means it could."}},
    "required": ["rows"]}),

 "decide": (t_decide,
   "USE THIS WHEN you are about to recommend one option over another and the numbers behind the recommendation are judgements rather than measurements -- which is most of the time. It will not tell you the answer is right. It will tell you which of your beliefs cannot possibly change it, and the exact value at which each one would flip it, and those are the two things worth knowing.\n\nCOMPUTE A DECISION UNDER UNCERTAINTY. Give it options, and beliefs held "
   "as RANGES (low/high/mode) rather than numbers, and it returns which "
   "option wins, how confident that is as a percentage, which beliefs cannot "
   "change the answer, the exact value at which each one would flip it, and "
   "what further research is worth.\n\n"
   "WHAT IT DOES: computes what the stated beliefs IMPLY. Compounding "
   "uncertainty across many terms is something human intuition does badly, "
   "and this does it exactly.\n\n"
   "WHAT IT DOES NOT DO, and this matters: it does not derive the beliefs "
   "from data. It cannot look at a history of anything -- meals, trades, "
   "symptoms, past choices -- and tell you an effect size. Somebody must "
   "supply each range and say where it came from. A made-up range drives the "
   "answer exactly as hard as a measured one, so the report states what "
   "share of the total uncertainty was guessed.\n\n"
   "SHAPE: each option is a set of +1/-1/0 coefficients on the beliefs, plus "
   "an optional constant. Payoffs are LINEAR. Every belief should carry "
   "`provenance` (measured | estimated | guessed) and, where a reference "
   "class exists, a `history` block with `signal_sd` -- the absolute error "
   "of the historical evidence, IN THE BELIEF'S OWN UNITS. A belief with no "
   "history block reports that the past cannot inform it.\n\n"
   "Set answer_only for just the verdict and confidence.",
   {"type": "object", "properties": {
      "decision": {"type": "object",
        "description": "Inline spec: decision, unit, uncertainties[], "
                       "options[]. See harness/decisions/*.json for shape."},
      "name": {"type": "string", "description": "Or a saved decision name."},
      "answer_only": {"type": "boolean",
        "description": "Return only the verdict block, not the working."}}}),

 "decide_list": (t_decide_list,
   "List saved decisions that can be rerun by name.",
   {"type": "object", "properties": {}}),

 "decide_save": (t_decide_save,
   "Save an inline decision so it can be rerun, revised and compared later. "
   "Worth doing for anything recurring -- the point of saving is that when a "
   "belief changes you rerun and see what moved, rather than re-arguing it.",
   {"type": "object", "properties": {
      "name": {"type": "string"}, "decision": {"type": "object"}},
    "required": ["name", "decision"]}),

 "decide_elicit": (t_decide_elicit,
   "Emit a BLANK elicitation sheet for a decision: the channel list with "
   "every number stripped out and every judgement about magnitude or "
   "evidence quality removed. Give it to a DIFFERENT model or person who "
   "has not seen the existing estimates. The disagreement between the "
   "filled sheets measures how much the answer depends on whoever wrote it. "
   "Independence is what makes this worth doing, not capability: two "
   "authors who share a prior reduce the shared error by almost nothing, "
   "however strong they are.",
   {"type": "object", "properties": {
      "decision": {"type": "object"}, "name": {"type": "string"}}}),


 "audit": (t_audit,
   "RUN THIS FIRST. Takes a question object and runs every check in "
   "cheapest-first order, short-circuiting when one fails: budget, frame, "
   "lineage, entailment, ledger. Most questions die at stage 1 in seconds, "
   "and you never have to write the later sections. The question object may "
   "contain only the sections it got far enough to need.",
   {"type": "object", "properties": {
      "question": {"type": "object"}, "name": {"type": "string"}},
    "required": ["question"]}),

 "check_budget": (t_check_budget,
   "USE THIS BEFORE DECIDING WHAT TO MEASURE, and before writing any model at all. It takes seconds and it kills most questions outright: the number of variables your evidence can actually carry is roughly the square root of your independent case count, and almost every model anyone builds has more moving parts than its evidence supports.\n\nCHEAPEST CHECK, RUN BEFORE CHOOSING VARIABLES. Given a reference class "
   "and its cases, returns how many variables the sample can actually carry "
   "(roughly sqrt of the usable case count, further reduced when cases "
   "cluster). Discounts cases that fail transport, and counts independent "
   "groups rather than raw cases. If you have listed variables it tells you "
   "how many to cut.",
   {"type": "object", "properties": {"question": {"type": "object"}},
    "required": ["question"]}),

 "check_frame": (t_check_frame,
   "Is the question answerable at all? Forces it into six slots and catches: "
   "comparison to an imaginary ideal (the nirvana fallacy), claims with no "
   "measure attached, measures that are not counts of anything, measures "
   "observable for only one system, and whether the underlying value is "
   "actually disputed — which decides whether a single verdict is permitted.",
   {"type": "object", "properties": {"frame": {"type": "object"}},
    "required": ["frame"]}),

 "check_lineage": (t_check_lineage,
   "USE THIS WHEN a claim is widely repeated and you are about to treat the repetition as evidence. Forty citations with one origin is one source with an echo, and the difference is invisible until you walk the graph backwards.\n\nHow many INDEPENDENT origins does a claim have, as opposed to citations? "
   "Walks the citation graph backwards and collapses everything that traces "
   "to a shared ancestor. Flags disqualifying origins (fiction, retracted, "
   "fabricated, derived-by-arithmetic) and origins that benefit from the "
   "claim. Forty citations with one origin is one source with an echo.",
   {"type": "object", "properties": {"claim": {"type": "object"}},
    "required": ["claim"]}),

 "check_entailment": (t_check_entailment,
   "USE THIS WHEN you have good sources and are about to state something slightly stronger than they support. That gap is the most common way careful work goes wrong, and it is invisible from the inside -- a claim can pass every sourcing check with six excellent references and still fail this badly.\n\nDoes the evidence support THIS claim or a weaker neighbour? Nine gap "
   "types: scope, quantity substitution, missing variable, population, "
   "mechanism assumed, composition, target substitution, temporal, "
   "direction. Returns the strongest claim the evidence actually supports. "
   "A claim can pass lineage with six excellent sources and fail this badly.",
   {"type": "object", "properties": {"claim": {"type": "object"}},
    "required": ["claim"]}),

 "ledger_add": (t_ledger_add,
   "USE THIS THE MOMENT YOU STATE A PROBABILITY, before you find out whether you were right, and before you know the answer. Nothing downstream in this toolkit means anything without it: a probability that was never written down in advance cannot be scored, and a forecaster who cannot be scored cannot improve. This is the step every working forecasting system starts from, and it is the one a model will never take on its own.\n\nPREFER CLAIMS THAT RESOLVE IN MONTHS. A claim resolving in twenty-five years gives one data point in twenty-five years, and no amount of further analysis on it will teach you anything in the meantime. If the question is long-horizon, log the near-term claim the same belief implies instead, and log that too.\n\nWrite a prediction down BEFORE checking it. Requires resolution criteria "
   "and a baseline — decide afterwards what would have counted and you will "
   "decide you were right; skip the baseline and you will never know whether "
   "your reasoning beat the dumb answer. Give the reasoning mode and the "
   "topic as separate lists (`mode`, `topic`). Where a market prices the "
   "question, the market price IS the baseline. A corrected probability is "
   "stored alongside yours, pulled toward the baseline by the k the record "
   "supports; both are scored.",
   {"type": "object", "properties": {"claim": {"type": "object"}},
    "required": ["claim"]}),

 "ledger_status": (t_ledger_status,
   "Open claims and which are due for resolution now.", OBJ),

 "ledger_score": (t_ledger_score,
   "USE THIS BEFORE TRUSTING YOUR OWN CONFIDENCE, and especially before "
   "telling someone you are 80% sure of anything. " + _ledger_blurb() +
   " Check before claiming.\n\nCalibration report: Brier score against the "
   "baseline's, directional bias, a calibration table, reasoning modes and "
   "topics separately, and whether correcting toward the baseline helps. "
   "Being wrong on average is useless; being wrong in one specific mode is "
   "fixable.", OBJ),

 "ledger_resolve": (t_ledger_resolve,
   "Record what actually happened for an open claim. Every rerun of the same "
   "question resolves with it. If the question genuinely cannot be settled, "
   "pass unresolvable: true instead of an outcome -- it is closed and left "
   "out of the score, which is honest; forcing it to false is not. A claim "
   "that is not yet due stays open unless `early` says why (a settled market, "
   "or an event that has plainly happened). A question about what the research "
   "says (literature-check, replication-forecast, search-prediction) is never "
   "scored before its date unless `force` is true.",
   {"type": "object", "properties": {
      "id": {"type": "string"}, "outcome": {"type": "boolean"},
      "unresolvable": {"type": "boolean"},
      "note": {"type": "string"},
      "early": {"type": "string",
                "description": "Why closing before the date is right."},
      "force": {"type": "boolean"}},
    "required": ["id"]}),

 "ledger_rerun": (t_ledger_rerun,
   "USE THIS WHEN NEW INFORMATION CHANGES AN OPEN FORECAST. Never edit the "
   "old number: overwrite, and you can always 'update' to the answer the day "
   "before it resolves and look brilliant. This logs a new dated forecast on "
   "the same question, pointing at the one it revises; both are scored. "
   "Optionally pass a new baseline, e.g. a fresh market price, as "
   "{probability, what}.",
   {"type": "object", "properties": {
      "id": {"type": "string"},
      "probability": {"type": "number"},
      "reasoning": {"type": "string"},
      "baseline": {"type": "object"}},
    "required": ["id", "probability", "reasoning"]}),

 "ledger_calibrate": (t_ledger_calibrate,
   "How much of your own judgment the record says to keep. Fits k in "
   "p_corrected = b + k(p_raw - b) on every resolved forecast, shows the "
   "working, and runs the honest test: leave-one-out, so no forecast is "
   "corrected with a k that saw its own answer. Run it before stating any "
   "probability you have not checked.", OBJ),

 "ledger_due": (t_ledger_due,
   "Only the open forecasts whose resolution date has passed, each with its "
   "resolution criteria, so they can be settled.", OBJ),

 "evidence": (t_evidence,
   "ASK BEFORE REPORTING ANY INTERVAL: does it settle the decision? "
   "Two imports from outside intelligence tradecraft, both filling "
   "gaps this server had.\n\n"
   "GRADE, from medicine, rates certainty of evidence across four "
   "levels and downgrades it for six named reasons: risk of bias, "
   "inconsistency, INDIRECTNESS (measured on a different population "
   "than the one you care about -- the error this server commits "
   "most), imprecision, publication bias and dissemination bias.\n\n"
   "BUT THE VALUABLE PART IS THE DEFINITION. GRADE defines certainty "
   "as confidence the true value falls in a range 'OR ABOVE OR BELOW "
   "A DECISION-MAKING THRESHOLD'. Precision is relative to the "
   "decision. A Frechet "
   "bound of 0 to 40% is useless in the abstract and DECISIVE against "
   "a 50% threshold, and a precise point estimate in its place adds "
   "precision that changes nothing. Pass `low`, `high` and `threshold` and it "
   "returns DECIDED-BELOW, DECIDED-ABOVE or STRADDLES. Only in the "
   "straddling case is narrowing the estimate worth paying for.\n\n"
   "SEVERITY, from Deborah Mayo's error statistics: evidence supports "
   "a claim only if the claim passed a test it COULD HAVE FAILED. "
   "This server asks whether a claim is fragile; it never asked "
   "whether the sweep was severe. Five questions, and the sharpest is "
   "the last: construct a FALSE version of the claim and ask whether "
   "your evidence would look any different. If it would not, the "
   "evidence carries no information about which version you have.\n\n"
   "Verdicts: SEVERE, WEAK, or DEMONSTRATION -- the last meaning no "
   "failing result was ever specified, so nothing was tested.\n\n"
   "Pass `worked: true` for any saved worked examples where a very "
   "wide interval still settled the question.",
   {"type": "object", "properties": {
      "low": {"type": "number",
        "description": "Bottom of the interval, as a fraction."},
      "high": {"type": "number",
        "description": "Top of the interval, as a fraction."},
      "threshold": {"type": "number",
        "description": "The decision threshold to compare against. "
                       "Say why you chose it."},
      "worked": {"type": "boolean",
        "description": "Show the worked cases instead."}},
    "required": []}),

 "loop": (t_loop,
   "CALL THIS BEFORE ANY OTHER TOOL ON THIS SERVER. It asks whether you should be using this server at all.\n\n"
   "EVERY OTHER MODULE HERE IS COMPENSATION FOR A BROKEN FEEDBACK LOOP. The sweeps, the mirror, the steelman, the Frechet bounds -- if you could just check, you would not need any of them. You would check. So sometimes the right output of an analysis toolkit is PUT THIS DOWN AND GO AND LOOK, and until this tool existed there was no way to say it.\n\n"
   "A thermostat holds a room at 20 degrees with no theory of thermodynamics -- no heat-transfer equations, no knowledge of the insulation, no forecast. It measures and corrects, and it beats an open-loop system with an excellent model. LOOP QUALITY SUBSTITUTES FOR MODEL QUALITY and costs far less.\n\n"
   "FOUR GATES, ALL OF WHICH MUST PASS before go-and-measure is the right advice.\n\n"
   "1 RATE. R = T_change / T_loop -- how many corrections you get before the situation moves. Above 5, checking beats forecasting outright. Near 1, you want both. Below 1, nothing you learn arrives in time to apply and you are stuck with a model. THIS IS WHY THE HARD QUESTIONS ARE HARD: not complexity, but a loop slower than the thing it watches.\n\n"
   "2 CLOSURE. Is the ERROR fed back, or only new input? The gate that quietly fails in almost every continuously-updating system ever built. Re-running a case on fresh data is the INPUT half; without the scoring step nothing corrects and you have bought a TREADMILL that feels like progress and costs more than doing the analysis once. Needs all three of: observable error, separable from noise, and a lever to change the next call.\n\n"
   "3 RESOLUTION. n = (sigma/delta)^2 cycles before a real change is visible. Faster is NOT better past this point -- correcting inside the detection window responds to noise and amplifies it, which control engineers call hunting.\n\n"
   "4 SURVIVABILITY. Is one failed cycle acceptable? A fast loop is not an affordable one. You do not learn whether the bridge holds by driving over it. Gate 4 OVERRIDES gate 1.\n\n"
   "Pass `t_loop` and `t_change` in the same unit for gate 1; t_loop null means the claim never resolves, which is worse than slow and is where most contested political claims sit. Add `sigma`, `delta` and `cycles_available` for gate 3. Pass `cases: true` for the worked examples.",
   {"type": "object", "properties": {
      "t_loop": {"type": ["number", "null"],
        "description": "How long until you find out you were wrong. Null if it never resolves."},
      "t_change": {"type": "number",
        "description": "How long before the situation that produced the call has shifted. SAME UNIT as t_loop."},
      "unit": {"type": "string",
        "description": "weeks, months, elections -- for the printout."},
      "sigma": {"type": "number",
        "description": "Gate 3: cycle-to-cycle noise."},
      "delta": {"type": "number",
        "description": "Gate 3: the real movement worth seeing."},
      "cycles_available": {"type": "number",
        "description": "Gate 3: how many cycles you actually get."},
      "cases": {"type": "boolean",
        "description": "Show the worked examples."}},
    "required": []}),

 "operation": (t_operation,
   "THE FRONT DOOR. CALL THIS FIRST, BEFORE `route`, BEFORE `steelman`. It asks the one question that tells you which of the other catalogues to open: WHAT KIND OF FINDING-OUT IS THIS?\n\n"
   "Sorting this server's eleven problem shapes by what kind of object each actually is left four categories -- failure mode, argument scheme, method, operation -- and exactly ONE of the eleven turned out to be an operation. `comparison` had been sitting in the list as though it were the same kind of thing as `denominator`. That gap is why the pipeline felt arbitrary.\n\n"
   "THE PROPER ORDER IS operation -> scheme -> method -> failure mode. What kind of finding-out, then how is it justified, then what gets computed, then which defects are live -- and which defects are live DEPENDS on the first three. The flat eleven is the degenerate case you run when all you have is somebody's conclusion.\n\n"
   "EIGHTEEN OPERATIONS: estimate, bound, compare, diagnose, attribute, predict, detect, classify, aggregate, allocate, sequence, measure, cause, strategize, simulate, trend, connect, optimize. Each returns the methods to reach for, the failure that bites hardest, and a building-site example -- the index is worthless if it only works on geopolitics.\n\n"
   "AND THE PART THAT MATTERS MOST. Most operations have a FAST feedback loop: you estimate, you do it, you find out. That beats any formula here, because a fast loop substitutes for a good model -- a thermostat holds a room at 20 degrees with no theory of thermodynamics, by measuring and correcting. The loop wins when T_loop < T_change: how long until you find out you were wrong, versus how fast the thing moves. THAT IS WHY THE HARD QUESTIONS ARE HARD -- not complexity, but a feedback loop slower than the thing it is watching, so you never get to correct.\n\n"
   "This index does not exist anywhere else. Walton catalogued the schemes, operations research has the methods, this server has the failure modes. The list of OPERATIONS is the one nobody built, and it is the one that routes you to the other three. Per this server's own doctrine on partition dependence, eighteen is a CUT somebody chose -- re-cut it if your domain wants different joints.",
   {"type": "object", "properties": {
      "operation": {"type": "string",
        "description": "One of the eighteen, for the full entry. Omit for the index."}},
    "required": []}),

 "ancestry": (t_ancestry,
   "WHERE EVERY MODULE IN THIS SERVER ALREADY EXISTED, decades "
   "earlier, in public. Call it before presenting any of this as "
   "novel.\n\n"
   "causal_rivals is Heuer's ANALYSIS OF COMPETING HYPOTHESES "
   "(1970s). Percentages-both-ways is Sherman Kent's WORDS OF "
   "ESTIMATIVE PROBABILITY (1964). SHOW_WORK is ICD 203 ANALYTIC "
   "STANDARDS (2007). The "
   "provenance tags are ICD 203 standards 2 and 3. mirror is RED CELL "
   "and devil's advocacy. steelman is mandated ALTERNATIVE ANALYSIS. "
   "The denominator and start-date sweeps are Key Assumptions Check, "
   "and closer still to specification curve analysis. pitf is not "
   "even an ancestor -- it is theirs, imported.\n\n"
   "NONE OF THESE WERE CONSULTED WHILE BUILDING THIS. They were "
   "reconstructed without attribution by a model near-certainly "
   "trained on them, since all of it is published -- Heuer is on the "
   "CIA's own website. Reconstructing a known framework and not "
   "citing it is worse than inventing or citing it: it reads as "
   "originality, is not, and costs the reader the better original. "
   "This server already tags NUMBERS by provenance; this tags the "
   "IDEAS.\n\n"
   "ONE ROW IS EMPTY AND IT IS THE POINT. `ledger` -- a published "
   "calibration record -- has no ancestor, for a structural reason: "
   "scoring a classified estimate in public discloses what was "
   "estimated. Their own tournament (IARPA ACE, 2011-2015, 500 "
   "questions, over a million forecasts) found that tracked, scored, "
   "publicly-compared forecasting was what let amateurs beat "
   "intelligence officers holding clearances by a reported 30%. The "
   "one column they cannot fill is the one their own experiment "
   "identified as decisive.",
   {"type": "object", "properties": {}, "required": []}),

 "steelman": (t_steelman,
   "RUN THIS FIRST, BEFORE ANY OTHER CHECK. State the strongest "
   "version of a claim before auditing the words it was written in.\n\n"
   "THE FAILURE IT CATCHES. Somebody's words are a lossy encoding of "
   "their argument. Audit the encoding and report on the argument and "
   "you produce findings that are true about a point nobody was "
   "making.\n\n"
   "Reading somebody at their most literal while granting yourself "
   "interpretive latitude is an isolated demand for rigor one level "
   "up. `mirror` catches it inside the arithmetic; this catches it "
   "before the arithmetic starts.\n\n"
   "SEVEN QUESTIONS, and two of them do the work:\n"
   "  what_you_supplied      list EVERY word, premise or connection "
   "you added. This is the ONLY thing separating a steelman from a "
   "different and easier claim of your own invention.\n"
   "  which_are_you_auditing declare it before you start. Undeclared, "
   "this is where the switch happens -- refute the literal version, "
   "report as though you addressed the argument.\n\n"
   "The other five: strongest_version, load_bearing_words (is "
   "one word doing more work than the rest?), different_mechanism (a weak "
   "illustration often sits on a strong mechanism), "
   "would_they_accept_it (a steelman can be a strawman in the other "
   "direction), and reduces_to_a_parameter -- the best ones collapse "
   "to ONE measurable number, which is the most valuable thing this "
   "step produces.\n\n"
   "FOUR VERDICTS: SAME, STRENGTHENED, DIFFERENT_MECHANISM, and "
   "TECHNICALITY -- which means you refuted the wording and the "
   "argument survives. That is a FAILURE STATE, not a finding, and "
   "publishing it as one is the thing this exists to stop.\n\n"
   "ORDER: steelman -> route -> the eleven -> mirror.",
   {"type": "object", "properties": {
      "claim": {"type": "string",
        "description": "The claim as written, to hold the seven "
                       "questions against."},
      "case": {"type": "string",
        "description": "A saved worked case, if any (call with no arguments to list them)."}},
    "required": []}),

 "mirror": (t_mirror,
   "RUN THIS LAST, ON YOUR OWN CORRECTION. A correction is a claim, "
   "so point the same eleven questions at it and publish what comes "
   "back.\n\n"
   "WHY. A reply that sweeps somebody's number and leaves its own "
   "unswept has applied rigour to one side. Every individual finding "
   "can be correct and the aggregate output still biased, because "
   "scrutiny only ever pointed one way. That is the strongest "
   "objection to this whole server and it is structural rather than a "
   "matter of execution.\n\n"
   "SEVEN QUESTIONS: same_shape_back, new_shape_introduced, "
   "constant_out_of_scope, asymmetric_precision, unswept_residual, "
   "direction_of_convenience (if every correction you publish moves "
   "the same way, that is a finding about you), decision_relevance.\n\n"
   "VERDICTS: HOLDS, RESIZED, REVERSED, UNCHECKABLE. Publishing the "
   "HOLDS cases is what makes the rest mean anything -- a test that "
   "never passes carries no information.\n\n"
   "The count that matters is how many shapes fire ONLY on your own "
   "correction. Each one is something you did to them after objecting "
   "to it being done.",
   {"type": "object", "properties": {
      "case": {"type": "string",
        "description": "A saved worked case, if any (call with no arguments to list them)."}},
    "required": []}),

 "route": (t_route,
   "THE ELEVEN SHAPE QUESTIONS. Given a claim, which formula applies? "
   "Code asks, a model answers -- never the other way round.\n\n"
   "Each question is answerable from the TEXT of the claim alone: no "
   "world knowledge, no forecast, no view on whether it is true. "
   "'Does this need several things to all happen' is a grammar "
   "question; 'will they all happen' is not, and is not asked here.\n\n"
   "A claim can be more than one shape and that is normal. Run every "
   "one that matches.\n\n"
   "Every shape now carries its formula's NAME and SOURCE, and "
   "block() refuses to render a legend that skips any mark in the "
   "formula -- including the operators, which are the ones readers "
   "most need and authors most often drop.\n\n"
   "THE ELEVEN ARE NOT ONE THING, and `split: true` shows why. Sorted "
   "by what kind of object each is:\n"
   "  FAILURE MODE (5 shapes) -- a defect in how the "
   "claim was built. Visible in the claim's TEXT, which is why these "
   "dominate. This category is genuinely this project's own.\n"
   "  ARGUMENT SCHEME (3 shapes) -- a pattern of inference. "
   "Visible only if the REASONING IS STATED, and most claims assert a "
   "conclusion and stop. Walton, Reed & Macagno catalogued 65 of "
   "these in 2008; ours are three of them reinvented, and "
   "`conjunction` is his slippery slope with the arithmetic done.\n"
   "  METHOD (2 shapes) -- a procedure once you know what "
   "you are computing. Operations research has had these for "
   "decades.\n"
   "  OPERATION (1 shape) -- what kind of finding-out is "
   "being attempted. THE MISSING FRONT DOOR: exactly one of the "
   "eleven is an operation and nobody has catalogued these properly "
   "anywhere.\n\n"
   "Failure modes show up far more often than schemes on any corpus "
   "of assertions, because one is visible without the reasoning and "
   "the other is not.\n\n"
   "AND THE PROPER ORDER IS NOT FLAT: operation, then scheme, then "
   "method, then failure mode -- since which defects are live depends "
   "on the first three. The flat eleven is the degenerate case, run "
   "when all you have is a conclusion.\n\n"
   "Pass `shape` for one entry, `category` for one of the four, "
   "`split: true` for the full breakdown, or nothing for all eleven.",
   {"type": "object", "properties": {
      "shape": {"type": "string",
        "description": "One of: conjunction, union, growth, "
                       "accuracy_stat, causal_rivals, comparison, "
                       "stock_vs_flow, window_shopping, survivorship, "
                       "correlation_causal, denominator."},
      "category": {"type": "string",
        "description": "One of: failure_mode, argument_scheme, "
                       "method, operation."},
      "split": {"type": "boolean",
        "description": "Show the four-category breakdown with fire "
                       "counts and what it explains."}},
    "required": []}),

 "constant": (t_constant,
   "USE THIS BEFORE QUOTING ANY PUBLISHED EFFECT SIZE about elections, "
   "coalitions or party systems. Ten regularities that survive three "
   "filters -- a published effect size WITH an interval, an "
   "out-of-sample test somebody else ran, and a public dataset that "
   "operationalises the inputs.\n\n"
   "WHAT IT IS REALLY FOR. A constant applied outside its scope is "
   "worse than no constant, because it arrives wearing a citation. So "
   "every entry carries a `misuse` field naming the specific wrong way "
   "it gets used, and you cannot get a computed number out of this "
   "tool without that warning attached to it.\n\n"
   "THE THREE THAT PRODUCE NUMBERS\n"
   "  cost_of_ruling    governing parties lose 2.25 pp per term, range "
   "1.6-2.5, measured on 282 elections in 19 democracies. Pass "
   "`observed_gap` and it does the subtraction that separates a real "
   "policy effect from the ordinary price of office -- below about 2.25 "
   "points there is nothing left to explain.\n"
   "  gamson            cabinet posts track coalition seat share: "
   "p = 0.069 + 0.793s, R^2 = 0.89. s is the share of THE COALITION's "
   "seats, not of parliament, and confusing the two moves the answer by "
   "over 20 points.\n"
   "  economic_voting   1.55 pp of incumbent vote per point of GDP "
   "growth where responsibility is clear, 0.92 where government is "
   "fragmented. The conditioning IS the finding.\n\n"
   "FOUR MORE ARE PURE ARITHMETIC with no theory risk at all: "
   "effective_parties, volatility, disproportionality and "
   "seat_allocation. That last one turns a poll share into seats, which "
   "is the step that decides whether a party actually takes power.\n\n"
   "TWO DELIBERATELY CARRY NO NUMBER. duverger holds at district "
   "level and has no published national coefficient. pitf outputs a "
   "rank and refuses to become a probability.\n\n"
   "Call with no arguments for the catalogue, the filters and the "
   "REJECTED list -- the median voter theorem, the cube law, and any "
   "'X% chance' read off a model that only publishes a rank. Pass "
   "`id` for one entry in full. Pass `id` and `apply` to compute.",
   {"type": "object", "properties": {
      "id": {"type": "string",
        "description": "One of: cost_of_ruling, gamson, economic_voting, "
                       "effective_parties, "
                       "volatility, disproportionality, seat_allocation, "
                       "duverger, pitf. Omit for the catalogue."},
      "apply": {"type": "object",
        "description": "Arguments to compute with. cost_of_ruling: "
                       "{terms} or {observed_gap, terms}. gamson: "
                       "{coalition_seat_share}. economic_voting: "
                       "{growth_pp, clarity: high|low}. "
                       "effective_parties: {shares:[...]}. volatility: "
                       "{prev:{}, curr:{}}. disproportionality: "
                       "{votes:{}, seats:{}}. seat_allocation: {votes:{}, "
                       "total_seats, threshold, sainte_lague}. duverger: "
                       "{magnitude}."}},
    "required": []}),

 "theory_slot": (t_theory_slot,
   "USE THIS WHEN somebody proposes wiring a social-science theory into "
   "an analysis. It routes the theory to one of three slots, and the "
   "whole point is that most theories are not estimators and using one "
   "as if it were is how fabricated numbers get made.\n\n"
   "  SLOT 1  STRUCTURE GENERATOR -- tells you what the steps ARE, "
   "predicts nothing, and does not need to. Most grand social "
   "theories live here. Feed the steps to `chain` and price them yourself.\n"
   "  SLOT 2  ESTIMATOR -- produces a number with an interval. Rare. "
   "Goes in `constant`.\n"
   "  SLOT 3  MEASUREMENT -- supplies input values, ideally with their "
   "own uncertainty: surveys, expert panels, registers.\n\n"
   "A theory that explains everything forbids nothing, and a theory "
   "that forbids nothing has no predictive content however true it is. "
   "That is not a criticism of slot 1 -- it is what a classification "
   "scheme is for, and misreading it as slot 2 is the error.\n\n"
   "Answer the three filters honestly. If you do not know whether an "
   "out-of-sample test exists, the answer is no.",
   {"type": "object", "properties": {
      "theory": {"type": "string", "description": "Name of the theory."},
      "has_interval": {"type": "boolean",
        "description": "Is there a published effect size WITH an "
                       "interval? Not a direction, a number."},
      "tested_out_of_sample": {"type": "boolean",
        "description": "Did somebody other than the original author "
                       "test it on data it was not fitted to?"},
      "has_dataset": {"type": "boolean",
        "description": "Is there a public dataset that operationalises "
                       "the inputs?"}},
    "required": ["theory"]}),

 "render_finding": (t_render_finding,
   "Write a standalone HTML page presenting a result in plain English — a "
   "verdict, bar charts, and the claims that could not be tested.",
   {"type": "object", "properties": {
      "title": {"type": "string"}, "verdict": {"type": "string"},
      "charts": {"type": "array", "items": {"type": "object"}},
      "refusals": {"type": "array", "items": {"type": "object"}},
      "filename": {"type": "string"}},
    "required": ["title", "verdict"]}),
}


# ------------------------------------------------------------- transport ---

def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def handle(req):
    m, rid = req.get("method"), req.get("id")
    if m == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
            "serverInfo": {"name": "elipsis", "version": "0.3.0"},
            "instructions": SHOW_WORK}}
    if m in ("notifications/initialized", "initialized"):
        return None
    if m == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if m == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": [
            {"name": n, "description": SHOW_WORK_SHORT + d, "inputSchema": s}
            for n, (_, d, s) in TOOLS.items()]}}
    if m == "tools/call":
        p = req.get("params", {})
        name = p.get("name")
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32601, "message": f"no tool '{name}'"}}
        try:
            text = TOOLS[name][0](p.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"content": [{"type": "text", "text": text}]}}
        except Exception as e:
            # A bad or missing argument is the caller's to fix: say what, without
            # a traceback. Anything else is a bug here, so keep the traceback.
            detail = "" if isinstance(e, (ValueError, KeyError, TypeError)) \
                else "\n" + traceback.format_exc()
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "isError": True,
                "content": [{"type": "text",
                             "text": f"{type(e).__name__}: {e}{detail}"}]}}
    if rid is None:
        return None
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"unknown method '{m}'"}}


def main():
    paths.seed()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            send(resp)


if __name__ == "__main__":
    main()
