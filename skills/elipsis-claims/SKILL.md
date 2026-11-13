---
name: elipsis-claims
description: Run the Elipsis claim-checking tools: steelman a claim, pick the formula that fits, audit a question, trace where a claim came from, check whether sources entail it, look up published fact checks and effect sizes, and write up a finding. Use when checking whether a claim is true.
---

# elipsis-claims

Each tool is a script shipped inside this plugin. Run it with the Bash tool:

```bash
python "${CLAUDE_PLUGIN_ROOT}/harness/run_tool.py" --data "${CLAUDE_PLUGIN_DATA}" TOOL '{"argument": "value"}'
```

- Arguments are one JSON object. When the text has quotes or is long, write the JSON to a file and pass `@path/to/args.json` instead, or pipe it in and pass `-`.
- Use `python3` where `python` is not found (most Macs and Linux), or `py` on Windows where only that works.
- `python "${CLAUDE_PLUGIN_ROOT}/harness/run_tool.py" --data "${CLAUDE_PLUGIN_DATA}" --schema TOOL` prints a tool's full description and argument schema.
- Saved work (forecasts, decisions, chains) is kept in the plugin's data folder, so it survives updates.
- Report the result by the answer rules in the `elipsis` skill: roughness first, the claim quoted in full, formulas with a legend, every percentage both ways.

## Tools

### `operation`

THE FRONT DOOR. CALL THIS FIRST, BEFORE `route`, BEFORE `steelman`. It asks the one question that tells you which of the other catalogues to open: WHAT KIND OF FINDING-OUT IS THIS? Sorting this server's eleven problem shapes by what kind of object each actually is left four categories -- failure mode, argument scheme, method, operation -- and exactly ONE of the eleven turned out to be an operation. `comparison` had been sitting in the list as though it were the same kind of thing as `denominator`. That gap is why the pipeline felt arbitrary. THE PROPER ORDER IS operation -> scheme -> method -> failure mode. What kind of finding-out, then how is it justified, then what gets computed, then which defects are live -- and which defects are live DEPENDS on the first three. The flat eleven is the degenerate case you run when all you have is somebody's conclusion. EIGHTEEN OPERATIONS: estimate, bound, compare, diagnose, attribute, predict, detect, classify, aggregate, allocate, sequence, measure, cause, strategize, simulate, trend, connect, optimize. Each returns the methods to reach for, the failure that bites hardest, and a building-site example -- the index is worthless if it only works on geopolitics. AND THE PART THAT MATTERS MOST. Most operations have a FAST feedback loop: you estimate, you do it, you find out. That beats any formula here, because a fast loop substitutes for a good model -- a thermostat holds a room at 20 degrees with no theory of thermodynamics, by measuring and correcting. The loop wins when T_loop < T_change: how long until you find out you were wrong, versus how fast the thing moves. THAT IS WHY THE HARD QUESTIONS ARE HARD -- not complexity, but a feedback loop slower than the thing it is watching, so you never get to correct. This index does not exist anywhere else. Walton catalogued the schemes, operations research has the methods, this server has the failure modes. The list of OPERATIONS is the one nobody built, and it is the one that routes you to the other three. Per this server's own doctrine on partition dependence, eighteen is a CUT somebody chose -- re-cut it if your domain wants different joints.

- `operation` (string): One of the eighteen, for the full entry. Omit for the index.

### `loop`

