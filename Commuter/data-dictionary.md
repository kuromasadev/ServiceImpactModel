# Commuter data contract · version 1

The native IVOMS mapping is based on the Dropbox commuter R template, not yet verified against the MobileStats CSV contents. Never rename incompatible fields merely to pass validation. Use `python -m CMBT.ivoms inspect ...` first and create an explicit mapping in ignored `CMBT/private/`.

## Canonical private stop-pair input

UTF-8 CSV with this exact header order (no additional columns):

```csv
schema_version,route,direction,service_date,trip_id,vehicle_id,from_sequence,to_sequence,from_stop_id,to_stop_id,scheduled_start,scheduled_end,actual_start,actual_end,scheduled_miles,observed_miles,movement,load,boardings,alightings,terminal_event
```

| Fields | Contract |
| --- | --- |
| `schema_version` | Literal `1`. |
| `route` | R162, R221 or R222. |
| `direction` | Explicit source direction code; never inferred from AM/PM. |
| `service_date` | Source operating date, YYYY-MM-DD; may differ from actual calendar date after midnight. |
| `trip_id`, `vehicle_id` | Nonempty stable source identifiers; private only. |
| `from_sequence`, `to_sequence` | Nonnegative integer scheduled sequence, increasing. Include sequence to distinguish repeated stop visits. |
| `from_stop_id`, `to_stop_id` | Explicit scheduled/observed stop IDs, private only. |
| `scheduled_start`, `actual_start` | Departure from first stop, ISO 8601 with explicit UTC offset. |
| `scheduled_end`, `actual_end` | Arrival at next stop, ISO 8601 with explicit UTC offset. Negative runtimes fail validation. |
| `scheduled_miles`, `observed_miles` | Nonnegative finite miles or empty if unavailable. Scheduled mileage must come from a verified schedule; the template supplies observed odometer deltas only. |
| `movement` | `scheduled_service`, `deadhead`, `other_non_revenue`; explicit source classification. Unknown labels block conversion. |
| `load`, `boardings`, `alightings` | Nonnegative finite values or empty if unknown. Adapter takes maximum across the two endpoints to infer presence only; these are not exported passenger totals. All three zero establishes empty service; any positive establishes presence; otherwise unknown. |
| `terminal_event` | `true` only for arrival at a verified route/direction terminal in config; otherwise `false`. Last observed stop alone is insufficient. One terminal event per route/date/trip/vehicle. |

Stable pair key: route / service date / trip / vehicle / from sequence / to sequence. Identical duplicates retain all batch-hash provenance; conflicting duplicates roll back the whole batch. Batch SHA-256 ensures rerunning the same file is a no-op. Malformed rows reject the batch rather than silently reducing the denominator. A mixed-route batch is read once, not once per route; missing routes receive QA warnings.

IVOMS adapter accepts BOM-marked UTF-16, unmarked UTF-16LE, UTF-8, comma or tab delimiters, and expected template dates `%m/%d/%Y`. It requires explicit vehicle and sequence column mappings. It orders records by stable source sequence, retains empty scheduled service, and does not infer deadhead from passenger counts. A per-batch, private SQLite scratch database avoids loading the raw batch into memory. Cross-batch input must contain complete overlapping trips: do not combine complementary partial stop exports without a reviewed upstream merge, as this adapter cannot reconstruct intervals across files. Configurable 03:00 service-day rollover follows the commuter template; DST ambiguity/nonexistent times require explicitly offset canonical input.

## One public candidate: `commuter.csv.gz`

Deterministic gzip (mtime 0), UTF-8 CSV, one row per grouping below. Generated only under ignored `CMBT/private/` until a data-owner review covers its exact bytes/hash and every displayed metric. Aggregate cells and delay distributions can still be sensitive; the approval must cover granularity and small cells. No automatic public-release decision or invented suppression threshold is made.

Dropbox retains the source CSVs. Approved processed copies are stored as dated GitHub Release assets named `commuter-YYYY-MM-DD-HASH12.csv.gz`; prior snapshots are retained. The repository and Pages contain code/docs and a small `Commuter/manifest.json` pointing to the current asset, never the compressed payload. The manifest records the date, release tag, asset ID, API/download URLs, SHA-256, bytes, row/pair totals, and coverage. Uploaded Release metadata must match the approved bytes before manifest generation. The 95 MiB project target remains a browser-input constraint; GitHub's separate 100 MB Git-blob limit is not a Release storage limit.

