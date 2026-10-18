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
- Visualization input is one unified processed data file with a 95 MiB project target, stored as a dated compressed GitHub Release asset. Dropbox retains the source CSVs; Git and Pages retain code and a small current-data manifest, never data payloads. GitHub's 100 MB Git-blob limit is separate from Release asset storage.
- Route 9 time-of-day labels/order are the reference. The overnight Late label/fallback discrepancy needs a documented resolution.

## Work plan

- [ ] Inventory Route 9 workflow, current commuter code, source schemas, and data approvals.
- [ ] Place approved commuter processing code and schema documentation in `CMBT/`.
- [x] Implement weekly ingest for a batch containing all three routes, with provenance, deduplication, and QA. Synthetic checks pass; real source-schema validation remains pending.
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
| 2026-10-18 | Source location | User directed the implementation to Dropbox project files and provided the commuter Source folder link. | Located the commuter R template and all three route CSVs; keep raw content out of the public checkout. | Located; downloads blocked by environment proxy |
| 2026-10-18 | Implementation choices | No additional policy or public-data approval was supplied. | Implemented configurable alternatives, provisional August 1 baseline start, scheduled pair-departure slices, per-pair cutoff classification plus crossing-trip flag. These are reviewable implementation defaults, not new user approvals. | Implemented; domain review pending |
| 2026-10-18 | Storage architecture | “Dropbox keeps the source CSVs; GitHub Releases keep dated compressed processed copies; the repository and Pages site hold the code and a small manifest pointing to the current data.” | Replaced the site-local dataset design with dated, hash-named Release snapshots and manifest-only Pages promotion. Preserve historical snapshots; never commit processed payloads. | Accepted and implemented; actual upload pending data access/approval |

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
- 2026-10-18: Added dependency-free Python processing, source-schema inspection/adapter, private weekly batch inventory, deduplication, baseline freeze/revision records, deterministic single-file gzip aggregates, exact-file release checks, static visualization source/output, and synthetic checks. Preserved all prior comments. No actual baseline was frozen, no agency dataset was exported, and no site was published.
- 2026-10-18: User storage decision supersedes the initial site-local payload design: Dropbox sources, dated processed GitHub Release assets, code and a small current manifest in Git/Pages. Added private release preparation, uploaded-asset metadata validation, remote browser loader and regression checks. No real Release asset has been uploaded.

## Execution status · October 18, 2026

The repository initially contained documentation only. The implementation now runs locally. **Real-data processing and publication are pending**, for the concrete reasons below.

| Work area | Result |
| --- | --- |
| Source inventory | Dropbox contains `Commuter-IVOMS-Baseline.R` and R162/R221/R222 MobileStats CSVs. See [source inventory and template audit](source_inventory.md). The original Route 9 pilot and completed boundaries were not found by targeted searches. |
| Existing code | Inspected the full commuter R template and retained an unchanged private reference in ignored `private/reference/`. New Python tools implement its stop-departure/next-arrival method with the repository's corrections. The legacy R script was not run or copied into the public site. |
| Raw source access | Download through the environment proxy failed with `403 Forbidden` for Dropbox content hosts. Source sizes are 153,457,004; 16,262,832; and 38,163,134 bytes, all beyond the Dropbox connector's 5 MiB text-extraction limit. No raw CSV reached this workspace. |
| Native schema | Adapter is based on template field names; actual headers, vehicle and stable sequence columns, direction codes and movement labels must be confirmed from source. It refuses guessed identity fields. |
| Ingest and baseline | Private transactional ingest, overlap deduplication, batch inventory, provenance, cutoff/trip flags and approval-recorded baseline freeze/revision support implemented. No actual baseline/data approval exists yet. |
| Unified data | Deterministic aggregate CSV gzip export with a 95 MiB project ceiling, private dated Release preparation, and uploaded-asset hash/size checks implemented. Only synthetic exports have been created during tests and then removed. No actual processed-file size or public Release can yet be claimed. |
| Visualization | Source in `site/`; generated static assets in `../Commuter/`. Route/direction/date/time-slice/phase/movement/presence filters, explicit scenarios/rankings, terminal deviations, runtime/mileage, closure context and QA warnings implemented. Current manifest has no dataset and displays a pending notice. |
| Verification | 25 Python regression checks and 8 JavaScript checks pass, including dated snapshot preservation, metadata matching, manifest-only builds, credential-free remote fetch, byte/hash validation, gzip parsing and visible network/CORS/API failures using synthetic data and mocked downloads. The actual private batch inventory is empty. No live GitHub download, browser visual test or deployed Pages cross-origin fetch has been verified. |
| Publication | No deployment workflow enabled, no public data copied, no push or Pages deployment performed. Exact-file data-owner approval, verified boundaries/terminals, approved baseline, actual file-size validation and deployed fetch/parser verification remain required. |