CALL THIS BEFORE ANY OTHER TOOL ON THIS SERVER. It asks whether you should be using this server at all. EVERY OTHER MODULE HERE IS COMPENSATION FOR A BROKEN FEEDBACK LOOP. The sweeps, the mirror, the steelman, the Frechet bounds -- if you could just check, you would not need any of them. You would check. So sometimes the right output of an analysis toolkit is PUT THIS DOWN AND GO AND LOOK, and until this tool existed there was no way to say it. A thermostat holds a room at 20 degrees with no theory of thermodynamics -- no heat-transfer equations, no knowledge of the insulation, no forecast. It measures and corrects, and it beats an open-loop system with an excellent model. LOOP QUALITY SUBSTITUTES FOR MODEL QUALITY and costs far less. FOUR GATES, ALL OF WHICH MUST PASS before go-and-measure is the right advice. 1 RATE. R = T_change / T_loop -- how many corrections you get before the situation moves. Above 5, checking beats forecasting outright. Near 1, you want both. Below 1, nothing you learn arrives in time to apply and you are stuck with a model. THIS IS WHY THE HARD QUESTIONS ARE HARD: not complexity, but a loop slower than the thing it watches. 2 CLOSURE. Is the ERROR fed back, or only new input? The gate that quietly fails in almost every continuously-updating system ever built. Re-running a case on fresh data is the INPUT half; without the scoring step nothing corrects and you have bought a TREADMILL that feels like progress and costs more than doing the analysis once. Needs all three of: observable error, separable from noise, and a lever to change the next call. 3 RESOLUTION. n = (sigma/delta)^2 cycles before a real change is visible. Faster is NOT better past this point -- correcting inside the detection window responds to noise and amplifies it, which control engineers call hunting. 4 SURVIVABILITY. Is one failed cycle acceptable? A fast loop is not an affordable one. You do not learn whether the bridge holds by driving over it. Gate 4 OVERRIDES gate 1. Pass `t_loop` and `t_change` in the same unit for gate 1; t_loop null means the claim never resolves, which is worse than slow and is where most contested political claims sit. Add `sigma`, `delta` and `cycles_available` for gate 3. Pass `cases: true` for the worked examples.

- `t_loop` (number or null): How long until you find out you were wrong. Null if it never resolves.
- `t_change` (number): How long before the situation that produced the call has shifted. SAME UNIT as t_loop.
- `unit` (string): weeks, months, elections -- for the printout.
- `sigma` (number): Gate 3: cycle-to-cycle noise.
- `delta` (number): Gate 3: the real movement worth seeing.
- `cycles_available` (number): Gate 3: how many cycles you actually get.
- `cases` (boolean): Show the worked examples.

### `route`

THE ELEVEN SHAPE QUESTIONS. Given a claim, which formula applies? Code asks, a model answers -- never the other way round. Each question is answerable from the TEXT of the claim alone: no world knowledge, no forecast, no view on whether it is true. 'Does this need several things to all happen' is a grammar question; 'will they all happen' is not, and is not asked here. A claim can be more than one shape and that is normal. Run every one that matches. Every shape now carries its formula's NAME and SOURCE, and block() refuses to render a legend that skips any mark in the formula -- including the operators, which are the ones readers most need and authors most often drop. THE ELEVEN ARE NOT ONE THING, and `split: true` shows why. Sorted by what kind of object each is: FAILURE MODE (5 shapes) -- a defect in how the claim was built. Visible in the claim's TEXT, which is why these dominate. This category is genuinely this project's own. ARGUMENT SCHEME (3 shapes) -- a pattern of inference. Visible only if the REASONING IS STATED, and most claims assert a conclusion and stop. Walton, Reed & Macagno catalogued 65 of these in 2008; ours are three of them reinvented, and `conjunction` is his slippery slope with the arithmetic done. METHOD (2 shapes) -- a procedure once you know what you are computing. Operations research has had these for decades. OPERATION (1 shape) -- what kind of finding-out is being attempted. THE MISSING FRONT DOOR: exactly one of the eleven is an operation and nobody has catalogued these properly anywhere. Failure modes show up far more often than schemes on any corpus of assertions, because one is visible without the reasoning and the other is not. AND THE PROPER ORDER IS NOT FLAT: operation, then scheme, then method, then failure mode -- since which defects are live depends on the first three. The flat eleven is the degenerate case, run when all you have is a conclusion. Pass `shape` for one entry, `category` for one of the four, `split: true` for the full breakdown, or nothing for all eleven.

- `shape` (string): One of: conjunction, union, growth, accuracy_stat, causal_rivals, comparison, stock_vs_flow, window_shopping, survivorship, correlation_causal, denominator.
- `category` (string): One of: failure_mode, argument_scheme, method, operation.
- `split` (boolean): Show the four-category breakdown with fire counts and what it explains.

### `steelman`

