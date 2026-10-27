#!/usr/bin/env python3
"""
icons.py -- draw a chance as counted people: a grid of dots (an icon array).

People get chance questions right far more often when a chance is shown as a count
("8 in 100") than as a percentage, and a grid of dots shows the same count as a picture.
This draws that grid as plain text, so it can be pasted anywhere, including a phone.

    python harness/icons.py 0.08                 -- one chance, 100 dots
    python harness/icons.py 8 92 --of 100        -- counts: 8 shaded, the rest open
    python harness/icons.py 8 95 --of 1000       -- two shades on 1,000 dots

A chance under 1 in 100 is drawn on 1,000 dots, so a small share still shows.
Standard library only.
"""
import sys

MARKS = ["●", "◐", "◆", "▲"]     # shaded groups, in order
OPEN = "○"                       # everyone else


def counts_for(p, n=None):
    """The number of dots to shade for chance p, and the grid size."""
    n = n or (1000 if 0 < p < 0.01 else 100)
    return [round(p * n)], n


def grid(counts, n=100, labels=None):
    """Text grid: counts[i] dots of MARKS[i], the rest OPEN, then a key line."""
    if sum(counts) > n:
        raise ValueError(f"the counts add to {sum(counts)}, more than the {n} dots")
    if len(counts) > len(MARKS):
        raise ValueError(f"at most {len(MARKS)} shaded groups")
    dots = [m for m, k in zip(MARKS, counts) for _ in range(k)]
    dots += [OPEN] * (n - len(dots))
    cols = 10 if n <= 100 else 25
    sep = " " if cols == 10 else ""
    rows = [sep.join(dots[i:i + cols]) for i in range(0, n, cols)]
    labels = labels or ["shaded"] * len(counts)
    key = [f"{m} {k} in {n:,} {lab}" for m, k, lab in zip(MARKS, counts, labels)]
    key.append(f"{OPEN} {n - sum(counts)} in {n:,} not")
    return "\n".join(rows) + "\n" + ", ".join(key)


def tool(args):
    """For the tool server: pass `p` (a chance from 0 to 1) or `counts` (a list), with
    optional `of` (dots in the grid) and `labels` (one per count)."""
    if "counts" in args:
        counts = [int(c) for c in args["counts"]]
        n = int(args.get("of", 100))
    else:
        counts, n = counts_for(float(args["p"]), args.get("of"))
    return grid(counts, n, args.get("labels"))


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    n = None
    if "--of" in argv:
        i = argv.index("--of")
        n = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if len(argv) == 1 and "." in argv[0]:
        counts, n = counts_for(float(argv[0]), n)
    else:
        counts = [int(a) for a in argv]
        n = n or 100
        if len(counts) > 1 and sum(counts) == n:
            counts = counts[:-1]       # "8 92 --of 100": the last number is the open dots
    print(grid(counts, n))


if __name__ == "__main__":
    main(sys.argv[1:])
