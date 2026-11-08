# Location data

`nyc-zips.json` is a local extract downloaded September 27, 2026 from [NYC Open Data, ZIP Code Tabulation Areas](https://data.cityofnewyork.us/City-Government/ZIP-Code-Tabulation-Areas/35j5-n34v).

Fields: `zcta5`, `centlat`, `centlon`. The source includes surrounding areas; this extract retains NYC postal prefixes 100/101/102/103/104/111/112/113/114/116 and 11004/11005. It contains 211 geographic ZIP areas, not every USPS delivery or building-specific ZIP. ZIPs absent from the reference are rejected with an actionable error. Review a requested missing ZIP before adding it; do not geocode exact home addresses.

Distances use the haversine formula between ZIP representative centers. They are neither address-level distances nor travel-time estimates. Same-ZIP members have a displayed distance of zero regardless of where they actually live.

Borough labels use postal-prefix mapping. A small display-only neighborhood dictionary covers the fictional seed profiles; other ZIPs display their borough. Neighborhood names do not determine matching.

`demo-members.json` contains wholly fictional people, employers, and `example.com` addresses. It is intentionally separate from collected friend data.