RUN THIS FIRST, BEFORE ANY OTHER CHECK. State the strongest version of a claim before auditing the words it was written in. THE FAILURE IT CATCHES. Somebody's words are a lossy encoding of their argument. Audit the encoding and report on the argument and you produce findings that are true about a point nobody was making. Reading somebody at their most literal while granting yourself interpretive latitude is an isolated demand for rigor one level up. `mirror` catches it inside the arithmetic; this catches it before the arithmetic starts. SEVEN QUESTIONS, and two of them do the work: what_you_supplied list EVERY word, premise or connection you added. This is the ONLY thing separating a steelman from a different and easier claim of your own invention. which_are_you_auditing declare it before you start. Undeclared, this is where the switch happens -- refute the literal version, report as though you addressed the argument. The other five: strongest_version, load_bearing_words (is one word doing more work than the rest?), different_mechanism (a weak illustration often sits on a strong mechanism), would_they_accept_it (a steelman can be a strawman in the other direction), and reduces_to_a_parameter -- the best ones collapse to ONE measurable number, which is the most valuable thing this step produces. FOUR VERDICTS: SAME, STRENGTHENED, DIFFERENT_MECHANISM, and TECHNICALITY -- which means you refuted the wording and the argument survives. That is a FAILURE STATE, not a finding, and publishing it as one is the thing this exists to stop. ORDER: steelman -> route -> the eleven -> mirror.

- `claim` (string): The claim as written, to hold the seven questions against.
- `case` (string): A saved worked case, if any (call with no arguments to list them).

### `audit`

RUN THIS FIRST. Takes a question object and runs every check in cheapest-first order, short-circuiting when one fails: budget, frame, lineage, entailment, ledger. Most questions die at stage 1 in seconds, and you never have to write the later sections. The question object may contain only the sections it got far enough to need.

- `question` (object, required)
- `name` (string)

### `check_frame`

Is the question answerable at all? Forces it into six slots and catches: comparison to an imaginary ideal (the nirvana fallacy), claims with no measure attached, measures that are not counts of anything, measures observable for only one system, and whether the underlying value is actually disputed — which decides whether a single verdict is permitted.

- `frame` (object, required)

### `check_lineage`

USE THIS WHEN a claim is widely repeated and you are about to treat the repetition as evidence. Forty citations with one origin is one source with an echo, and the difference is invisible until you walk the graph backwards. How many INDEPENDENT origins does a claim have, as opposed to citations? Walks the citation graph backwards and collapses everything that traces to a shared ancestor. Flags disqualifying origins (fiction, retracted, fabricated, derived-by-arithmetic) and origins that benefit from the claim. Forty citations with one origin is one source with an echo.

- `claim` (object, required)

### `check_entailment`

USE THIS WHEN you have good sources and are about to state something slightly stronger than they support. That gap is the most common way careful work goes wrong, and it is invisible from the inside -- a claim can pass every sourcing check with six excellent references and still fail this badly. Does the evidence support THIS claim or a weaker neighbour? Nine gap types: scope, quantity substitution, missing variable, population, mechanism assumed, composition, target substitution, temporal, direction. Returns the strongest claim the evidence actually supports. A claim can pass lineage with six excellent sources and fail this badly.

- `claim` (object, required)

### `fact_check_lookup`

HAS THIS CLAIM ALREADY BEEN FACT-CHECKED? Call this early in any claim check, before searching from scratch. Searches published fact checks (PolitiFact, FactCheck.org, AFP, Full Fact, Snopes and the other outlets that publish schema.org ClaimReview markup) through a local index of Google's public ClaimReview feed (Data Commons; no key). Pass `query`: the claim or its key words (names, numbers, places work best; every word is tried first, then any word). Returns each match with the outlet, date, their rating as written, who made the claim, their stated reason and the link. A MATCH IS A LEAD, NOT A VERDICT: confirm it is the same claim (same numbers, place and date) and read the article before citing it. No match means nothing is indexed, not that the claim is true. If the answer says there is no local copy, it must be built once (about 200 MB download); ask the user before doing that.

- `query` (string, required): The claim, or its key words.
- `limit` (integer): How many matches (1 to 30, default 10).

### `constant`

