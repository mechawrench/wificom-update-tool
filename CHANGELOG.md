# Changelog

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
