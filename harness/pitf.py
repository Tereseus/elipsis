#!/usr/bin/env python3
"""
pitf.py -- the Political Instability Task Force global forecasting model.

WHY THIS FILE EXISTS, AND WHY IT IS DIFFERENT FROM EVERYTHING ELSE HERE

The coefficients below are not mine.
They were fitted to 141 onsets of political instability in every country
with a population over 500,000 between 1955 and 2003, published in the
American Journal of Political Science, and the confidence intervals are
the authors' own. They can be cited, checked, and argued with.

  Goldstone, Bates, Epstein, Gurr, Lustik, Marshall, Ulfelder & Woodward
  (2010), "A Global Model for Forecasting Political Instability",
  American Journal of Political Science 54(1): 190-208.

THE ONE THING MOST REPORTS OF THIS MODEL GET WRONG

The model is usually described as "right more than eighty percent of the
time, two years in advance". That is true and it is not the useful number.

The authors' own out-of-sample test, 1995-2004, is Table 2 of the paper.
1,246 country-years. 21 onsets. The model flags the top quintile by risk
score -- 251 country-years -- and 18 of the 21 onsets fall inside it.

  86% of the onsets correctly flagged, and
  81% of the stable years correctly cleared,

and, from the same four cells, read the other way:

  of the 251 country-years it FLAGGED, 18 had an onset. That is 7 in
  100. The other 233 flags -- 93 in 100 -- were false alarms.

Neither sentence is a criticism. A screen that lifts you from 2-in-100 to
7-in-100 two years out, on four variables, is a serious result. But
"eighty percent accurate" and "seven percent of what it flags happens" are
the same fact, and quoting the first without the second gives you the
flattering half.

That is the both-directions rule this toolkit already enforces on its own
output, turned on somebody else's model.

WHAT IT PREDICTS, WHICH IS BROADER THAN PEOPLE ASSUME

"Instability onset" is a compound outcome: revolutionary war, ethnic war,
adverse regime change, or genocide/politicide. An adverse regime change is
a significant move toward autocracy and need not be violent. A flag is
therefore NOT a civil-war forecast. Of the 117 onsets in the full problem
set, 65 begin as civil war and 49 as adverse regime change -- so a flag is
closer to a coin toss between "war" and "the government turns", and the
model does not tell you which.

WHAT THE MODEL ACTUALLY OUTPUTS, WHICH IS A RANK AND NOT A PROBABILITY

This matters and it is the thing that makes the model hard to misuse
accidentally and easy to misuse deliberately. The paper publishes no
intercept. It cannot: the design is case-control with roughly one onset
per three controls, so any fitted intercept describes a sample built at
25% instability, not a world running at 1.7%. What the authors do instead
is RANK every country by score and flag the top fifth.

So the honest output for any country is a position in the ranking, plus
the calibration the paper's own out-of-sample table supplies for that
position. Anything that hands you a single percent-per-year for one named
country has added an assumption the paper does not contain.

THE LIMIT THAT MATTERS FOR RICH COUNTRIES

The estimation sample is dominated by developing countries, because that
is where the onsets were. Scoring a rich democracy puts three
of four variables outside the fitted range: infant mortality far below the
sample's 25th percentile, no bordering states at war, and a regime type
the sample holds few examples of. A logistic model extrapolates silently.
It returns a number either way, and the published intervals do not cover
it.
"""

import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decide as D                                        # noqa: E402


CITE = ("Goldstone, Bates, Epstein, Gurr, Lustik, Marshall, Ulfelder & "
        "Woodward (2010), 'A Global Model for Forecasting Political "
        "Instability', American Journal of Political Science 54(1):190-208. "
        "Table 1 = coefficients on the full problem set; Table 2 = the "
        "out-of-sample test, 1995-2004.")

# ---------------------------------------------------------------------
# TABLE 1, FULL PROBLEM SET. Log-odds relative to the reference profile:
# full autocracy, sample-median infant mortality, fewer than four
# bordering states at war, no state-led discrimination.
# N = 468 (117 onsets, 351 controls). Onsets classed correctly 80.3%,
# controls 81.8%.
# ---------------------------------------------------------------------

