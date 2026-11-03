---
name: forecast
description: How to log, settle and score a forecast with the Elipsis ledger. Use when someone asks "will X happen", wants a probability written down, asks what is due to be settled, or asks how good the forecasts have been.
---

# Forecasting with the Elipsis ledger

A probability that was never written down before the answer was known cannot be scored. The ledger exists to write it down first.

## Logging a forecast

1. **Check the question is still open.** Search for its current state with a dated source. If it has already happened, or already cannot happen, do not log it: that is a free win, not a forecast.
2. **Pin the question down.** Write the resolution criteria so a stranger could settle it: what counts as yes, what counts as no, the source that decides it, and the date.
3. **Write your own probability before looking at any market price.** A number formed after seeing the market is the market's number.
4. **Find a starting number (the baseline).** In order of preference: a count from past cases of the same kind (`baseline.count = {yes, of, source}`), a market price that asks the same question (copy the market's full rules into `market_rules` and say in `wording_vs_market` whether the wording matches), or "nothing changes" (`kind: persistence`). A guessed baseline must say why nothing could be counted.
5. **Explain any big move.** A forecast more than 0.10 from its baseline needs a `departure`: what this case has that the usual case lacks.
6. **Log it** with `ledger_add`. The ledger stores a corrected probability next to yours, pulled toward the baseline by as much as the track record supports. Report the corrected number first and yours second, as "before correction".

Prefer questions that settle within months. One that settles in twenty years gives one data point in twenty years.

## Settling forecasts

1. Run `ledger_due` to list what is past its date.
2. For each one, find a dated, credible source and read it against the logged resolution criteria, not against what a market or a headline decided.
3. Settle only what is clearly settled, with `ledger_resolve` and a note naming the source. Leave anything unclear open and say why.

## Reporting the score

Use `ledger_score`. Explain the Brier score with its formula and a legend:

B = (f − o)²

- B is the score for one forecast. Lower is better: 0 is perfect, and always saying 50 in 100 earns 0.25.
- f is the forecast, as a chance between 0 and 1.
- o is what happened: 1 if it came true, 0 if not.

Compare the record against the baseline's score, not against zero. Forecasts that do not beat the starting numbers add nothing, however confident they sound.

The ledger is append-only. Never edit its file by hand. When new information changes an open forecast, log the new number with `ledger_rerun`: it keeps the old one, and both are scored.