USE THIS BEFORE QUOTING ANY PUBLISHED EFFECT SIZE about elections, coalitions or party systems. Ten regularities that survive three filters -- a published effect size WITH an interval, an out-of-sample test somebody else ran, and a public dataset that operationalises the inputs. WHAT IT IS REALLY FOR. A constant applied outside its scope is worse than no constant, because it arrives wearing a citation. So every entry carries a `misuse` field naming the specific wrong way it gets used, and you cannot get a computed number out of this tool without that warning attached to it. THE THREE THAT PRODUCE NUMBERS cost_of_ruling governing parties lose 2.25 pp per term, range 1.6-2.5, measured on 282 elections in 19 democracies. Pass `observed_gap` and it does the subtraction that separates a real policy effect from the ordinary price of office -- below about 2.25 points there is nothing left to explain. gamson cabinet posts track coalition seat share: p = 0.069 + 0.793s, R^2 = 0.89. s is the share of THE COALITION's seats, not of parliament, and confusing the two moves the answer by over 20 points. economic_voting 1.55 pp of incumbent vote per point of GDP growth where responsibility is clear, 0.92 where government is fragmented. The conditioning IS the finding. FOUR MORE ARE PURE ARITHMETIC with no theory risk at all: effective_parties, volatility, disproportionality and seat_allocation. That last one turns a poll share into seats, which is the step that decides whether a party actually takes power. TWO DELIBERATELY CARRY NO NUMBER. duverger holds at district level and has no published national coefficient. pitf outputs a rank and refuses to become a probability. Call with no arguments for the catalogue, the filters and the REJECTED list -- the median voter theorem, the cube law, and any 'X% chance' read off a model that only publishes a rank. Pass `id` for one entry in full. Pass `id` and `apply` to compute.

- `id` (string): One of: cost_of_ruling, gamson, economic_voting, effective_parties, volatility, disproportionality, seat_allocation, duverger, pitf. Omit for the catalogue.
- `apply` (object): Arguments to compute with. cost_of_ruling: {terms} or {observed_gap, terms}. gamson: {coalition_seat_share}. economic_voting: {growth_pp, clarity: high|low}. effective_parties: {shares:[...]}. volatility: {prev:{}, curr:{}}. disproportionality: {votes:{}, seats:{}}. seat_allocation: {votes:{}, total_seats, threshold, sainte_lague}. duverger: {magnitude}.

### `reference_models`

THE STANDARD FORMAL MODEL FOR A TOPIC, so the steelman step has something real to hold a claim against. Call it AFTER `steelman` names the strongest version: it hands back the recognised equation for that topic, its legend, and the list of quantities the claim MUST supply, so the check becomes mechanical -- does the claim fill the terms or leave them empty. 26 models on ten shelves (war and escalation, terrorism and civil war, epidemics, collective behaviour, animal conflict, sex ratio and demography, economics and geography, adoption and technology, forecasting itself, and dose, feedback and learning), each marked [math] (substitute into it) or [logic] (establish its conditions). Pass `match` (words from the claim, e.g. 'will this spiral') to find the fitting model, `model` (an id) for the full entry with notation and needs, or `topic` (a shelf) to list one shelf. No argument lists all. It hands you the equation and what it needs; it does not fit parameters or decide the case.

- `match` (string)
- `model` (string)
- `topic` (string)

### `theory_slot`

USE THIS WHEN somebody proposes wiring a social-science theory into an analysis. It routes the theory to one of three slots, and the whole point is that most theories are not estimators and using one as if it were is how fabricated numbers get made. SLOT 1 STRUCTURE GENERATOR -- tells you what the steps ARE, predicts nothing, and does not need to. Most grand social theories live here. Feed the steps to `chain` and price them yourself. SLOT 2 ESTIMATOR -- produces a number with an interval. Rare. Goes in `constant`. SLOT 3 MEASUREMENT -- supplies input values, ideally with their own uncertainty: surveys, expert panels, registers. A theory that explains everything forbids nothing, and a theory that forbids nothing has no predictive content however true it is. That is not a criticism of slot 1 -- it is what a classification scheme is for, and misreading it as slot 2 is the error. Answer the three filters honestly. If you do not know whether an out-of-sample test exists, the answer is no.

