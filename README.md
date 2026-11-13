# Elipsis

Tools for checking claims and making forecasts with Claude. The model does the language; plain, readable Python does the arithmetic, and shows it.

(One L in the name, on purpose.)

Elipsis is a set of tools that run on your own computer as plain Python scripts. As a Claude plugin, each group of tools comes as a skill that tells Claude which script to run. The same tools can also be served over MCP, the Model Context Protocol, for other clients. Either way they need only Python 3: no account, no API key, no hosting, no other packages. Almost every tool works offline. What goes over the network, and when, is listed under [What it connects to](#what-it-connects-to).

## What it does

- **Decide.** Options, plus beliefs held as ranges rather than single numbers. It returns which option wins, how confident to be, which beliefs could flip the answer and where, and what further research would be worth.
- **Chains.** A compound claim ("by 2036, X, then Y, then Z") becomes a product of conditional steps. It reports the step that kills it and guards against multiplying guesses into doom.
- **Forecast ledger.** Log a probability with a resolution date, resolve it later, and score the record (Brier score, calibration). The record is append-only.
- **Audits.** Steelman a claim before checking it; test whether a conclusion follows from its premises; check how a question is framed; trace where an idea already existed; grade the evidence.
- **Trials.** Design a small self-experiment (n-of-1), assign days to arms, and analyse the result.
- **Gap map.** Build your own map of open problems in science from public research databases, and see which ones are moving.
- **Claim rows.** One row per checked claim: its verdict, the open problem it belongs to, the chain of steps to its milestone, and computed odds by year. Across many rows it counts where known approaches get stuck: the step whose improvement is worth the most. It ranks the options it knows about and says what it believes. It cannot invent new options, and its beliefs are scored as forecasts.

The full list of tools, with one line each, is in [TOOLS.md](TOOLS.md). Every tool tells Claude to show the formula, the numbers substituted in, and a plain-English legend for every symbol.

## Install

### 1. As a Claude Code plugin (recommended)

At the prompt of a Claude Code terminal session:

```
/plugin install elipsis --marketplace Tereseus/elipsis
```

Answer `y` to add the marketplace, then pick a scope (user scope makes it available in every project). From a shell, the same is:

```
claude plugin install elipsis --marketplace Tereseus/elipsis
```

In the Claude desktop app, where `/plugin` does not run: click + next to the prompt box, then Plugins, Add marketplace with `Tereseus/elipsis`, then Add plugin.

The plugin brings eight skills and no server. Two say how to work: `elipsis` (how to answer: roughness first, the steelman, formulas with legends, percentages both ways) and `forecast` (how to log, settle and score a forecast in the ledger). Six run the tools, grouped by job: `elipsis-claims`, `elipsis-chains`, `elipsis-decisions`, `elipsis-ledger`, `elipsis-trials` and `elipsis-gapmap`. Each one lists its tools and has Claude run `harness/run_tool.py` from the plugin folder.

Claude runs the scripts with `python`, or `python3` or `py` where that is the command your computer has. Nothing needs setting.

Your saved work (forecasts, decisions, chains) is kept in Claude Code's plugin data folder, so it survives updates. The tools start empty: nothing is saved until you save it.

### 2. Clone and open

```
git clone https://github.com/Tereseus/elipsis
cd elipsis
claude
```

Ask Claude to run any tool with `python harness/run_tool.py TOOL '{...}'` (`--list` shows them all), or add the server as in the next section. Saved work stays inside the clone, in `harness/`.

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

- Python 3 on your PATH (tested on 3.13), as `python`, `python3` or `py`.
- Windows: install Python from python.org and tick "Add python.exe to PATH". If only `py` works on your machine, use `py` in place of `python` in the commands above.

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

## What it connects to

The full privacy policy is in [PRIVACY.md](PRIVACY.md). Nothing runs in the background, nothing is sent anywhere when a tool starts, and no tool sends personal data, files or conversation text. The network is used in three places only.

1. **The `fact_check_lookup` tool.** It searches a local index of published fact checks. You build that index once by hand with `python harness/factcheck.py fetch`, which downloads Google's public ClaimReview feed (about 200 MB, from `storage.googleapis.com`). The lookup itself is local: it never contacts Google or any other service, and it uses no API key.
2. **Settling number forecasts by hand.** `python harness/number_ledger.py auto` fetches the published figure from `api.bls.gov` (US Bureau of Labor Statistics) or `fred.stlouisfed.org` (Federal Reserve Bank of St. Louis), for forecasts that name one of those sources.
3. **Gap-map scripts, run by hand.** `gapmap.py`, `gapmap_daily.py`, `gapmap_topics.py`, `gapsources.py` and `gaphistory.py` query public research and news databases: `api.openalex.org`, `clinicaltrials.gov`, `europepmc.org`, `www.ebi.ac.uk`, `www.gap-map.org`, `doi.org`, `export.arxiv.org`, `api.jstage.jst.go.jp`, `api.nsf.gov`, `www.nsf.gov`, `api.reporter.nih.gov`, `www.osti.gov`, `www.federalregister.gov`, `news.google.com`, `api.fda.gov`, `api.manifold.markets` and `web.archive.org`. They send search terms only, with no email address or other personal data. OpenAlex's free allowance is about 1,000 requests a day, and the scripts stop themselves below a reserve.

## Where saved work goes

| How you installed | Where it is saved |
|---|---|
| Plugin | `~/.claude/plugins/data/<plugin id>/` |
| Clone | `harness/` inside the clone |
| Your choice | Pass `--data FOLDER` to `harness/run_tool.py` |

## A worked example

[examples/ageing-top-ten-video.md](examples/ageing-top-ten-video.md) checks ten claims from a popular video on ageing research against the original studies. It then estimates when each line of research could be approved for use in people, as a chain of trial stages with published success rates. The simulation behind the table is [examples/ageing_milestones.py](examples/ageing_milestones.py).

## Licence

MIT. See [LICENSE](LICENSE).
