#!/usr/bin/env python3
"""
reference_models.py -- the standard formal model for a topic, so the
                       steelman step has something real to hold a claim
                       against.

WHY THIS EXISTS. The core Elipsis move is to take a confident claim, build
its strongest form, and then show whether the model underneath has measured
numbers in it or is only a DIRECTION WITH NO MEASURED NUMBERS IN IT. That move only works if, at the steelman step, you already
know what the real formal model for the topic looks like. Without that recognition
there is nothing to hold the claim up against, and a strong-sounding
argument walks through unchecked.

So the value is not any one model. It is having, per topic that keeps
coming up, the one or two models somebody has actually written as maths,
with the quantities they REQUIRE you to measure. Then the check is
mechanical: pull the standard model, write it in standard notation, and
ask whether the claim in front of you fills in the terms or leaves them
empty. Most confident claims leave them empty. That is the finding.

HOW IT PLUGS IN. steelman -> (this) -> router -> the eleven -> mirror.
After the steelman names the strongest version, reference_models supplies
the formal shape for its topic and the `needs` list becomes the checklist
the claim must satisfy. A model marked `math` gives you terms to
substitute into; a model marked `logic` gives you conditions the claim
must establish, which is still a checklist, just not an arithmetic one.

THE DOCTRINE IS UNCHANGED. Code holds the catalogue; a model does the
substituting. Nothing here fits parameters or decides a case. It hands
you the equation and the list of what it needs, and the honesty is in
whether you can fill the list.

Every model: standard notation, an example substituted where there is a
clean one, a legend for every symbol, the measurable quantities it needs,
what it outputs, and a dated source. Facts are general knowledge unless a
source names otherwise.

Run:  python harness/reference_models.py
      python harness/reference_models.py war
      python harness/reference_models.py --model richardson_arms_race
      python harness/reference_models.py --match "will this spiral"
"""

import sys

# --------------------------------------------------------------------
# the catalogue
# --------------------------------------------------------------------
# Each entry:
#   id        short handle
#   topic     the shelf it sits on
#   name      what it is called, and by whom
#   kind      "math"  -> terms to substitute into
#             "logic" -> conditions the claim must establish
#   layer     the QUESTION_LIBRARY math layer (see harness/QUESTION_LIBRARY.md)
#   operation the Elipsis operation it serves (see the `operation` tool)
#   notation  standard notation, unicode
#   example   numbers substituted, when there is a clean one (else "")
#   legend    [(symbol, plain English), ...], every symbol defined
#   needs     the measurable quantities the claim MUST supply
#   output    what the model produces
#   source    dated citation
#   use       when to reach for it, and what it exposes
#   why       why this notation / one line