## Runbook

Run commands from the repository root. Python 3.12+ with timezone data and Node 22+ are sufficient. No R or Python package installation is needed for the new tools.

### 1. Inspect approved local source files

Keep raw files in their approved Dropbox location. A temporary local working copy, if approved for the environment, belongs only in ignored `CMBT/private/source/`; never stage it.

```sh
python -m CMBT.ivoms inspect CMBT/private/source/*.csv
```

This prints encoding, delimiter, header names, file size and hash, not raw records. If network settings still block downloads, allow the appropriate `*.dl.dropboxusercontent.com` content hosts through the supported cloud-environment configuration workflow. Do not bypass the proxy. The shared Source folder link identifies the files but does not change this environment policy.

Copy `CMBT/ivoms_mapping.example.json` to `CMBT/private/ivoms_mapping.json` and replace template assumptions with verified header names. `vehicle_id` and `sequence` intentionally start unset. Confirm exact movement labels, service-day rollover and direction meanings. The adapter currently expects complete trips within each batch; overlapping complete trips are supported, complementary partial-trip files require a reviewed upstream merge.

### 2. Configure boundaries and terminals

`CMBT/config.json` retains the cutoff exactly at October 9, 2026 21:00 Central. August 1 baseline start remains provisional. Add verified physical phase entries for each observed stop pair, route and direction. Each entry contains:

```json
{
  "route": "R162",
  "direction": "VERIFIED_SOURCE_DIRECTION",
  "from_stop_id": "VERIFIED_FROM_STOP",
  "to_stop_id": "VERIFIED_TO_STOP",
  "phase": "freeway",
  "verified": true,
  "evidence": "Reference to approved schedule/map verification"
}
```

The other phase names are `pr_connection` and `destination_connection`. These are physical labels on reverse trips too. The example is a shape, not approved route information. Add `terminals` entries with `route`, `direction`, `stop_id`, `verified: true`, and `evidence`. Missing boundaries remain unclassified; missing terminal configuration yields no terminal events and warnings. Public release refuses unverified boundaries/terminals.

Config is fingerprinted at first ingest. Any later config change requires a separate private database rebuild, preservation of prior results, and review of any baseline revision. Do not alter an approved frozen baseline in place.

### 3. Adapt and ingest each weekly batch once

```sh
python -m CMBT.ivoms adapt CMBT/private/source/weekly.csv --mapping CMBT/private/ivoms_mapping.json --output CMBT/private/weekly-pairs.csv
python -m CMBT.pipeline ingest CMBT/private/weekly-pairs.csv --received 2026-10-18
python -m CMBT.pipeline inventory
python -m CMBT.pipeline export
```

Replace filenames and received date with the actual batch metadata. A weekly source may contain all three routes; run one adapter and one ingest for that batch. The initial three separate source files each require one ingest into the same database. The inventory links the canonical batch hash to its filename, received date, service-date coverage, routes, schema, QA and original source hash/mapping. Equal duplicates preserve all provenance; conflicting records or malformed input roll back the batch. A rerun of the exact batch is a no-op.

Database defaults to `CMBT/private/commuter.sqlite`. The candidate output defaults to `CMBT/private/commuter.csv.gz`, accompanied by a private `.qa.json` report. This is one unified aggregate file, not trip/passenger records. Export reports its exact byte size and SHA-256. When replacing a changed candidate, the previous file and QA report are preserved by content hash in ignored `CMBT/private/archive/`. Unavailable scheduled mileage stays missing with coverage counts. Files above 95 MiB are rejected; do not split the dataset. Review a coarser approved aggregation or approved hosting and record that decision here before upload.

