# Rugby Data Repository

This repository contains scoring information from various professional rugby union leagues in both YAML and JSON format.

The data in each format should be the same.

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

Use `python update_data.py -t all` to update all supported leagues, or specify individual leagues with `-t <league-code>`.

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

Top 14 data are available from the 2009-2010 season to the 2014-2015 season, and 2016-2017 to 2021-2022 seasons. Automated updates are now available for current seasons.
The 2006-2007 and 2015-2016 seasons are incomplete.

## Pro D2 (France)

Pro D2 (French second-tier) data is now available via automated updates for current seasons.

## European Challenge & Champions Cup

The European Champions' and Challenge Cups data are available between the 2006-2007 season and the 2021-2022 season. Automated updates are now available for current seasons.
