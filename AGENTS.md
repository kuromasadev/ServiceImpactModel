# ServiceImpactModel Codex project instructions

These instructions apply across this repository. Keep commuter work in `CMBT/` and use the existing local Route 9 pilot as the methodological reference.

## Project goals

1. Bring the approved commuter processing code, schemas, and documentation into `CMBT/`.
2. Build a reproducible weekly ingest for CSV batches containing R162, R221, and R222, then produce one unified processed dataset for the policy visualization.
3. Build and publish a static policy visualization at the repository path `Commuter/`, so the site URL is the GitHub Pages base URL followed by `/Commuter/`.

## Cutover and baseline

- The construction closure began Friday, October 9, 2026 at 9:00 PM Central Time.
- Classify service at or after `2026-10-09 21:00:00 America/Chicago` as post-closure impact-window service.
- The available route batch spans August 1–October 14, 2026. October 10–14 are post-cutover and must not enter the pre-closure baseline. If August 1 is the agreed baseline start, cap baseline service at October 9, 2026 20:59:59 Central.
- Classify at the stop-pair/service timestamp. Flag trips crossing the cutoff; do not silently assign a whole trip to one period based on service date alone.
- Freeze the pre-closure baseline once approved. Record any correction or revision, its reason, and approval in `CMBT/README.md`.

## Weekly input handling and data protection

- A weekly batch may contain all three commuter routes. Ingest each batch once and record its filename, received date, date coverage, schema version, route coverage, and QA result.
- Deduplicate with stable route/service-date/trip/vehicle/stop-sequence keys. Preserve source provenance in processed outputs.
- `ServiceImpactModel` is a public GitHub repository. Do not commit raw IVOMS/APC files, passenger-level records, credentials, or unapproved agency data. Keep raw batches in the approved source location; commit code, schemas, docs, tests, and only data explicitly approved for public release.
- Confirm data-owner approval for the exact processed file and displayed metrics before publishing.

## Commuter service phases and measures

Use verified route- and direction-specific boundaries to separate:

1. P&R connection: leaving or arriving at the Park & Ride.
2. Freeway: travel between verified freeway entry and exit boundaries.
3. Destination connection: travel between the freeway and the destination drop-off/pick-up zone.

Preserve physical phases for PM/reverse trips and label direction. Separate deadhead and other non-revenue movement from passenger-carrying service. Keep an empty service trip distinct from deadhead and document how passenger presence is inferred from load, boarding, and alighting fields.

Report scheduled and observed miles/minutes, freeway runtime and schedule deviation, actual terminal arrival versus schedule, and non-revenue miles/minutes. Call freeway runtime an IVOMS travel-time measure or proxy unless an independent traffic source supports a direct congestion measure. Do not present schedule deviation as observed traffic time without explaining the distinction.

## OTP and policy scenarios

- The statutory scenario uses the user's definition: on time from 59 seconds early through 5 minutes 59 seconds late, inclusive. Earlier than -59 seconds is Early; later than +359 seconds is Late.
- Test boundary values: -60 = Early, -59 = On Time, +359 = On Time, +360 = Late.
- Keep statutory OTP distinct from alternatives. Make each alternative's thresholds, denominator, event timestamp, and ranking direction visible and configurable.
- Make ranking measures and tie handling transparent. Do not create an unexplained composite score or describe an alternative as agency policy without approval.
- Show actual terminal lateness against schedule by route, direction, date, time slice, and commuter phase where data allow.

## Route 9 time-of-day alignment

Reuse the Route 9 pilot's labels and chronological order: Early AM, AM Peak, Morning, Mid-Day, Afternoon, PM Peak, After PM, Evening, Late. Match the pilot's departure-hour bands as closely as possible: 04–05, 06–08, 09–11, 12–13, 14–15, 16–17, 18–19, 20–21, and overnight. Document whether slices use scheduled or actual departure and retain a stable sort key.

Audit the Route 9 implementation's Late category: its label says 10 PM–2 AM, while its fallback captures the remaining hours, including 2 AM–3:59 AM. Resolve and document the mapping; do not silently omit or relabel overnight service.

## Unified file and GitHub's 100 MB limit

- Produce one unified, documented processed commuter file for the visualization, with all three routes, a data dictionary, provenance, and QA fields.
- Measure exact file size before each upload. Target at most 95 MiB; never exceed GitHub's 100 MB per-file limit.
- A compressed CSV is acceptable if the browser can decompress and parse the single file. Test the deployed fetch path and parser.
- Do not split the processed dataset into several files to bypass the requested unified-file design. If one approved file cannot fit below the safe target, stop before upload and document a compacting or approved hosting option in `CMBT/README.md` for user review.
- Never commit raw weekly batches or sensitive intermediate files to this public repository.

## Visualization and publication

Build an accessible static policy visualization using the approved unified file. Include scenario rankings, route/direction/time-slice filters, closure context, commuter phases, definitions, data coverage, and missing/unclassified-data warnings. Keep processing code in `CMBT/`; generate the publishable site into `Commuter/`.

Do not enable or claim GitHub Pages publication until data approval, build checks, file-size checks, and deployed URL verification pass. Do not expose passenger-level or sensitive operations details in charts, tooltips, downloads, or logs.

## Review and maintenance

Add meaningful checks for cutoff classification, OTP boundaries, deduplication, route/time-slice mapping, segment boundaries, file size, and summary totals. Verify baseline observations end before cutover and impact-window observations start at/after cutover. Preserve the approved baseline and prior results. Keep `CMBT/README.md` current, append user comments and decisions rather than replacing them, and record open questions, actions, status, and approvals.