MODELS = [

    # ---------------------------- WAR AND ESCALATION ----------------
    {
        "id": "richardson_arms_race",
        "topic": "war and escalation",
        "name": "Richardson's arms-race equations",
        "kind": "math",
        "layer": "8 calculus",
        "operation": "predict",
        "notation": "dx/dt = k.y - a.x + g ,   dy/dt = l.x - b.y + h",
        "example": "with k=l=0.4, a=b=0.3, g=h=2 the race converges; with "
                   "k=l=0.5, a=b=0.3 it runs away",
        "legend": [
            ("x, y", "the two sides' arms spending (or arsenals)"),
            ("dx/dt", "how fast side x's spending is changing"),
            ("k, l", "how hard each side reacts to the other's arms "
                     "(the fear terms)"),
            ("a, b", "how fast each side's own spending tires under its own "
                     "cost (the fatigue terms)"),
            ("g, h", "standing grievance, the spending each side does even "
                     "with no threat"),
        ],
        "needs": [
            "current x and y, in one unit",
            "the reaction coefficients k, l (measured from past responses)",
            "the fatigue coefficients a, b",
            "the grievance constants g, h",
        ],
        "output": "whether the race settles to a stable level or diverges; "
                  "the stability test is k.l < a.b",
        "source": "Lewis Fry Richardson, Arms and Insecurity (1960).",
        "use": "The oldest formal arms-race model. Its gift is the stability "
               "line k.l < a.b: 'is this an escalating spiral' becomes one "
               "inequality in four measurable coefficients, the same "
               "collapse-to-a-parameter the steelman step wants.",
        "why": "Coupled rates of change, layer 8, because each side's "
               "spending changes in response to the other's level.",
    },
    {
        "id": "lanchester_square",
        "topic": "war and escalation",
        "name": "Lanchester's square law of combat",
        "kind": "math",
        "layer": "8 calculus",
        "operation": "predict",
        "notation": "dA/dt = -b.B ,  dB/dt = -a.A ;   conserved:  "
                    "a.A^2 - b.B^2 = constant",
        "example": "100 vs 80 at equal lethality: A ends with "
                   "sqrt(100^2 - 80^2) = 60 survivors, not 20",
        "legend": [
            ("A, B", "the two forces' numbers over time"),
            ("a, b", "each unit's firing effectiveness (kills per unit time)"),
            ("A^2, B^2", "numbers squared, which is why a 5:4 edge becomes a "
                         "much larger survivor margin"),
        ],
        "needs": [
            "starting numbers A and B",
            "the effectiveness a and b of each side's units",
            "that fire is aimed and concentrated (the law's assumption)",
        ],
        "output": "who wins and with how many left; the square makes numbers "
                  "dominate quality",
        "source": "F. W. Lanchester, Aircraft in Warfare (1916).",
        "use": "Whenever a claim says a smaller, better force wins, or "
               "concentration does not matter. The square law puts a number "
               "on how much numerical edge beats per-unit quality, and "
               "exposes 'quality over quantity' claims that never price the "
               "quality.",
        "why": "Attrition rates, layer 8; the conserved quantity is where "
               "the square, and the whole point, lives.",
    },
    {
        "id": "bdm_expected_utility",
        "topic": "war and escalation",
        "name": "the expected-utility model of conflict (Bueno de Mesquita)",
        "kind": "math",
        "layer": "6 probability / 10 optimization",
        "operation": "predict",
        "notation": "E(U) = p.U_win + (1 - p).U_lose - c",
        "example": "p=0.6, U_win=+10, U_lose=-8, c=3  ->  "
                   "0.6(10) + 0.4(-8) - 3 = -0.2, so do not start it",
        "legend": [
            ("E(U)", "expected value of starting the fight, all outcomes "
                     "weighted by their chance"),
            ("p", "probability of winning"),
            ("U_win", "value of the win"),
            ("U_lose", "value (negative) of the loss"),
            ("c", "the cost paid whether you win or lose"),
        ],
        "needs": [
            "an estimate of p, the win probability",
            "the values U_win and U_lose on one scale",
            "the certain cost c",
        ],
        "output": "whether a rational actor starts the conflict (E(U) > 0) or "
                  "not",
        "source": "Bruce Bueno de Mesquita, The War Trap (1981).",
        "use": "The decision-theoretic skeleton under most 'they would never "
               "dare' or 'they have no choice' claims. It forces the "
               "unstated p and the unstated costs onto the table; the claim "
               "usually asserts the sign of E(U) without any of its terms.",
        "why": "An expectation, layer 6 into layer 10, because it is a choice "
               "made under a probability.",
    },
    {
        "id": "fearon_bargaining",
        "topic": "war and escalation",
        "name": "the bargaining model of war (Fearon)",
        "kind": "logic",
        "layer": "12 game theory",
        "operation": "diagnose",
        "notation": "war occurs  <=>  no deal x in [0,1] beats fighting for "
                    "BOTH sides, which needs one of: private information + "
                    "incentive to bluff; a commitment problem; or an "
                    "indivisible stake",
        "example": "",
        "legend": [
            ("x", "a share of the disputed thing, 0 to 1"),
            ("the bargaining range", "the deals both sides prefer to war; war "
                                     "is a failure to find one in it"),
            ("the three mechanisms", "the only rational routes to an empty "
                                     "range: hidden strength you bluff about, "
                                     "a promise neither can be held to, or a "
                                     "prize that cannot be split"),
        ],
        "needs": [
            "which of the three mechanisms the claim says is operating",
            "evidence that a splitting deal really was unavailable, not just "
            "unwanted",
            "why the losing side could not be bought off",
        ],
        "output": "a diagnosis of WHY bargaining failed, not a probability; "
                  "if none of the three mechanisms holds, the war-as-"
                  "inevitable story is incomplete",
        "source": "James Fearon, 'Rationalist Explanations for War,' "
                  "International Organization 49(3), 1995.",
        "use": "The standard check on 'war was inevitable' or 'there was no "
               "choice.' Since a deal almost always exists on paper, the "
               "claim must name which of three specific failures blocked it. "
               "Most do not, and that gap is the finding.",
        "why": "A game-theoretic existence condition, layer 12: the content "
               "is whether a mutually-preferred deal exists, not a number.",
    },

    # ---------------------------- TERRORISM AND CIVIL WAR -----------
    {
        "id": "collier_hoeffler",
        "topic": "terrorism and civil war",
        "name": "the greed-versus-grievance model of civil-war onset "
                "(Collier and Hoeffler)",
        "kind": "math",
        "layer": "7 statistics / 9 linear algebra",
        "operation": "cause",
        "notation": "P(war) = 1 / (1 + e^-(B0 + B1.X1 + B2.X2 + ... ))",
        "example": "",
        "legend": [
            ("P(war)", "the fitted probability a country slides into civil "
                       "war in a given window"),
            ("X1, X2, ...", "the predictors: primary-commodity exports, "
                            "low income, slow growth, diaspora size, "
                            "mountainous terrain, ethnic dominance"),
            ("B0, B1, ...", "weights fitted from the historical record"),
            ("e^-(...)", "the logistic link that keeps the output between 0 "
                         "and 1"),
        ],
        "needs": [
            "values of the predictors X for the case in question",
            "the fitted weights B (from the study, or refitted)",
            "awareness that 'greed' proxies are contested, not clean causes",
        ],
        "output": "a probability of civil-war onset, and which predictors "
                  "carry it",
        "source": "Paul Collier and Anke Hoeffler, 'Greed and Grievance in "
                  "Civil War,' Oxford Economic Papers 56(4), 2004.",
        "use": "The reference point for any 'rebellion is about injustice' or "
               "'it is really about resources' claim. It is a real fitted "
               "model, so it turns a moral story into predictors with "
               "weights, and shows which the data actually supports.",
        "why": "A logistic regression, layers 7 and 9: many predictors at "
               "once, squeezed to a probability.",
    },

    # ---------------------------- EPIDEMICS AND SPREAD --------------
    {
        "id": "sir_seir",
        "topic": "epidemics and spread",
        "name": "the SIR / SEIR compartment model",
        "kind": "math",
        "layer": "8 calculus",
        "operation": "predict",
        "notation": "dS/dt = -b.S.I/N ,  dI/dt = b.S.I/N - g.I ,  "
                    "dR/dt = g.I ;   R0 = b/g",
        "example": "b=0.6/day, g=0.2/day  ->  R0 = 3, so each case makes "
                   "three while everyone is susceptible",
        "legend": [
            ("S, I, R", "susceptible, infected, recovered counts"),
            ("N", "the total population, S+I+R"),
            ("b (beta)", "transmission rate, contacts times infection chance "
                         "per unit time"),
            ("g (gamma)", "recovery rate; 1/g is how long one stays "
                          "infectious"),
            ("R0", "the basic reproduction number, cases made per case in a "
                   "fully susceptible population"),
        ],
        "needs": [
            "the transmission rate b",
            "the recovery rate g (or the infectious period 1/g)",
            "the starting S, I, R and N",
        ],
        "output": "the epidemic curve, the peak, and the final size; it grows "
                  "if R0 > 1 and dies out if R0 < 1",
        "source": "W. O. Kermack and A. G. McKendrick, Proceedings of the "
                  "Royal Society A 115, 1927.",
        "use": "For anything that spreads through contact: disease, rumour, a "
               "meme, a bank run by word of mouth. 'Will this take off' "
               "becomes 'is R0 above 1', one ratio of two measurable rates. "
               "This is the collapse-to-a-parameter the steelman step prizes.",
        "why": "Compartment flows, layer 8; R0 = b/g is the single number the "
               "whole curve turns on.",
    },

    # ---------------------------- COLLECTIVE BEHAVIOUR --------------
    {
        "id": "granovetter_threshold",
        "topic": "collective behaviour",
        "name": "the threshold model of collective behaviour (Granovetter)",
        "kind": "math",
        "layer": "7 statistics / 11 networks",
        "operation": "predict",
        "notation": "r(t+1) = F(r(t)) ;   outcome is the stable point where "
                    "F(x*) = x*",
        "example": "a crowd where thresholds are spread evenly 0..100 tips to "
                   "everyone; shift one person's threshold up by one and it "
                   "can stall at a handful",
        "legend": [
            ("r(t)", "the fraction already taking part at time t"),
            ("threshold", "how many others a given person needs to see acting "
                          "before they join"),
            ("F", "the cumulative distribution of thresholds: the share whose "
                  "threshold is at or below the current turnout"),
            ("x*", "the equilibrium turnout, where no one new is tipped"),
        ],
        "needs": [
            "the distribution of thresholds across the population",
            "the starting fraction r(0)",
            "that people see and respond to the current turnout",
        ],
        "output": "the final size of the movement, riot or cascade, which can "
                  "flip wildly on a tiny change in the threshold distribution",
        "source": "Mark Granovetter, 'Threshold Models of Collective "
                  "Behavior,' American Journal of Sociology 83(6), 1978.",
        "use": "The right lens for bank runs, riots, viral "
               "adoption: it shows a cascade can happen with NO extreme "
               "individuals, just an unlucky threshold spread. Kills the "
               "'they must all be zealots' reading of a pile-on.",
        "why": "A fixed-point of a cumulative distribution, layers 7 and 11: "
               "the outcome is where turnout reproduces itself.",
    },
    {
        "id": "schelling_segregation",
        "topic": "collective behaviour",
        "name": "the segregation / tipping model (Schelling)",
        "kind": "logic",
        "layer": "11 networks (agent-based)",
        "operation": "simulate",
        "notation": "each agent moves if  (like neighbours / all neighbours) "
                    "< tau ;  run to rest",
        "example": "with tau = 1/3 (each wants only a third like itself) a "
                   "grid still sorts into sharp blocks",
        "legend": [
            ("tau (tau)", "the tolerance threshold: the smallest share of "
                          "like-neighbours an agent will stay for"),
            ("the rule", "unhappy agents relocate; repeat until no one wants "
                         "to move"),
        ],
        "needs": [
            "the tolerance threshold tau",
            "the starting layout and move rule",
            "a simulation, since there is no closed formula",
        ],
        "output": "the resting pattern, which is far more segregated than any "
                  "individual preference",
        "source": "Thomas Schelling, 'Dynamic Models of Segregation,' "
                  "Journal of Mathematical Sociology 1, 1971.",
        "use": "Whenever an outcome (segregated neighbourhoods, sorted "
               "audiences) is blamed on strong individual prejudice. Schelling "
               "shows mild preferences produce extreme sorting, so the "
               "aggregate pattern is poor evidence of individual intensity.",
        "why": "Agent-based, layer 11: the macro pattern emerges from local "
               "moves and must be simulated, not solved.",
    },

    # ---------------------------- ANIMAL CONFLICT ------------------
    {
        "id": "hawk_dove_ess",
        "topic": "animal conflict and social evolution",
        "name": "the hawk-dove game and the evolutionarily stable strategy "
                "(Maynard Smith)",
        "kind": "math",
        "layer": "12 game theory",
        "operation": "strategize",
        "notation": "payoff(Hawk vs Hawk) = (V - C)/2 ;  when C > V the ESS "
                    "is mixed with  p* = V/C  hawks",
        "example": "V=2, C=10  ->  p* = 0.2, so a stable population settles "
                   "near one in five playing hawk",
        "legend": [
            ("V", "the value of the contested resource"),
            ("C", "the cost of an escalated fight (injury)"),
            ("Hawk", "escalate and risk the fight"),
            ("Dove", "display, retreat if challenged"),
            ("p*", "the stable fraction playing hawk; no mutant does better"),
        ],
        "needs": [
            "the resource value V and the injury cost C, in one unit",
            "whether contests are symmetric or settled by an asymmetry "
            "(ownership, size)",
        ],
        "output": "the stable mix of force and restraint; force pays only up "
                  "to p* = V/C, after which restraint does better",
        "source": "John Maynard Smith and George Price, 'The Logic of Animal "
                  "Conflict,' Nature 246, 1973; Maynard Smith, Evolution and "
                  "the Theory of Games (1982).",
        "use": "The formal model of force versus power: when "
               "does aggression pay, and when does a coalition suppress it. It "
               "shows force is self-limiting (high C lowers p*), so unchecked "
               "dominance is bounded, not total.",
        "why": "An ESS, layer 12: the stable point is a strategy mix no "
               "mutant can beat, which is exactly 'what will the other side "
               "do'.",
    },
    {
        "id": "lotka_volterra",
        "topic": "animal conflict and social evolution",
        "name": "the Lotka-Volterra predator-prey equations",
        "kind": "math",
        "layer": "8 calculus",
        "operation": "predict",
        "notation": "dx/dt = a.x - b.x.y ,   dy/dt = d.x.y - g.y",
        "example": "predators lag prey by a quarter-cycle; both oscillate "
                   "forever in the simplest form",
        "legend": [
            ("x", "prey numbers"),
            ("y", "predator numbers"),
            ("a", "prey birth rate with no predators"),
            ("b", "rate prey are caught per predator"),
            ("d", "predator births per prey eaten"),
            ("g", "predator death rate with no prey"),
        ],
        "needs": [
            "the four rates a, b, d, g",
            "starting x and y",
        ],
        "output": "the cycle of boom and bust, and whether it is stable; "
                  "neither population sits still",
        "source": "Alfred Lotka (1925); Vito Volterra, Nature 118, 1926.",
        "use": "For any claim that two "
               "coupled populations (hunters and hunted, buyers and sellers) "
               "reach a flat equilibrium. The base model says they cycle, so "
               "'it settled down' needs the damping term that does it.",
        "why": "Coupled growth rates, layer 8: each population's change "
               "depends on the product of the two.",
    },

    # ---------------------------- SEX RATIO AND DEMOGRAPHY ----------
    {
        "id": "fisher_sex_ratio",
        "topic": "sex ratio and demography",
        "name": "Fisher's principle of sex ratio",
        "kind": "math",
        "layer": "12 game theory / 6 probability",
        "operation": "predict",
        "notation": "at equal cost per sex the stable ratio is 1:1; a parent "
                    "gains by making the rarer sex until  "
                    "(spend on sons)/(sons) = (spend on daughters)/(daughters)",
        "example": "if sons cost twice as much to raise, the stable NUMBER "
                   "ratio is two daughters per son, equal INVESTMENT either "
                   "way",
        "legend": [
            ("the ratio", "newborn males to females"),
            ("frequency dependence", "whichever sex is rarer has more mates "
                                     "each, so parents of it out-reproduce"),
            ("equal investment", "the equilibrium balances total spend on "
                                 "each sex, not head count"),
        ],
        "needs": [
            "the relative cost of raising each sex",
            "whether some force (a 50:50 meiosis, a distorter gene, "
            "selective survival) breaks the equal-investment default",
        ],
        "output": "the sex ratio a population should sit at, and why it "
                  "returns there after a shock",
        "source": "Ronald Fisher, The Genetical Theory of Natural Selection "
                  "(1930).",
        "use": "It says the default "
               "is near 1:1 by investment, so a sustained skew needs a named "
               "distorting force; it turns 'the ratio is skewed here' into "
               "'what is pushing off the Fisher equilibrium, and by how "
               "much'.",
        "why": "A frequency-dependent equilibrium, layer 12 on layer 6: the "
               "payoff to producing a sex falls as that sex gets common.",
    },
    {
        "id": "trivers_willard",
        "topic": "sex ratio and demography",
        "name": "the Trivers-Willard hypothesis",
        "kind": "logic",
        "layer": "6 probability",
        "operation": "predict",
        "notation": "mothers in good condition should bias offspring toward "
                    "the sex whose reproductive payoff rises fastest with "
                    "condition (often sons); poor condition toward the other",
        "example": "",
        "legend": [
            ("condition", "the mother's resources or status"),
            ("the bias", "a shift in the sex ratio of her offspring, not a "
                         "guarantee"),
            ("the premise", "one sex's breeding success varies more with "
                            "early advantage than the other's"),
        ],
        "needs": [
            "evidence the two sexes really differ in how payoff scales with "
            "condition, for this species",
            "a measured ratio shift tied to measured condition, not a story",
        ],
        "output": "a predicted direction of sex-ratio bias by parental "
                  "condition; a hypothesis, often weakly supported in humans",
        "source": "Robert Trivers and Dan Willard, Science 179, 1973.",
        "use": "The named hypothesis behind 'wealthy / tall / high-status "
               "families have more sons (or daughters)'. Mark it logic: the "
               "human evidence is mixed, so a claim invoking it owes a "
               "measured shift, not the mechanism alone.",
        "why": "A conditional direction, layer 6: it predicts the sign of a "
               "bias given condition, with no magnitude of its own.",
    },
    {
        "id": "leslie_matrix",
        "topic": "sex ratio and demography",
        "name": "the Leslie matrix for population projection",
        "kind": "math",
        "layer": "9 linear algebra",
        "operation": "predict",
        "notation": "n(t+1) = L . n(t) ;   long-run growth = lambda, the "
                    "largest eigenvalue of L",
        "example": "lambda = 1.00 means a stable population; 1.02 means 2 "
                   "more per 100 per step; below 1 it shrinks",
        "legend": [
            ("n(t)", "the age structure: how many in each age band now"),
            ("L", "the projection matrix: birth rates along the top row, "
                  "survival rates on the sub-diagonal"),
            ("lambda (lambda)", "the dominant eigenvalue, the eventual "
                                "growth factor per step"),
        ],
        "needs": [
            "age-specific birth rates",
            "age-specific survival rates",
            "the current age structure n(0)",
        ],
        "output": "the population's size and age shape over time, and its "
                  "long-run growth rate lambda",
        "source": "P. H. Leslie, Biometrika 33, 1945.",
        "use": "For any 'this population will collapse / explode' claim. "
               "It converts a scary "
               "headline into lambda, one eigenvalue, and shows whether "
               "momentum or decline is already locked into the age "
               "structure.",
        "why": "A matrix iteration, layer 9: many age bands advance at once, "
               "and the eigenvalue is the growth rate they settle to.",
    },

    # ---------------------------- ECONOMICS AND GEOGRAPHY ----------
    {
        "id": "gravity_trade",
        "topic": "economics and geography",
        "name": "the gravity model of trade",
        "kind": "math",
        "layer": "7 statistics / 9 linear algebra",
        "operation": "estimate",
        "notation": "T_ij = G . (M_i . M_j) / D_ij^th",
        "example": "double the distance with th=1 and trade roughly halves, "
                   "holding sizes fixed",
        "legend": [
            ("T_ij", "trade between places i and j"),
            ("M_i, M_j", "the two places' economic size (GDP) or population"),
            ("D_ij", "the distance, or broader friction, between them"),
            ("th (theta)", "how sharply trade falls with distance"),
            ("G", "a scaling constant"),
        ],
        "needs": [
            "the sizes M_i, M_j",
            "the distance or friction D_ij",
            "the distance elasticity th (fitted from data)",
        ],
        "output": "the expected flow between two places; residuals flag pairs "
                  "that trade far more or less than size and distance predict",
        "source": "Jan Tinbergen (1962); modern form, James Anderson and "
                  "Eric van Wincoop, American Economic Review 93(1), 2003.",
        "use": "For any 'country A should trade / align with B' claim. It "
               "gives the baseline from size and distance, so the real "
               "question becomes what explains the gap from it, not the raw "
               "flow.",
        "why": "A multiplicative law fitted in logs, layers 7 and 9; named "
               "for its likeness to Newton's gravity.",
    },
    {
        "id": "krugman_core_periphery",
        "topic": "economics and geography",
        "name": "the core-periphery model of new economic geography "
                "(Krugman)",
        "kind": "logic",
        "layer": "10 optimization / 12 game theory",
        "operation": "predict",
        "notation": "industry concentrates when  (scale economies + linkages) "
                    "> transport cost ;  below a transport-cost threshold the "
                    "symmetric spread becomes unstable and one region wins",
        "example": "",
        "legend": [
            ("forward/backward linkages", "firms want to be near suppliers "
                                          "and customers, which pulls them "
                                          "together"),
            ("transport cost", "the force pushing production out toward "
                               "dispersed markets"),
            ("the threshold", "the trade-cost level below which concentration "
                              "suddenly takes over"),
        ],
        "needs": [
            "the strength of scale economies and linkages",
            "the level of transport / trade cost",
            "whether the economy is above or below the tipping threshold",
        ],
        "output": "whether industry agglomerates into one core or spreads "
                  "out; concentration is often the stable outcome",
        "source": "Paul Krugman, 'Increasing Returns and Economic Geography,' "
                  "Journal of Political Economy 99(3), 1991.",
        "use": "It says concentration is a tipping outcome, not a choice, once "
               "trade costs fall, so 'build one hub' can be right for "
               "structural reasons, and 'spread it evenly' can be unstable.",
        "why": "A tipping model from increasing returns, layers 10 and 12: "
               "the symmetric outcome loses stability at a cost threshold.",
    },
    {
        "id": "leontief_io",
        "topic": "economics and geography",
        "name": "the Leontief input-output model",
        "kind": "math",
        "layer": "9 linear algebra",
        "operation": "allocate",
        "notation": "x = (I - A)^-1 . d",
        "example": "a demand d for cars pulls steel, glass and rubber through "
                   "(I - A)^-1, giving the total output x each industry must "
                   "make",
        "legend": [
            ("x", "total output needed from each industry"),
            ("A", "the input-output table: how much of each industry's output "
                  "every other industry needs per unit"),
            ("I", "the identity matrix"),
            ("d", "final demand, what end users want"),
            ("(I - A)^-1", "the Leontief inverse, which traces every "
                           "knock-on requirement"),
        ],
        "needs": [
            "the technical-coefficient table A (from BEA / Census make-use "
            "tables)",
            "the final demand vector d",
        ],
        "output": "the output every industry must produce to meet demand, "
                  "including all the indirect supply-chain pulls",
        "source": "Wassily Leontief (1936); U.S. BEA input-output accounts.",
        "use": "The spine of an industrial gap map: what feeds what, and "
               "where a missing domestic supplier forces imports. It turns "
               "'the US cannot make X on its own' into which rows of (I - A) "
               "point abroad.",
        "why": "A linear system solved by matrix inverse, layer 9: the "
               "indirect requirements are the whole point and only the "
               "inverse captures them.",
    },
    {
        "id": "economic_complexity",
        "topic": "economics and geography",
        "name": "the Economic Complexity Index and product space "
                "(Hausmann and Hidalgo)",
        "kind": "math",
        "layer": "9 linear algebra / 11 networks",
        "operation": "estimate",
        "notation": "RCA_cp > 1 marks what a place makes well; iterate "
                    "diversity and ubiquity (the method of reflections) to "
                    "get ECI",
        "example": "",
        "legend": [
            ("RCA_cp", "revealed comparative advantage: does country c export "
                       "more of product p than its share of world trade would "
                       "predict"),
            ("diversity", "how many products a country makes well"),
            ("ubiquity", "how many countries make a given product well"),
            ("ECI", "the complexity score: high means a place makes many "
                    "things few others can"),
        ],
        "needs": [
            "the export (or production) matrix by place and product",
            "the RCA cutoff",
        ],
        "output": "a ranking of what each place can do and what it is "
                  "plausibly near doing next in the product space",
        "source": "Cesar Hidalgo and Ricardo Hausmann, PNAS 106(26), 2009; "
                  "the Atlas of Economic Complexity.",
        "use": "The existing gap map's economic cousin. For 'the US should "
               "build industry X here', it shows whether the local capability "
               "set is near X in the product space or a long jump away.",
        "why": "An eigenvector-style index on a bipartite network, layers 9 "
               "and 11: capability is inferred from who else makes the same "
               "things.",
    },

    # ---------------------------- ADOPTION AND TECHNOLOGY ----------
    {
        "id": "bass_diffusion",
        "topic": "adoption and technology",
        "name": "the Bass diffusion model",
        "kind": "math",
        "layer": "8 calculus",
        "operation": "predict",
        "notation": "f(t) / (1 - F(t)) = p + q . F(t)",
        "example": "p=0.03, q=0.38 gives the classic adoption S-curve "
                   "peaking partway up",
        "legend": [
            ("F(t)", "the fraction who have adopted by time t"),
            ("f(t)", "the rate of new adoption at t"),
            ("p", "coefficient of innovation: adoption from outside influence "
                  "(ads, novelty)"),
            ("q", "coefficient of imitation: adoption driven by those who "
                  "already have it (word of mouth)"),
        ],
        "needs": [
            "the innovation rate p",
            "the imitation rate q",
            "the eventual market size the fraction is of",
        ],
        "output": "the whole adoption curve and its peak timing; the "
                  "imitation term q is what makes it an S, not a straight "
                  "line",
        "source": "Frank Bass, Management Science 15(5), 1969.",
        "use": "For any 'this technology will take over in N years' claim. "
               "It forces the imitation term that governs speed; a fast "
               "takeover claim asserts a q it never measures.",
        "why": "A hazard split into innovation and imitation, layer 8: the "
               "S-shape comes from q, the feedback from current adopters.",
    },
    {
        "id": "logistic_scurve",
        "topic": "adoption and technology",
        "name": "the logistic (Verhulst) growth curve",
        "kind": "math",
        "layer": "8 calculus",
        "operation": "predict",
        "notation": "dN/dt = r.N.(1 - N/K) ;   N(t) = K / (1 + e^-r.(t - t0))",
        "example": "growth is fastest at N = K/2 and flattens as N nears K",
        "legend": [
            ("N(t)", "the amount present at time t"),
            ("r", "the intrinsic growth rate when room is plentiful"),
            ("K", "the ceiling, the carrying capacity"),
            ("t0", "the midpoint, when N = K/2"),
        ],
        "needs": [
            "the growth rate r",
            "the ceiling K",
            "where on the curve the present sits",
        ],
        "output": "an S-curve that looks exponential early and saturates "
                  "late; distinguishes 'still accelerating' from 'near the "
                  "ceiling'",
        "source": "Pierre Verhulst (1838).",
        "use": "The general shape under most 'exponential' claims. The useful "
               "move is to ask for K: a curve called exponential is usually "
               "logistic with the ceiling left offstage, which changes every "
               "forecast past the midpoint.",
        "why": "Self-limiting growth, layer 8: the (1 - N/K) term is the brake "
               "that an 'exponential' story omits.",
    },
    {
        "id": "chinchilla_scaling",
        "topic": "adoption and technology",
        "name": "the Chinchilla compute-optimal scaling law",
        "kind": "math",
        "layer": "7 statistics",
        "operation": "predict",
        "notation": "L(N, D) = E + A/N^al + B/D^be ;   at fixed compute, "
                    "optimal N and D both scale about C^0.5",
        "example": "for a fixed budget, best to grow model size and data "
                   "together, roughly in step, not one alone",
        "legend": [
            ("L", "the model's loss (lower is better)"),
            ("N", "number of model parameters"),
            ("D", "number of training tokens"),
            ("E", "the irreducible loss floor"),
            ("A, B, al, be", "fitted constants of the scaling curve"),
            ("C", "the compute budget, about 6.N.D"),
        ],
        "needs": [
            "the fitted constants for the setting",
            "the compute budget C",
        ],
        "output": "the loss you can expect from a given size and data, and "
                  "the size/data split that minimises loss for a budget",
        "source": "Jordan Hoffmann et al. (DeepMind), 'Training Compute-"
                  "Optimal Large Language Models,' 2022.",
        "use": "For claims about where AI capability is heading. It grounds "
               "'models will keep getting better' in a measurable curve with "
               "a floor E, so the question becomes how far the budget C can "
               "still move L, not whether progress is unlimited.",
        "why": "An empirical power-law fit, layer 7: loss falls as a power of "
               "size and data toward a floor.",
    },

    # ---------------------------- FORECASTING ITSELF ---------------
    {
        "id": "laplace_succession",
        "topic": "forecasting itself",
        "name": "Laplace's rule of succession",
        "kind": "math",
        "layer": "6 probability",
        "operation": "estimate",
        "notation": "P(next success) = (s + 1) / (n + 2)",
        "example": "3 of 5 past attempts worked  ->  (3+1)/(5+2) = 4/7 ~ 0.57, "
                   "not 0.60",
        "legend": [
            ("s", "successes seen so far"),
            ("n", "trials seen so far"),
            ("the +1, +2", "a flat prior, so zero successes never gives a "
                           "flat zero and one success never gives a flat one"),
        ],
        "needs": [
            "a count of comparable past trials n",
            "how many succeeded s",
            "that the trials really are comparable to the next one",
        ],
        "output": "a base-rate probability for the next case, pulled gently "
                  "off the raw fraction toward even",
        "source": "Pierre-Simon Laplace, Essai philosophique (1814). Used in "
                  "harness/simfutures.py.",
        "use": "The default when you have a count and need a next-case odds. "
               "It is what simfutures already runs on. Its discipline is "
               "forcing the denominator n: no counted trials, no rule, so it "
               "refuses to invent odds.",
        "why": "A Bayesian posterior mean, layer 6: the +1/+2 is the flat "
               "prior keeping the estimate off the hard 0 and 1.",
    },
    {
        "id": "bayes_odds",
        "topic": "forecasting itself",
        "name": "Bayesian updating, written as odds",
        "kind": "math",
        "layer": "6 probability",
        "operation": "aggregate",
        "notation": "posterior odds = prior odds . L1 . L2 . ... . Ln",
        "example": "even prior (odds 1) times evidence at 8x then 3x  ->  "
                   "odds 24, about 96 in 100",
        "legend": [
            ("odds", "chance-for divided by chance-against; even money is "
                     "odds of 1"),
            ("L", "a likelihood ratio: how many times more likely the "
                  "evidence is under one hypothesis than the other"),
            ("the product", "independent evidence multiplies; dependent "
                            "evidence must be grouped first"),
        ],
        "needs": [
            "a prior, ideally from a standing start rather than the author's "
            "post-hoc credence",
            "a likelihood ratio per piece of evidence",
            "a check that the pieces are independent, not the same fact "
            "counted twice",
        ],
        "output": "an updated probability; and a built-in trap, since "
                  "multiplying dependent ratios manufactures false certainty",
        "source": "Thomas Bayes (1763); odds form standard.",
        "use": "The combiner for several pieces of evidence. The Elipsis "
               "discipline is the grouping step: correlated ratios are grouped "
               "into independent observations before multiplying, because certainty by "
               "double-counting is exactly what the toolkit exists to catch.",
        "why": "Bayes in odds form, layer 6, because there it is just "
               "multiplication, and the dependence trap is visible.",
    },
    {
        "id": "brier_log_score",
        "topic": "forecasting itself",
        "name": "the Brier and logarithmic scoring rules",
        "kind": "math",
        "layer": "7 statistics",
        "operation": "predict",
        "notation": "Brier = (1/N) . sum (p_i - o_i)^2 ;   "
                    "log score = -(1/N) . sum [o_i.ln p_i + (1-o_i).ln(1-p_i)]",
        "example": "say 0.8 and it happens: Brier term (0.8-1)^2 = 0.04; say "
                   "0.8 and it does not: 0.64",
        "legend": [
            ("p_i", "the probability you gave for case i"),
            ("o_i", "what happened: 1 if it occurred, 0 if not"),
            ("N", "number of forecasts scored"),
            ("Brier", "mean squared miss, 0 is perfect, lower is better"),
            ("log score", "punishes confident wrong calls much harder than "
                          "Brier does"),
        ],
        "needs": [
            "dated forecasts with explicit probabilities",
            "their resolved outcomes",
        ],
        "output": "a single number grading a forecaster's calibration, so "
                  "predictions can be ranked instead of admired",
        "source": "Glenn Brier, Monthly Weather Review 78, 1950; log score, "
                  "I. J. Good, 1952. Used by harness/ledger.py.",
        "use": "The reason the ledger logs a probability before the event. It "
               "is what separates a scored forecaster from a pundit; any "
               "'my model is accurate' claim owes a Brier or log score on "
               "dated calls.",
        "why": "A proper scoring rule, layer 7: both are minimised by honest "
               "probabilities, so they reward calibration, not bravado.",
    },

    # ---------------------------- DOSE, FEEDBACK AND LEARNING -------
    {
        "id": "survivable_dose",
        "topic": "dose, feedback and learning",
        "name": "the survivable-dose curve with a live feedback loop "
                "(the inverted-U, plus the correction gate)",
        "kind": "math",
        "layer": "7 statistics / 6 probability",
        "operation": "predict",
        "notation": "G(a) = G0 + b1.a - b2.a^2 ,  peak at  a* = b1 / (2.b2) ; "
                    "and the loop keeps correcting only while  p.V > g",
        "example": "Seery's adversity data: best outcomes at a FEW life "
                   "events, worse at none and worse at many; 'bubble people' "
                   "are the p -> 0 end, where nothing is ever corrected",
        "legend": [
            ("G(a)", "how good the outcome is (competence, resilience, "
                     "innovation) at dose a"),
            ("a", "the dose of pressure: adversity, competition, challenge, "
                  "error, oversight"),
            ("G0", "the baseline outcome at zero dose"),
            ("b1", "the strengthening pull of facing some of it"),
            ("b2", "the damage term, which eventually dominates"),
            ("a*", "the sweet spot, the dose that does best"),
            ("p", "the chance a mistake is exposed and corrected"),
            ("V", "the value of the future lost when it is exposed"),
            ("g", "the one-time gain from not correcting"),
        ],
        "needs": [
            "the dose a measured on one scale",
            "evidence the relationship actually BENDS (a real quadratic term, "
            "not a straight line assumed)",
            "the feedback probability p: is there a live consequence at all",
            "whether the high end is survivable or ruinous (an absorbing "
            "barrier truncates the curve)",
        ],
        "output": "whether more of a thing helps or harms, where the peak "
                  "sits, and whether the system keeps learning; it flags both "
                  "failure ends at once -- too little pressure or dead "
                  "feedback (uncorrected rot) and too much (ruin)",
        "source": "Yerkes and Dodson (1908) for the original arousal "
                  "inverted-U; Seery, Holman and Silver (JPSP 2010) for "
                  "adversity and resilience; Aghion, Bloom, Blundell, "
                  "Griffith and Howitt (QJE 2005) for competition and "
                  "innovation; the feedback gate is reputation in repeated "
                  "games (Kreps, Milgrom, Roberts, Wilson, 1982) and Taleb on "
                  "ruin (the absorbing barrier).",
        "use": "Reach for it whenever a claim says 'more X is better' or "
               "'less X is better' about pressure, stress, competition, "
               "adversity, error or oversight. It forces two questions the "
               "claim usually skips: where is the peak, and is the feedback "
               "loop live. Most such claims assume a straight line and a "
               "working loop, and usually neither holds. Its discipline is "
               "that a single number or one anecdote cannot settle a shape "
               "that bends.",
        "why": "A quadratic, layer 7, because the effect reverses sign past "
               "the peak, which a line cannot do; the correction gate is an "
               "inequality, layer 6, because being caught is probabilistic.",
    },
]
try:  # optional extra entries, loaded when present
    from private_examples import MODELS_EXTRA
    MODELS += MODELS_EXTRA
