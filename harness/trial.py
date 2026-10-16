#!/usr/bin/env python3
"""
trial.py -- n-of-1 trial design, assignment and analysis.

The decision calculator computes what your beliefs imply. This is the other
half: the only thing in the project that can produce a belief worth having.

An n-of-1 trial is a real clinical methodology, used for chronic conditions
where the population average is not the question and the patient is. It is
also the one design where the transfer problem that wrecks this whole field
dissolves, because you are measuring the target population directly -- you
ARE the target population.

FOUR ARROWS, AND WHAT CLOSES EACH

    1. treatment -> outcome     the thing you want to know
    2. outcome -> treatment     you choose it BECAUSE you feel bad
    3. something -> both        sleep, stress, an illness starting
    4. arm -> instrument        whatever records the outcome knows the arm

RANDOMISING closes 2 and 3. It does nothing to 4.
BLINDING THE MEASUREMENT closes 4. Randomising does not.

They are different guarantees and a design needs both. A measurement bias
about the size of the smallest true effect a trial could detect will
manufacture a SIGNIFICANT result for an effect that is exactly zero. An
unblinded trial cannot tell those apart, at any n.

ASSIGNMENT IS DETERMINISTIC ON PURPOSE. A fresh coin every morning leaves
no audit trail and nothing stopping a re-roll after a bad night. Assignment
here is a hash of trial id and date, so it is fixed in advance, reproducible
by anyone, and re-running it cannot change it.

Run:  python harness/trial.py design <sigma> --effect <effect>
      python harness/trial.py assign <trial_id> <YYYY-MM-DD>
"""

import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402  (sits next to this file)
TRIALS = paths.data("trials")

Z_ALPHA = 1.959963984540054      # two-sided 5%
Z_POWER = {0.80: 0.8416212335729143, 0.90: 1.2815515655446004,
           0.95: 1.6448536269514722}


def _z_power(p):
    if p in Z_POWER:
        return Z_POWER[p]
    # Acklam's inverse normal, good to ~1e-9 across the useful range
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    dd = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
          3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# ------------------------------------------------------------- design ---

def mde(sigma, n_per_arm, power=0.80):
    """Smallest true effect this trial could detect, in the outcome's own
    units. Anything smaller than this, the trial cannot see, and running it
    longer is the only fix."""
    if n_per_arm < 2:
        return float("inf")
    return (Z_ALPHA + _z_power(power)) * sigma * math.sqrt(2.0 / n_per_arm)


def days_needed(sigma, effect, power=0.80):
    """Total days (both arms) to detect an effect of this size."""
    if effect <= 0:
        return float("inf")
    n = 2.0 * (sigma ** 2) * ((Z_ALPHA + _z_power(power)) ** 2) / (effect ** 2)
    return int(math.ceil(n)) * 2


def power_at(sigma, n_per_arm, effect):
    if n_per_arm < 2 or sigma <= 0:
        return 0.0
    se = sigma * math.sqrt(2.0 / n_per_arm)
    return phi(abs(effect) / se - Z_ALPHA)


def design(sigma, days=None, effect=None, power=0.80, unblind_bias=None):
    """Everything worth knowing before starting. Returns a dict."""
    out = {"sigma": sigma, "power": power}
    if days:
        n = days // 2
        out["days"] = days
        out["n_per_arm"] = n
        out["mde"] = mde(sigma, n, power)
        if effect:
            out["power_for_effect"] = power_at(sigma, n, effect)
    if effect:
        out["effect_of_interest"] = effect
        out["days_needed"] = days_needed(sigma, effect, power)
    if unblind_bias is not None:
        out["unblind_bias"] = unblind_bias
        ref = out.get("mde")
        if ref and ref != float("inf"):
            out["bias_as_share_of_mde"] = unblind_bias / ref
    return out


# --------------------------------------------------------- assignment ---

def assign(trial_id, day, arms=("A", "B")):
    """Deterministic, auditable, fixed in advance.

    A fresh random coin each morning leaves no way to prove the assignment
    was not re-rolled after a bad night -- and the person most able to do
    that is the person the trial is about. Hashing the trial id and the
    date means the whole schedule already exists before the trial starts,
    anyone can recompute it, and re-running cannot change it.
    """
    h = hashlib.sha256(f"{trial_id}|{day}".encode("utf-8")).hexdigest()
    return arms[int(h[:8], 16) % len(arms)]


def schedule(trial_id, days, start=None, arms=("A", "B")):
    """The whole assignment sequence, computable before day one."""
    import datetime as dt
    d0 = (dt.date.fromisoformat(start) if start else dt.date.today())
    return [{"day": (d0 + dt.timedelta(days=i)).isoformat(),
             "arm": assign(trial_id, (d0 + dt.timedelta(days=i)).isoformat(),
                           arms)}
            for i in range(days)]


