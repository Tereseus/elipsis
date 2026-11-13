---
name: elipsis-ledger
description: Run the Elipsis forecast ledger: log a probability before the answer is known, rerun it on new information, settle it, and score the record. Use with the forecast skill.
---

# elipsis-ledger

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

### `ledger_add`

USE THIS THE MOMENT YOU STATE A PROBABILITY, before you find out whether you were right, and before you know the answer. Nothing downstream in this toolkit means anything without it: a probability that was never written down in advance cannot be scored, and a forecaster who cannot be scored cannot improve. This is the step every working forecasting system starts from, and it is the one a model will never take on its own. PREFER CLAIMS THAT RESOLVE IN MONTHS. A claim resolving in twenty-five years gives one data point in twenty-five years, and no amount of further analysis on it will teach you anything in the meantime. If the question is long-horizon, log the near-term claim the same belief implies instead, and log that too. Write a prediction down BEFORE checking it. Requires resolution criteria and a baseline — decide afterwards what would have counted and you will decide you were right; skip the baseline and you will never know whether your reasoning beat the dumb answer. Give the reasoning mode and the topic as separate lists (`mode`, `topic`). Where a market prices the question, the market price IS the baseline; then copy the market's rules in full into `market_rules` and say in `wording_vs_market` whether resolution_criteria means the same ('same') or what differs. A corrected probability is stored alongside yours, pulled toward the baseline by the k the record supports; both are scored. The baseline should be COUNTED: baseline.count = {yes, of, source} from past cases of the same kind (made into a chance by (yes+1)/(of+2)), or a market price, or 'nothing changes' (kind: persistence). A guessed baseline must give baseline.why_no_count. A forecast more than 0.10 from its baseline must give `departure`: what this case has that the usual case lacks. Big moves from the starting number are where overconfidence shows, and the report scores them apart.

- `claim` (object, required)

### `ledger_rerun`

USE THIS WHEN NEW INFORMATION CHANGES AN OPEN FORECAST. Never edit the old number: overwrite, and you can always 'update' to the answer the day before it resolves and look brilliant. This logs a new dated forecast on the same question, pointing at the one it revises; both are scored. Optionally pass a new baseline, e.g. a fresh market price, as {probability, what}.

- `id` (string, required)
- `probability` (number, required)
- `reasoning` (string, required)
- `baseline` (object)

### `ledger_resolve`

Record what actually happened for an open claim. Every rerun of the same question resolves with it. If the question genuinely cannot be settled, pass unresolvable: true instead of an outcome -- it is closed and left out of the score, which is honest; forcing it to false is not. A claim that is not yet due stays open unless `early` says why (a settled market, or an event that has plainly happened). A question about what the research says (literature-check, replication-forecast, search-prediction) is never scored before its date unless `force` is true.

- `id` (string, required)
- `outcome` (boolean)
- `unresolvable` (boolean)
- `note` (string)
- `early` (string): Why closing before the date is right.
- `force` (boolean)

### `ledger_status`

Open claims and which are due for resolution now.

No arguments.

### `ledger_due`

Only the open forecasts whose resolution date has passed, each with its resolution criteria, so they can be settled.

No arguments.

### `ledger_score`

USE THIS BEFORE TRUSTING YOUR OWN CONFIDENCE, and especially before telling someone you are 80% sure of anything. Too few forecasts have resolved to score yet. Check before claiming. Calibration report: Brier score against the baseline's, directional bias, a calibration table, reasoning modes and topics separately, and whether correcting toward the baseline helps. Being wrong on average is useless; being wrong in one specific mode is fixable.

No arguments.

### `ledger_calibrate`

How much of your own judgment the record says to keep. Fits k in p_corrected = b + k(p_raw - b) on every resolved forecast, shows the working, and runs the honest test: leave-one-out, so no forecast is corrected with a k that saw its own answer. Run it before stating any probability you have not checked.

No arguments.