- `theory` (string, required): Name of the theory.
- `has_interval` (boolean): Is there a published effect size WITH an interval? Not a direction, a number.
- `tested_out_of_sample` (boolean): Did somebody other than the original author test it on data it was not fitted to?
- `has_dataset` (boolean): Is there a public dataset that operationalises the inputs?

### `instability_score`

USE THIS FOR ANY QUESTION ABOUT A COUNTRY COMING APART -- civil war, coup, collapse, a democracy sliding. It replaces a guess with published coefficients, and it is the only tool here whose numbers were measured by someone else rather than judged by whoever is asking. SCORE A COUNTRY ON THE PITF GLOBAL INSTABILITY MODEL -- Goldstone et al. (2010), AJPS 54(1):190-208, the model the CIA-convened Political Instability Task Force built. Four variables, fitted to 141 onsets across every country over 500,000 people, 1955-2003. THIS IS THE ONLY TOOL HERE WITH MEASURED COEFFICIENTS. Everything else computes over ranges somebody supplied. These are published numbers with published confidence intervals that can be checked against the paper. THE FOUR VARIABLES, and three of them get left out by people quoting this model: regime type -- five categories, and partial democracy WITH factionalism carries an odds ratio of 36.91 against full autocracy. This is the one everybody quotes. Note the categories come from the Polity EXREC and PARCOMP components, NOT the composite Polity score; factionalism is PARCOMP=3. An argument that reaches a category via the headline Polity number has taken a road the model does not use. infant mortality -- as a GLOBAL PERCENTILE, not a raw rate. OR 6.59 between the 75th and 25th percentiles. Second-largest term, and strongly protective for rich countries. four or more bordering states at war -- OR 22.0. Off for most countries, which means a quarter of the model is inactive. state-led discrimination -- OR 1.93. The smallest term. WHAT IT RETURNS IS A RANK, NOT A PROBABILITY, and that is the paper's design rather than a limitation of this implementation. The paper publishes no intercept and cannot: the design is case-control at one onset per three controls, so any fitted intercept describes a sample built at 25% instability rather than a world running at 1.7%. The authors rank countries and flag the top fifth. Absolute risk comes from their own out-of-sample table, and it is the same number for everyone on the same side of the cut. THE ACCURACY, BOTH WAYS. 'Right more than 80% of the time two years ahead' is true: 86% of onsets flagged, 81% of stable years cleared. From the same four cells: of the 251 country-years it FLAGGED, 18 had an onset -- 7 in 100, and 233 false alarms. A flag is a fourfold lift from a 1.7% base rate, not a prediction of collapse. Always report both. AN ONSET IS NOT A CIVIL WAR. Of 117 onsets, 65 began as civil war and 49 as adverse regime change -- a significant move toward autocracy, not necessarily violent. Do not report a flag as a civil-war forecast. Pass `card_only` for the accuracy table alone.

- `profile` (string): A saved profile name (call with no arguments to list them). Or build one inline with the fields below.
- `regime` (string): full_autocracy | partial_autocracy | partial_dem_factional | partial_dem_nonfactional | full_democracy. From Polity EXREC and PARCOMP, not the composite score.
- `imr_percentile` (number): Position in the GLOBAL infant-mortality distribution, 0-100, lower is safer. Required for an inline profile -- omitting it is the single most common way this model gets misapplied.
- `neighbours_at_war` (integer): Bordering states in major armed conflict. The variable is a threshold at 4, not a count.
- `discrimination` (boolean): State-led political or economic discrimination against at least one minority, per Minorities at Risk.
- `card_only` (boolean): Return only the accuracy table.

### `mirror`

RUN THIS LAST, ON YOUR OWN CORRECTION. A correction is a claim, so point the same eleven questions at it and publish what comes back. WHY. A reply that sweeps somebody's number and leaves its own unswept has applied rigour to one side. Every individual finding can be correct and the aggregate output still biased, because scrutiny only ever pointed one way. That is the strongest objection to this whole server and it is structural rather than a matter of execution. SEVEN QUESTIONS: same_shape_back, new_shape_introduced, constant_out_of_scope, asymmetric_precision, unswept_residual, direction_of_convenience (if every correction you publish moves the same way, that is a finding about you), decision_relevance. VERDICTS: HOLDS, RESIZED, REVERSED, UNCHECKABLE. Publishing the HOLDS cases is what makes the rest mean anything -- a test that never passes carries no information. The count that matters is how many shapes fire ONLY on your own correction. Each one is something you did to them after objecting to it being done.

