# Changelog

## v0.7.0 - 2025-06-03

### Added
* Support for WiFiCom 2.x

### Changed
* Significant refactoring to support future features

## v0.6.0 - 2024-10-20

### Added
* Build a proper executable for Mac

### Changed
* Avoid overwriting digiroms.txt (used in dev version of WiFiCom at the time of this release)

### Fixed
* Correctly detect CircuitPython beta versions etc
* Detect additional CIRCUITPY drive location on Linux

## v0.5.1 - 2023-11-27

### Added
* More help on Mac

### Changed
* Locked to pyinstaller v5
* Renamed program folder on Mac

## v0.5.0 - 2023-11-19

### Added
* Allow installation on any CircuitPython board (wificom-lib v1.1.0 can be used without WiFi)
* Check for a board_config.py which doesn't include the word "wificom" and ask to delete it

### Changed
* Menu UI is more consistent

### Fixed
* No longer crashes on invalid menu selection

## v0.4.0 - 2023-08-12

### Added
* Link to UF2 file for CircuitPython upgrade/downgrade
* More useful help text
* Basic progress reporting
* Version string in opening text

### Changed
* The program filenames make more sense
* Keep window open when there is an error

### Fixed
* Check that the CIRCUITPY drive exists and is writeable
* Look for alternate CIRCUITPY location common on Linux
* Avoid unnecessary uses of the GitHub API
* Make the minimum wificom-lib release version 0.10.0 (older versions don't work with this tool)
* Mac version no longer breaks trying to delete metadata files

## v0.3.0 - 2023-05-12
