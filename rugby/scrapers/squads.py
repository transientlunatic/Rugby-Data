"""
Scrape rugby squad information from Wikipedia squad pages.

Fetches squad listings from Wikipedia pages like:
- 2026 Six Nations Championship squads
- 2024 Rugby Championship squads
- 2023 Rugby World Cup squads

Parses wikitext to extract player information including:
- Name, position, age, caps, club
"""

import requests
import json
import re
from typing import Dict, List, Optional
from pathlib import Path

# User agent for Wikipedia API
HEADERS = {'User-Agent': 'RugbyDataBot/1.0 (Rugby-Data scraper)'}

# Position abbreviation mapping
POSITION_MAP = {
    'HK': 'Hooker',
    'PR': 'Prop',
    'LK': 'Lock',
    'BR': 'Back Row',
    'SH': 'Scrum-half',
    'FH': 'Fly-half',
    'CE': 'Centre',
    'WG': 'Wing',
    'FB': 'Fullback',
}


def get_page_title(year: int, tournament: str) -> str:
    """Generate the Wikipedia page title for squad pages."""
    if "Six Nations" in tournament:
        return f"{year}_Six_Nations_Championship_squads"
    elif "Rugby Championship" in tournament:
        return f"{year}_Rugby_Championship_squads"
    elif "Rugby World Cup" in tournament or "RWC" in tournament:
        return f"{year}_Rugby_World_Cup_squads"
    elif "British" in tournament or "Lions" in tournament:
        return f"{year}_British_&_Irish_Lions_tour_squads"
    else:
        return f"{year}_{tournament.replace(' ', '_')}_squads"


