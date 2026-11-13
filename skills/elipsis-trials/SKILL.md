---
name: elipsis-trials
description: Run the Elipsis self-experiment tools: design a randomised trial on one person, decide whether it is worth running, get each day's assigned arm, and analyse the result.
---

# elipsis-trials

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

### `trial_design`

DESIGN AN N-OF-1 TRIAL BEFORE RUNNING IT. Given the outcome's spread (sigma, in the outcome's own units) it returns the smallest effect the trial could detect, how many days a given effect would need, and the power you would actually have. Pass unblind_bias if the thing recording the outcome can tell which arm the day was in -- it reports that bias as a share of the smallest detectable effect. Above roughly half, the trial cannot separate a real minimum effect from the instrument leaning, and more days will not fix it: the bias does not shrink with n while the detectable effect does.

- `sigma` (number, required): SD of the outcome measure, in its own units.
- `days` (integer): Total days, both arms.
- `effect` (number): Effect size worth detecting, same units as sigma.
- `power` (number): Default 0.80.
- `unblind_bias` (number): Suspected measurement bias if the outcome is not blind to the assignment.

### `trial_worth`

USE THIS WHEN someone is about to run a test to settle a decision and nobody has asked whether its answer could change the choice. A power calculation says whether a test can SEE an effect; this says whether seeing it is worth the days. IS THIS TEST WORTH RUNNING? Given a decision (inline or saved), the belief the test would measure, the daily outcome's SD, and how long the choice will last, it returns for several test lengths what the test is worth, what it costs, and the net: SE = sigma x sqrt(2 / (days/2)) worth(n) = EVSI(n) x periods left AFTER the test net(n) = worth(n) - fixed_cost - cost_per_day x n EVSI is `decide`'s own value of a noisy signal, with the noise set by the test instead of by history. By default a test day costs half the current gap between the top two options, because a two-arm test spends half its days on the one you would otherwise not pick. A belief that cannot change the choice has EVPI = 0 and gets 'don't run it for this decision'. An instrument that can see the arm adds a floor under the noise that more days cannot shrink. UNITS. If the decision's unit is a rate (per day, per year), pass `horizon_days`; otherwise the report warns and counts one period only. Long tests inside a short horizon lose, because the answer only pays once it has arrived. The net-benefit idea is ENBS, as in voiage (Apache-2.0).

- `decision` (object): Inline decision.
- `name` (string): Or a saved decision.
- `belief` (string, required): Id of the belief the test would measure.
- `outcome_sd` (number, required): SD of the daily outcome, in the belief's units.
- `days` (array): Test lengths to price. Default 14, 28, 56, 112, 224.
- `cost_per_day` (number): Cost of one test day in the decision's unit. Default: half the gap between the top two options.
- `fixed_cost` (number): Default 0.
- `unblind_bias` (number): Bias if the instrument can see the arm. Default 0.
- `horizon_days` (number): Days from now the choice will apply for. Needed when the decision's unit is a rate.

### `trial_assign`

GET THE ARM FOR A DAY, OR THE WHOLE SCHEDULE. Assignment is a hash of trial id and date, not a fresh coin. That is deliberate and it matters more than it sounds. A fresh random draw each morning leaves nothing to stop a re-roll after a bad night, and the person best placed to do that is the person the trial is about. A hash means the entire schedule exists before day one, anyone can recompute it, and re-running returns the same answer. The assignment may be as visible as you like. The OUTCOME is what has to be blind.

- `trial_id` (string, required)
- `day` (string): ISO date, for one day.
- `days` (integer): Or a count, for the whole schedule.
- `start` (string): ISO start date.
- `arms` (array)

### `trial_analyse`

ANALYSE A FINISHED OR RUNNING TRIAL. Takes rows of {arm, outcome} and returns the difference in means, its standard error and confidence interval, the observed sigma, and the smallest effect the trial could have detected. ALWAYS PASS `blinded`. If the instrument recording the outcome could see the assignment, say so -- the result is then an upper bound on the real effect rather than an estimate of it, and the tool says so in the output. Randomising protects the assignment; only blinding protects the measurement. They are different guarantees.

- `rows` (array, required): [{"arm": "A", "outcome": 3.0}, ...]
- `blinded` (boolean): Could the thing recording the outcome tell which arm the day was in? false means it could.
