#!/usr/bin/env python3
"""
run_tool.py -- run one Elipsis tool from the command line and print its answer.

The same 48 tools the MCP server offers, without a server: the plugin's skills tell
Claude to run this script, so nothing has to be started or kept running.

    python harness/run_tool.py --list                      # every tool, one line each
    python harness/run_tool.py --schema ledger_add         # one tool's description and arguments
    python harness/run_tool.py steelman '{"claim": "..."}'   # run a tool, arguments as JSON
    python harness/run_tool.py steelman -  < args.json     # or read the JSON from stdin
    python harness/run_tool.py --data DIR ledger_status    # keep saved work in DIR

--data names the folder for saved work (forecasts, decisions, chains). The plugin's
skills pass Claude Code's plugin data folder here. Without it, saved work goes where
harness/paths.py puts it for a clone: inside harness/.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv):
    sys.path.insert(0, HERE)
    import paths
    if "--data" in argv:
        i = argv.index("--data")
        if i + 1 >= len(argv) or "${" in argv[i + 1]:
            sys.exit("--data needs a folder")
        # Before the tools are imported: each fixes its file paths on import.
        paths.use(argv[i + 1])
        del argv[i:i + 2]
    import mcp_server as srv

    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    if argv[0] == "--list":
        for name, (_, desc, _) in srv.TOOLS.items():
            print(f"{name}: {' '.join(desc.split())[:110]}")
        return 0
    if argv[0] == "--schema":
        if len(argv) < 2 or argv[1] not in srv.TOOLS:
            sys.exit("give a tool name; --list shows them")
        _, desc, schema = srv.TOOLS[argv[1]]
        print(" ".join(desc.split()))
        print(json.dumps(schema, indent=1))
        return 0

    name = argv[0]
    if name not in srv.TOOLS:
        sys.exit(f"no tool '{name}'; --list shows them")
    raw = argv[1] if len(argv) > 1 else "{}"
    if raw == "-":
        raw = sys.stdin.read()
    elif raw.startswith("@"):
        raw = open(raw[1:], encoding="utf-8").read()
    try:
        args = json.loads(raw or "{}")
    except json.JSONDecodeError as e:
        sys.exit(f"the arguments are not valid JSON: {e}")
    if not isinstance(args, dict):
        sys.exit("the arguments must be a JSON object, such as {\"claim\": \"...\"}")

    paths.seed()
    try:
        out = srv.TOOLS[name][0](args)
    except (ValueError, KeyError, TypeError) as e:
        sys.exit(f"{type(e).__name__}: {e}")
    sys.stdout.reconfigure(encoding="utf-8")
    print(srv.SHOW_WORK_SHORT.strip())
    print()
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
