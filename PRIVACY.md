# Privacy policy

Elipsis runs entirely on your own computer. Its author runs no server and receives no data from it: no usage statistics, no error reports, no account.

## What it stores

Only what you choose to save (forecasts, decisions, chains, claim rows), as files in the plugin's data folder on your computer, or in `harness/` inside a clone, or in the folder you name with `ELIPSIS_DATA`. It stays there until you delete it. Nothing is uploaded.

## What it reads

The text Claude passes to a tool when you ask for one. It does not read your files, browser, email or any other personal data.

## What it sends, and where

No tool sends personal data, files or conversation text anywhere. The network is used only in these cases:

1. `fact_check_lookup` searches a local index. You build the index once by hand (`python harness/factcheck.py fetch`), which downloads Google's public ClaimReview feed from `storage.googleapis.com`. If you run Elipsis from a clone and set a `GOOGLE_FACTCHECK_KEY` environment variable yourself, the tool also sends your search words, with that key, to `factchecktools.googleapis.com`. The plugin never sets one.
2. `python harness/number_ledger.py auto`, run by hand, fetches published figures from `api.bls.gov` or `fred.stlouisfed.org`.
3. The gap-map scripts, run by hand, send search terms to the public research and news databases listed in the README under "What it connects to". They send no email address or other personal data.

Those services have their own privacy policies.

## Children

Elipsis is not intended for people under 18.

## Changes

Changes to this policy are made in this file, and its history is public in this repository.
