# CarrierBoard — EDMC Plugin

An EDMC plugin that brings the Elite Carrier Job Board directly into Elite Dangerous.

## Features

- **Live job list** inside EDMC's main window, refreshed every 5 minutes
- **Complete jobs** (including PIN-protected ones) without leaving the game
- **Post new jobs** from a dialog — carrier details are cached so you only enter them once
- **Shared board** — syncs with the same public API the website uses, so everyone sees the same jobs

## Installation

1. Download the latest `CarrierBoard.zip` from the [Releases page](https://github.com/G4MERL1FE/EDMC-CarrierBoard/releases/latest)
2. Extract the `CarrierBoard` folder into `%LOCALAPPDATA%\EDMarketConnector\plugins\`
3. Restart EDMC
4. Look for the **CarrierBoard** panel in the main EDMC window

## Requirements

- EDMC 6.1.0 or later
- An internet connection

## Website

https://ed-carrier-board.th3-g4mer-l1fe.workers.dev

## Notes

Fleet Carrier market orders aren't exposed by Frontier's CAPI or the journal, so posting is done manually via the plugin's **Post Job** dialog.

## License

MIT — see [LICENSE](LICENSE)
