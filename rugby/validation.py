"""Sanity checks for match data, run on what a data-update job just changed.

The source files contain historical oddities we can't repair without a second
source (blank team names, 0-0 placeholders, duplicates). Those are left alone;
what we want is to stop *new* ones being committed unnoticed. So the checks
run only on matches that are new or different from a git baseline (default
``HEAD``), and historical problems never block a scheduled run.

Errors should stop the commit; warnings are reported.
"""

import json
import math
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .team_names import canonical_team_name

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    file: str
    severity: str
    rule: str
    message: str
    match: str  # "date home v away", for humans


def _score(side: dict) -> Optional[float]:
    s = side.get("score")
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return None
    return s


def match_key(match: dict) -> str:
    home = canonical_team_name((match.get("home") or {}).get("team")) or ""
    away = canonical_team_name((match.get("away") or {}).get("team")) or ""
    return f"{str(match.get('date', ''))[:10]}|{home}|{away}"


def _label(match: dict) -> str:
    home, away = match.get("home") or {}, match.get("away") or {}
    return f"{str(match.get('date', ''))[:10]} {home.get('team')!r} v {away.get('team')!r}"


def check_match(match: dict, now: Optional[datetime] = None) -> List[Tuple[str, str, str]]:
    """Problems with one match as (severity, rule, message)."""
    now = now or datetime.now(timezone.utc)
    found: List[Tuple[str, str, str]] = []
    home, away = match.get("home"), match.get("away")
    if not isinstance(home, dict) or not isinstance(away, dict):
        return [(ERROR, "malformed", "home/away missing or not objects")]

    names = [home.get("team"), away.get("team")]
    if any(n is None or not str(n).strip() for n in names):
        found.append((ERROR, "blank_team", "a team name is missing or blank"))
    else:
        if str(names[0]).strip() == str(names[1]).strip():
            found.append((ERROR, "same_team", f"{names[0]!r} plays itself"))
        for n in names:
            if canonical_team_name(n) != n:
                found.append((ERROR, "non_canonical",
                              f"{n!r} should be {canonical_team_name(n)!r} (run `rugby data normalise`)"))

    try:
        when = datetime.fromisoformat(str(match.get("date")).replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
    except ValueError:
        when = None
        found.append((ERROR, "bad_date", f"unparseable date {match.get('date')!r}"))

    hs, as_ = _score(home), _score(away)
    if (hs is None) != (as_ is None):
        found.append((ERROR, "half_result", "only one side has a score"))
    elif hs is not None:
        if hs < 0 or as_ < 0:
            found.append((ERROR, "negative_score", f"score {hs}-{as_}"))
        if hs == 0 and as_ == 0:
            found.append((WARNING, "scoreless", "0-0 result (usually a cancelled or placeholder fixture)"))
        if when is not None and when > now + timedelta(days=1):
            found.append((WARNING, "future_result", f"has a result but is dated {when.date()}"))
    elif when is not None and match.get("status") != "void" and when < now - timedelta(days=3):
        found.append((WARNING, "missing_result", f"dated {when.date()} but has no result"))
    return found


def load_matches(text: str) -> List[dict]:
    """Matches from a list-format JSON file (legacy column-oriented files hold
    historical seasons only and aren't produced by the updater: ignored)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return [m for m in data if isinstance(m, dict)] if isinstance(data, list) else []


def _canon(match: dict) -> str:
    return json.dumps(match, sort_keys=True, default=str)


def _git(args: List[str], cwd: Path) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
        return out.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def baseline_text(path: Path, ref: str) -> Optional[str]:
    """The file's content at ``ref``, or None if it didn't exist / no git."""
    top = _git(["rev-parse", "--show-toplevel"], path.parent)
    if top is None:
        return None
    rel = path.resolve().relative_to(Path(top.strip()).resolve())
    return _git(["show", f"{ref}:{rel.as_posix()}"], path.parent)


def validate_directory(
    directory: Path, against: Optional[str] = "HEAD", every_match: bool = False,
    now: Optional[datetime] = None,
) -> List[Issue]:
    """Issues in ``directory/*.json``.

    By default only matches that are new or differ from ``against`` are
    checked. ``every_match`` audits everything (expect known historical
    problems).
    """
    issues: List[Issue] = []
    for path in sorted(Path(directory).glob("*.json")):
        matches = load_matches(path.read_text())
        if not matches:
            continue
        if every_match or against is None:
            selected = list(matches)
        else:
            old = baseline_text(path, against)
            # Compare whole-match content, not a key: several historical rows
            # share a key (e.g. blank team names on one date).
            known = {_canon(m) for m in load_matches(old)} if old else set()
            selected = [m for m in matches if _canon(m) not in known]
        if not selected:
            continue

        for m in selected:
            for severity, rule, message in check_match(m, now):
                issues.append(Issue(path.name, severity, rule, message, _label(m)))

        counts: Dict[str, int] = {}
        for m in matches:
            counts[match_key(m)] = counts.get(match_key(m), 0) + 1
        for m in selected:
            if counts[match_key(m)] > 1 and match_key(m) != "||" and "TBC" not in match_key(m):
                issues.append(Issue(path.name, ERROR, "duplicate",
                                    f"{counts[match_key(m)]} matches with the same date and teams", _label(m)))
    return issues


def summarise(issues: Iterable[Issue]) -> str:
    """Markdown table for a CI step summary."""
    issues = list(issues)
    if not issues:
        return "No problems in the matches this run added or changed.\n"
    lines = ["| severity | rule | file | match | detail |", "|---|---|---|---|---|"]
    for i in sorted(issues, key=lambda i: (i.severity != ERROR, i.rule, i.file)):
        lines.append(f"| {i.severity} | {i.rule} | {i.file} | {i.match} | {i.message} |")
    return "\n".join(lines) + "\n"
