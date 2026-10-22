#!/usr/bin/env python3
"""
case_lint.py -- catch a verdict that says more than its evidence.

Three failures this exists to catch, all of the same kind (the words at the
top of an answer go further than the facts underneath them):

  GROUP      the claim is about a whole people, faith, sex, class or era
             ("the X were...", "women always..."), but the round has no
             Scope line saying who the evidence actually covers. Evidence
             about some members is not evidence about the group.
  STEELMAN   the verdict grades the steelman instead of the words said
             ("true at its core", "true in spirit"). The steelman is for
             testing the argument; the verdict on the words must stand on
             its own, and on a claim about a whole group it must not borrow
             the steelman's generosity.
  KINDS      a case file has no "- **Question kinds:**" line naming which of the twelve
             kinds of question below it asks (numbers, most important first). The tags
             let a scored record show which kinds the checker gets right.

  OVERREACH  a sweeping word (all, always, never, accepted, celebrated,
             proven...) appears in the verdict, answer or summary but not
             in the evidence above it.

Code asks; a model answers. Every flag is a question, not a ruling: answer
it by adding a Scope line, a separate "Verdict, as said" line, or by
softening the summary.

Run:  python harness/case_lint.py                 -- rounds dated today or later in cases/claims
      python harness/case_lint.py --all           -- every claim case (an audit)
      python harness/case_lint.py --text FILE     -- a draft reply, before it is sent
      python harness/case_lint.py FILE.md         -- one case file
Standard library only.
"""
import datetime
import glob
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CLAIMS = os.path.join(HERE, "..", "cases", "claims")

QUESTION_KINDS = {
    1: "Lookup: a date or a figure that is on record",
    2: "Claim against sources: is what was said true, by the record",
    3: "Cause: did X cause Y",
    4: "Forecast: will X happen by a date",
    5: "What if: what would have happened (counterfactual)",
    6: "Choice or design: which option is best, or build something that does X",
    7: "Values: what should we want",
    8: "Meaning: is X a Y (definitions)",
    9: "Motive: why did they do it (intent)",
    10: "Real or fake: did they really say it, is it authentic (provenance)",
    11: "Proof: does the logic or arithmetic hold",
    12: "Strategy: what will others do in response (the answer can change the outcome)",
}

GROUP_WORDS = r"""peoples tribe tribes women men
Christians Jews Hindus Buddhists Catholics Protestants Mormons atheists
blacks whites Asians Africans Europeans Westerners
gays boomers millennials Kurds Serbs Croats Poles Swedes Danes Finns Scots Celts
Slavs Moors Huns Mongols Goths Vikings""".split()
try:  # more group words, kept with the owner's worked examples; the tool works without them
    from private_examples import CASE_LINT_GROUP_WORDS
    GROUP_WORDS += CASE_LINT_GROUP_WORDS
except ImportError:
    pass
DEMONYM = re.compile(r"\b[A-Z][a-z]+(?:ians|ans|eks|rks|abs|ews|ites)\b|\b[A-Z][a-z]+ese\b(?! [a-z])")
GROUP = re.compile(r"\b(?:" + "|".join(GROUP_WORDS) + r")\b|\bthe (?:poor|rich|young|old|left|right)\b")
SOFT_VERDICT = re.compile(r"at (?:its|the) core|in spirit|at heart|essentially true|basically true|"
                          r"broadly true|true at root|true underneath", re.I)
SWEEPING = """all always never every everyone everybody nobody none entirely completely wholly
universally proven proves certainly accepted celebrated loved hated whole""".split()
CLAIM_LINE = re.compile(r"^(?:\*\*(?:[A-Z][\w' ]*?)?(?:claim|question|quote)[^*]*\*\*|>)", re.I)
VERDICT_LINE = re.compile(r"^(?:\*\*)?(?:revised )?verdict", re.I)
SUMMARY_HEAD = re.compile(r"^(?:#+\s*)?(?:summary|answer|verdict)\b", re.I)


def rounds(text):
    parts = re.split(r"(?m)^## (?=Round)", text)
    out = []
    for p in parts[1:]:
        head = p.splitlines()[0]
        m = re.search(r"\((\d{4}-\d{2}-\d{2})\)|(\d{4}-\d{2}-\d{2})", head)
        out.append((head.strip(), (m.group(1) or m.group(2)) if m else "", p))
    return out or [("(whole text)", "", text)]


