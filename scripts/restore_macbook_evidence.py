"""Restore the pinned research bundle without overwriting different local files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/ai/MACBOOK_EVIDENCE_MANIFEST_20261027.json"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def restore(archive, destination, manifest_path=MANIFEST, verify_only=False):
    archive, destination = Path(archive), Path(destination).resolve()
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if (
        archive.stat().st_size != manifest["archive"]["bytes"]
        or digest(archive) != manifest["archive"]["sha256"]
    ):
        raise ValueError(
            "archive size/hash differs from the committed transfer manifest"
        )
    expected = manifest["files"]
    result = {"verified": 0, "restored": 0, "already_present": 0}
    with tarfile.open(archive, "r:gz") as package:
        members = package.getmembers()
        if len(members) != len(expected) or {m.name for m in members} != set(expected):
            raise ValueError("archive file list differs from the committed manifest")
        targets = {}
        # Complete preflight before creating any output file.
        for member in members:
            relative = PurePosixPath(member.name)
            if (
                not member.isfile()
                or relative.is_absolute()
                or ".." in relative.parts
                or "\\" in member.name
                or ":" in member.name
                or str(relative) != member.name
            ):
                raise ValueError(f"unsafe archive member: {member.name}")
            if member.size != expected[member.name]["bytes"]:
                raise ValueError(f"member size differs: {member.name}")
            target = destination.joinpath(*relative.parts)
            if not target.resolve().is_relative_to(destination) or target.is_symlink():
                raise ValueError(
                    f"destination escapes or redirects the research directory: {member.name}"
                )
            if not verify_only and target.exists():
                if (
                    not target.is_file()
                    or digest(target) != expected[member.name]["sha256"]
                ):
                    raise ValueError(
                        f"refusing to overwrite different existing file: {target}"
                    )
            targets[member.name] = target

        for member in members:
            target = targets[member.name]
            if not verify_only and target.exists():
                result["already_present"] += 1
                result["verified"] += 1
                continue
            value = hashlib.sha256()
            created = False
            output = None
            try:
                if not verify_only:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    output = target.open("xb")
                    created = True
                with package.extractfile(member) as source:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        value.update(block)
                        if output:
                            output.write(block)
                if output:
                    output.close()
                if value.hexdigest() != expected[member.name]["sha256"]:
                    raise ValueError(f"member hash differs: {member.name}")
                result["verified"] += 1
                if created:
                    if member.name.startswith(
                        "live_movers_contract_20261027_production/"
                    ):
                        target.chmod(0o444)
                    result["restored"] += 1
            except BaseException:
                if output and not output.closed:
                    output.close()
                if created:
                    target.unlink()  # only this newly created, preflighted file
                raise
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument(
        "--destination", type=Path, default=Path.home() / ".moonwalking/analysis"
    )
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            restore(args.archive, args.destination, args.manifest, args.verify_only),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
