#!/usr/bin/env python3
"""
Six Nations Wikipedia Scraper - Wikitext Parser

Fetches and parses rugby championship data from Wikipedia using raw wikitext.
Supports both modern and historical formats:

- Modern (2000+): Rugbybox templates with lineup tables
- Historical (pre-2000): Plain text lineups in <small> tags

This is much more reliable than parsing rendered HTML because it works directly
with the structured wikitext source.

Usage:
    # Modern format
    result = scrape_championship(2025, "Six Nations Championship")
    
    # Historical format  
    result = scrape_championship(1904, "Home Nations Championship")

See SCRAPER_USAGE.md for detailed examples and data structures.
"""

import requests
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

HEADERS = {'User-Agent': 'RugbyDataBot/1.0'}

def get_wikipedia_page_title(year: int, championship_name: str) -> str:
    """
    Map competition name and year to the correct Wikipedia page title.
    
    Handles different competitions that have different naming conventions.
    
    Args:
        year: Championship year
        championship_name: Championship name (e.g., "Six Nations Championship", "Super Rugby")
        
    Returns:
        The Wikipedia page title to search for
    """
    # Super Rugby has different page title formats by era
    if "Super Rugby" in championship_name:
        if year >= 2021:
            return f"List of {year} Super Rugby Pacific matches"
        elif year >= 2016:  # 2016-2020 use "List of" format
            return f"List of {year} Super Rugby matches"
        elif year >= 2011:
            return f"{year} Super Rugby season"
        elif year >= 2006:
            return f"{year} Super 14 season"
        else:
            return f"{year} Super 12 season"
    
    # Mid-year/Summer rugby union tests (summer internationals)
    # These can have various formats: "mid-year", "June", "July", "World Cup warm-up", etc.
    if any(term in championship_name.lower() for term in ["mid-year", "mid year", "summer", "june", "july"]):
        # World Cup years (every 4 years from 2007) use "warm-up matches" format
        if year in [2007, 2011, 2015, 2019, 2023, 2027]:
            return f"{year} Rugby World Cup warm-up matches"
        # Modern format (2022+)
        elif year >= 2022:
            return f"{year} mid-year rugby union tests"
        # Historical format (2004-2021)
        elif year >= 2004:
            # For non-World Cup years, try June/July first
            # These will be tried in order by the fetch function if needed
            return f"{year} June rugby union tests"
    
    # Default: "{year} {championship_name}"
    return f"{year} {championship_name}"

def get_championship_page_wikitext(year: int = 2025, championship_name: str = "Six Nations Championship", 
                                    page_title: Optional[str] = None) -> Optional[str]:
    """
    Fetch raw wikitext for a championship page.
    
    Args:
        year: Championship year
        championship_name: Championship name (e.g., "Six Nations Championship", "Home Nations Championship")
        page_title: Optional custom page title. If not provided, will be derived from championship_name and year.
    """
    
    # Determine the page titles to fetch (can try multiple for some competitions)
    if page_title is None:
        page_titles = [get_wikipedia_page_title(year, championship_name)]
        
        # For summer internationals, also try alternative formats
        if any(term in championship_name.lower() for term in ["mid-year", "mid year", "summer", "june", "july"]):
            # Special case: 2019 uses "internationals" instead of "tests" (non-World Cup)
            if year == 2019:
                page_titles.append(f"{year} mid-year rugby union internationals")
            # For pre-2022 non-World Cup years, also try July format
            elif year < 2022 and year not in [2007, 2011, 2015, 2019]:
                page_titles.append(f"{year} July rugby union tests")
    else:
        page_titles = [page_title]
    
    url = f'https://en.wikipedia.org/w/api.php'
    
    for page_title in page_titles:
        params = {
            'action': 'query',
            'titles': page_title,
            'prop': 'revisions',
            'rvprop': 'content',
            'format': 'json',
            'redirects': 1,  # Follow redirects automatically
        }
        
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            pages = data['query']['pages']
            page_data = list(pages.values())[0]
            
            if 'revisions' in page_data:
                return page_data['revisions'][0]['*']
        
        except Exception as e:
            # Try next page title
            continue
    
    # If all attempts failed
    return None

