"""Release packaging must work from tracked files and a standalone source ZIP."""

import shutil
import subprocess
import sys
import zipfile

from tools import build


def test_source_archive_rebuilds_from_a_clean_checkout(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout"
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=build.ROOT).decode().split("\0")
    for name in filter(None, tracked):
        target = checkout / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(build.ROOT / name, target)
    assert not (checkout / ".github/HACS_SUBMISSION.md").exists()
    monkeypatch.setattr(build, "ROOT", checkout)
    monkeypatch.setattr(build, "COMPONENT", checkout / "custom_components/dashboard_alarms")
    build.package()

    installation = f"outputs/dashboard-alarms-{build.VERSION}.zip"
    source = checkout / f"outputs/dashboard-alarms-source-{build.VERSION}.zip"
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(source) as archive:
        assert archive.testzip() is None
        archive.extractall(extracted)
    subprocess.run([sys.executable, "tools/build.py"], cwd=extracted, check=True, capture_output=True)
    subprocess.run([sys.executable, "tools/verify_archive.py"], cwd=extracted, check=True, capture_output=True)
    with zipfile.ZipFile(checkout / installation) as original, zipfile.ZipFile(extracted / installation) as rebuilt:
        assert sorted(original.namelist()) == sorted(rebuilt.namelist())
        for name in original.namelist():
            assert original.read(name) == rebuilt.read(name), name
