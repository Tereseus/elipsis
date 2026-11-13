---
name: elipsis-decisions
description: Run the Elipsis decision tools: compare options under uncertainty, ask whether more evidence would change the choice, find unstated assumptions, and test whether a conclusion survives other plausible numbers. Use before recommending one option.
---

# elipsis-decisions

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

### `decide`

USE THIS WHEN you are about to recommend one option over another and the numbers behind the recommendation are judgements rather than measurements -- which is most of the time. It will not tell you the answer is right. It will tell you which of your beliefs cannot possibly change it, and the exact value at which each one would flip it, and those are the two things worth knowing. COMPUTE A DECISION UNDER UNCERTAINTY. Give it options, and beliefs held as RANGES (low/high/mode) rather than numbers, and it returns which option wins, how confident that is as a percentage, which beliefs cannot change the answer, the exact value at which each one would flip it, and what further research is worth. WHAT IT DOES: computes what the stated beliefs IMPLY. Compounding uncertainty across many terms is something human intuition does badly, and this does it exactly. WHAT IT DOES NOT DO, and this matters: it does not derive the beliefs from data. It cannot look at a history of anything -- meals, trades, symptoms, past choices -- and tell you an effect size. Somebody must supply each range and say where it came from. A made-up range drives the answer exactly as hard as a measured one, so the report states what share of the total uncertainty was guessed. SHAPE: each option is a set of +1/-1/0 coefficients on the beliefs, plus an optional constant. Payoffs are LINEAR. Every belief should carry `provenance` (measured | estimated | guessed) and, where a reference class exists, a `history` block with `signal_sd` -- the absolute error of the historical evidence, IN THE BELIEF'S OWN UNITS. A belief with no history block reports that the past cannot inform it. Set answer_only for just the verdict and confidence.

