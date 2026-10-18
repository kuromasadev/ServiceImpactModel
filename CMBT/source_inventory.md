# Source inventory and commuter template audit

Inspection date: October 18, 2026. This records code/file metadata, not agency observations or public-data approval.

The user identified Dropbox project files and supplied a shared Source folder link. Dropbox metadata resolves that link to `ALBERTO/RAW/CBD_ivoms/Source`. The folder contains three separate initial inputs, not one already combined weekly file. All three listings were complete (`has_more: false`).

| Source | Exact bytes | Dropbox modified (UTC) | Inspection result |
| --- | ---: | --- | --- |
| `CBD_ivoms/Commuter-IVOMS-Baseline.R` | 18,623 | 2026-10-18 16:40:11 | Full source text inspected; unchanged reference retained only in ignored private storage. |
| `Source/R162-08012026-10142026_MobileStats.csv` | 153,457,004 | 2026-10-18 15:52:22 | Metadata only; download blocked. |
| `Source/R221-08012026-10142026_MobileStats.csv` | 16,262,832 | 2026-10-18 15:52:18 | Metadata only; download blocked. |
| `Source/R222-08012026-10142026_MobileStats.csv` | 38,163,134 | 2026-10-18 15:52:00 | Metadata only; download blocked. |

The file names state August 1–October 14 coverage; actual row coverage remains unverified. Dropbox text extraction supports only files up to 5 MiB. Temporary download URLs were obtained but the cloud environment's outbound proxy denied the Dropbox content hosts with HTTP 403. No raw file was downloaded, committed or uploaded elsewhere. The shared folder's access status does not establish public-release approval for a derived dataset or this study's metrics.

Targeted Dropbox searches for ServiceImpactModel, Route9, Route 9, IVOMS Processing Weekly Template, No Streetlight, and route_boundaries did not locate the original pilot or completed boundary file. Direct browsing found only the commuter template and Source folder in `CBD_ivoms`. Other IVOMS project folders were inspected at their immediate-child level; no exhaustive account-wide scan is claimed. No earlier chat transcript is present in this repository or workspace.

## Method carried forward and corrections

| Template behavior | New implementation / review requirement |
| --- | --- |
| Says adapted from `IVOMS Processing Weekly Template No Streetlight.R` (Route 9). | Retains departure-to-next-arrival stop-pair method; original pilot comparison remains pending. |
| Baseline ends October 14, using service-date-only inclusion. | Actual pair-end timestamps before October 9 21:00 Central only; impact observations excluded; crossing pairs/trips explicitly flagged. August 1 start provisional. |
| Writes placeholder direction labels and four unfilled boundary stop IDs. | No boundary IDs invented. Config requires verified route/direction/stop-pair evidence and separately verified terminals; unclassified data remains visible and blocks release. |
| Groups trips without vehicle, orders by actual departure, no weekly dedup registry. | Explicit stable vehicle and scheduled sequence required; transactional stable-key dedup and source-batch provenance. Source schema must establish these columns. |
| Coalesces missing passenger values to zero. | Missing stays unknown unless a positive endpoint establishes presence; empty service requires explicit zeros. |
| Non-revenue mileage includes empty scheduled service. | Empty scheduled service remains scheduled service. Deadhead/other non-revenue require explicit source pattern mappings. |
| Uses last observed stop as terminal. | Only verified terminal IDs produce terminal events; missing or repeated terminal observations exposed. |
| OTP bounds −59 through +359 inclusive. | Preserved and regression-checked at −60/−59/+359/+360 and fractional seconds. |
| Freeway observed runtime and schedule difference used as proxy. | Preserved; never labeled direct congestion without independent evidence. |
| Three-hour service-day rollover and possible UTF-16/tab inputs. | Explicit configurable rollover and encoding/delimiter inspection; ambiguous/nonexistent DST source times require offsets. |
| Exports multiple detailed CSVs/workbook. | One unified aggregate gzip candidate; private raw/intermediate storage and exact-file metric release approval. |

The new Python mapping example uses expected template names, including `OPD_DATE`, `ROUTE`, `Trip`, `PATTERN_DIRECTION`, `PATTERN.TYPE`, `Sched..Dep`, `Sched..Arr`, `Actual.Dep`, `Actual.Arr`, `Stop`, `Odometer.Miles`, `LOAD`, `BOARDINGS`, and `ALIGHTING`. Vehicle and sequence names are intentionally unset because the template does not establish them. Scheduled mileage is unavailable from the template's observed odometer fields and must not be invented.

The Route 9 time labels and hours currently come from this repository's AGENTS.md, not a newly audited pilot. The provisional Late interval 22:00–03:59 preserves the documented fallback's full coverage and exposes the old label mismatch. Final alignment still needs the pilot and a recorded decision.
