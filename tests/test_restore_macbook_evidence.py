"""Transfer tests: no network and no real research records."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest

path = Path(__file__).resolve().parents[1] / "scripts/restore_macbook_evidence.py"
spec = importlib.util.spec_from_file_location("restore_evidence", path)
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)


def bundle(tmp_path, files=None, link=False):
    files = files or {"sample/a.txt": b"original", "sample/b.txt": b"evidence"}
    archive = tmp_path / "evidence.tar.gz"
    with tarfile.open(archive, "w:gz") as package:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            if link:
                member.type = tarfile.SYMTYPE
                member.linkname = "outside"
                member.size = 0
            package.addfile(member, None if link else io.BytesIO(data))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "archive": {
                    "bytes": archive.stat().st_size,
                    "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                },
                "files": {
                    name: {
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                    for name, data in files.items()
                },
            }
        )
    )
    return archive, manifest


def test_restore_is_exact_and_repeat_preserves_existing_files(tmp_path):
    archive, manifest = bundle(tmp_path)
    destination = tmp_path / "restored"
    assert transfer.restore(archive, destination, manifest) == {
        "verified": 2,
        "restored": 2,
        "already_present": 0,
    }
    first = (destination / "sample/a.txt").stat().st_mtime_ns
    assert transfer.restore(archive, destination, manifest) == {
        "verified": 2,
        "restored": 0,
        "already_present": 2,
    }
    assert (destination / "sample/a.txt").read_bytes() == b"original"
    assert (destination / "sample/a.txt").stat().st_mtime_ns == first


def test_conflict_is_found_before_writing_any_new_file(tmp_path):
    archive, manifest = bundle(tmp_path)
    destination = tmp_path / "restored"
    (destination / "sample").mkdir(parents=True)
    (destination / "sample/b.txt").write_bytes(b"active work")
    with pytest.raises(ValueError, match="overwrite"):
        transfer.restore(archive, destination, manifest)
    assert not (destination / "sample/a.txt").exists()
    assert (destination / "sample/b.txt").read_bytes() == b"active work"


def test_tampered_archive_creates_no_output(tmp_path):
    archive, manifest = bundle(tmp_path)
    with archive.open("ab") as stream:
        stream.write(b"corruption")
    with pytest.raises(ValueError, match="archive size/hash"):
        transfer.restore(archive, tmp_path / "restored", manifest)
    assert not (tmp_path / "restored").exists()


@pytest.mark.parametrize(
    "name,link", [("../escape", False), ("sample/link", True), ("C:/escape", False)]
)
def test_unsafe_members_are_rejected(tmp_path, name, link):
    archive, manifest = bundle(tmp_path, {name: b"bad"}, link=link)
    with pytest.raises(ValueError, match="unsafe"):
        transfer.restore(archive, tmp_path / "restored", manifest)


def test_verify_only_reads_every_member_without_creating_a_destination(tmp_path):
    archive, manifest = bundle(tmp_path)
    destination = tmp_path / "restored"
    result = transfer.restore(archive, destination, manifest, verify_only=True)
    assert result == {"verified": 2, "restored": 0, "already_present": 0}
    assert not destination.exists()
