"""Canonical team names.

The sources spell the same club differently by era and competition
("Leinster" / "Leinster Rugby", "Cardiff Blues" / "Cardiff Rugby"). Names are
made canonical here, once, when data is written, so every consumer of the JSON
sees one spelling per club and no downstream alias tables are needed.

``rugby data normalise`` applies this table to existing files (and
``--check`` fails if any file is not canonical, which CI runs as a test).

Rename entries record *same franchise* changes:
  - Canterbury Crusaders (to 2004) -> Crusaders
  - Neath-Swansea Ospreys (2003-05) -> Ospreys
  - Free State Cheetahs (Currie Cup) and Toyota Cheetahs (Challenge Cup)
    -> Cheetahs
"""

import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

TEAM_NAME_ALIASES: Dict[str, str] = {
    'Crusaders |': 'Crusaders',
    'Cheetahs |': 'Cheetahs',
    'Neath–Swansea Ospreys': 'Ospreys',
    'Glasgow ': 'Glasgow Warriors',
    'Glasgow': 'Glasgow Warriors',
    'Edinburgh': 'Edinburgh Rugby',
    'Leinster': 'Leinster Rugby',
    'Munster': 'Munster Rugby',
    'Ulster': 'Ulster Rugby',
    'Connacht': 'Connacht Rugby',
    'Cardiff': 'Cardiff Rugby',
    'Cardiff Blues': 'Cardiff Rugby',
    'Dragons': 'Dragons RFC',
    'Benetton': 'Benetton Rugby',
    'Zebre': 'Zebre Parma',
    'Sharks': 'Hollywoodbets Sharks',
    'Lions': 'Emirates Lions',
    'Stormers': 'DHL Stormers',
    'Blue Bulls': 'Vodacom Bulls',
    'Bulls': 'Vodacom Bulls',
    'Northampton': 'Northampton Saints',
    'Newcastle Red Bulls': 'Newcastle Falcons',
    'Leicester': 'Leicester Tigers',
    'Bath': 'Bath Rugby',
    'Sale': 'Sale Sharks',
    'Exeter': 'Exeter Chiefs',
    'Newcastle': 'Newcastle Falcons',
    'Worcester': 'Worcester Warriors',
    'Bristol': 'Bristol Bears',
    'Gloucester': 'Gloucester Rugby',
    'Lyon O.U.': 'Lyon',
    'Racing': 'Racing 92',
    'Stade Francais Paris': 'Stade Francais',
    'Clermont Auvergne': 'Clermont',
    'Bordeaux-Beg': 'Bordeaux-Begles',
    'Castres Olympique': 'Castres',
    'Biarritz Olympique': 'Biarritz',
    'Canterbury Crusaders': 'Crusaders',
    'Neath-Swansea Ospreys': 'Ospreys',
    'Free State Cheetahs': 'Cheetahs',
    'Toyota Cheetahs': 'Cheetahs',
}

# A JSON string value following a "team" key, in compact or indented files.
_TEAM_VALUE = re.compile(r'("team"\s*:\s*)("(?:[^"\\]|\\.)*")')
# "<comp>-YYYY-YYYY.json" with the years the wrong way round.
_SEASON_FILE = re.compile(r"^(?P<comp>.+)-(?P<a>\d{4})-(?P<b>\d{4})(?P<ext>\.json)$")


def canonical_team_name(name: Optional[str]) -> Optional[str]:
    """Canonical spelling of ``name`` (stripped); ``None`` and blanks pass through."""
    if name is None:
        return None
    return TEAM_NAME_ALIASES.get(name, TEAM_NAME_ALIASES.get(name.strip(), name.strip()))


def normalise_match_teams(match: dict) -> dict:
    """Canonicalise the team names of one match dict in place and return it."""
    for side in ("home", "away"):
        side_data = match.get(side)
        if isinstance(side_data, dict) and "team" in side_data:
            side_data["team"] = canonical_team_name(side_data["team"])
    return match


def rewrite_team_names(text: str) -> Tuple[str, Dict[str, int]]:
    """Canonicalise every ``"team": "..."`` value in JSON ``text``.

    Substitutes in place, leaving every other byte (indentation, key order,
    number formatting, unicode escapes) untouched so the diff shows only the
    names that changed. Returns (new text, {old name: count}). Idempotent.
    """
    changed: Dict[str, int] = {}

    def sub(m: "re.Match") -> str:
        literal = m.group(2)
        old = json.loads(literal)
        new = canonical_team_name(old)
        if new == old:
            return m.group(0)
        changed[old] = changed.get(old, 0) + 1
        escaped = "\\u" in literal   # keep the file's escaping style
        return m.group(1) + json.dumps(new, ensure_ascii=escaped)

    return _TEAM_VALUE.sub(sub, text), changed


def canonical_filename(name: str) -> str:
    """Put the years of a ``comp-YYYY-YYYY.json`` name in ascending order
    (``top14-2011-2010.json`` holds the 2010-2011 season)."""
    m = _SEASON_FILE.match(name)
    if m and int(m.group("b")) < int(m.group("a")):
        return f"{m.group('comp')}-{m.group('b')}-{m.group('a')}{m.group('ext')}"
    return name


def normalise_directory(directory: Path, check: bool = False) -> Dict[str, dict]:
    """Make every ``*.json`` in ``directory`` canonical.

    Returns {filename: {"renamed_to": str | None, "teams": {old: count}}} for
    files that needed changes. With ``check`` nothing is written.
    """
    report: Dict[str, dict] = {}
    for path in sorted(Path(directory).glob("*.json")):
        text = path.read_text()
        new_text, changed = rewrite_team_names(text)
        target = canonical_filename(path.name)
        if not changed and target == path.name:
            continue
        report[path.name] = {"renamed_to": target if target != path.name else None, "teams": changed}
        if check:
            continue
        if target != path.name and (path.parent / target).exists():
            raise FileExistsError(f"cannot rename {path.name}: {target} already exists")
        if changed:
            path.write_text(new_text)
        if target != path.name:
            path.rename(path.parent / target)
    return report
