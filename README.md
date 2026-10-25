# CarrierBoard — EDMC Plugin

✨ **Officially available in the EDMC Plugin Browser!** ✨

Open EDMC → Settings → Plugins, search for **CarrierBoard**, and click Install.

CarrierBoard brings the shared Elite Dangerous carrier job board and scanner-derived Trade Opportunities into EDMC.

## Features in v1.0.3

- **Community Jobs** tab for viewing, posting, and completing community carrier jobs.
- **Trade Opportunities** tab with scanner routes, buy/sell systems and stations, prices, margin per tonne, estimated volume, estimated total profit, and market report age.
- Filter trade opportunities by commodity, system, or station.
- Black-and-orange cards, buttons, and outlined tabs.
- Market reports over 12 hours old are highlighted for in-game verification; the API filters reports older than 24 hours.
- Both feeds use `https://carrierboard.738294016.xyz`.
- PINs are not written to debug logs; delete query parameters are encoded safely.
- Periodic refresh stops when EDMC shuts down, and API response shapes are validated before rendering.

## Manual installation

1. Close EDMC.
2. Back up your existing `CarrierBoard` plugin folder.
3. Extract the downloaded ZIP's contained `CarrierBoard` folder into `%LOCALAPPDATA%\EDMarketConnector\plugins\` so the path is `plugins\CarrierBoard\load.py`.
4. Restart EDMC and open the CarrierBoard panel.

Requires EDMC 6.1.0 or later and an internet connection.

## Notes

- Trade Opportunities are suggestions based on scanner market reports, not confirmed community jobs. Verify both markets in-game before travelling.
- The plugin cannot automatically publish Fleet Carrier market orders.
- Completing a community job changes the shared board for everyone.

Website: https://carrierboard.738294016.xyz  
Source: https://github.com/G4MERL1FE/EDMC-CarrierBoard