REGIME = {
    # category                      coef    OR      95% CI on the OR
    "full_autocracy":              (0.000,  1.00,  (None, None)),
    "partial_autocracy":           (1.850,  6.37,  (2.53, 16.02)),
    "partial_dem_factional":       (3.610, 36.91,  (13.5, 101.0)),
    "partial_dem_nonfactional":    (1.830,  6.20,  (2.17, 17.8)),
    "full_democracy":              (0.981,  2.67,  (0.70, 10.2)),
}

IMR_COEF = 1.590          # on the normalised, logged infant mortality scale
IMR_OR_75_VS_25 = 6.59    # 95% CI (2.91, 14.9)

NEIGHBOURS_COEF = 3.090   # four or more bordering states at war, vs 0-3
NEIGHBOURS_OR = 22.0      # 95% CI (3.42, 142)

DISCRIM_COEF = 0.657      # state-led discrimination against a minority
DISCRIM_OR = 1.93         # 95% CI (1.08, 3.45)

# ---------------------------------------------------------------------
# TABLE 2, THE OUT-OF-SAMPLE TEST. The only calibration in the paper.
# ---------------------------------------------------------------------

OOS = {
    "country_years": 1246, "onsets": 21, "flagged": 251,
    "flagged_and_onset": 18, "clear": 995, "clear_and_onset": 3,
    "window_years": 2, "period": "1995-2004",
}


def base_rates():
    o = OOS
    return {
        "overall":     o["onsets"] / o["country_years"],
        "if_flagged":  o["flagged_and_onset"] / o["flagged"],
        "if_clear":    o["clear_and_onset"] / o["clear"],
        "sensitivity": o["flagged_and_onset"] / o["onsets"],
        "specificity": (o["clear"] - o["clear_and_onset"]) /
                       (o["country_years"] - o["onsets"]),
        "false_alarms": o["flagged"] - o["flagged_and_onset"],
    }


# ---------------------------------------------------------------------
# The infant mortality scale.
#
# The published effect is a single quartile contrast: odds ratio 6.59
# between the 75th and 25th percentiles of the global distribution. To
# place a country anywhere else on that scale you need a shape, and the
# defensible one is that log infant mortality is roughly normal across
# countries. The quartiles then sit at -+0.6745 standard deviations, so
# the published contrast spans 1.349 SD.
#
# Linear-in-percentile would be the lazier choice and it UNDERSTATES the
# tails, which is exactly where the rich countries are -- so it would
# flatter rich democracies. The normal map is used instead.
# ---------------------------------------------------------------------

_SPAN = math.log(IMR_OR_75_VS_25) / IMR_COEF      # 1.186 logged units
_PER_SD = _SPAN / 1.3490                          # 0.879 per SD