except ImportError:
    pass

TOPICS = []
for _m in MODELS:
    if _m["topic"] not in TOPICS:
        TOPICS.append(_m["topic"])


# --------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------

def wrap(s, w=66, ind="   "):
    out, line = [], ""
    for word in str(s).split():
        if len(line) + len(word) + 1 > w:
            out.append(ind + line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        out.append(ind + line)
    return "\n".join(out)


def rule(c="=", w=74):
    return c * w


def by_id(mid):
    for m in MODELS:
        if m["id"] == mid:
            return m
    raise KeyError(mid)


def one_line(m):
    tag = "[math] " if m["kind"] == "math" else "[logic]"
    return "   {} {:<26} {}".format(tag, m["id"], m["name"].split("(")[0].strip())


def list_all(topic=None):
    out = [rule(), "  REFERENCE MODELS -- the formal shape for a topic, and "
           "what it needs measured", rule(), ""]
    out.append(wrap(
        "Pull the model for the topic, write it in standard notation, then "
        "ask whether the claim fills in the terms its `needs` list names. "
        "[math] gives you numbers to substitute; [logic] gives you "
        "conditions to establish. Most confident claims leave the terms "
        "empty, and that gap is the finding.", 70, "  "))
    out.append("")
    shelves = [topic] if topic else TOPICS
    for t in shelves:
        ms = [m for m in MODELS if m["topic"] == t]
        if not ms:
            continue
        out.append("  " + t.upper())
        for m in ms:
            out.append(one_line(m))
        out.append("")
    out.append(rule("-"))
    out.append("  detail:  --model <id>     search:  --match <words>")
    out.append("  shelves: " + "; ".join(TOPICS))
    out.append("")
    return "\n".join(out)


def detail(m):
    out = [rule(), "  " + m["id"].upper(), rule(), ""]
    out.append("  " + m["name"])
    out.append("")
    out.append("  TOPIC   " + m["topic"])
    out.append("  KIND    " + ("real maths, substitute into it"
                               if m["kind"] == "math"
                               else "a logic / checklist, establish its "
                                    "conditions"))
    out.append("  SERVES  the " + m["operation"] + " operation, math layer "
               + m["layer"])
    out.append("")
    out.append("  STANDARD NOTATION")
    out.append(wrap(m["notation"], 66, "     "))
    out.append("")
    if m["example"]:
        out.append("  WITH NUMBERS")
        out.append(wrap(m["example"], 66, "     "))
        out.append("")
    out.append("  LEGEND (every symbol, in plain English)")
    for sym, mean in m["legend"]:
        out.append(wrap("- " + sym + ":  " + mean, 64, "     "))
    out.append("")
    out.append("  WHAT THE CLAIM MUST SUPPLY")
    for n in m["needs"]:
        out.append(wrap("- " + n, 64, "     "))
    out.append("")
    out.append("  WHAT IT OUTPUTS")
    out.append(wrap(m["output"], 66, "     "))
    out.append("")
    out.append("  WHEN TO REACH FOR IT")
    out.append(wrap(m["use"], 66, "     "))
    out.append("")
    out.append("  WHY THIS NOTATION")
    out.append(wrap(m["why"], 66, "     "))
    out.append("")
    out.append("  SOURCE")
    out.append(wrap(m["source"], 66, "     "))
    out.append("")
    return "\n".join(out)


def match(words):
    q = words.lower().split()
    scored = []
    for m in MODELS:
        hay = " ".join([m["id"], m["name"], m["topic"], m["use"],
                        m["operation"], m["output"]]).lower()
        score = sum(hay.count(w) for w in q)
        if score:
            scored.append((score, m))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return ("No model matched '" + words + "'. The shelves are: "
                + "; ".join(TOPICS) + ".\nRun with no argument to see all "
                + str(len(MODELS)) + ".")
    out = [rule(), "  MODELS THAT FIT: " + words, rule(), ""]
    for sc, m in scored[:5]:
        out.append(one_line(m))
        out.append(wrap(m["use"], 64, "        "))
        out.append("")
    out.append("  detail:  --model <id>")
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------
# MCP tool
# --------------------------------------------------------------------

def tool(args):
    mid = args.get("model")
    if mid:
        try:
            return detail(by_id(mid))
        except KeyError:
            return ("No model '" + str(mid) + "'. The " + str(len(MODELS))
                    + " are: " + ", ".join(m["id"] for m in MODELS))
    mt = args.get("match")
    if mt:
        return match(mt)
    topic = args.get("topic")
    if topic:
        hits = [t for t in TOPICS if topic.lower() in t.lower()]
        if hits:
            return list_all(hits[0])
        return ("No shelf matching '" + str(topic) + "'. The shelves are: "
                + "; ".join(TOPICS))
    return list_all()


# --------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------

def main():
    a = sys.argv[1:]
    if not a:
        print(list_all())
        return
    if a[0] == "--model" and len(a) > 1:
        try:
            print(detail(by_id(a[1])))
        except KeyError:
            print("No model '" + a[1] + "'. The " + str(len(MODELS))
                  + " are: " + ", ".join(m["id"] for m in MODELS))
        return
    if a[0] == "--match" and len(a) > 1:
        print(match(" ".join(a[1:])))
        return
    # a bare word is treated as a topic filter
    topic = " ".join(a)
    hits = [t for t in TOPICS if topic.lower() in t.lower()]
    if hits:
        print(list_all(hits[0]))
    else:
        # maybe it is a model id
        try:
            print(detail(by_id(topic)))
        except KeyError:
            print("No shelf or model '" + topic + "'. Shelves: "
                  + "; ".join(TOPICS))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
