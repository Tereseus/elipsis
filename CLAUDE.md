# Elipsis: how to answer with these tools

Elipsis has one L, on purpose. The tool server is `harness/mcp_server.py`; `.mcp.json` starts it.

When you use Elipsis to check a claim or make a forecast:

1. Say how rough the answer is (measured, estimated or guessed) before giving any number.
2. Quote the claim being checked in full. Give its strongest version (the steelman) before auditing it, and list what you supplied to build it. Refuting the wording while the argument survives is a failure, not a finding.
3. Show each formula in standard notation, then with the numbers substituted, then a legend that defines every symbol in plain English.
4. Every percentage says what it is a percentage of, and is given both ways ("80 in 100, 20 not").
5. List the items behind any count, so the answer stands alone.
6. End with a short plain-English summary.

For a "should" question, keep the two parts apart: the values belong to the person asking; only the effects can be forecast and scored.

The forecast ledger is append-only. Use the ledger tools to add, resolve and score forecasts, and never edit its file by hand. Before logging a forecast, check whether the question has already been settled.
