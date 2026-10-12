"""Repairs for known data-quality problems in the match JSON.

``dedupe_matches``  drops repeated rows for the same fixture.
``mark_void``       turns placeholder 0-0 rows (cancelled or never-played
                    fixtures that carry no scorers or lineups) into unplayed
                    fixtures: ``score`` becomes ``null`` and the match gets
                    ``"status": "void"``, so models don't read them as results.

Both are idempotent and run via ``rugby data clean``.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

from .validation import load_matches, match_key

PLACEHOLDER_TEAMS = {"TBC", "TBD", "tbc", "tbd"}


def _richness(match: dict) -> Tuple[int, int, int]:
    """Prefer the copy with a score, then more lineup/scoring detail."""
    def n(side, key):
        return len(side.get(key) or [])
    h, a = match.get("home") or {}, match.get("away") or {}
    scored = int(h.get("score") is not None and a.get("score") is not None)
    return scored, n(h, "lineup") + n(a, "lineup"), n(h, "scores") + n(a, "scores")


def _is_placeholder(match: dict) -> bool:
    return any((match.get(s) or {}).get("team") in PLACEHOLDER_TEAMS for s in ("home", "away"))


def _is_unnamed(match: dict) -> bool:
    return any(not str((match.get(s) or {}).get("team") or "").strip() for s in ("home", "away"))


def dedupe_matches(matches: List[dict]) -> Tuple[List[dict], int]:
    """Keep one row per (date, home, away), preferring the richest.

    Unannounced fixtures (``TBC v TBC``) and rows without team names are never
    merged: they say nothing about which fixture they are.
    """
    best: Dict[str, int] = {}
    keep: List[dict] = []
    removed = 0
    for m in matches:
        if _is_placeholder(m) or _is_unnamed(m):
            keep.append(m)
            continue
        k = match_key(m)
        if k not in best:
            best[k] = len(keep)
            keep.append(m)
        elif _richness(m) > _richness(keep[best[k]]):
            keep[best[k]] = m
            removed += 1
        else:
            removed += 1
    return keep, removed


def is_void_placeholder(match: dict) -> bool:
    h, a = match.get("home") or {}, match.get("away") or {}
    return (
        h.get("score") == 0 and a.get("score") == 0
        and not (h.get("scores") or a.get("scores") or h.get("lineup") or a.get("lineup"))
    )


def mark_void(matches: List[dict]) -> int:
    n = 0
    for m in matches:
        if is_void_placeholder(m):
            m["home"]["score"] = None
            m["away"]["score"] = None
            m["status"] = "void"
            n += 1
    return n


def clean_directory(directory: Path, check: bool = False) -> Dict[str, Dict[str, int]]:
    """Apply both repairs to every list-format file. Returns {file: counts}
    for files that changed; with ``check`` nothing is written."""
    report: Dict[str, Dict[str, int]] = {}
    for path in sorted(Path(directory).glob("*.json")):
        matches = load_matches(path.read_text())
        if not matches:
            continue
        matches, dupes = dedupe_matches(matches)
        voided = mark_void(matches)
        if dupes or voided:
            report[path.name] = {"duplicates": dupes, "void": voided}
            if not check:
                path.write_text(json.dumps(matches, indent=2))
    return report