- `decision` (object): Inline spec: decision, unit, uncertainties[], options[]. See harness/decisions/*.json for shape.
- `name` (string): Or a saved decision name.
- `answer_only` (boolean): Return only the verdict block, not the working.

### `decide_save`

Save an inline decision so it can be rerun, revised and compared later. Worth doing for anything recurring -- the point of saving is that when a belief changes you rerun and see what moved, rather than re-arguing it.

- `name` (string, required)
- `decision` (object, required)

### `decide_list`

List saved decisions that can be rerun by name.

No arguments.

### `decide_elicit`

Emit a BLANK elicitation sheet for a decision: the channel list with every number stripped out and every judgement about magnitude or evidence quality removed. Give it to a DIFFERENT model or person who has not seen the existing estimates. The disagreement between the filled sheets measures how much the answer depends on whoever wrote it. Independence is what makes this worth doing, not capability: two authors who share a prior reduce the shared error by almost nothing, however strong they are.

- `decision` (object)
- `name` (string)

### `decide_panel`

READ BACK FILLED ELICITATION SHEETS FOR A DECISION and MEASURE the shared-author bias instead of assuming it. WHAT IT FIXES. `decide` carries one number it cannot justify: b, the shared-author term, set by assertion at 0.35. It exists because channels are not independent draws from the world -- one mind sets every range in one sitting, and if that mind is tilted every channel tilts the same way and the tilt never averages out. Without it, confidence is manufactured by counting channels. A panel is the only thing that turns b from a guess into a measurement: z(a,i) = [ mu(a,i) - mean_a mu(a,i) ] / mean_a sigma(a,i) B(a) = mean_i [ z(a,i) * dir(i) ] b = sd across authors of B(a) dir(i) is +1 for a benefit and -1 for a cost, so an author who inflates every cost AND deflates every benefit registers as one large tilt rather than cancelling to zero. IF THE MEASURED b EXCEEDS THE ASSUMED ONE, every confidence figure the model has produced is too high, and the tool says so. If it comes in LOWER, that is not reassurance until you have checked the authors were independent -- agreement between near-copies measures nothing. OMISSIONS PRINT BEFORE ANY NUMBER. Splitting a channel leaves the mean untouched; omitting one is the only error here that can reverse a verdict. CHOOSE AUTHORS FOR DISAGREEMENT, NOT CAPABILITY. Averaging two authors correlated at rho leaves sqrt((1+rho)/2) of the tilt; at rho=1 there is no reduction at all however capable they are. Models from one family share training lineage and will correlate highly. An sd from two authors is barely an estimate -- treat it as an order of magnitude until there are four or five. Pass `sheets` to supply filled answers inline, or leave it empty to read harness/panels/<name>/. Generate blank sheets with `decide_elicit`.

- `name` (string, required): Saved decision name. Required -- the panel compares sheets against the saved decision.
- `sheets` (array): Filled sheets, inline. Each: {author, channels: {<id>: {low, high, mode, k}}, missing[], objections[]}.

### `evidence`

ASK BEFORE REPORTING ANY INTERVAL: does it settle the decision? Two imports from outside intelligence tradecraft, both filling gaps this server had. GRADE, from medicine, rates certainty of evidence across four levels and downgrades it for six named reasons: risk of bias, inconsistency, INDIRECTNESS (measured on a different population than the one you care about -- the error this server commits most), imprecision, publication bias and dissemination bias. BUT THE VALUABLE PART IS THE DEFINITION. GRADE defines certainty as confidence the true value falls in a range 'OR ABOVE OR BELOW A DECISION-MAKING THRESHOLD'. Precision is relative to the decision. A Frechet bound of 0 to 40% is useless in the abstract and DECISIVE against a 50% threshold, and a precise point estimate in its place adds precision that changes nothing. Pass `low`, `high` and `threshold` and it returns DECIDED-BELOW, DECIDED-ABOVE or STRADDLES. Only in the straddling case is narrowing the estimate worth paying for. SEVERITY, from Deborah Mayo's error statistics: evidence supports a claim only if the claim passed a test it COULD HAVE FAILED. This server asks whether a claim is fragile; it never asked whether the sweep was severe. Five questions, and the sharpest is the last: construct a FALSE version of the claim and ask whether your evidence would look any different. If it would not, the evidence carries no information about which version you have. Verdicts: SEVERE, WEAK, or DEMONSTRATION -- the last meaning no failing result was ever specified, so nothing was tested. Pass `worked: true` for any saved worked examples where a very wide interval still settled the question.

- `low` (number): Bottom of the interval, as a fraction.
- `high` (number): Top of the interval, as a fraction.
- `threshold` (number): The decision threshold to compare against. Say why you chose it.
- `worked` (boolean): Show the worked cases instead.

### `check_budget`

USE THIS BEFORE DECIDING WHAT TO MEASURE, and before writing any model at all. It takes seconds and it kills most questions outright: the number of variables your evidence can actually carry is roughly the square root of your independent case count, and almost every model anyone builds has more moving parts than its evidence supports. CHEAPEST CHECK, RUN BEFORE CHOOSING VARIABLES. Given a reference class and its cases, returns how many variables the sample can actually carry (roughly sqrt of the usable case count, further reduced when cases cluster). Discounts cases that fail transport, and counts independent groups rather than raw cases. If you have listed variables it tells you how many to cut.

- `question` (object, required)

### `find_gaps`

USE THIS WHEN you are about to hand someone a number and you cannot say out loud what you left out of it. HUNT FOR WHAT IS MISSING AND WHAT IS IN THERE TWICE. Every other tool computes over what it is given; this is the only one that asks what is absent. Three passes: OVERLAP -- every pair of beliefs ranked by shared vocabulary, so the pairs that could plausibly be the same thing twice come first. Double counting moves the MEAN; correlation only moves the spread, so this is the more damaging of the two and the easier to miss. COUNTER -- for each belief, the strongest case its range is too high and too low. One-sided sourcing is invisible from inside a model. OMISSION -- eight error classes that have actually reversed an answer: a baseline that pays nothing, an option nobody listed, no wait option, someone bearing a cost with no term, two names for one thing, several beliefs from one source, the question not being the one asked, and what the opposite model looks like. THE CODE GENERATES THE QUESTIONS; A MODEL ANSWERS THEM. That direction matters: assigning probabilities is a calibration task and models are bad at it, while spotting that two paragraphs describe the same thing is recall, which fails differently. Pass `findings` back to log a pass and get told whether you have converged -- stop when a pass finds nothing new, not at a fixed depth.

- `decision` (object)
- `chain` (object)
- `name` (string)
- `findings` (array): What this pass found, to log and check convergence.

### `robust`

USE THIS WHEN someone says 'but you made those numbers up', or when you are about to act on a margin that looks comfortable. It answers the actual objection: how wrong could EVERY input be, at once, in the worst direction, before the answer flips. Report that number instead of the probability when talking to anyone sceptical. THE CONCLUSIONS THAT DO NOT DEPEND ON THE WEIGHTS. Run this whenever someone doubts the numbers, which they should. Four standard analyses, each dropping an assumption the main report relies on: STOCHASTIC DOMINANCE -- if one option dominates another at first order, EVERY decision-maker who prefers more to less agrees, whatever their values and whatever their risk attitude. Second order is the same for risk-averse ones. No weight is consulted, so no weight being wrong can undo it. This is the strongest conclusion available. MINIMAX REGRET (Savage) -- drops probabilities entirely. Picks the option whose worst-case regret is smallest. When it disagrees with expected value, that disagreement is informative: expected value is right over many similar bets and strange for a single irreversible choice. ROBUSTNESS RADIUS -- how wrong can EVERY input be, at once, in the worst direction, before the answer flips. Exact under a linear payoff. Report this number rather than the probability when talking to someone sceptical, because it answers their actual objection. CHEAPEST ATTACK -- the minimum-effort change that reverses the verdict, solved in closed form. It names the belief an opponent should go after first.

- `decision` (object)
- `name` (string)
