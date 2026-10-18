# ServiceImpactModel

Transit Service Impact Model evaluating the effects of the North Houston Highway Improvement Project on different transit modes.

## Work areas

- [Commuter Bus Transit (CMBT)](CMBT/README.md): commuter baseline, weekly route batches, policy scenario visualization, and user review log.
- [Codex project instructions](AGENTS.md): repository-wide implementation and data-handling requirements.

## Run the commuter tools

Python 3.12+ and Node 22+ are sufficient; no package installation is required.

```sh
python -m unittest discover -s CMBT/tests -v
node CMBT/tests/model.test.mjs
python -m CMBT.build_site
```

The last command generates local static assets in `Commuter/` with a pending-data notice. It does not publish a site or include unapproved data. See the [CMBT runbook](CMBT/README.md#runbook) for source inspection, weekly ingest, baseline review and approved release instructions.

Dropbox retains source CSVs. GitHub Releases retain dated, compressed processed snapshots. Git and Pages contain the code and a small current-data manifest; processed files are never committed to the repository.
