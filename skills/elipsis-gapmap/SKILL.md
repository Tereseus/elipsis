---
name: elipsis-gapmap
description: Run the Elipsis gap map tools: research gaps ranked by recent activity, new papers for a gap, the base-rate odds for a proposed fix, and simulated futures for a drug in trials.
---

# elipsis-gapmap

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

### `gaps_moving`

GAP MAP GAPS RANKED BY RECENT ACTIVITY: papers in the last `days` that the daily reading judged on topic, with the judged and unjudged counts beside them. Activity is not progress.

- `days` (integer)
- `top` (integer)

### `whats_new_for_gap`

NEW PAPERS FOR ONE GAP MAP GAP, since the last look. Reads the daily sweep (papers matched to fixes and judged on topic by the daily reading). Pass `gap` (a gap name or fragment, or a pilot-node name); `since` (YYYY-MM-DD) or `days`; `mark_seen: true` to record today as the last look so the next call returns only newer papers. Counted, but 'on topic' is a judgement, and only fixes tagged for the sweep are covered.

- `gap` (string, required)
- `since` (string)
- `days` (integer)
- `limit` (integer)
- `mark_seen` (boolean)

### `will_this_work`

THE ODDS FOR ONE GAP MAP FIX: its counted base rate (s of n similar attempts and the rule of succession (s + 1) / (n + 2)), the forecast on the record for a near-term question, and what is known. For a fix with no counted base rate it says there are no odds rather than inventing them. Pass `fix` (a fix or pilot-node name or fragment).

- `fix` (string, required)

### `simulate_futures`

SIMULATE MANY FUTURES FOR A DRUG, THEN COUNT (the method of Epic's Curiosity model, with the next step copied from similar past drugs instead of learned). Histories come from ClinicalTrials.gov phases and first FDA approvals in gapmap/history.db. Pass `conditions` (comma-separated words that define similar drugs, e.g. 'alzheimer'), `stage` (1, 2 or 3), `years_in` (years already spent at that stage), `horizon` (years), or `drug` (a name: its own history sets the start). Returns the share of simulated futures approved within the horizon, given both ways, where the rest ended, and a plain-count check. Approvals filed under a different name than the trial used are missed, so the share runs low.

- `conditions` (string)
- `stage` (integer)
- `years_in` (number)
- `horizon` (number)
- `drug` (string)
- `sims` (integer)
- `seed` (integer)
