"""The Wikipedia filler finds every rugbybox, nested templates included."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from fill_from_wikipedia import rugbyboxes, same_fixture  # noqa: E402

PAGE = """
==Round 1==
{{rugbybox | date = 1 September 2006 | home = [[Cardiff Blues]] {{flagicon|WAL}} | score = 22 – 13
 | away = {{flagicon|IRL}} [[Munster Rugby|Munster]] | stadium = [[Cardiff Arms Park]] }}
Some prose about a rearranged game.
{{rugbybox
 | date = 12 September 2006 | home = [[Dragons (rugby union)|Newport Gwent Dragons]] {{flagicon|WAL}}
 | score = 25 – 18 | away = {{flagicon|WAL}} [[Scarlets|Llanelli Scarlets]] }}
"""


def test_finds_boxes_with_nested_templates():
    boxes = list(rugbyboxes(PAGE))
    assert len(boxes) == 2
    assert boxes[0].endswith('}}') and 'Cardiff Arms Park' in boxes[0]
    assert 'Llanelli Scarlets' in boxes[1]


def test_same_fixture_either_way_round_within_a_day_and_old_names():
    ours = {'date': '2006-09-12T19:10:00', 'home': {'team': 'Dragons RFC'}, 'away': {'team': 'Scarlets'}}
    wiki = {'date': '2006-09-13', 'home': {'team': 'Llanelli Scarlets'}, 'away': {'team': 'Newport Gwent Dragons'}}
    assert same_fixture(ours, wiki)
    assert not same_fixture(ours, {**wiki, 'date': '2006-09-15'})
