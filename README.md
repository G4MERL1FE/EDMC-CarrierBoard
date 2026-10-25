# CarrierBoard — EDMC Plugin

✨ Officially available in the EDMC Plugin Browser! ✨  
Open **EDMC → Settings → Plugins**, search for **CarrierBoard**, and click **Install**.

CarrierBoard brings the Elite Dangerous Fleet Carrier community job board and scanner-discovered trade opportunities into EDMC.

## Features

- **Community Jobs** — view shared carrier trade jobs, with current job details and completion controls.
- **Post jobs** — create a listing from EDMC; carrier name, callsign and system details are cached for convenience.
- **PIN-protected jobs** — complete protected listings by entering their PIN; the PIN is not written to debug logs.
- **Trade Opportunities** — view scanner-discovered buy/sell routes separately from community-posted carrier jobs.
- **Scanner filtering** — filter opportunities by commodity, loading/unloading system, or station.
- **Trade details** — buy and sell prices, estimated margin per tonne, estimated volume, and estimated total profit.
- **Market freshness warnings** — reports older than 12 hours are highlighted for in-game verification; the scanner API filters routes beyond its 24-hour freshness window.
- **Shared feeds** — the plugin reads the same public CarrierBoard API used by the website and refreshes in the background every five minutes.

Scanner opportunities are suggestions only. They are not confirmed carrier jobs, cannot be claimed on the community board, and market data should be checked in-game before travelling.

## Installation

1. Download the latest plugin ZIP from the [Releases page](https://github.com/G4MERL1FE/EDMC-CarrierBoard/releases/latest).
2. Extract the contained **CarrierBoard** folder into `%LOCALAPPDATA%\\EDMarketConnector\\plugins\\`.
3. Restart EDMC.
4. Look for the **CarrierBoard** panel in EDMC's main window.

## Requirements

- EDMC 6.1.0 or later.
- An internet connection.

## Website

[carrierboard.738294016.xyz](https://carrierboard.738294016.xyz)

## Notes

Fleet Carrier market orders aren't exposed by Frontier's CAPI or the journal, so carrier jobs must be posted manually using the plugin's **Post Job** dialog.

## License

MIT — see [LICENSE](LICENSE).