def get_championship_page_html(year: int, championship_name: str, page_title: Optional[str] = None) -> Optional[str]:
    """Fetch parsed HTML for a championship page via MediaWiki parse API."""
    if page_title is None:
        page_title = get_wikipedia_page_title(year, championship_name)
    url = 'https://en.wikipedia.org/w/api.php'
    params = {
        'action': 'parse',
        'page': page_title,
        'prop': 'text',
        'format': 'json',
        'redirects': 1,
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        data = resp.json()
        html = data.get('parse', {}).get('text', {}).get('*')
        return html
    except Exception:
        return None

def _extract_matches_from_parsed_html(html: str) -> List[Dict[str, Any]]:
    """Extract match data from parsed HTML blocks (vevent summaries)."""
    matches: List[Dict[str, Any]] = []
    if not html:
        return matches
    # Each match block is a div with class="vevent summary"
    for block in re.findall(r'<div[^>]*class="vevent summary"[^>]*>(.*?)</div>', html, flags=re.DOTALL | re.IGNORECASE):
        # Extract team names (two occurrences of <span class="fn org">...<a>Team</a>)
        teams = re.findall(r'<span[^>]*class="fn org"[^>]*>.*?<a[^>]*>([^<]+)</a>', block, flags=re.DOTALL | re.IGNORECASE)
        if len(teams) < 2:
            continue
        home_team, away_team = teams[0].strip(), teams[1].strip()
        # Extract score from the middle cell
        score_match = re.search(r'>\s*(\d+)\s*[–—-]\s*(\d+)\s*<', block)
        if not score_match:
            continue
        home_score = int(score_match.group(1))
        away_score = int(score_match.group(2))
        # Extract date from the date column preceding row
        date_match = re.search(r'<td[^>]*>\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})\s*</td>', block)
        iso_date = None
        if date_match:
            iso_date = parse_date_string(date_match.group(1))
        # Extract venue if present
        venue_match = re.search(r'<span[^>]*class="location"[^>]*>\s*(.*?)\s*</span>', block, flags=re.DOTALL | re.IGNORECASE)
        venue = None
        if venue_match:
            # Strip HTML tags from venue
            venue_raw = re.sub(r'<[^>]+>', '', venue_match.group(1))
            venue = venue_raw.strip()
        match_obj = {
            'date': iso_date,
            'home': {'team': home_team, 'score': home_score},
            'away': {'team': away_team, 'score': away_score},
        }
        if venue:
            match_obj['stadium'] = venue
        matches.append(match_obj)
    return matches

def extract_match_sections_from_text(wikitext: str) -> List[Tuple[str, str, str]]:
    """
    Extract match sections from the wikitext for historical format pages.
    
    Handles multiple page structures:
    1. Modern (2010+): == Matches == section with === Match Title === subsections
    2. Mid-era (2003-2009): == Results == section with === Round 1 === subsections
    
    Within each section, can have one or more {{Rugbybox}} templates.
    
    Returns:
        List of (match_id, rugbybox_text, lineup_text)
    """
    matches = []
    
    # Try modern format first: Find the "Matches" section with level-3 subsections
    for section_name in ["Matches", "The matches"]:
        for pattern in [f"== {section_name} ==", f"=={section_name}==", f"== {section_name}=="]:
            section_start = wikitext.find(pattern)
            if section_start != -1:
                section_text = wikitext[section_start:]
                # Use level-3 headings (=== ===)
                match_heading_pattern = r'===\s*([^=]+?)\s*===\s*\n(.*?)(?=\n===|\Z)'
                heading_matches = list(re.finditer(match_heading_pattern, section_text, re.DOTALL))
                if heading_matches:
                    return _extract_rugbyboxes_from_sections(heading_matches)
    
    # Try older format: Look for "Results"/"Fixtures"/"International matches" section with "Round X" subsections at level-3
    for section_name in ["Results", "Fixtures", "Matches", "Regular season", "International matches"]:
        for pattern in [f"== {section_name} ==", f"=={section_name}==", f"== {section_name}=="]:
            section_start = wikitext.find(pattern)
            if section_start != -1:
                section_text = wikitext[section_start:]
                # Look for "Round X", "Week X", or special sections like "Rescheduled match" at level-3
                round_pattern = r'===\s*((?:Round|Week)\s*\d+|Rescheduled match)\s*===\s*\n(.*?)(?=\n===|\Z)'
                round_matches = list(re.finditer(round_pattern, section_text, re.DOTALL))
                if round_matches:
                    matches = _extract_rugbyboxes_from_sections(round_matches)
                    
                    # If this is "Regular season", also check for Finals section with level-3 subsections
                    if section_name == "Regular season" and matches:
                        finals_start = wikitext.find("==Finals==", section_start + len(pattern))
                        if finals_start == -1:
                            finals_start = wikitext.find("== Finals ==", section_start + len(pattern))
                        
                        if finals_start != -1:
                            finals_text = wikitext[finals_start:]
                            # Look for Finals with level-3 subsections (Semifinals, Final, Qualifiers)
                            finals_pattern = r'===\s*((?:Qualifier|Qualifiers|Semifinal|Semi-final|Semifinals?|Semi-finals?|Final|Grand Final))\s*===\s*\n(.*?)(?=\n===|\Z)'
                            finals_matches = list(re.finditer(finals_pattern, finals_text, re.DOTALL | re.IGNORECASE))
                            if finals_matches:
                                finals_data = _extract_rugbyboxes_from_sections(finals_matches)
                                if finals_data:
                                    matches.extend(finals_data)
                    
                    return matches
                
                # If no subsections, extract all rugbyboxes directly from the section
                # This handles pages like 2002 that have rugbyboxes directly under ==Results==
                # Find the section end (next == heading or end of text)
                section_end_match = re.search(r'\n==(?!=)', section_text[len(pattern):])
                if section_end_match:
                    section_content = section_text[len(pattern):len(pattern) + section_end_match.start()]
                else:
                    section_content = section_text[len(pattern):]
                
                # Create a fake heading match to reuse the extraction logic
                class FakeMatch:
                    def group(self, n):
                        if n == 1:
                            return section_name
                        elif n == 2:
                            return section_content
                
                rugbyboxes = _extract_rugbyboxes_from_sections([FakeMatch()])
                # Only return if we got a reasonable number of matches (>5)
                # This avoids returning early on summary sections with only 1-2 matches
                if rugbyboxes and len(rugbyboxes) > 5:
                    return rugbyboxes
                # If we got very few matches and found Results in the section name,
                # it's likely a summary, so continue trying other patterns
                if rugbyboxes and len(rugbyboxes) <= 5 and "Results" in section_name:
                    continue
                elif rugbyboxes:
                    return rugbyboxes
    
    # Try Super Rugby format: Look for direct level-2 "Round X" headers (no parent Results section)
    # This handles 2013, 2014, 2015, etc.
    # Pattern: ==RoundX== or == Round X == (flexible spacing)
    round_pattern_level2 = r'==(Round|Week)\s*(\d+)==\s*\n(.*?)(?=\n==|\Z)'
    round_matches = list(re.finditer(round_pattern_level2, wikitext, re.DOTALL | re.IGNORECASE))
    if round_matches:
        # Convert regex matches to the format expected by _extract_rugbyboxes_from_sections
        class RoundMatch:
            def __init__(self, text):
                self._text = text
            def group(self, n):
                if n == 1:
                    return self._text[0]  # Round 1, Round 2, etc.
                else:
                    return self._text[1]  # Content
        
        matches_to_extract = []
        for m in round_matches:
            header_text = f"{m.group(1)} {m.group(2)}"  # e.g., "Round 1"
            content = m.group(3)
            matches_to_extract.append((header_text, content))
        
        result_matches = _extract_rugbyboxes_from_sections([RoundMatch((h, c)) for h, c in matches_to_extract])
        if result_matches:
            return result_matches
    
    # If no Round sections found, try Finals, Qualifiers, etc.
    finals_pattern = r'==(Qualifiers|Semi-finals?|Finals?|Promotion/relegation)[\w\s]*==\s*\n(.*?)(?=\n==|\Z)'
    finals_matches = list(re.finditer(finals_pattern, wikitext, re.DOTALL | re.IGNORECASE))
    if finals_matches:
        class FinalsMatch:
            def __init__(self, text):
                self._text = text
            def group(self, n):
                if n == 1:
                    return self._text[0]
                else:
                    return self._text[1]
        
        result_matches = _extract_rugbyboxes_from_sections([FinalsMatch((m.group(1), m.group(2))) for m in finals_matches])
        if result_matches:
            return result_matches
    
    # Final fallback: extract all rugbybox templates from the entire page
    # This handles pages with unconventional structures (e.g., 2007 World Cup warm-ups with date sections)
    all_rugbyboxes = extract_all_rugbyboxes(wikitext)
    if all_rugbyboxes:
        return all_rugbyboxes
    
    return matches


def _extract_rugbyboxes_from_sections(heading_matches) -> List[Tuple[str, str, str]]:
    """
    Helper function to extract all rugbyboxes from a list of section matches.
    Each section can contain one or more rugbybox templates.
    
    Args:
        heading_matches: List of regex match objects with groups (heading, content)
    
    Returns:
        List of (match_id, rugbybox_text, lineup_text) tuples
    """
    matches = []
    
    for heading_match in heading_matches:
        heading = heading_match.group(1).strip()
        match_content = heading_match.group(2)


def extract_all_rugbyboxes(wikitext: str) -> List[Tuple[str, str, str]]:
    """
    Extract all rugbybox templates from wikitext, regardless of structure.
    This is a fallback for pages with unconventional formats.
    
    Returns:
        List of (match_id, rugbybox_text, lineup_text) tuples
    """
    matches = []
    
    # Find all starting positions of rugbybox templates
    starts = []
    for match in re.finditer(r'{{(?:rugbybox|#invoke:rugby\s+box\|main)', wikitext, re.IGNORECASE):
        starts.append(match.start())
    
    # For each start, find the matching closing braces
    for i, start in enumerate(starts, 1):
        # Count braces to find the matching closing }}
        brace_count = 0
        pos = start
        template_end = None
        
        while pos < len(wikitext):
            if wikitext[pos:pos+2] == '{{':
                brace_count += 1
                pos += 2
            elif wikitext[pos:pos+2] == '}}':
                brace_count -= 1
                if brace_count == 0:
                    template_end = pos + 2
                    break
                pos += 2
            else:
                pos += 1
        
        if template_end is None:
            continue  # Couldn't find matching closing braces
        
        rugbybox = wikitext[start:template_end]
        match_id = f"Match {i}"
        
        # Try to find any lineup tables after this rugbybox
        next_start = starts[starts.index(start) + 1] if starts.index(start) + 1 < len(starts) else len(wikitext)
        next_section = wikitext.find('\n==', template_end)
        
        end_pos = len(wikitext)
        if next_section != -1:
            end_pos = min(next_start, next_section)
        else:
            end_pos = next_start
        
        lineups_text = wikitext[template_end:end_pos]
        matches.append((match_id, rugbybox, lineups_text))
    
    return matches


def _extract_rugbyboxes_from_sections(heading_matches) -> List[Tuple[str, str, str]]:
    """
    Helper function to extract all rugbyboxes from a list of section matches.
    Each section can contain one or more rugbybox templates.
    
    Args:
        heading_matches: List of regex match objects with groups (heading, content)
    
    Returns:
        List of (match_id, rugbybox_text, lineup_text) tuples
    """
    matches = []
    
    for heading_match in heading_matches:
        heading = heading_match.group(1).strip()
        match_content = heading_match.group(2)
        
        # Extract ALL rugbyboxes from this section
        # For modern pages (e.g., 2020+): one heading = one match = one rugbybox
        # For older pages (e.g., 2003): one heading = one round = multiple rugbyboxes
        rugbyboxes_found = []
        search_pos = 0
        
        while search_pos < len(match_content):
            rugbybox_start = match_content.find('{{', search_pos)
            if rugbybox_start == -1:
                break
            
            # Count braces to find the matching closing }}
            brace_count = 0
            rugbybox_end = -1
            i = rugbybox_start
            while i < len(match_content) - 1:
                if match_content[i:i+2] == '{{':
                    brace_count += 1
                    i += 2
                elif match_content[i:i+2] == '}}':
                    brace_count -= 1
                    i += 2
                    if brace_count == 0:
                        rugbybox_end = i
                        break
                else:
                    i += 1
            
            if rugbybox_end == -1:
                break
            
            rugbybox_text = match_content[rugbybox_start:rugbybox_end]
            
            # Check if this is actually a Rugbybox template (not some other template)
            if rugbybox_text.lower().startswith('{{rugbybox'):
                rugbyboxes_found.append((rugbybox_start, rugbybox_end, rugbybox_text))
            
            search_pos = rugbybox_end
        
        # For each rugbybox found, extract its lineup text
        for idx, (rb_start, rb_end, rugbybox_text) in enumerate(rugbyboxes_found):
            # For lineup text, use everything after this rugbybox until the next rugbybox (or end)
            if idx < len(rugbyboxes_found) - 1:
                next_rb_start = rugbyboxes_found[idx + 1][0]
                lineup_text = match_content[rb_end:next_rb_start]
            else:
                lineup_text = match_content[rb_end:]
            
            # Generate a match ID from the heading
            if len(rugbyboxes_found) == 1:
                match_id = heading
            else:
                match_id = f"{heading} - Match {idx + 1}"
            
            matches.append((match_id, rugbybox_text, lineup_text))
    
    return matches


def extract_rugbybox_templates(wikitext: str) -> List[Tuple[str, str, str]]:
    """
    Extract rugbybox + lineup tables for each match.
    
    Supports multiple formats:
    1. Modern Six Nations: {{rugbybox}} with |id = Team1 v Team2
    2. Super Rugby: {{rugbybox collapsible}} with |home = Team1 and |away = Team2
    3. Historical: === Match === sections with {{Rugbybox}} and <small> text lineups
    """
    
    matches = []
    
    # First, try the historical "== The matches ==" format
    historical_matches = extract_match_sections_from_text(wikitext)
    if historical_matches:
        return historical_matches
    
    # Otherwise, use the modern format with lineup tables
    matches = []
    
    # Find all rugbybox templates - flexible regex to handle both Six Nations and Super Rugby formats
    # Pattern: {{ rugbybox ... }} (handles both "rugbybox" and "rugbybox collapsible")
    # Also handle {{#invoke:rugby box|main ... }} format (2017 Super Rugby)
    rugbybox_pattern = r'(?:{{(?:rugbybox|#invoke:rugby\s+box\|main)[^}]*\n(.*?)\n}})'
    
    for rugbybox_match in re.finditer(rugbybox_pattern, wikitext, re.DOTALL):
        rugbybox = rugbybox_match.group(0)  # Full template
        rugbybox_end = rugbybox_match.end()
        
        # Parse parameters from the rugbybox
        # Extract top-level parameters only (not ones nested in other parameters)
        # This regex matches |key = value, being careful about multi-line values
        params = _parse_rugbybox_params(rugbybox)
        
        # Extract match ID or team names
        # Try Six Nations format first: |id = Team1 v Team2
        if 'id' in params:
            match_id = params['id']
        elif 'home' in params and 'away' in params:
            # Super Rugby format: |home = Team1 and |away = Team2
            home = params['home'].strip()
            away = params['away'].strip()
            
            # Handle {{Rut|TeamName}} format (2024 Super Rugby Pacific)
            rut_match_home = re.search(r'{{Rut\|([^}]+)}}', home)
            if rut_match_home:
                home = rut_match_home.group(1).strip()
            else:
                # Handle {{flagicon|...}} format (1996-2023)
                home = re.sub(r'{{flagicon\|[^}]+}}\s*', '', home).strip()
            
            rut_match_away = re.search(r'{{Rut\|([^}]+)}}', away)
            if rut_match_away:
                away = rut_match_away.group(1).strip()
            else:
                # Handle {{flagicon|...}} format (1996-2023)
                away = re.sub(r'{{flagicon\|[^}]+}}\s*', '', away).strip()
            
            match_id = f"{home} v {away}"
        else:
            continue  # Can't find team names
        
        # After rugbybox, find the lineup tables (if they exist)
        # The pattern is: after }} comes lineups which start with {|
        # But modern "List of matches" pages may not have lineup tables
        
        # Find where the lineups section starts (first {| after rugbybox)
        remaining_text = wikitext[rugbybox_end:]
        
        lineup_start = remaining_text.find('{|')
        lineups = None
        
        if lineup_start != -1:
            # Find the closing |} of the outer table
            # The outer table has {| at the beginning, so we need to find its matching |}
            # To find it: count all {| and |} and match them properly
            # For simplicity: find the LAST |} before the next ==  or next {{rugbybox
            
            # Find next section boundary
            next_section = remaining_text.find('\n==', lineup_start)  # Next == heading
            next_match = remaining_text.find('{{rugbybox', lineup_start + 10)  # Next rugbybox
            
            # Take whichever comes first
            end_pos = len(remaining_text)
            if next_section > 0:
                end_pos = min(end_pos, next_section)
            if next_match > 0:
                end_pos = min(end_pos, next_match)
            
            # Get the lineup section up to end_pos
            lineup_section = remaining_text[:end_pos]
            # Find the LAST |} in this section
            last_close = lineup_section.rfind('|}')
            if last_close != -1:
                lineups = lineup_section[:last_close + 2]  # Include the |}
        
        # Add match even if no lineups (modern Super Rugby pages don't have lineups)
        matches.append((match_id, rugbybox, lineups))
    
    return matches

def _parse_rugbybox_params(rugbybox_text: str) -> Dict[str, str]:
    """
    Parse top-level parameters from a rugbybox template.
    
    Properly handles multi-line parameter values by tracking parameter boundaries.
    """
    params = {}
    
    # Remove the opening {{ and closing }}
    content = rugbybox_text[2:-2].strip()
    
    # Split by lines and parse line by line
    lines = content.split('\n')
    current_key = None
    current_value = []
    
    for line in lines:
        # Check if this line starts a new parameter (starts with |)
        if line.strip().startswith('|') and '=' in line:
            # Save previous parameter if any
            if current_key:
                params[current_key] = '\n'.join(current_value)
            
            # Parse new parameter
            line = line.strip()[1:]  # Remove leading |
            key, value = line.split('=', 1)
            current_key = key.strip()
            current_value = [value.strip()]
        elif current_key:
            # Continuation of previous parameter value
            current_value.append(line)
    
    # Don't forget the last parameter
    if current_key:
        params[current_key] = '\n'.join(current_value)
    
    return params


def clean_team_name(team_str: str) -> str:
    """
    Clean team name by removing wiki syntax and formatting.
    
    Handles:
    - Wiki links: [[Team Name]] or [[Team Name|Display Name]]
    - Templates: {{flagicon|...}}, {{Rut|...}}, {{ru|...}}, {{ru-rt|...}}
    - Extra whitespace
    """
    if not team_str:
        return ""
    
    # Handle {{ru|CODE}} or {{ru-rt|CODE}} format (Rugby World Cup pages)
    # Common country codes used in World Cup pages
    rugby_codes = {
        'ARG': 'Argentina', 'AUS': 'Australia', 'ENG': 'England', 'FIJ': 'Fiji',
        'FRA': 'France', 'GEO': 'Georgia', 'IRE': 'Ireland', 'ITA': 'Italy',
        'JPN': 'Japan', 'NAM': 'Namibia', 'NZL': 'New Zealand', 'ROM': 'Romania',
        'RSA': 'South Africa', 'SAM': 'Samoa', 'SCO': 'Scotland', 'TON': 'Tonga',
        'URU': 'Uruguay', 'USA': 'United States', 'WAL': 'Wales',
        'CAN': 'Canada', 'CHI': 'Chile', 'CIV': "Ivory Coast", 'ESP': 'Spain',
        'HKG': 'Hong Kong', 'KOR': 'South Korea', 'NED': 'Netherlands',
        'POR': 'Portugal', 'RUS': 'Russia', 'ZIM': 'Zimbabwe'
    }
    
    ru_match = re.search(r'{{[Rr]u(?:-rt)?\|([A-Z]{3})}}', team_str)
    if ru_match:
        code = ru_match.group(1)
        if code in rugby_codes:
            return rugby_codes[code]
        # If code not in our mapping, return the code itself
        return code
    
    # Handle [[Team Name|Display Name]] format - extract display name
    match = re.search(r'\[\[([^\]]+)\|([^\]]+)\]\]', team_str)
    if match:
        team_str = match.group(2)  # Use the display name part
    
    # Handle [[Team Name]] format - extract team name
    team_str = re.sub(r'\[\[([^\]]+)\]\]', r'\1', team_str)
    
    # Handle {{Rut|TeamName}} format (2024 Super Rugby Pacific)
    rut_match = re.search(r'{{Rut\|([^}]+)}}', team_str)
    if rut_match:
        team_str = rut_match.group(1).strip()
    
    # Handle {{flagicon|...}} format (1996-2023)
    team_str = re.sub(r'{{flagicon\|[^}]+}}\s*', '', team_str).strip()
    
    # Remove any remaining wiki syntax
    team_str = re.sub(r'{{[^}]+}}', '', team_str)
    team_str = re.sub(r'\[\[[^\]]+\]\]', '', team_str)
    
    return team_str.strip()

def parse_rugbybox(template_str: str, match_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Parse a single rugbybox template.
    
    Args:
        template_str: The rugbybox template wikitext
        match_id: Optional match ID from section header (for historical formats)
    """
    
    match_data = {}
    
    # Use the proper parameter parsing function
    params = _parse_rugbybox_params(template_str)
    
    # Parse teams - try multiple formats:
    # 1. Six Nations format: |id = Team1 v Team2
    # 2. Super Rugby format: |home = Team1 and |away = Team2
    # 3. Early Super Rugby format: |team1 = Team1 and |team2 = Team2
    team_source = params.get('id', match_id)
    teams_found = False
    
    if team_source:
        teams = re.split(r'\s+v(?:s?)\.?\s+', team_source)
        if len(teams) == 2:
            match_data['home_team'] = clean_team_name(teams[0])
            match_data['away_team'] = clean_team_name(teams[1])
            teams_found = True
    
    # Try Super Rugby format with |home and |away if we haven't found teams yet
    if not teams_found and 'home' in params and 'away' in params:
        home = clean_team_name(params['home'])
        away = clean_team_name(params['away'])
        
        match_data['home_team'] = home
        match_data['away_team'] = away
    
    # Try older format with |team1 and |team2 (used in some 1996-2005 seasons)
    if not teams_found and 'team1' in params and 'team2' in params:
        home = clean_team_name(params['team1'])
        away = clean_team_name(params['team2'])
        
        match_data['home_team'] = home
        match_data['away_team'] = away
    
    # Parse date/time
    if 'date' in params:
        match_data['date'] = parse_date_string(params['date'])
    
    if 'time' in params:
        time_match = re.search(r'(\d{1,2}):(\d{2})', params['time'])
        if time_match:
            match_data['time'] = f"{time_match.group(1)}:{time_match.group(2)}"
    
    # Parse score - for Super Rugby, it may be in |score parameter instead of separate params
    if 'score' in params:
        # Handle HTML entities like &ndash;
        score_text = params['score'].replace('&ndash;', '–').replace('&mdash;', '—')
        score_match = re.search(r'(\d+)\s*[–—-]\s*(\d+)', score_text)
        if score_match:
            match_data['home_score'] = int(score_match.group(1))
            match_data['away_score'] = int(score_match.group(2))
    
    # Parse scoring
    match_data['home_tries'] = parse_try_scorers(params.get('try1', ''))
    match_data['away_tries'] = parse_try_scorers(params.get('try2', ''))
    match_data['home_conversions'] = parse_conversion_line(params.get('con1', ''))
    match_data['away_conversions'] = parse_conversion_line(params.get('con2', ''))
    match_data['home_penalties'] = parse_penalty_line(params.get('pen1', ''))
    match_data['away_penalties'] = parse_penalty_line(params.get('pen2', ''))
    
    # Parse venue/attendance/referee
    if 'stadium' in params:
        venues = re.findall(r'\[\[([^\]]+)\]\]', params['stadium'])
        if venues:
            match_data['venue'] = ', '.join(venues)
    
    if 'attendance' in params:
        att_match = re.search(r'([\d,]+)', params['attendance'])
        if att_match:
            try:
                match_data['attendance'] = int(att_match.group(1).replace(',', ''))
            except ValueError:
                pass
    
    if 'referee' in params:
        ref_match = re.search(r'\[\[([^\]|]+)', params['referee'])
        if ref_match:
            match_data['referee'] = ref_match.group(1)
    
    return match_data

def parse_date_string(date_str: str) -> Optional[str]:
    """Parse date string like '8 March 2025' to ISO format."""
    
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    
    date_match = re.search(r'(\d+)\s+(\w+)\s+(\d{4})', date_str)
    if not date_match:
        return None
    
    day, month_str, year = date_match.groups()
    month_num = next((i + 1 for i, m in enumerate(months) if m.lower() == month_str.lower()), None)
    
    if not month_num:
        return None
    
    try:
        date_obj = datetime(int(year), month_num, int(day))
        return date_obj.isoformat().split('T')[0]
    except ValueError:
        return None

def parse_try_scorers(line: str) -> List[Dict[str, Any]]:
    """Parse try scorers from wikitext."""
    
    tries = []
    
    if not line.strip():
        return tries
    
    entries = re.split(r'<br\s*/?>', line)
    
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        
        player_match = re.search(r'\[\[(?:[^\]|]+\|)?([^\]]+)\]\]', entry)
        if not player_match:
            continue
        
        player_name = player_match.group(1)
        times_section = entry[player_match.end():]
        time_pattern = r'(\d+)(?:\+(\d+))?[\'′]\s*([cm]?)'
        
        for time_match in re.finditer(time_pattern, times_section):
            minutes = int(time_match.group(1))
            seconds = int(time_match.group(2)) if time_match.group(2) else 0
            marker = time_match.group(3)
            
            tries.append({
                'player': player_name,
                'minutes': minutes,
                'seconds': seconds,
                'converted': marker == 'c',
                'missed': marker == 'm',
            })
    
    return tries

def parse_conversion_line(line: str) -> List[Dict[str, Any]]:
    """Parse conversion line from wikitext."""
    
    conversions = []
    
    if not line.strip():
        return conversions
    
    player_match = re.search(r'\[\[(?:[^\]|]+\|)?([^\]]+)\]\]', line)
    if not player_match:
        return conversions
    
    player_name = player_match.group(1)
    
    fraction_match = re.search(r'\((\d+)/(\d+)\)', line)
    successful = int(fraction_match.group(1)) if fraction_match else None
    attempted = int(fraction_match.group(2)) if fraction_match else None
    
    times_section = line[player_match.end():]
    time_pattern = r'(\d+)(?:\+(\d+))?[\'′]'
    
    times = []
    for time_match in re.finditer(time_pattern, times_section):
        minutes = int(time_match.group(1))
        seconds = int(time_match.group(2)) if time_match.group(2) else 0
        times.append({'minutes': minutes, 'seconds': seconds})
    
    if times:
        conversions.append({
            'player': player_name,
            'successful': successful,
            'attempted': attempted,
            'times': times,
        })
    
    return conversions

def parse_penalty_line(line: str) -> List[Dict[str, Any]]:
    """Parse penalty line from wikitext (same format as conversions)."""
    
    return parse_conversion_line(line)

def parse_lineup_text(lineup_text: str, team_name: str = '') -> List[Dict[str, Any]]:
    """
    Parse lineup from plain text format (historical pages).
    
    Format (from <small> tags):
        '''Team:''' [[Player|Display]] ([[Club|Full]]), ... '''capt.'''
        or
        '''Team:''' Player1 (Club), Player2 (Club), ...
    
    Args:
        lineup_text: The plain text containing players
        team_name: Team name (for logging)
        
    Returns:
        List of player dicts (without positions/numbers for historical data)
    """
    players = []
    
    if not lineup_text.strip():
        return players
    
    # Remove the team label at the beginning
    lineup_text = re.sub(r"'''\s*[A-Za-z\s]+:\s*'''", '', lineup_text)
    
    # Split by comma, but respect wikitext link boundaries [[...]]
    def smart_split_by_comma(text):
        """Split by comma, but not inside [[...]] wikitext links"""
        parts = []
        current = []
        i = 0
        
        while i < len(text):
            # Check for start of wikitext link
            if i < len(text) - 1 and text[i:i+2] == '[[':
                # Found link start, find the matching ]]
                current.append('[[')
                i += 2
                while i < len(text):
                    if i < len(text) - 1 and text[i:i+2] == ']]':
                        current.append(']]')
                        i += 2
                        break
                    else:
                        current.append(text[i])
                        i += 1
            elif text[i] == ',' and not any(p == '[' for p in current if p == '['):
                # Found comma outside of links
                parts.append(''.join(current))
                current = []
                i += 1
            else:
                current.append(text[i])
                i += 1
        
        if current:
            parts.append(''.join(current))
        
        return parts
    
    # Use smart split instead of simple split
    parts = smart_split_by_comma(lineup_text)
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Check if captain
        captain = 'capt' in part.lower()
        
        # Remove club links first (in parentheses): ([[Club|Text]]) or (Club)
        part_no_club = re.sub(r'\s*\(\[\[[^\]]+\]\]\)', '', part)
        part_no_club = re.sub(r'\s*\([^)]+\)(?!\])', '', part_no_club)
        
        # Now extract player name from wikitext link format
        # [[Full Name|Display Name]] or just [[Player Name]]
        # Handle newlines that might be inside the link text
        link_match = re.search(r'\[\[(?:[^\|\]]+\|)?([^\]]+)\]\]', part_no_club, re.DOTALL)
        if link_match:
            player_name = link_match.group(1).strip()
            # Clean up any newlines/extra spaces
            player_name = ' '.join(player_name.split())
        else:
            # If no wiki link, just use the text (after removing '''capt.''' etc.)
            player_name = re.sub(r"'''[^']+'''", '', part_no_club).strip()
            
        # Skip if doesn't look like a player name
        if not player_name or len(player_name) < 2:
            continue
        
        players.append({
            'position': '',  # Not available in historical format
            'number': 0,     # Not available
            'player': player_name,
            'captain': captain,
            'events': []
        })
    
    return players


def parse_lineup_table(table_wikitext: str) -> List[Dict[str, Any]]:
    """Parse a lineup table from wikitext."""
    
    lineup = []
    rows = re.split(r'^\s*\|-', table_wikitext, flags=re.MULTILINE)
    
    for row in rows[1:]:  # Skip header
        if row.strip().startswith('!'):
            continue
        
        if 'colspan' in row or "'''" in row.split('\n')[0]:
            if 'Replacements' in row or 'Coach' in row:
                continue
        
        cells = re.split(r'\|\|', row)
        
        if len(cells) < 3:
            continue
        
        position = cells[0].strip().replace('|', '').strip()
        if not position or position.startswith('!'):
            continue
        
        number_str = cells[1].strip().replace("'''", '').strip()
        if not number_str.isdigit():
            continue
        
        number = int(number_str)
        
        player_cell = cells[2].strip()
        player_match = re.search(r'\[\[(?:[^\]|]+\|)?([^\]]+)\]\]', player_cell)
        if not player_match:
            continue
        
        player_name = player_match.group(1)
        
        events = []
        for cell in cells[3:]:
            cell = cell.strip()
            if not cell:
                continue
            
            yel_match = re.search(r'{{yel\|(\d+)}}', cell)
            if yel_match:
                events.append({'type': 'yellow_card', 'minute': int(yel_match.group(1))})
            
            red_match = re.search(r'{{red\|(\d+)}}', cell)
            if red_match:
                events.append({'type': 'red_card', 'minute': int(red_match.group(1))})
            
            suboff_match = re.search(r'{{suboff\|(\d+)}}', cell)
            if suboff_match:
                events.append({'type': 'substitution_off', 'minute': int(suboff_match.group(1))})
            
            subon_match = re.search(r'{{subon\|(\d+)}}', cell)
            if subon_match:
                events.append({'type': 'substitution_on', 'minute': int(subon_match.group(1))})
        
        is_captain = '(c)' in player_cell or '([[Captain' in player_cell
        
        lineup.append({
            'position': position,
            'number': number,
            'player': player_name,
            'captain': is_captain,
            'events': events,
        })
    
    return lineup

def extract_lineups_from_match_section(match_text: str) -> tuple:
    """
    Extract lineups from a match section, handling both table and text formats.
    
    Returns:
        (home_lineup, away_lineup) - both can be from tables or text
    """
    home_lineup = []
    away_lineup = []
    
    # First, try to find structured lineup tables (modern format)
    table_parts = match_text.split('{|')
    
    if len(table_parts) > 1:
        # Find inner tables and collect them all in order
        inner_tables = []
        for part in table_parts[1:]:  # Skip text before the first table
            if '|}' in part:
                table_end_idx = part.index('|}')
                table_content = '{|' + part[:table_end_idx] + '|}'
                inner_tables.append(table_content)
        
        # Filter tables to those that look like player lineup tables, skipping kit/outer layout tables
        def looks_like_lineup_table(tbl: str) -> bool:
            # Heuristics: contains player wikilinks and position/number columns
            if 'Football kit' in tbl:
                return False
            if re.search(r"\|\s*[A-Z]{1,3}\s*\|\|\s*'''+?\d+'''+?\|\|", tbl):
                return True
            if 'FB' in tbl and re.search(r"\[\[(?:[^\]|]+\|)?[^\]]+\]\]", tbl):
                return True
            # Also accept tables that have many rows with '||' and wikilinks
            if tbl.count('||') >= 10 and re.search(r"\[\[(?:[^\]|]+\|)?[^\]]+\]\]", tbl):
                return True
            return False
        
        lineup_tables = [t for t in inner_tables if looks_like_lineup_table(t)]
        
        # We expect exactly two lineup tables (home and away). If more, take the first two.
        if len(lineup_tables) >= 2:
            home_lineup = parse_lineup_table(lineup_tables[0])
            away_lineup = parse_lineup_table(lineup_tables[1])
            if home_lineup and away_lineup:
                return home_lineup, away_lineup
    
    # If no structured tables, try plain text format (historical)
    # Look for <small>'''Team:''' ... </small> patterns
    small_pattern = r"<small>'''([^:]+):\s*'''([^<]+)</small>"
    
    def normalize_wikitext_links(text):
        """Remove newlines from within wikitext links [[...]]"""
        result = []
        i = 0
        while i < len(text):
            if i < len(text) - 1 and text[i:i+2] == '[[':
                # Found start of link, find the end
                result.append('[[')
                i += 2
                while i < len(text):
                    if i < len(text) - 1 and text[i:i+2] == ']]':
                        result.append(']]')
                        i += 2
                        break
                    elif text[i] in '\n\r':
                        result.append(' ')  # Replace newlines with space
                        i += 1
                    else:
                        result.append(text[i])
                        i += 1
            else:
                result.append(text[i])
                i += 1
        return ''.join(result)
    
    for match in re.finditer(small_pattern, match_text, re.DOTALL):
        team_name = match.group(1).strip()
        lineup_text = match.group(2).strip()
        
        # Normalize wikitext links before parsing
        lineup_text = normalize_wikitext_links(lineup_text)
        
        parsed_lineup = parse_lineup_text(lineup_text, team_name)
        
        if not parsed_lineup:
            continue
        
        # Try to determine if this is home or away based on position in text
        # The first one is typically home team
        if not home_lineup:
            home_lineup = parsed_lineup
        else:
            away_lineup = parsed_lineup
    
    return home_lineup, away_lineup


def main():
    """Scrape 2025 Six Nations Championship using wikitext."""
    
    print("Fetching wikitext for 2025 Six Nations Championship...")
    wikitext = get_championship_page_wikitext(2025)
    
    if not wikitext:
        print("Failed to fetch wikitext")
        return
    
    print(f"Fetched {len(wikitext)} characters")
    print()
    
    match_sections = extract_rugbybox_templates(wikitext)
    print(f"Found {len(match_sections)} match sections")
    print()
    
    matches = []
    for match_id, rugbybox, lineups_wikitext in match_sections:
        match_data = parse_rugbybox(rugbybox, match_id=match_id)
        if match_data:
            # Parse lineups - try both table and text formats
            if lineups_wikitext:
                home_lineup, away_lineup = extract_lineups_from_match_section(lineups_wikitext)
                
                if home_lineup:
                    match_data['home_lineup'] = home_lineup
                if away_lineup:
                    match_data['away_lineup'] = away_lineup
            
            matches.append(match_data)
            lineup_status = ""
            if 'home_lineup' in match_data:
                lineup_status = f" ✓ {len(match_data['home_lineup'])} vs {len(match_data['away_lineup'])} players"
            print(f"  {match_data.get('home_team')} vs {match_data.get('away_team')}{lineup_status}")
    
    print()
    print(f"Successfully parsed {len(matches)} matches")
    
    # Count with lineups
    with_lineups = sum(1 for m in matches if 'home_lineup' in m)
    print(f"  {with_lineups}/{len(matches)} with lineups")
    print()
    
    # Save to JSON
    output_file = 'six_nations_2025_wikitext.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'competition': '2025 Six Nations Championship',
            'source': 'Wikipedia wikitext',
            'matches': matches,
            'total_matches': len(matches),
            'matches_with_lineups': with_lineups,
        }, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Saved to {output_file}")
    print()
    
    # Show sample
    sample = None
    for m in matches:
        if 'home_lineup' in m:
            sample = m
            break
    
    if not sample:
        sample = matches[0]
    
    print("Sample match (first match with complete data):")
    sample_json = json.dumps(sample, indent=2, ensure_ascii=False)
    print(sample_json[:2000])
    if len(sample_json) > 2000:
        print("...")


def scrape_championship(year: int, championship_name: str = "Six Nations Championship") -> List[Dict[str, Any]]:
    """
    Scrape a rugby championship from Wikipedia.
    
    Args:
        year: Championship year (e.g., 2025, 1904)
        championship_name: Championship name (e.g., "Six Nations Championship", "Home Nations Championship")
        
    Returns:
        List of match dictionaries in the standard format (matching URC/Celtic format)
    """
    
    print(f"Fetching wikitext for {year} {championship_name}...")
    wikitext = get_championship_page_wikitext(year, championship_name)
    
    if not wikitext:
        print(f"Failed to fetch {championship_name}")
        return []
    
    print(f"Fetched {len(wikitext)} characters")
    
    # Special handling for Rugby World Cup - check if pool matches are on separate pages
    all_match_sections = []
    
    # Extract matches from main page first
    main_matches = extract_rugbybox_templates(wikitext)
    all_match_sections.extend(main_matches)
    
    if "Rugby World Cup" in championship_name and year >= 2003:
        # Check for pool page references
        pool_pages = re.findall(rf'{year} Rugby World Cup Pool [A-D]', wikitext)
        
        # Only fetch pool pages if:
        # 1. Pool pages are referenced AND
        # 2. Main page has fewer than 30 matches (meaning it's knockouts only)
        if pool_pages and len(main_matches) < 30:
            print(f"Detected {len(set(pool_pages))} pool pages with fewer than 30 matches on main, fetching pool pages...")
            
            # Fetch each pool page
            for pool in ['A', 'B', 'C', 'D']:
                pool_title = f"{year} Rugby World Cup Pool {pool}"
                pool_wikitext = get_championship_page_wikitext(year, championship_name, page_title=pool_title)
                
                if pool_wikitext:
                    pool_matches = extract_rugbybox_templates(pool_wikitext)
                    all_match_sections.extend(pool_matches)
                    print(f"  Pool {pool}: {len(pool_matches)} matches")
    
    print(f"Found {len(all_match_sections)} total match sections")
    
    # Special fallback: if no rugbybox templates found for specific years (e.g., 1995, 1987),
    # parse the rendered HTML to extract matches.
    html_fallback_matches: List[Dict[str, Any]] = []
    if "Rugby World Cup" in championship_name and len(all_match_sections) == 0 and year in [1995, 1987]:
        print("No rugbybox templates found; attempting HTML parse fallback...")
        html = get_championship_page_html(year, championship_name)
        html_fallback_matches = _extract_matches_from_parsed_html(html or "")
    
    # Special handling for 2007: if pool pages have few matches, try alternate titles
    if "Rugby World Cup" in championship_name and year == 2007 and len(all_match_sections) < 40:
        print("Trying alternate pool page titles for 2007...")
        for pool in ['A', 'B', 'C', 'D']:
            for title_variant in [
                f"{year} Rugby World Cup Pool {pool}",
                f"2007 Rugby World Cup – Pool {pool}",
            ]:
                pool_wikitext = get_championship_page_wikitext(year, championship_name, page_title=title_variant)
                if pool_wikitext:
                    pool_matches = extract_rugbybox_templates(pool_wikitext)
                    if pool_matches:
                        all_match_sections.extend(pool_matches)
                        print(f"  Pool {pool}: {len(pool_matches)} matches (via {title_variant})")
                        break
    
    matches: List[Dict[str, Any]] = []
    if all_match_sections:
        for match_id, rugbybox, lineups_wikitext in all_match_sections:
            match_data = parse_rugbybox(rugbybox, match_id=match_id)
            if match_data:
                # Parse lineups using flexible format detection
                home_lineup = None
                away_lineup = None
                if lineups_wikitext:
                    home_lineup, away_lineup = extract_lineups_from_match_section(lineups_wikitext)
                
                # Transform to standard format (matching URC/Celtic structure)
                standard_match = transform_to_standard_format(match_data, home_lineup, away_lineup)
                matches.append(standard_match)
    elif html_fallback_matches:
        # Already in standard format
        matches.extend(html_fallback_matches)
    
    return matches


def transform_to_standard_format(match_data: Dict[str, Any], 
                                 home_lineup: Optional[List[Dict]] = None,
                                 away_lineup: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """
    Transform Wikipedia match data to the standard format used by URC/Celtic scrapers.
    
    Args:
        match_data: Raw match data from Wikipedia rugbybox
        home_lineup: Optional home team lineup
        away_lineup: Optional away team lineup
        
    Returns:
        Match dictionary in standard format
    """
    # Build the standard format match object
    standard_match = {
        "date": match_data.get("date"),
        "home": {
            "team": match_data.get("home_team", ""),
            "score": match_data.get("home_score"),
        },
        "away": {
            "team": match_data.get("away_team", ""),
            "score": match_data.get("away_score"),
        }
    }
    
    # Add optional fields if present
    if match_data.get("venue"):
        standard_match["stadium"] = match_data["venue"]
    
    if match_data.get("attendance"):
        standard_match["attendance"] = match_data["attendance"]
    
    if match_data.get("referee"):
        standard_match["referee"] = match_data["referee"]
    
    if match_data.get("time"):
        # Combine date and time if both present
        if standard_match["date"] and match_data["time"]:
            # Format as ISO timestamp
            standard_match["date"] = f"{standard_match['date']}T{match_data['time']}:00"
    
    # Transform lineups to standard format
    if home_lineup:
        standard_match["home"]["lineup"] = transform_lineup_to_standard(home_lineup)
    
    if away_lineup:
        standard_match["away"]["lineup"] = transform_lineup_to_standard(away_lineup)
    
    # Add scores breakdown if available (as array of scoring events)
    home_scores = []
    away_scores = []
    
    # Add tries with conversion status
    for try_obj in match_data.get('home_tries', []):
        minute = try_obj.get('minutes', 0)
        home_scores.append({
            'minute': minute,
            'type': 'Try',
            'player': try_obj.get('player', ''),
            'value': 5
        })
        # If converted, add conversion immediately after
        if try_obj.get('converted'):
            home_scores.append({
                'minute': minute + 1,
                'type': 'Conversion',
                'player': try_obj.get('player', ''),
                'value': 2
            })
        elif try_obj.get('missed'):
            home_scores.append({
                'minute': minute + 1,
                'type': 'Missed conversion',
                'player': try_obj.get('player', ''),
                'value': 0
            })
    
    for try_obj in match_data.get('away_tries', []):
        minute = try_obj.get('minutes', 0)
        away_scores.append({
            'minute': minute,
            'type': 'Try',
            'player': try_obj.get('player', ''),
            'value': 5
        })
        if try_obj.get('converted'):
            away_scores.append({
                'minute': minute + 1,
                'type': 'Conversion',
                'player': try_obj.get('player', ''),
                'value': 2
            })
        elif try_obj.get('missed'):
            away_scores.append({
                'minute': minute + 1,
                'type': 'Missed conversion',
                'player': try_obj.get('player', ''),
                'value': 0
            })
    
    # Add penalties
    for pen_obj in match_data.get('home_penalties', []):
        for time_obj in pen_obj.get('times', []):
            home_scores.append({
                'minute': time_obj.get('minutes', 0),
                'type': 'Penalty',
                'player': pen_obj.get('player', ''),
                'value': 3
            })
    
    for pen_obj in match_data.get('away_penalties', []):
        for time_obj in pen_obj.get('times', []):
            away_scores.append({
                'minute': time_obj.get('minutes', 0),
                'type': 'Penalty',
                'player': pen_obj.get('player', ''),
                'value': 3
            })
    
    # Add drop goals if present
    for drop_obj in match_data.get('home_drop_goals', []):
        for time_obj in drop_obj.get('times', []):
            home_scores.append({
                'minute': time_obj.get('minutes', 0),
                'type': 'Drop goal',
                'player': drop_obj.get('player', ''),
                'value': 3
            })
    
    for drop_obj in match_data.get('away_drop_goals', []):
        for time_obj in drop_obj.get('times', []):
            away_scores.append({
                'minute': time_obj.get('minutes', 0),
                'type': 'Drop goal',
                'player': drop_obj.get('player', ''),
                'value': 3
            })
    
    # Sort by minute and add to match
    if home_scores:
        home_scores.sort(key=lambda x: x['minute'])
        standard_match["home"]["scores"] = home_scores
    
    if away_scores:
        away_scores.sort(key=lambda x: x['minute'])
        standard_match["away"]["scores"] = away_scores
    
    return standard_match


def transform_lineup_to_standard(lineup: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Transform Wikipedia lineup format to standard format (keyed by jersey number).
    
    Args:
        lineup: List of player dictionaries with position, number, player, etc.
        
    Returns:
        Dictionary keyed by jersey number with player details
    """
    standard_lineup = {}
    
    for player in lineup:
        number = str(player.get("number", ""))
        if not number:
            continue
        
        player_data = {
            "name": player.get("player", ""),
            "on": [0],  # Assume starting lineup
            "off": [],
            "reds": [],
            "yellows": []
        }
        
        # Extract substitution/card events if present
        events = player.get("events", [])
        for event in events:
            event_type = event.get("type", "")
            minute = event.get("minute", 0)
            
            if event_type == "substitution_on" and minute > 0:
                player_data["on"] = [minute]
            elif event_type == "substitution_off":
                player_data["off"].append(minute)
            elif event_type == "yellow_card":
                player_data["yellows"].append(minute)
            elif event_type == "red_card":
                player_data["reds"].append(minute)
        
        # Add position if available
        if player.get("position"):
            player_data["position"] = player["position"]
        
        standard_lineup[number] = player_data
    
    return standard_lineup


if __name__ == '__main__':
    main()