| Field | Definition |
| --- | --- |
| `route`, `direction`, `service_date` | Grouping from source; public only after review. |
| `time_slice`, `time_slice_order` | Scheduled pair-departure hour in America/Chicago; order 0–8: Early AM 04–05, AM Peak 06–08, Morning 09–11, Mid-Day 12–13, Afternoon 14–15, PM Peak 16–17, After PM 18–19, Evening 20–21, Late 22–03. This preserves all hours of the pilot fallback; actual pilot not yet located, mapping provisional. |
| `period` | Actual pair-end arrival at/after cutoff → `impact`; before cutoff and actual local arrival date at/after baseline start → `baseline`; earlier → `outside_baseline`. Cutoff is 2026-10-09 21:00 Central (2026-10-10 02:00 UTC). |
| `phase` | `pr_connection`, `freeway`, `destination_connection`, `unclassified`. Exact route/direction/stop-pair config entries require `verified: true` and evidence. Direction-specific physical phases persist on reverse trips; no guessed freeway boundaries. |
| `movement` | Source class; empty scheduled service remains scheduled service. |
| `passenger_presence` | `present`, `empty`, `unknown`; no passenger counts/identifiers exported. |
| `crosses_cutover` | Actual pair start < cutoff <= actual pair end. Full runtime/mileage belongs to its arrival period and is explicitly flagged; no proportional allocation assumed. |
| `trip_crosses_cutover` | Same test using earliest actual start/latest actual end of the stable trip across ingested batches. Trip observations retain their separate per-pair periods. |
| `pairs` | Unique stop-pair count, not passengers or trips. |
| `scheduled_seconds`, `observed_seconds` | Sum of departure-to-next-arrival runtimes, excludes stop dwell. Divide by 60 for minutes. Observed minus scheduled is runtime difference, not direct traffic delay. |
| `scheduled_miles`, `observed_miles` | Sum over available samples; never treat a zero sum without samples as observed zero mileage. |
| `scheduled_miles_samples`, `observed_miles_samples` | Number of pairs with the corresponding mileage. Missing mileage remains visible. |
| `delay_histogram` | JSON map signed actual pair-end arrival minus scheduled arrival, seconds → count. Fractional seconds retained; permits configurable exact OTP thresholds. |
| `terminal_delay_histogram` | Same map, restricted to verified terminal arrivals. Default statutory OTP denominator is scheduled-service terminal events with valid arrivals. Phase and time-slice filters refer to that terminal pair. |
| `source_batch_sha256` | Sorted JSON array of contributing canonical batch hashes; private inventory links these to filenames, received dates, source hashes and mapping. |
| `qa_flags` | Sorted JSON array of warnings. |
| `baseline_status` | `provisional` until explicitly frozen; `frozen` only after integrity check. |

Summing `pairs` and the pair-delay histogram frequencies must reconcile with unique private records. Terminal histogram frequencies must not exceed pair counts. Exactly one terminal event per stable trip is allowed. The site additionally verifies gzip SHA-256, byte size, row count and pair totals against its release manifest.

The site requests the public GitHub Release asset API with `Accept: application/octet-stream` and no credentials. Live cross-origin API/redirect support from the deployed Pages origin remains a deployment check; mocked parser/download tests do not establish it. API metadata, rate-limit/access errors, CORS failures, and mismatched bytes remain visible and block data display.

## QA flags and scope

- `unverified_phase`, `unverified_terminal`: missing verified configuration; release build is blocked.
- `missing_verified_terminal_for_trip`: no verified terminal arrival in the observed trip; not silently counted as on time.
- `unknown_passenger_presence`: insufficient fields to establish empty or present.
- `passengers_on_non_revenue_movement`: source-classification contradiction requiring review.
- `missing_miles`: scheduled or observed mileage absent; show sample coverage.
- `cutover_crossing_pair_full_runtime_assigned_to_arrival_period`: pair crosses closure; full-pair allocation disclosed.
- Batch-level `missing_routes:...`: partial route coverage; publication requires all three routes in the unified file.

No filtering by service date alone defines the baseline. Freeze records the digest of the pre-cutover records, count, approval identity, reason and revision history privately. New baseline observations after freeze require explicitly recorded revision approval. Conflicting observations are never overwritten; corrections require a separate rebuilt database and a documented, approved baseline revision preserving prior outputs.

## Policy calculations

Statutory terminal OTP: Early < −59 seconds; On Time −59 through +359 inclusive; Late > +359. All eligible scheduled-service terminal arrivals form the denominator, including empty/unknown passenger presence. Stop-pair arrivals are a separately labeled exploratory measure. UI alternatives expose early/late limits, timestamp, denominator and ascending/descending share rankings. Equal shares use competition rank; no composite score. Higher OTP share under a relaxed threshold does not establish a better service policy.

Terminal mean signed deviation is sum(delay × frequency) / count / 60. Mean positive lateness is sum(max(delay, 0) × frequency) / count / 60; late event counts use the statutory +359 bound. Non-revenue miles/minutes include `deadhead` and `other_non_revenue` only. Freeway runtime is an IVOMS travel-time proxy, never an independent congestion estimate.
