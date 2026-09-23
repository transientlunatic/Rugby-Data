#!/usr/bin/env python3
"""Temporary diagnostic script for the Japan Rugby League One parsing bug.

Not part of the package - run manually via a throwaway workflow, then delete.
"""
import sys
sys.path.insert(0, '.')

from rugby.scrapers.six_nations import (
    get_wikipedia_page_title,
    get_championship_page_wikitext,
    extract_rugbybox_templates,
    parse_rugbybox,
    _parse_rugbybox_params,
)

import sys as _sys
YEAR = int(_sys.argv[1]) if len(_sys.argv) > 1 else 2025
NAME = "Japan Rugby League One"

title = get_wikipedia_page_title(YEAR, NAME)
print(f"Resolved title: {title!r}")

wikitext = get_championship_page_wikitext(YEAR, NAME)
if wikitext is None:
    print("FAILED to fetch wikitext (page not found or request error)")
    sys.exit(1)

print(f"Fetched {len(wikitext)} characters")

sections = extract_rugbybox_templates(wikitext)
print(f"extract_rugbybox_templates found {len(sections)} section(s)\n")

for i, (match_id, rugbybox, lineups) in enumerate(sections, 1):
    print(f"=== Section {i}: match_id={match_id!r} ===")
    print(f"--- rugbybox (first 500 chars) ---")
    print(rugbybox[:500])
    print(f"--- parsed params ---")
    params = _parse_rugbybox_params(rugbybox)
    print(params)
    print(f"--- parse_rugbybox() result ---")
    result = parse_rugbybox(rugbybox, match_id=match_id)
    print(result)
    print()
