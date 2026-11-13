---
name: elipsis-chains
description: Run the Elipsis chain tools: the odds of a claim that needs several steps to all go right, a plan that is said to be nearly done, and saved chains with elicitation sheets. Use when a forecast depends on a sequence of conditions.
---

# elipsis-chains

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

### `chain`

USE THIS WHEN a claim needs several separate things to ALL go right -- 'X will happen, and then Y, and then Z'. People state compound claims with the confidence of their strongest link, and the size of that error is the whole reason this exists. PRICE A COMPOUND CLAIM -- something that happens only if several things all happen. Returns the product, which link kills it, how rough the whole thing is, and the near-term versions that can actually be scored. WHY THIS IS A DIFFERENT TOOL FROM `decide`. A decision compares options and its damaging error is double counting, which moves the mean. A chain multiplies conditional probabilities and its damaging error is the INDEPENDENCE ASSUMPTION, which nobody writes down. EVERY LINK AFTER THE FIRST MUST BE CONDITIONAL on the ones before it. Write the statement as 'Given X, ...'. A marginal multiplied as if conditional breaks the arithmetic invisibly, because both are decimals between 0 and 1. OPTIONAL BLOCKS worth having. `outside_view` prices a route the links do not describe, because an unlisted route is priced at zero silently while the product still looks complete. `regimes` names a common cause and prices every link twice, once in each of its worlds -- the only way to represent links that share a driver but respond to it with opposite signs, which a correlation coefficient cannot do. The arithmetic checks that regime values average back to the stated marginal, so a split cannot quietly revise a belief. THE OPPOSITE ERROR IS CHECKED TOO. Multiplying corrects overconfidence and, overdone, manufactures doom -- the multiple-stage fallacy (six 50% stages give 1.6%). A step can list other `routes` through it and a number of `attempts`, joined through a named `shared_block` {p, what} -- the one obstacle that would stop every route and retry at once -- so retries are not priced as fresh coins; the report prints both ends, all blocked by one thing and each failing for its own reasons. Every report ends with THE MULTIPLE-STAGE CHECK: stacked guessed middling steps, later steps that do not say what they assume, and no other way through anywhere. SHAPE: {claim, horizon_years, links:[{id, p, low, high, statement, basis, provenance, already_occurred?, p_by_regime?, attempts?, routes?:[{id, p, low?, high?, attempts?, statement?}], shared_block?:{p, what}}], outside_view?, regimes?, scoreable_version?}. See harness/chains/*.json.

- `chain` (object): Inline chain spec.
- `name` (string): Or a saved chain name.

### `plan_audit`

USE THIS WHEN someone says a plan is nearly done, or 'it'll probably work', and you want to know how done it really is. HOW DONE IS THIS PLAN? Puts the person's own probability (`gut`) next to the product of the plan's steps, gives the spread with every step uncertain, names the step that swings the answer and the step to CHECK FIRST -- the one with the most to lose per unit of evidence behind it, its leave-one-out gain times the share of it that was not measured -- and says how far the gut number is from the steps, in odds as well as probability. IT ALSO RUNS THE MULTIPLE-STAGE CHECK, because an audit that only ever says 'less done than you think' is a pessimism machine, not an audit. It looks for Yudkowsky's three causes: stacked middling guesses (0.35-0.65 with nothing measured behind them, with the product recomputed at the top of their own ranges), later steps that do not say what they assume, and no other way through any step. SHAPE: the same chain as `chain`, inline or by saved name, plus an optional `gut` between 0 and 1. Use `chain` for the full working and `find_gaps` for the omission hunt.

- `chain` (object): Inline chain spec.
- `name` (string): Or a saved chain name.
- `gut` (number): Your own probability that the plan comes off, 0 to 1, before seeing the steps.

### `chain_save`

Save an inline chain so it can be rerun and revised. Renders it first, so a malformed chain fails here rather than on disk. Worth doing for anything you will revisit -- the point of saving is that when a link changes you rerun and see what moved, rather than re-arguing it from scratch.

- `name` (string, required)
- `chain` (object, required)

### `chain_list`

List saved chains that can be rerun by name.

No arguments.

### `chain_elicit`

EMIT A BLANK ELICITATION SHEET FOR A CHAIN. The statements with every number and every argument stripped out. Give it to a DIFFERENT model or person who has not seen the existing answer. This is not the decision sheet reworded. It forces the conditioning at every step, because an author who prices marginals when the model multiplies conditionals breaks the arithmetic without leaving a trace. It asks directly which links share a driver, because that is the chain-specific error and an author who prices four links without saying how they relate has answered the easy part. And it sends only the `statement` of each link, never the `basis` -- the basis is the argument for the number, and sending it hands the new author the old author's conclusion. WHY BOTHER: passes of a gaps run by the same author are the same prior re-expressed, not new evidence. This is the only thing that adds a genuinely separate source. CHOOSE FOR DISAGREEMENT, NOT CAPABILITY. Averaging two authors correlated at rho leaves sqrt((1+rho)/2) of the original tilt; at rho=1 there is no reduction at all however capable they are. A model from the same family shares training lineage and will correlate highly -- it will agree with you and the panel will report a false narrowing.

- `chain` (object)
- `name` (string)

### `chain_panel`

READ BACK FILLED ELICITATION SHEETS FOR A CHAIN and report what the claim comes to under each author. It reports a SPREAD, not a corrected number. A chain has no simulation and no confidence percentage, so there is no bias term to feed anywhere -- it has one number, and the useful thing a panel does to one number is show how far it moves when somebody else writes it. If three authors give 0.4%, 1.2% and 3%, the honest report of the claim is that range, and the file's third significant figure was never real. OMISSIONS PRINT BEFORE ANY NUMBER, because splitting a link does not move the answer and leaving out a route does. It also ranks which step the panel disagrees about most, which is NOT the same as which step the leave-one-out calls decisive: a step everyone agrees about cannot be improved by asking again. Pass `sheets` to supply filled answers inline, or leave it empty to read harness/panels/<name>/. The file's own numbers always appear as one author, named honestly, because leaving them out would hide the thing being tested.

- `name` (string, required): Saved chain name. Required -- the panel compares sheets against the saved chain.
- `sheets` (array): Filled sheets, inline. Each: {author, q?, links: {<id>: {low,high,mode} or {<regime>: {low,high,mode}}}, missing_routes[], dependencies[], objections[]}.
