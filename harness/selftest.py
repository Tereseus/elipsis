"""Check that the Elipsis tool server works: start it the way Claude does, list its tools,
and run the shipped examples. Uses a throwaway data folder, so nothing you saved is touched.

    python harness/selftest.py

Exit code 0 means every check passed.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# (tool, arguments, text the answer must contain)
CHECKS = [
    ("decide_list", {}, "saved decisions"),
    ("chain_list", {}, "chains"),
    ("chain", {"chain": {"claim": "A fair coin lands heads three times in a row.",
                         "horizon_years": 1,
                         "links": [{"id": f"toss_{i}", "p": 0.5, "low": 0.5, "high": 0.5,
                                    "provenance": "measured",
                                    "statement": f"Toss {i} lands heads.",
                                    "basis": "A fair coin."} for i in (1, 2, 3)]}},
     "0.125"),
    ("ledger_status", {}, ""),
    ("steelman", {}, "STEELMAN"),
    ("evidence", {}, "EVIDENCE"),
]


def main():
    data = tempfile.mkdtemp(prefix="elipsis-selftest-")
    env = dict(os.environ, ELIPSIS_DATA=data, PYTHONIOENCODING="utf-8")
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "mcp_server.py")],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", env=env)
    ids = iter(range(1, 10**6))

    def rpc(method, params=None):
        msg = {"jsonrpc": "2.0", "id": next(ids), "method": method}
        if params is not None:
            msg["params"] = params
        p.stdin.write(json.dumps(msg) + "\n")
        p.stdin.flush()
        line = p.stdout.readline()
        if not line:
            raise SystemExit("FAIL  the server stopped:\n" + p.stderr.read()[-3000:])
        return json.loads(line)

    failed = 0
    try:
        info = rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                  "clientInfo": {"name": "selftest", "version": "1"}})["result"]
        print(f"ok    started {info['serverInfo']['name']} {info['serverInfo']['version']}")
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        print("ok    ping" if rpc("ping").get("result") == {} else "FAIL  ping")
        tools = {t["name"] for t in rpc("tools/list")["result"]["tools"]}
        print(f"ok    {len(tools)} tools listed")
        for name, args, must in CHECKS:
            if name not in tools:
                print(f"FAIL  {name}: not offered by the server"); failed += 1; continue
            res = rpc("tools/call", {"name": name, "arguments": args}).get("result", {})
            text = " ".join(c.get("text", "") for c in res.get("content", []))
            if res.get("isError") or (must and must not in text):
                print(f"FAIL  {name}: {text[:300]}"); failed += 1
            else:
                print(f"ok    {name}")
    finally:
        p.stdin.close()
        p.wait(timeout=20)
        shutil.rmtree(data, ignore_errors=True)
    print("all checks passed" if not failed else f"{failed} check(s) failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