def _probit(p):
    """Inverse normal CDF, Acklam's rational approximation."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02,
         -2.759285104469687e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02,
         -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00, 2.938163982698783e+00]
    dd = [7.784695709041462e-03, 3.224671290700398e-01,
          2.445134137142996e+00, 3.754408661907416e+00]
    pl = 0.02425
    if p <= 0:
        return -8.0
    if p >= 1:
        return 8.0
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1)
    if p > 1 - pl:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1)
    q, r = p - 0.5, (p - 0.5) ** 2
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def imr_scale(pct):
    return _probit(pct / 100.0) * _PER_SD


def score(regime, imr_percentile=50, neighbours_at_war=0,
          discrimination=False):
    """The model's risk score: the linear predictor, in log-odds relative
    to the reference profile. This is what the model actually produces and
    what it was designed to be ranked on."""
    z = REGIME[regime][0]
    z += IMR_COEF * imr_scale(imr_percentile)
    if neighbours_at_war >= 4:
        z += NEIGHBOURS_COEF
    if discrimination:
        z += DISCRIM_COEF
    return z


# ---------------------------------------------------------------------
# Locating a country in the ranking.
#
# The ranking needs a population to rank against. The regime shares below
# are estimates of today's roughly 165 eligible states and are the
# softest numbers in this file -- they carry provenance `estimated` and
# the sensitivity block reports what happens when they move. Infant
# mortality is uniform on percentile by definition, which costs nothing.
# ---------------------------------------------------------------------

WORLD = {
    "regime_shares": {
        "full_democracy":           0.34,
        "partial_dem_nonfactional": 0.15,
        "partial_dem_factional":    0.12,
        "partial_autocracy":        0.21,
        "full_autocracy":           0.18,
    },
    "p_four_neighbours_at_war": 0.06,
    "p_discrimination":         0.35,
    "_shares_basis":
        "Approximate shares of the ~165 states with population over "
        "500,000, from the Polity/V-Dem regime distributions. Estimated, "
        "not counted.",
    "_neighbours_basis":
        "The paper notes that 77 of 160 countries in 2003 had four or more "
        "bordering countries at all, and that 11 of 117 onsets occurred in "
        "countries with four or more neighbours IN CONFLICT. The share of "
        "all countries meeting the conflict threshold is smaller than "
        "either figure; 6% is an estimate.",
}


def ranking(n=60000, seed=11, world=None):
    """Simulate the world distribution of scores and return it sorted."""
    w = world or WORLD
    rng = random.Random(seed)
    cats = list(w["regime_shares"])
    wts = [w["regime_shares"][c] for c in cats]
    cum, acc = [], 0.0
    for x in wts:
        acc += x
        cum.append(acc)
    out = []
    for _ in range(n):
        u = rng.random() * cum[-1]
        reg = cats[next(i for i, c in enumerate(cum) if u <= c)]
        pct = rng.random() * 100
        nb = 4 if rng.random() < w["p_four_neighbours_at_war"] else 0
        di = rng.random() < w["p_discrimination"]
        out.append(score(reg, pct, nb, di))
    out.sort()
    return out


def percentile_of(z, dist):
    lo, hi = 0, len(dist)
    while lo < hi:
        mid = (lo + hi) // 2
        if dist[mid] < z:
            lo = mid + 1
        else:
            hi = mid
    return 100.0 * lo / len(dist)


def flagged(z, dist):
    """Is this score in the top quintile -- the cut the paper's own
    out-of-sample test was scored at."""
    return percentile_of(z, dist) >= 80.0


def annual_risk(z, dist):
    """The paper's own calibration for the two sides of the cut. This is
    the only absolute probability the paper supports, and it is the same
    for every country on the same side of the line."""
    b = base_rates()
    return b["if_flagged"] if flagged(z, dist) else b["if_clear"]


def over(annual, years):
    return 1 - (1 - annual) ** years


def extrapolating(imr_percentile, regime, neighbours_at_war):
    out = []
    if imr_percentile < 25:
        out.append(
            "Infant mortality sits below the 25th percentile of the global "
            "distribution, which is the lowest point the published effect "
            "is anchored at. Below it, the line is being continued past "
            "its data.")
    if regime == "full_democracy":
        out.append(
            "The full-democracy coefficient has a 95% confidence interval "
            "of (0.70, 10.2) on the odds ratio. That interval crosses 1, "
            "so on this model a full democracy cannot be distinguished "
            "from a full autocracy on instability risk at all. It is the "
            "one coefficient in Table 1 that is not significant, and it is "
            "the one most rich-country applications lean on.")
    if neighbours_at_war < 4:
        out.append(
            "The neighbours-at-war variable is off, and it is the largest "
            "coefficient in the model after factionalism. For a country "
            "that cannot plausibly reach the threshold, a quarter of the "
            "model is permanently inactive -- which is a reason its "
            "remaining variables carry more weight than they were fitted "
            "to carry.")
    return out


# ---------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------

try:  # optional worked examples, loaded when present
    from private_examples import PITF_PROFILES as PROFILES
except ImportError:
    PROFILES = {}

PROV_W = {"measured": 1.0, "estimated": 0.45, "guessed": 0.0}


def grade(name, dist):
    """Roughness, weighted by how much each variable moves the country's
    POSITION IN THE RANKING -- which is what the model outputs."""
    p = PROFILES[name]
    here = percentile_of(score(p["regime"], p["imr_percentile"],
                               p["neighbours_at_war"],
                               p["discrimination"]), dist)

    def at(**kw):
        a = dict(regime=p["regime"], imr_percentile=p["imr_percentile"],
                 neighbours_at_war=p["neighbours_at_war"],
                 discrimination=p["discrimination"])
        a.update(kw)
        return percentile_of(score(**a), dist)

    alt = ("full_democracy" if p["regime"] != "full_democracy"
           else "partial_dem_factional")
    infl = {
        "regime":     abs(at(regime=alt) - here),
        "imr":        abs(at(imr_percentile=50) - here),
        "neighbours": abs(at(neighbours_at_war=4) - here),
        "discrim":    abs(at(discrimination=not p["discrimination"]) - here),
    }
    provs = {"regime": p["regime_prov"], "imr": p["imr_prov"],
             "neighbours": p["neighbours_prov"], "discrim": p["discrim_prov"]}
    tot = sum(infl.values()) or 1.0
    sc = sum(PROV_W[provs[k]] * infl[k] for k in infl) / tot
    band = ("WELL GROUNDED" if sc >= 0.75 else "MODERATE" if sc >= 0.50
            else "ROUGH" if sc >= 0.25 else "VERY ROUGH")
    return sc, band, infl, provs, here


def report(name):
    p = PROFILES[name]
    b = base_rates()
    dist = ranking()
    sc, band, infl, provs, here = grade(name, dist)
    z = score(p["regime"], p["imr_percentile"], p["neighbours_at_war"],
              p["discrimination"])

    print("=" * 74)
    print("  PITF INSTABILITY MODEL -- " + name.replace("_", " ").upper())
    print("=" * 74)
    print()
    print(f"  HOW ROUGH: {band}  (provenance score {sc:.2f})")
    print("  " + "-" * 70)
    D.para("Weighted by how far each variable moves this country in the "
           "ranking, not by counting variables. A measured variable that "
           "decides nothing should not lift the grade, and a judged one "
           "that decides everything should sink it.")
    print()
    for k in sorted(infl, key=lambda x: -infl[x]):
        print(f"   {k:<12}{provs[k]:<11}moves it "
              f"{infl[k]:>5.1f} percentile points in the ranking")
    print()

    print("  THE PROFILE")
    print("  " + "-" * 70)
    print(f"   regime type           {p['regime']}")
    print(f"   infant mortality      {p['imr_percentile']}th percentile "
          f"globally (lower is safer)")
    print(f"   neighbours at war     {p['neighbours_at_war']}  "
          f"(the threshold is 4)")
    print(f"   state discrimination  {'yes' if p['discrimination'] else 'no'}")
    print()

    print("  WHERE IT LANDS")
    print("  " + "-" * 70)
    fl = flagged(z, dist)
    D.para(f"Risk score {z:+.2f} in log-odds against the reference profile, "
           f"which puts this country at the {here:.0f}th percentile of the "
           f"world ranking. The model flags the top 20th percentile. "
           f"This country is {'INSIDE' if fl else 'OUTSIDE'} the flag.")
    print()
    r = annual_risk(z, dist)
    D.para(f"The paper's own out-of-sample calibration for that side of the "
           f"cut: about {r*100:.1f} in 100 chance per year that an "
           f"instability onset begins -- a civil war, an ethnic war, or an "
           f"adverse regime change, not specifically a civil war. Which is "
           f"the same as about {(1-r)*100:.1f} in 100 that no onset begins "
           f"in a given year.")
    print()
    D.para(f"Against the world base rate of {b['overall']*100:.1f} in 100 "
           f"per country-year, that is {r/b['overall']:.1f} times an "
           f"average country's risk.")
    print()
    print(f"   over 10 years at that rate: {over(r,10)*100:>5.1f}%  "
          f"({(1-over(r,10))*100:.1f}% that nothing starts)")
    print(f"   over 25 years at that rate: {over(r,25)*100:>5.1f}%  "
          f"({(1-over(r,25))*100:.1f}% that nothing starts)")
    print()
    D.para("Both lines assume the classification holds for the whole "
           "period, which is the least likely thing in this file. "
           "Factionalism episodes in the Polity record usually run under a "
           "decade. Read these as what the arithmetic implies if nothing "
           "changes, which is not a forecast.")
    print()

    print("  WHAT IS OUTSIDE THE FITTED RANGE")
    print("  " + "-" * 70)
    for w in extrapolating(p["imr_percentile"], p["regime"],
                           p["neighbours_at_war"]):
        for line in D.wrap(w, 66):
            print("   " + line)
        print()

    print("  IF ONE VARIABLE WERE CODED DIFFERENTLY")
    print("  " + "-" * 70)
    print("   {:<34}{:>8}{:>12}".format("", "rank", "flagged?"))
    for lab, kw in [
        ("full democracy", dict(regime="full_democracy")),
        ("partial democracy, no factionalism",
         dict(regime="partial_dem_nonfactional")),
        ("partial democracy WITH factionalism",
         dict(regime="partial_dem_factional")),
        ("partial autocracy", dict(regime="partial_autocracy")),
        ("discrimination flipped",
         dict(discrimination=not p["discrimination"])),
        ("infant mortality at world median", dict(imr_percentile=50)),
        ("infant mortality at 75th percentile", dict(imr_percentile=75)),
        ("four neighbours at war", dict(neighbours_at_war=4)),
    ]:
        a = dict(regime=p["regime"], imr_percentile=p["imr_percentile"],
                 neighbours_at_war=p["neighbours_at_war"],
                 discrimination=p["discrimination"])
        a.update(kw)
        zz = score(**a)
        print("   {:<34}{:>7.0f}{:>12}".format(
            lab, percentile_of(zz, dist),
            "YES" if flagged(zz, dist) else "no"))
    print()

    print("  WHAT WOULD HAVE TO CHANGE TO CROSS THE FLAG")
    print("  " + "-" * 70)
    lo, hi = 0.5, 99.5
    for _ in range(50):
        mid = (lo + hi) / 2
        a = dict(regime=p["regime"], imr_percentile=mid,
                 neighbours_at_war=p["neighbours_at_war"],
                 discrimination=p["discrimination"])
        if flagged(score(**a), dist):
            hi = mid
        else:
            lo = mid
    if 1 < hi < 99:
        D.para(f"Holding everything else, infant mortality would have to "
               f"reach the {hi:.0f}th percentile globally for this country "
               f"to cross into the flagged fifth "
               f"{'(it is already inside)' if flagged(z, dist) else ''}. "
               f"It is at the {p['imr_percentile']}th.")
    else:
        D.para("Infant mortality alone cannot move this country across the "
               "cut in either direction -- the regime coding decides it.")
    print()


def model_card():
    b, o = base_rates(), OOS
    print("=" * 74)
    print("  WHAT THE MODEL'S ACCURACY ACTUALLY IS")
    print("=" * 74)
    print()
    D.para(f"The authors' own out-of-sample test, {o['period']}. Forecasts "
           f"made from data {o['window_years']} years earlier, on every "
           f"country over 500,000 people with no ongoing conflict. Table 2 "
           f"of the paper, printed as a table rather than as a sentence.")
    print()
    print("                         onset followed     stayed stable")
    print("   " + "-" * 62)
    print(f"   model flagged it     {o['flagged_and_onset']:>10}"
          f"      {b['false_alarms']:>13}")
    print(f"   model cleared it     {o['clear_and_onset']:>10}"
          f"      {o['clear']-o['clear_and_onset']:>13}")
    print()
    print(f"   of {o['onsets']} onsets, {o['flagged_and_onset']} were "
          f"flagged              {b['sensitivity']*100:>5.1f}%")
    print(f"   of {o['country_years']-o['onsets']} stable years, "
          f"{o['country_years']-o['onsets']-b['false_alarms']:.0f} cleared"
          f"      {b['specificity']*100:>5.1f}%")
    print("   " + "-" * 62)
    print(f"   of the {o['flagged']} it FLAGGED, {o['flagged_and_onset']} "
          f"had an onset       {b['if_flagged']*100:>5.1f}%")
    print(f"   of the {o['clear']} it CLEARED, {o['clear_and_onset']} had "
          f"an onset         {b['if_clear']*100:>5.1f}%")
    print()
    D.para(f"All four lines come out of the same four cells. The first two "
           f"are what gets quoted; the last two are what you need if you "
           f"are the country being flagged. A flag moves you from "
           f"{b['overall']*100:.1f} in 100 to {b['if_flagged']*100:.1f} in "
           f"100 per year, and being cleared puts you at "
           f"{b['if_clear']*100:.1f} in 100. That is a real screen -- a "
           f"{b['if_flagged']/b['overall']:.1f}-fold lift two years out "
           f"from four variables. It is not a prediction that the flagged "
           f"country breaks down.")
    print()
    print("  SOURCE")
    print("  " + "-" * 70)
    for line in D.wrap(CITE, 66):
        print("   " + line)
    print()


def main():
    if len(sys.argv) < 2:
        print("profiles:", ", ".join(PROFILES))
        print("also: card")
        return
    if sys.argv[1] == "card":
        model_card()
        return
    report(sys.argv[1])


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
