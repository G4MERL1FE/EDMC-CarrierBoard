# Changelog

## v1.0.3 — Trade Opportunities and visual refresh

- Added a Trade Opportunities tab backed by the scanner opportunities API.
- Added route cards showing locations, prices, margin, estimated volume, total profit, and market-report age.
- Added filtering by commodity, system, and station.
- Added the approved black-and-orange cards, buttons, and outlined-tab styling.
- Switched both API feeds to the custom CarrierBoard domain.
- Removed PIN-bearing payloads from debug logging and safely encodes delete query parameters.
- Corrected station field defaulting and validates API response shapes before UI rendering.
- Stored the cache in the plugin folder and added background-refresh shutdown handling.

## v1.0.2 — Domain migration

- Moved the API endpoint to the custom CarrierBoard domain.
- No other functional changes.
