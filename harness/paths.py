"""Where Elipsis keeps what it saves (forecasts, decisions, chains, frames and the rest).

By default that is this folder, next to the code, which is right for anyone who cloned
the repository. When Elipsis is installed as a Claude Code plugin, the code folder is
replaced on every update, so saved work must live elsewhere: set ELIPSIS_DATA to a
folder (the plugin sets it to its own data folder). The first time a new data folder
is used, the examples that ship with the code are copied into it; nothing already
there is ever overwritten.
"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED = ("frames", "budgets", "claims", "entail", "ledger", "decisions", "trials",
         "passes", "chains", "panels", "questions", "rows")


def _pick():
    for v in (os.environ.get("ELIPSIS_DATA"), os.environ.get("CLAUDE_PLUGIN_DATA")):
        if v and "${" not in v:          # an unexpanded placeholder counts as unset
            return os.path.abspath(os.path.expanduser(v))
    return HERE


DATA = _pick()

# Every saved-work folder exists, even when no examples ship with the code.
for _sub in SAVED:
    try:
        os.makedirs(os.path.join(DATA, _sub), exist_ok=True)
    except OSError:
        pass


def data(*parts):
    return os.path.join(DATA, *parts)


def seed():
    """Copy the shipped examples into a separate data folder, never overwriting."""
    if DATA == HERE:
        return
    for sub in SAVED:
        src = os.path.join(HERE, sub)
        if not os.path.isdir(src):
            continue
        for dirpath, _, files in os.walk(src):
            out = os.path.join(DATA, sub, os.path.relpath(dirpath, src))
            os.makedirs(out, exist_ok=True)
            for f in files:
                if not os.path.exists(os.path.join(out, f)):
                    shutil.copy2(os.path.join(dirpath, f), os.path.join(out, f))