def split_summary(lines):
    """Lines of the verdict/answer/summary part, and the rest (the evidence)."""
    top, body, inside = [], [], False
    for ln in lines:
        s = ln.strip()
        if SUMMARY_HEAD.match(s.strip("*# ")) or VERDICT_LINE.match(s):
            inside = True
            top.append(ln)
            continue
        if inside and (s.startswith("#") or (s.startswith("**") and not VERDICT_LINE.match(s))):
            inside = SUMMARY_HEAD.match(s.strip("*# ")) is not None
        (top if inside else body).append(ln)
    return top, body


def words(text):
    return set(re.findall(r"[a-z]+", text.lower()))


def lint_round(text):
    lines = text.splitlines()
    claims = " ".join(ln for ln in lines if CLAIM_LINE.match(ln.strip()))
    flags = []
    groups = sorted(set(DEMONYM.findall(claims)) | set(GROUP.findall(claims)))
    has_scope = any(re.match(r"^(?:\*\*)?scope", ln.strip(), re.I) for ln in lines)
    verdicts = [ln for ln in lines if VERDICT_LINE.match(ln.strip())]
    if groups and not has_scope:
        flags.append(("GROUP", "the claim names a whole group ({}); add a Scope line: who, where, when and how "
                      "many the evidence covers, against who the claim covers".format(", ".join(groups[:5]))))
    for v in verdicts:
        if SOFT_VERDICT.search(v):
            flags.append(("STEELMAN", "verdict grades the steelman ('{}'); give a separate 'Verdict, as said' "
                          "on the words used".format(SOFT_VERDICT.search(v).group(0))))
        if groups and re.search(r"\btrue\b", v, re.I) and not re.search(r"partly|part|some|false|wrong|mostly", v, re.I) \
                and not re.search(r"whole group|all members", text, re.I):
            flags.append(("GROUP", "verdict 'true' on a claim about a whole group; the evidence must cover the "
                          "group, or the verdict is at most 'partly true, for some'"))
    top, body = split_summary(lines)
    body_words = words("\n".join(body))
    for w in SWEEPING:
        if w in words("\n".join(top)) and w not in body_words:
            flags.append(("OVERREACH", "'{}' is in the verdict or summary but nowhere in the evidence".format(w)))
    return flags


def lint_file(path, since=None):
    text = io.open(path, encoding="utf-8").read()
    found = []
    if os.path.basename(path) == "INDEX.md" or "**Merged into:**" in text[:3000]:
        return found    # the generated index, or a pointer to where a thread moved
    dated = [d for _, d, _ in rounds(text)]
    if "**Question kinds:**" not in text and (not since or any(d and d >= since for d in dated)):
        found.append(("(file)", "KINDS", "no '- **Question kinds:**' line; tag it with numbers from "
                      "QUESTION_KINDS, most important first"))
    for head, date, body in rounds(text):
        if since and (not date or date < since):
            continue
        if re.search(r"superseded by round", body, re.I):
            continue
        for kind, msg in lint_round(body):
            found.append((head, kind, msg))
    return found


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if argv[:1] == ["--text"]:
        flags = lint_round(io.open(argv[1], encoding="utf-8").read())
        for kind, msg in flags:
            print("  {:9s} {}".format(kind, msg))
        print("case_lint: {} flag(s) in the draft".format(len(flags)))
        return len(flags)
    files = [a for a in argv if a.endswith(".md")] or sorted(glob.glob(os.path.join(CLAIMS, "*.md")))
    since = None if ("--all" in argv or any(a.endswith(".md") for a in argv)) else datetime.date.today().isoformat()
    total = 0
    for f in files:
        for head, kind, msg in lint_file(f, since):
            print("  {} | {} | {:9s} {}".format(os.path.basename(f), head[:40], kind, msg))
            total += 1
    print("case_lint: {} flag(s){}".format(total, "" if since is None else " in rounds dated " + since + " or later"))
    return total


if __name__ == "__main__":
    main(sys.argv[1:])
