# Rugby Data Repository

This repository contains scoring information from various professional rugby union leagues in JSON format (`json/`).

Please submit a pull request if you spot any mistakes!

## Automated Updates

This repository is configured to automatically update match data weekly. The system now supports multiple leagues and is easily extensible. See [AUTOMATION.md](AUTOMATION.md) for:
- How the automation works
- How to trigger manual updates
- How to add support for new leagues

### Supported Leagues for Automated Updates

The following leagues are currently supported for automated data updates:

- **United Rugby Championship (URC)** - Celtic League / Pro12 / Pro14
- **Gallagher Premiership** - English top-tier rugby
- **RFU Championship** - English second-tier rugby
- **Top 14** - French top-tier rugby
- **Pro D2** - French second-tier rugby
- **European Rugby Champions Cup** - Premier European club competition
- **European Rugby Challenge Cup** - Secondary European club competition
- **Six Nations Championship**, **mid-year** and **end-of-year internationals**, and the **Rugby World Cup**
- **Super Rugby**, the **Rugby Championship**, **Japan Rugby League One**, **Currie Cup**, and the **National Provincial Championship (NPC)**
- **Major League Rugby** and the **Rugby Europe Championship**

Use `rugby data update -t all` to update all supported leagues, or specify individual leagues with `-t <league-code>`. See [AUTOMATION.md](AUTOMATION.md) for the full list of league codes.

Note: Historical data availability varies by competition. The RFU Championship has automated data available from the 2025-2026 season onwards.

# Internationals

Complete international results are available to the end of 2020, thanks to http://www.lassen.co.nz/pickandgo.php

# European Domestic Competitions

## English Premiership

English Premiership data is available for the 2006-2007 season through to the 2021-2022 season. Automated updates are now available for current seasons.

## RFU Championship

RFU Championship (English second-tier) data is now available via automated updates for the 2025-2026 season. This includes teams such as Ealing Trailfinders, Cornish Pirates, Bedford Blues, and Nottingham Rugby.

## Celtic League / Pro12 / Pro14 / United Rugby Championship

Celtic League data are available (in its various guises) between the 2006-2007 season and the 2021-2022 season. Automated updates are now available for current seasons.
The Pro14 Rainbow Cup is not currently included.

## Top 14

Top 14 data are available for the 2011-2012 to 2015-2016 seasons and 2017-2018 onwards; 2016-2017 is missing and 2015-2016 is incomplete (88 matches). Automated updates are now available for current seasons.
Lineups come from the main feed for recent seasons and from ESPN for earlier ones (starters and bench only, no substitution minutes: see below).
The 2010-2016 files originally had every date set to 2019, and 2017-2019 had autumn dates a year late; both were repaired with `rugby data fix-dates` (see below).

## Pro D2 (France)

Pro D2 (French second-tier) data is now available via automated updates for current seasons.

## European Challenge & Champions Cup

The European Champions' and Challenge Cups data are available between the 2006-2007 season and the 2021-2022 season. Automated updates are now available for current seasons.

## Team names

Team names in `json/` are canonical: one spelling per club, whatever the source
called it that year ("Leinster" and "Leinster Rugby" are both `Leinster Rugby`;
Canterbury Crusaders is `Crusaders`; Neath-Swansea Ospreys is `Ospreys`).
`rugby/team_names.py` holds the table and is applied whenever data is written
(`rugby data update`), so new matches arrive canonical.

```bash
rugby data normalise --check   # list anything not canonical; exit 1 if found
rugby data normalise           # fix files in place (and un-reverse season filenames)
```

A test fails if non-canonical names are committed. To record a new variant or
rename, add it to `TEAM_NAME_ALIASES` and run `rugby data normalise`.

## Lineups from ESPN

The main feed has no Super Rugby, NPC or (for older seasons) Top 14 lineups, so
`rugby data enrich-lineups` fills them from ESPN's public JSON:

```bash
rugby data enrich-lineups -t top14 -t super-rugby -t npc --dry-run   # report only
rugby data enrich-lineups -t npc --season 2024-2025
```

- ESPN gives the matchday 23 but **no substitution minutes**. Starters are
  `on: [0]`, the bench `on: []`, and enriched matches carry
  `"lineup_source": "espn"` so consumers can tell.
- A lineup that already records minutes or cards is never replaced; a missing
  or shorter one is.
- Matches are paired by date (±1 day), team and score, so a mis-dated match is
  skipped rather than given someone else's lineup.
- Coverage when this was added: Top 14 2010 onward, Super Rugby Pacific 2022
  onward, NPC 2016 onward. The Currie Cup has no rosters on ESPN.
- ESPN's API is undocumented and may change without notice.

## Date repairs

`rugby data fix-dates` corrects matches whose date is in the wrong year (autumn
matches carrying the following year; files whose dates were all 2019). It is
idempotent, and `rugby data validate` now reports a `season_date` error for any
new northern-hemisphere match dated outside its season (2019-20 is exempt, as
it ran into autumn 2020).

## Cleaning

```bash
rugby data clean --check   # list duplicate rows and placeholder results; exit 1 if found
rugby data clean           # fix in place
```

Duplicate rows for one fixture are collapsed (keeping the one with a score, then
the most lineup/scoring detail); `TBC v TBC` knockout slots are left alone.
Placeholder results (0-0 with no scorers or lineups, i.e. cancelled or never
played) get `null` scores and `"status": "void"`, so they are not read as
results.

The scheduled update also refreshes the *previous* season while it still has
finished matches with no result, so results that arrive after the season rolls
over are picked up.

## Data checks on scheduled updates

The scheduled `Update Match Data` job normalises names, then runs
`rugby data validate` and the tests **before** committing, so a bad update stops
the job instead of landing on `master` (commits made with the default token
don't trigger the `Tests` workflow, so this is the only gate).

`rugby data validate` checks only matches that are new or changed since `HEAD`,
so historical oddities (blank team names, 0-0 placeholders, duplicates in old
seasons) can't block a run. Errors stop the job: blank or non-canonical team
names, a team playing itself, half a result, negative scores, unparseable
dates, duplicates. Warnings are reported only: 0-0 results and results dated
in the future. `rugby data validate --all` audits everything (report only).
