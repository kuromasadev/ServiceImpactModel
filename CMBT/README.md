# Commuter Bus Transit (CMBT)

This is the working review log for the commuter-service analysis. Add comments in the table or under Open Questions. Preserve earlier comments and record the resulting decision/action.

## Purpose

Complement the local Route 9 pilot with commuter-service analysis, transparent policy scenarios, and a static visualization published under `/Commuter/`.

## Current facts and constraints

- Initial routes: R162, R221, and R222.
- Closure cutover: Friday, October 9, 2026 at 9:00 PM Central Time.
- Impact window begins at/after `2026-10-09 21:00:00 America/Chicago`.
- Baseline is pre-closure only. The available route batch spans August 1–October 14, 2026; exclude all service after the October 9 9:00 PM cutover from baseline. With an August 1 baseline start, cap it at October 9, 2026 20:59:59 Central.
- Statutory OTP scenario: from 59 seconds early through 5 minutes 59 seconds late, inclusive.
- Revenue phases: P&R connection, freeway, and destination connection, with verified route/direction stop boundaries.
- Deadhead and other no-passenger movement must be separated from passenger-carrying service; empty scheduled service is its own class.
- The repository is public. Keep raw IVOMS/APC and passenger-level files in the approved source location unless an authorized public-release decision is recorded.
- Visualization input is one unified processed data file, below a 95 MiB target and always under GitHub's 100 MB per-file limit.
- Route 9 time-of-day labels/order are the reference. The overnight Late label/fallback discrepancy needs a documented resolution.

## Work plan

- [ ] Inventory Route 9 workflow, current commuter code, source schemas, and data approvals.
- [ ] Place approved commuter processing code and schema documentation in `CMBT/`.
- [ ] Implement weekly ingest for a batch containing all three routes, with provenance, deduplication, and QA.
- [ ] Validate the frozen pre-closure baseline and post-cutover impact classification, including trips that cross the cutoff.
- [ ] Confirm direction-specific P&R, freeway entry/exit, and destination stop boundaries.
- [ ] Produce one approved unified processed file and verify it is below 95 MiB.
- [ ] Implement and review policy scenarios, rankings, and Route 9-aligned time slices.
- [ ] Build and verify the GitHub Pages site at `/Commuter/` after approval.

## User comments and decisions

| Date (Central) | Topic | User comment / decision | Follow-up action | Status |
|---|---|---|---|---|
| 2026-10-18 | Cutover | Closure began Friday, October 9, 2026 at 9 PM; service after that belongs in the impact study window. | Freeze baseline through 8:59:59 PM Central and classify service at/after 9 PM as impact-window service. | Incorporated |
| 2026-10-18 | Weekly inputs | Future weekly CSV batches will include all three services. | Design one batch-ingest and validation flow for R162, R221, and R222. | Planned |
| 2026-10-18 | Visualization | Use one processed unified dataset, respect the 100 MB limit, align time slices to Route 9, and rank policy scenarios. | Build a single-file static data path with size checks and documented ranking. | Planned |
| 2026-10-18 | Publishing | Publish the commuter tool at ServiceImpactModel/Commuter. | Generate site output under repository path `Commuter/` and verify the Pages URL. | Planned |

## Open questions

- What are the verified P&R, freeway entry/exit, and destination stop IDs for each route and direction?
- Should a trip that crosses 9:00 PM be split into pre/post service intervals in every summary, or also receive a trip-level impact flag?
- Route 9 labels Late as 10 PM–2 AM, but the code's fallback appears to include 2 AM–3:59 AM. Should the tool reproduce the code's actual band or the label's stated band?
- Which alternative OTP thresholds and ranking measures should be available?
- Who approves the processed dataset and aggregate metrics for public display?

## Comment template

Add each comment as a new row; do not remove earlier entries.

| Date (Central) | Topic | User comment / decision | Follow-up action | Status |
|---|---|---|---|---|
| YYYY-MM-DD |  |  |  | Open |

## Change log

- 2026-10-18: Initial CMBT scope, cutover, route set, data-size constraint, work plan, and comment log recorded.
