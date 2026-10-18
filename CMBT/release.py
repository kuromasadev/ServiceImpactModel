"""Prepare a dated, approved GitHub Release asset in private working storage."""
import argparse
from datetime import date
import json
from pathlib import Path
import re
import shutil
import sys

from .pipeline import PRIVATE, private_path, sha


def identity(repository, release_date, digest):
    if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*/[A-Za-z0-9_-][A-Za-z0-9_.-]*", repository):
        raise ValueError("Repository must be OWNER/REPOSITORY")
    if date.fromisoformat(release_date).isoformat() != release_date:
        raise ValueError("Snapshot date must be YYYY-MM-DD")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Expected a complete SHA-256 digest")
    tag = f"commuter-{release_date}-{digest[:12]}"
    name = f"{tag}.csv.gz"
    return {"repository": repository, "date": release_date, "tag": tag, "asset_name": name,
            "download_url": f"https://github.com/{repository}/releases/download/{tag}/{name}"}


def reference(repository, release_date, manifest, metadata):
    """Match published Release API metadata against the locally approved bytes."""
    release = identity(repository, release_date, manifest["sha256"])
    if (metadata.get("tag_name") != release["tag"] or metadata.get("draft") is not False
            or metadata.get("prerelease") is not False
            or metadata.get("html_url") != f"https://github.com/{repository}/releases/tag/{release['tag']}"):
        raise ValueError("Published release metadata must match the dated repository/tag")
    assets = [asset for asset in metadata.get("assets", []) if asset.get("name") == release["asset_name"]]
    if len(assets) != 1:
        raise ValueError("Release must contain exactly one matching dated asset")
    asset = assets[0]
    asset_id = asset.get("id")
    if type(asset_id) is not int or asset_id <= 0:
        raise ValueError("Release asset requires a positive GitHub asset ID")
    api_url = f"https://api.github.com/repos/{repository}/releases/assets/{asset_id}"
    if (asset.get("state") != "uploaded" or asset.get("url") != api_url
            or asset.get("size") != manifest["bytes"]
            or asset.get("digest") != "sha256:" + manifest["sha256"]
            or asset.get("browser_download_url") != release["download_url"]):
        raise ValueError("Uploaded Release asset URL, digest and size must match the approved file")
    return {"dataset": api_url, "release": {**release, "asset_id": asset_id}}


def prepare(data, approval, repository, release_date):
    from .build_site import validate_release
    manifest = validate_release(data, approval)
    release = identity(repository, release_date, manifest["sha256"])
    destination = private_path(PRIVATE / "releases" / release["tag"] / release["asset_name"])
    if destination.exists() and sha(destination) != manifest["sha256"]:
        raise ValueError("Existing dated snapshot differs; preserved without overwriting")
    if not destination.exists():
        shutil.copyfile(data, destination)
    if sha(destination) != manifest["sha256"] or destination.stat().st_size != manifest["bytes"]:
        raise ValueError("Prepared snapshot differs from the approved bytes")
    descriptor = {**release, "sha256": manifest["sha256"], "bytes": manifest["bytes"],
                  "coverage_start": manifest["coverage_start"], "coverage_end": manifest["coverage_end"],
                  "rows": manifest["rows"], "pairs": manifest["pairs"]}
    (destination.parent / "release.json").write_text(json.dumps(descriptor, indent=2) + "\n")
    notes = (f"Approved unified commuter snapshot dated {release_date}.\n\n"
             f"Coverage: {manifest['coverage_start']} through {manifest['coverage_end']}.\n"
             f"SHA-256: {manifest['sha256']}\nBytes: {manifest['bytes']}\n"
             f"Aggregate rows: {manifest['rows']}; stop-pair observations: {manifest['pairs']}.\n\n"
             "Schema and metric definitions are in CMBT/schema.md in the repository.\n"
             "Raw sources remain in Dropbox. Prior dated snapshots must be retained.\n")
    (destination.parent / "release-notes.md").write_text(notes)
    return {**descriptor, "prepared_file": str(destination),
            "notes_file": str(destination.parent / "release-notes.md"), "uploaded": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--date", required=True, help="Snapshot date YYYY-MM-DD")
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.data, args.approval, args.repository, args.date), indent=2))
    except (ValueError, OSError, KeyError) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
