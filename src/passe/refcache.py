"""Ref cache — bridges ax-tree --flat-refs output to click/type/hover eN args.

ax-tree --flat-refs assigns e0..eN to interactive elements and persists
{ref: backendDOMNodeId} per tab. Interaction verbs resolve eN back to the
live element via DOM.resolveNode. Files live in ~/.passe/refs/<tab_id>.json
so the refs survive across passe invocations (scout in one call, act in the
next); navigation clears them — a backendDOMNodeId never survives a page
load. No passe imports: both verbs_observation (writer) and
verbs_interaction (reader) import this without widening the DAG.
"""

import json
import re
import time
from pathlib import Path

REFS_DIR = None  # resolved lazily; tests patch this

REF_PATTERN = re.compile(r'^e\d+$')

STALE_AFTER_S = 7 * 86400  # refs outlive their tab; prune on write


def _base_dir() -> Path:
    return REFS_DIR or Path.home() / '.passe' / 'refs'


def tab_id_of(client) -> str:
    """Current tab id, or '' — tolerant of spec'd test doubles that lack
    the _target_id instance attribute."""
    return getattr(client, '_target_id', None) or ''


def _refs_file(tab_id: str) -> Path:
    return _base_dir() / (str(tab_id).replace('/', '_') + '.json')


def save_refs(tab_id: str, mapping: dict) -> None:
    """Persist {ref: backendDOMNodeId} for a tab. Best-effort.

    Also prunes refs files older than STALE_AFTER_S — tabs close but their
    refs files used to accumulate forever (one per tab id).
    """
    if not tab_id:
        return
    try:
        path = _refs_file(tab_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(mapping, f)
        cutoff = time.time() - STALE_AFTER_S
        for stale in path.parent.glob('*.json'):
            try:
                if stale != path and stale.stat().st_mtime < cutoff:
                    stale.unlink()
            except OSError:
                pass
    except Exception:
        pass


def newest_refs_tab(live_tab_ids) -> str | None:
    """The most recently snapped refs tab that is still open, or None.

    The scout-then-act flow writes refs moments before the act step — the
    newest refs file among live tabs is the tab the refs were snapped from.
    """
    live = set(live_tab_ids)
    try:
        candidates = sorted(_base_dir().glob('*.json'),
                            key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return None
    for path in candidates:
        if path.stem in live:
            return path.stem
    return None


def load_refs(tab_id: str) -> dict | None:
    """Load the ref mapping for a tab, or None."""
    if not tab_id:
        return None
    try:
        with open(_refs_file(tab_id)) as f:
            return json.load(f)
    except Exception:
        return None


def clear_refs(tab_id: str) -> None:
    """Drop a tab's refs (called on navigation). Best-effort."""
    if not tab_id:
        return
    try:
        _refs_file(tab_id).unlink(missing_ok=True)
    except Exception:
        pass