# ------------------------------------------------------------ analysis ---

def analyse(rows, blinded=None):
    """rows: [{"arm": "A"|"B", "outcome": <number>}, ...]

    Returns the difference in means, its standard error, t, and a plain
    reading -- plus the blinding warning, because an unblinded outcome is
    not a weaker result, it is a differently-shaped one.
    """
    a = [float(r["outcome"]) for r in rows if r.get("arm") == "A"]
    b = [float(r["outcome"]) for r in rows if r.get("arm") == "B"]
    out = {"n_A": len(a), "n_B": len(b), "blinded": blinded}
    if len(a) < 2 or len(b) < 2:
        out["verdict"] = "not enough data in one or both arms"
        return out
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va = sum((x - ma) ** 2 for x in a) / (len(a) - 1)
    vb = sum((x - mb) ** 2 for x in b) / (len(b) - 1)
    se = math.sqrt(va / len(a) + vb / len(b))
    est = ma - mb
    t = abs(est / se) if se else 0.0
    sd_pooled = math.sqrt(((len(a)-1)*va + (len(b)-1)*vb) /
                          max(1, len(a)+len(b)-2))
    out.update(mean_A=ma, mean_B=mb, estimate=est, std_error=se, t=t,
               sigma_observed=sd_pooled,
               ci_low=est - Z_ALPHA * se, ci_high=est + Z_ALPHA * se,
               mde_at_this_n=mde(sd_pooled, min(len(a), len(b))))
    out["verdict"] = ("no detectable effect" if t < 2 else
                      "detectable" if t < 4 else "large and consistent")
    if blinded is False:
        out["WARNING"] = (
            "THE OUTCOME WAS NOT BLIND TO THE ASSIGNMENT. Randomising "
            "protects which arm you were in; it does nothing about an "
            "instrument that can see which arm it is rating. A differential "
            "measurement error is indistinguishable from a treatment "
            "effect, and at this sample size a bias of roughly "
            f"{out['mde_at_this_n']:.2f} -- the same size as the smallest "
            "effect this trial could detect -- would produce a significant "
            "result from a true effect of exactly zero. Treat the estimate "
            "as an upper bound on the real effect, not an estimate of it.")
    elif blinded is None:
        out["WARNING"] = ("Blinding not declared. State whether the thing "
                          "recording the outcome could tell which arm the "
                          "day was in. It changes how the number reads.")
    return out


# ------------------------------------------------------------- reporting ---

def report(d):
    print("=" * 74)
    print("  N-OF-1 TRIAL DESIGN")
    print("=" * 74)
    print()
    print(f"  outcome spread (sigma)      {d['sigma']:.3f}")
    if "days" in d:
        print(f"  days                        {d['days']}")
        print(f"  per arm                     {d['n_per_arm']}")
        print(f"  smallest detectable effect  {d['mde']:.3f}")
        if "power_for_effect" in d:
            print(f"  power for {d['effect_of_interest']:.2f}"
                  f"               {d['power_for_effect']:.0%}")
    if "days_needed" in d:
        print(f"  to detect {d['effect_of_interest']:.3f}          "
              f"  {d['days_needed']} days")
    if "bias_as_share_of_mde" in d:
        print()
        r = d["bias_as_share_of_mde"]
        print(f"  an unblinded measurement bias of {d['unblind_bias']:.2f} is "
              f"{r:.0%} of the")
        print(f"  smallest effect this trial can detect.")
        if r > 0.5:
            print()
            print("  AT THAT RATIO THE TRIAL CANNOT SEPARATE A REAL MINIMUM")
            print("  EFFECT FROM THE INSTRUMENT LEANING. Blind the outcome or")
            print("  do not run it -- more days will not fix this, because the")
            print("  bias does not shrink with n and the effect does not grow.")
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "design":
        sigma = float(sys.argv[2])
        kw = {}
        for i, a in enumerate(sys.argv[3:]):
            if a == "--days":
                kw["days"] = int(sys.argv[4 + i])
            if a == "--effect":
                kw["effect"] = float(sys.argv[4 + i])
            if a == "--bias":
                kw["unblind_bias"] = float(sys.argv[4 + i])
        report(design(sigma, **kw))
    elif cmd == "assign":
        print(assign(sys.argv[2], sys.argv[3]))
    elif cmd == "schedule":
        for r in schedule(sys.argv[2], int(sys.argv[3])):
            print(r["day"], r["arm"])
    else:
        print(__doc__)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