def fetch_wikitext(page_title: str) -> Optional[str]:
    """Fetch raw wikitext from Wikipedia API."""
    api_url = "https://en.wikipedia.org/w/api.php"
    params = {
        'action': 'parse',
        'page': page_title,
        'prop': 'wikitext',
        'format': 'json'
    }

    try:
        response = requests.get(api_url, params=params, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()

        if 'parse' in data and 'wikitext' in data['parse']:
            return data['parse']['wikitext']['*']
        elif 'error' in data:
            print(f"Wikipedia API error: {data['error'].get('info', 'Unknown error')}")
            return None
        else:
            print(f"Unexpected response format: {data}")
            return None

    except requests.RequestException as e:
        print(f"Error fetching page '{page_title}': {e}")
        return None


def extract_player_from_template(template_text: str) -> Optional[Dict]:
    """Extract player information from a {{nat rs player}} template."""
    player = {}

    pos_match = re.search(r'\|pos=([A-Z]{2,3})', template_text)
    if pos_match:
        pos_abbr = pos_match.group(1)
        player['position'] = POSITION_MAP.get(pos_abbr, pos_abbr)
        player['position_abbr'] = pos_abbr

    name_match = re.search(r'\|name=\{\{sortname\|([^|]+)\|([^|}]+)', template_text)
    if name_match:
        first_name = name_match.group(1).strip()
        last_name = name_match.group(2).strip()
        player['name'] = f"{first_name} {last_name}"
        player['first_name'] = first_name
        player['last_name'] = last_name

    player['captain'] = '([[Captain' in template_text or '(c)' in template_text

    caps_match = re.search(r'\|caps=(\d+)', template_text)
    if caps_match:
        player['caps'] = int(caps_match.group(1))
    else:
        player['caps'] = 0

    club_match = re.search(r'\|club=\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', template_text)
    if club_match:
        player['club'] = club_match.group(2) if club_match.group(2) else club_match.group(1)
        player['club'] = player['club'].strip()

    clubnat_match = re.search(r'\|clubnat=([A-Z]{3})', template_text)
    if clubnat_match:
        player['club_country'] = clubnat_match.group(1)

    age_match = re.search(r'\{\{[Bb]irth date and age2?\|(\d{4})\|(\d{1,2})\|(\d{1,2})', template_text)
    if age_match:
        try:
            if 'age2' in template_text:
                ref_date_match = re.search(
                    r'\{\{Birth date and age2\|(\d{4})\|(\d{1,2})\|(\d{1,2})\|df=[yn]es?\}\}\|(\d{4})\|(\d{1,2})\|(\d{1,2})',
                    template_text
                )
                if ref_date_match:
                    birth_year = ref_date_match.group(4)
                    birth_month = ref_date_match.group(5)
                    birth_day = ref_date_match.group(6)
                else:
                    alt_match = re.search(r'\|(\d{4})\|(\d{1,2})\|(\d{1,2})\|df=[yn]', template_text)
                    if alt_match:
                        birth_year = alt_match.group(1)
                        birth_month = alt_match.group(2)
                        birth_day = alt_match.group(3)
                    else:
                        birth_year = age_match.group(1)
                        birth_month = age_match.group(2)
                        birth_day = age_match.group(3)
            else:
                birth_year = age_match.group(1)
                birth_month = age_match.group(2)
                birth_day = age_match.group(3)

            player['birth_date'] = f"{birth_year}-{birth_month.zfill(2)}-{birth_day.zfill(2)}"
        except Exception:
            pass

    return player if 'name' in player else None


def parse_squads_from_wikitext(wikitext: str) -> Dict[str, Dict]:
    """Parse all team squads from wikitext."""
    squads = {}

    team_sections = re.split(r'\n==([^=]+)==\n', wikitext)

    for i in range(1, len(team_sections), 2):
        team_name = team_sections[i].strip()
        section_content = team_sections[i + 1] if i + 1 < len(team_sections) else ""

        if any(skip in team_name.lower() for skip in ['call-up', 'reference', 'external', 'see also', 'note']):
            continue

        player_templates = []
        for match in re.finditer(r'\{\{nat rs player\|', section_content):
            start = match.start()
            brace_count = 2
            pos = match.end()
            while pos < len(section_content) and brace_count > 0:
                if section_content[pos:pos+2] == '{{':
                    brace_count += 2
                    pos += 2
                elif section_content[pos:pos+2] == '}}':
                    brace_count -= 2
                    pos += 2
                else:
                    pos += 1

            if brace_count == 0:
                player_templates.append(section_content[start:pos])

        players = []
        for template in player_templates:
            player = extract_player_from_template(template)
            if player:
                players.append(player)

        if players:
            coach_match = re.search(
                r"'''Head [Cc]oach[^:]*:?[^[]*\[\[([^\]|]+)(?:\|([^\]]+))?\]\]",
                section_content
            )
            coach = None
            if coach_match:
                coach = coach_match.group(2) if coach_match.group(2) else coach_match.group(1)

            squads[team_name] = {
                'team': team_name,
                'head_coach': coach,
                'players': players,
                'squad_size': len(players)
            }

    return squads


def save_squads(squads: Dict, output_file: str, output_format: str = 'json'):
    """Save squad data to file."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_format == 'json':
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(squads, f, indent=2, ensure_ascii=False)

    elif output_format == 'csv':
        import csv

        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            fieldnames = [
                'team', 'name', 'first_name', 'last_name', 'position', 'position_abbr',
                'caps', 'club', 'club_country', 'birth_date', 'captain', 'head_coach'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()

            for team_name, team_data in squads.items():
                for player in team_data['players']:
                    row = {
                        'team': team_name,
                        'head_coach': team_data.get('head_coach', ''),
                        **player
                    }
                    writer.writerow(row)


def scrape_squads(year: int, tournament: str, page_title: str = None,
                  output_file: str = None, output_format: str = 'json',
                  verbose: bool = False) -> Optional[Dict]:
    """
    Scrape squad data for a tournament.

    Returns the squads dict, and optionally saves to file.
    """
    if page_title:
        title = page_title
    else:
        title = get_page_title(year, tournament)

    wikitext = fetch_wikitext(title)
    if not wikitext:
        return None

    squads = parse_squads_from_wikitext(wikitext)
    if not squads:
        return None

    if output_file:
        save_squads(squads, output_file, output_format)

    return squads
