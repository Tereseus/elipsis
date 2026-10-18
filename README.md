# Elipsis

Tools for checking claims and making forecasts with Claude. The model does the language; plain, readable Python does the arithmetic, and shows it.

(One L in the name, on purpose.)

Elipsis is an MCP server. MCP, the Model Context Protocol, is the standard way to give Claude extra tools. This one runs on your own computer and needs only Python 3: no account, no API key, no hosting, no other packages. The tools run offline. Only the gap-map update scripts, which you run by hand, read public research databases (OpenAlex, ClinicalTrials.gov and others), and they send no personal data.

## What it does

- **Decide.** Options, plus beliefs held as ranges rather than single numbers. It returns which option wins, how confident to be, which beliefs could flip the answer and where, and what further research would be worth.
- **Chains.** A compound claim ("by 2036, X, then Y, then Z") becomes a product of conditional steps. It reports the step that kills it and guards against multiplying guesses into doom.
- **Forecast ledger.** Log a probability with a resolution date, resolve it later, and score the record (Brier score, calibration). The record is append-only.
- **Audits.** Steelman a claim before checking it; test whether a conclusion follows from its premises; check how a question is framed; trace where an idea already existed; grade the evidence.
- **Trials.** Design a small self-experiment (n-of-1), assign days to arms, and analyse the result.
- **Gap map.** Build your own map of open problems in science from public research databases, and see which ones are moving.

The full list of tools, with one line each, is in [TOOLS.md](TOOLS.md). Every tool tells Claude to show the formula, the numbers substituted in, and a plain-English legend for every symbol.

## Install

### 1. As a Claude Code plugin (recommended)

In Claude Code:

```
/plugin marketplace add https://github.com/Tereseus/elipsis.git
/plugin install elipsis@elipsis
```

Your saved work (forecasts, decisions, chains) is kept in Claude Code's plugin data folder, so it survives updates. The tools start empty: nothing is saved until you save it.

### 2. Clone and open

```
git clone https://github.com/Tereseus/elipsis
cd elipsis
claude
```

Claude Code asks once whether to use the `elipsis` server in this folder; say yes. Saved work stays inside the clone, in `harness/`.

### 3. Any other MCP client

The server is a plain stdio process:

```
python /path/to/elipsis/harness/mcp_server.py
```

To add it to Claude Code for every project:

```
claude mcp add --scope user elipsis -- python /path/to/elipsis/harness/mcp_server.py
```

Claude Desktop and other MCP clients take the same command in their own settings. The claude.ai website and phone apps cannot use it, because they only connect to servers hosted on the internet.

## Requirements

- Python 3 on your PATH as `python` (tested on 3.13).
- Windows: install Python from python.org and tick "Add python.exe to PATH". If only `py` works on your machine, replace `python` with `py` in the commands above or in `.mcp.json`.

Check that everything works:

```
python harness/selftest.py
```

It starts the server, lists the tools and runs a few of them.

### Optional: the history database

One tool, `simulate_futures`, needs a base-rate database of past clinical trials and approvals (about 250 MB, built from public sources). It is not included. Build it once with:

```
python harness/gaphistory.py fetch-trials
python harness/gaphistory.py fetch-approvals
```

## Where saved work goes

| How you installed | Where it is saved |
|---|---|
| Plugin | `~/.claude/plugins/data/<plugin id>/` |
| Clone | `harness/` inside the clone |
| Your choice | Set the `ELIPSIS_DATA` environment variable to any folder |

## A worked example

[examples/ageing-top-ten-video.md](examples/ageing-top-ten-video.md) checks ten claims from a popular video on ageing research against the original studies. It then estimates when each line of research could be approved for use in people, as a chain of trial stages with published success rates. The simulation behind the table is [examples/ageing_milestones.py](examples/ageing_milestones.py).

## Licence

MIT. See [LICENSE](LICENSE).