- `case` (string): A saved worked case, if any (call with no arguments to list them).

### `publication_screen`

RUN THIS BEFORE PUBLISHING ANY ANSWER. Some questions get worse by being answered in public, and the test is not sensitivity -- it is whether a named party can MOVE THE INPUTS once they know the output. The clearest case is attribution. Publish a probability naming a suspect and you have published the scoring function an adversary needs in order to be misread; the model cannot detect a competent false flag because planted signals are exactly the signals it reads. Also screens target selection and probabilities attached to named private individuals. Everything else is cleared, and some questions get BETTER for being published: where several parties each run their own model, the disagreements separate a fight about facts from a fight about values, and only one of those is settleable.

- `question` (string, required): The question or claim about to be published.

### `ancestry`

WHERE EVERY MODULE IN THIS SERVER ALREADY EXISTED, decades earlier, in public. Call it before presenting any of this as novel. causal_rivals is Heuer's ANALYSIS OF COMPETING HYPOTHESES (1970s). Percentages-both-ways is Sherman Kent's WORDS OF ESTIMATIVE PROBABILITY (1964). SHOW_WORK is ICD 203 ANALYTIC STANDARDS (2007). The provenance tags are ICD 203 standards 2 and 3. mirror is RED CELL and devil's advocacy. steelman is mandated ALTERNATIVE ANALYSIS. The denominator and start-date sweeps are Key Assumptions Check, and closer still to specification curve analysis. pitf is not even an ancestor -- it is theirs, imported. NONE OF THESE WERE CONSULTED WHILE BUILDING THIS. They were reconstructed without attribution by a model near-certainly trained on them, since all of it is published -- Heuer is on the CIA's own website. Reconstructing a known framework and not citing it is worse than inventing or citing it: it reads as originality, is not, and costs the reader the better original. This server already tags NUMBERS by provenance; this tags the IDEAS. ONE ROW IS EMPTY AND IT IS THE POINT. `ledger` -- a published calibration record -- has no ancestor, for a structural reason: scoring a classified estimate in public discloses what was estimated. Their own tournament (IARPA ACE, 2011-2015, 500 questions, over a million forecasts) found that tracked, scored, publicly-compared forecasting was what let amateurs beat intelligence officers holding clearances by a reported 30%. The one column they cannot fill is the one their own experiment identified as decisive.

No arguments.

### `render_finding`

Write a standalone HTML page presenting a result in plain English — a verdict, bar charts, and the claims that could not be tested.

- `title` (string, required)
- `verdict` (string, required)
- `charts` (array)
- `refusals` (array)
- `filename` (string)

### `claim_rows`

ONE ROW PER CHECKED CLAIM, SO CLAIMS CAN BE COUNTED. A case checks a claim in prose; a row keeps the same fields for every claim: what was claimed and where, the gap-map entry it belongs to (`about`) and the one that blocks it (`blocked_by`), the evidence it rested on, the verdict (holds, partly, wrong), the milestone, and its routes: chains of steps, each with a chance `p`, a typical length `median` in years, years already `done`, a `kind` (funding or start, safety in people, first effect in people, confirmation, regulator) and `why`. A yearly-chance step uses `per_year` and `max_years` instead of p and median. Steps every route needs go in `shared`. Rows with no chain give `guessed` odds by year instead. The odds by 2030, 2035, 2040 and 2050 and the weakest step (dP/dp_j = P / p_j, the step worth most to improve) are computed, never typed in. An update keeps the old odds and the reason they changed. action `list` (optionally `entry`, a gap-map slug), `show` (`id`), `sticking` (optionally `field`): where known approaches get stuck, the weakest step of every row grouped by kind and by blocking gap-map entry, with every item listed. It ranks known options; it cannot invent new ones. `add` (`rows`, `reason`) saves or updates rows. Show the formula and its legend when you use the numbers.

- `action` (string)
- `id` (string)
- `entry` (string)
- `field` (string)
- `reason` (string)
- `rows` (any)
