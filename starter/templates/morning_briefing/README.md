# Stock and weather

This JSON is an illustrative offline sample, marked DEMO. Personalize the ticker,
US ZIP, units, heading and footer in `device.json`, which overrides matching sample
values. The board fetches actual weather/stock data directly in the configured
`workshop` build. `workshop_demo` always stays offline.

Drawing lives in `tools/render.py` for samples and `firmware/include/direct_data.h`
for live values. A new JSON key needs drawing code before it appears on screen.
See [the workshop guide](../../docs/WORKSHOP.md) to add another screen.