### 4. Review and freeze the baseline

After reviewing actual source QA, boundary evidence, cutoff classifications, mileage availability, terminal denominators and provisional baseline start, record the actual approval in this log. Only then run:

```sh
python -m CMBT.pipeline freeze-baseline --approved-by ACTUAL_APPROVER --reason ACTUAL_APPROVAL_REFERENCE
python -m CMBT.pipeline export
```

The approval arguments record an existing approval; running a command is not approval by itself. Freeze stores a digest of pre-cutover records and preserves revision history. Impact records never enter it. If a later batch adds legitimate baseline observations, both `--baseline-revision-approved-by` and `--baseline-revision-reason` are required on `ingest`, and the correction/approval must also be appended here. Conflicting record corrections require a separate private rebuilt database, preserving the previous database, exports and approval records.

### 5. Build the local visualization and prepare a release

```sh
python -m CMBT.build_site
```

This creates static assets at `Commuter/` with no data, ready for local review; it does not publish. It refuses to replace an existing approved manifest with a pending one. Dropbox retains source CSVs as the system of record; local source copies are working files, not a second source archive. GitHub Releases retain the dated compressed processed snapshots. Git and Pages contain code, documentation and the small current-data manifest only.

First have the data owner review the exact candidate, aggregate cell granularity, and every metric in `CMBT/approval.example.json`. Save the actual approval privately as `CMBT/private/release-approval.json`, including its exact hash/byte size, approval identity/date/evidence and full metric list. Record the decision here. Prepare a dated Release asset:

```sh
python -m CMBT.release --data CMBT/private/commuter.csv.gz --approval CMBT/private/release-approval.json --repository OWNER/ServiceImpactModel --date 2026-10-18
```

Replace the repository owner and snapshot date with the actual values. Preparation validates all three routes, frozen approved baseline, verified phases/terminals, matching hash/size and reconciled totals. It creates `CMBT/private/releases/commuter-YYYY-MM-DD-HASH12/commuter-YYYY-MM-DD-HASH12.csv.gz`, a private descriptor and release notes. It does not upload. The copied bytes match the exact approval; a preexisting different snapshot is preserved and rejected. The date plus hash prefix distinguishes same-day corrections.

After that exact file is approved for public upload, use the returned tag, asset and notes paths. Example commands below contain a hash placeholder which must be replaced with the preparation result:

```sh
COMMUTER_REPO="OWNER/ServiceImpactModel"
COMMUTER_CODE_COMMIT="REPLACE_WITH_APPROVED_PROCESSING_COMMIT_SHA"
COMMUTER_TAG="commuter-2026-10-18-REPLACE_WITH_HASH_PREFIX"
COMMUTER_ASSET="CMBT/private/releases/$COMMUTER_TAG/$COMMUTER_TAG.csv.gz"
COMMUTER_NOTES="CMBT/private/releases/$COMMUTER_TAG/release-notes.md"
gh release create "$COMMUTER_TAG" "$COMMUTER_ASSET" --repo "$COMMUTER_REPO" --target "$COMMUTER_CODE_COMMIT" --title "Commuter snapshot 2026-10-18" --notes-file "$COMMUTER_NOTES" --latest=false
gh api "repos/$COMMUTER_REPO/releases/tags/$COMMUTER_TAG" > CMBT/private/github-release.json
```

Publish the reviewed processing-code commit first and use its actual SHA as the release target so each snapshot has its matching code. GitHub CLI authentication belongs in the local/session CLI configuration, never in the site. Retain every prior dated release. Do not use overwrite/clobber options. If a tag already exists, inspect and reuse the matching published asset, or prepare a new date/hash version; do not replace its contents. GitHub's release “latest” selection is independent of the Pages manifest.

Only after the upload succeeds, build the current manifest from the published Release API metadata:

```sh
python -m CMBT.build_site --data CMBT/private/commuter.csv.gz --approval CMBT/private/release-approval.json --repository OWNER/ServiceImpactModel --release-date 2026-10-18 --release-metadata CMBT/private/github-release.json
```

This matches the repository, dated tag, asset name, numeric asset ID, uploaded state, GitHub-reported SHA-256 digest and byte size to the locally approved file. It generates a small `Commuter/manifest.json` with coverage, rows/pairs, checksum, date/tag/asset ID, API data URL and dated download URL. It never copies the payload into `Commuter/`. Approver identities and raw source paths stay private. A legacy `Commuter/data/` directory blocks the build and is preserved for deliberate migration. All `*.csv.gz` files are ignored; never force-add a payload, even if it is below Git's size limit.

The browser fetches `./manifest.json`, then the exact public `https://api.github.com/repos/OWNER/REPO/releases/assets/ASSET_ID` URL with `Accept: application/octet-stream`, CORS mode and no credentials. It follows GitHub's download redirect, verifies SHA-256 and size, decompresses with `DecompressionStream('gzip')`, and parses quoted CSV/JSON distributions. A current browser over HTTPS or localhost is required. The API endpoint is used instead of assuming the ordinary `github.com/releases/download/…` link allows cross-origin fetch. Actual GitHub API/redirect CORS behavior and unauthenticated rate limits must still be verified from the deployed Pages origin. Metadata JSON returned instead of bytes, network/CORS failures, HTTP errors and checksum mismatches produce visible errors; no browser token or payload-in-Git fallback is used.

GitHub Pages must serve the repository root so the path is the Pages base URL plus `/Commuter/`. No Pages settings have been changed. Validate the uploaded asset before promoting the current manifest, then stage code/docs and the reviewed small manifest only. Publish via the repository's authorized workflow and verify the deployed manifest, cross-origin Release fetch, gzip parser, totals, controls and warnings. Record the URL and successful checks here before claiming publication. Roll back by restoring a previous verified manifest pointing to its retained dated snapshot; no data re-upload or deletion is needed.

### 6. Repeat regression checks

```sh
python -m unittest discover -s CMBT/tests -v
node CMBT/tests/model.test.mjs
node CMBT/tests/data.test.mjs
node --check CMBT/site/app.mjs
python -m CMBT.build_site --output /tmp/commuter-review
```

CI repeats these checks without publishing and rejects committed gzip payloads or a Pages data directory. Tests use synthetic identifiers only, create temporary private files, and remove them afterward. Tests cover cutoff/UTC/crossing behavior, OTP inclusive/fractional bounds, all 24 time-slice hours, missing/empty/present passengers, reverse physical phases, provenance/dedup/conflict rollback, freeze/revision/integrity, missing/duplicate terminal behavior, gzip reproducibility/browser parsing, release hash/metrics/size, dated snapshot preservation, uploaded-asset metadata, small manifest-only output and remote-loader failures. Mocked fetch tests do not establish live GitHub CORS support.

## Remaining actions and approvals

1. Enable permitted Dropbox content downloads in the cloud environment, then inspect actual MobileStats schemas and validate mapping with all three route batches.
2. Locate the original Route 9 pilot; audit the actual Late fallback and departure timestamp basis. Current implementation provisionally retains 22:00–03:59 so no overnight hour is dropped, and documents the difference from the old label.
3. Obtain verified route/direction stop-pair phase boundaries and terminal IDs. None were present in the commuter project folder or its R template.
4. Validate actual coverage, source sequence/vehicle identities, mileage fields, passenger inference, complete-trip availability and source movement labels. Run real-data QA and produce the candidate export.
5. Approve baseline start and the documented arrival-based crossing-pair allocation; freeze the real baseline only after approval.
6. Review alternatives and ranking behavior. The editable alternative starts with the same bounds as statutory OTP and remains explicitly exploratory.
7. Obtain data-owner approval for the exact processed candidate and displayed metrics, verify actual size, upload its dated GitHub Release snapshot, validate uploaded metadata and promote the small manifest. Then complete GitHub Pages and deployed cross-origin URL/parser checks. Storage approval does not replace exact-file data approval.
