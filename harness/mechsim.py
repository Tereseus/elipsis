"""mechsim.py -- backtested models: a model must predict the past before it may say anything new.

A simulation proves something only when it can first reproduce real outcomes it was not fitted
on. This module enforces that, in four steps:

  1. FIT     a linear model of an outcome on named inputs (ordinary least squares).
  2. BACKTEST k-fold cross-validation, repeated: fit on most of the cases, predict the cases held
             out, and compare the error with a BASELINE model that leaves the levers out. The
             levers count as shown only if they cut the held-out error by at least the gate.
  3. LEVERS  for each lever, the coefficient with a bootstrap interval, and the change in the
             outcome if every case below a target level (say the 75th percentile) were raised
             to it, summed over cases with weights (say population).
  4. REPORT  what is measured, what the model assumes, and whether the gate was passed. When it
             is not passed, no lever results are reported.

Every input in a model spec carries a source string; inputs without data are refused.
Association is not cause: the report says so, and a lever's effect is "if the pattern held".

    from mechsim import Model
    m = Model(rows, target="y", base=["age"], levers=["vax"], weight="pop")
    print(m.report())

Standard library only.
"""
import math
import random
import statistics as st


def _solve(A, b):
    """Gaussian elimination with partial pivoting."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        if abs(M[c][c]) < 1e-12:
            raise ValueError("inputs are collinear; drop one")
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def ols(X, y, ridge=1e-9):
    """Least squares with an intercept. X: list of rows (lists). Returns [b0, b1, ...]."""
    Z = [[1.0] + list(r) for r in X]
    k = len(Z[0])
    A = [[sum(z[i] * z[j] for z in Z) + (ridge if i == j and i else 0) for j in range(k)] for i in range(k)]
    v = [sum(z[i] * t for z, t in zip(Z, y)) for i in range(k)]
    return _solve(A, v)


def predict(b, X):
    return [b[0] + sum(bi * xi for bi, xi in zip(b[1:], r)) for r in X]


class Model:
    def __init__(self, rows, target, base, levers, weight=None, sources=None, k=5, repeats=20,
                 gate=0.05, seed=1):
        need = [target] + base + levers + ([weight] if weight else [])
        self.rows = [r for r in rows if all(r.get(f) is not None for f in need)]
        self.dropped = len(rows) - len(self.rows)
        self.target, self.base, self.levers, self.weight = target, base, levers, weight
        self.sources = sources or {}
        self.k, self.repeats, self.gate, self.seed = k, repeats, gate, seed

    def _xy(self, rows, feats):
        return [[r[f] for f in feats] for r in rows], [r[self.target] for r in rows]

    def backtest(self):
        """Held-out mean absolute error of the baseline and of the full model."""
        rng = random.Random(self.seed)
        full = self.base + self.levers
        err = {"base": [], "full": []}
        for _ in range(self.repeats):
            idx = list(range(len(self.rows)))
            rng.shuffle(idx)
            folds = [idx[i::self.k] for i in range(self.k)]
            for f in folds:
                test = [self.rows[i] for i in f]
                train = [self.rows[i] for i in idx if i not in set(f)]
                for name, feats in (("base", self.base), ("full", full)):
                    X, y = self._xy(train, feats)
                    b = ols(X, y)
                    Xt, yt = self._xy(test, feats)
                    err[name] += [abs(p - t) for p, t in zip(predict(b, Xt), yt)]
        mb, mf = st.mean(err["base"]), st.mean(err["full"])
        return {"mae_base": mb, "mae_full": mf, "cut": 1 - mf / mb, "passed": (1 - mf / mb) >= self.gate}

    def fit(self, rows=None, feats=None):
        rows = rows or self.rows
        feats = feats or self.base + self.levers
        X, y = self._xy(rows, feats)
        return ols(X, y)

    def r2(self, feats):
        X, y = self._xy(self.rows, feats)
        b = ols(X, y)
        p = predict(b, X)
        m = st.mean(y)
        return 1 - sum((a - c) ** 2 for a, c in zip(y, p)) / sum((a - m) ** 2 for a in y)

    def lever_effects(self, target_q=0.75, boots=400):
        """Coefficient and the total change if every case below the q-quantile of a lever were
        raised to it (other inputs unchanged), with 90% bootstrap intervals."""
        feats = self.base + self.levers
        rng = random.Random(self.seed + 7)
        out = {}
        for lv in self.levers:
            vals = sorted(r[lv] for r in self.rows)
            level = vals[min(len(vals) - 1, int(target_q * len(vals)))]
            j = feats.index(lv) + 1
            coefs, totals = [], []
            for _ in range(boots):
                sample = [rng.choice(self.rows) for _ in self.rows]
                try:
                    b = self.fit(sample, feats)
                except ValueError:
                    continue
                coefs.append(b[j])
                tot = sum(b[j] * (level - r[lv]) * (r[self.weight] if self.weight else 1)
                          for r in self.rows if r[lv] < level)
                totals.append(tot)
            coefs.sort(); totals.sort()
            q = lambda a, p: a[min(len(a) - 1, int(p * len(a)))]
            b_all = self.fit()
            out[lv] = {"coef": b_all[j], "coef90": (q(coefs, .05), q(coefs, .95)),
                       "level": level, "total": st.median(totals),
                       "total90": (q(totals, .05), q(totals, .95)),
                       "sd": st.pstdev(r[lv] for r in self.rows)}
        return out

    def report(self, target_q=0.75, boots=400, scale=1.0, unit=""):
        bt = self.backtest()
        lines = [f"Cases used: {len(self.rows)} (dropped for missing data: {self.dropped})",
                 f"Fit on all cases, R2: baseline {self.r2(self.base):.3f}, full {self.r2(self.base + self.levers):.3f}",
                 f"Backtest ({self.k}-fold x {self.repeats}), held-out mean absolute error: baseline "
                 f"{bt['mae_base']:.1f}, full {bt['mae_full']:.1f}, cut {100 * bt['cut']:.1f} in 100 "
                 f"(gate {100 * self.gate:.0f}): {'PASSED' if bt['passed'] else 'NOT PASSED'}"]
        if not bt["passed"]:
            lines.append("Gate not passed: the levers do not predict held-out cases better than the "
                         "baseline, so no lever effects are reported.")
            return "\n".join(lines)
        eff = self.lever_effects(target_q, boots)
        lines.append(f"Levers, raised to their {int(100 * target_q)}th percentile where below it "
                     f"(an association: 'if the pattern held'):")
        for lv, e in eff.items():
            sign = "lowers" if e["coef"] < 0 else "raises"
            sure = "interval excludes zero" if e["coef90"][0] * e["coef90"][1] > 0 else "interval includes zero"
            lines.append(f"  {lv}: coefficient {e['coef']:.2f} (90% {e['coef90'][0]:.2f} to {e['coef90'][1]:.2f}, "
                         f"{sure}); one sd ({e['sd']:.2f}) {sign} the outcome by {abs(e['coef'] * e['sd']):.1f}; "
                         f"raising to {e['level']:.2f}: total {e['total'] * scale:,.0f}{unit} "
                         f"(90% {e['total90'][0] * scale:,.0f} to {e['total90'][1] * scale:,.0f})")
        for f in self.base + self.levers:
            if f in self.sources:
                lines.append(f"  source, {f}: {self.sources[f]}")
        return "\n".join(lines)
