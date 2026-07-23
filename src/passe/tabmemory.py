"""Last-tab memory — records which tab a run kept, per CDP endpoint.

--reuse-tab means "resume the tab passe kept for you". Before this module
it meant "attach to whatever tab happens to be first in Chrome's register",
which on a shared browser was nearly the human's live tab (2026-07-21) and,
once the kept tab had vanished, was chrome://newtab (2026-07-23, the Mac
PCA spike — three evals ran in a chrome:// origin and returned junk).

File: ~/.passe/last-tab.json — {endpoint: {target_id, url, ts}}.
No passe imports (same discipline as refcache.py): commands.py is the only
consumer, but keeping this module import-free means the state layer never
widens the dependency DAG. All operations are best-effort — a corrupt or
missing file degrades to "no memory", never to a crash.
"""

import json
import time
from pathlib import Path

LAST_TAB_PATH = None  # resolved lazily; tests patch this


def _path() -> Path:
    return LAST_TAB_PATH or Path.home() / '.passe' / 'last-tab.json'


def save_last_tab(endpoint: str, target_id: str, url: str = '') -> None:
    """Record the tab a run kept at this endpoint. Best-effort."""
    if not endpoint or not target_id:
        return
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        try:
            data = json.loads(path.read_text())
        except Exception:
            pass
        if not isinstance(data, dict):
            data = {}
        data[endpoint] = {'target_id': target_id, 'url': url,
                          'ts': time.time()}
        path.write_text(json.dumps(data))
    except Exception:
        pass


def load_last_tab(endpoint: str) -> dict | None:
    """Return {target_id, url, ts} for this endpoint, or None."""
    if not endpoint:
        return None
    try:
        record = json.loads(_path().read_text()).get(endpoint)
        return record if isinstance(record, dict) else None
    except Exception:
        return None


def clear_last_tab(endpoint: str) -> None:
    """Forget the recorded tab (e.g. it no longer exists). Best-effort."""
    if not endpoint:
        return
    try:
        path = _path()
        data = json.loads(path.read_text())
        if isinstance(data, dict) and endpoint in data:
            del data[endpoint]
            path.write_text(json.dumps(data))
    except Exception:
        pass
