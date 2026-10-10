"""Release metadata failures must block publication before creating output."""

import json

import pytest

from tools.verify_release import verify_release


@pytest.fixture
def release_root(tmp_path):
    """A minimal release independent of the integration's runtime imports."""
    component = tmp_path / "custom_components/dashboard_alarms"
    component.mkdir(parents=True)
    (component / "manifest.json").write_text('{"version": "1.2.3"}', encoding="utf-8")
    (component / "const.py").write_text('VERSION = "1.2.3"\n', encoding="utf-8")
    (tmp_path / "package.json").write_text('{"version": "1.2.3"}', encoding="utf-8")
    (tmp_path / "package-lock.json").write_text(
        '{"version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}', encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
        "Resource: `/dashboard_alarms/dashboard-alarms-card.js?v=1.2.3`\n", encoding="utf-8"
    )
    (tmp_path / "release-notes.md").write_text("# 1.2.3\n\nFix alarm playback.\n", encoding="utf-8")
    return tmp_path


def test_matching_release(release_root):
    assert verify_release(release_root, "v1.2.3") == ("1.2.3", "Fix alarm playback.\n")


@pytest.mark.parametrize("tag", ["v1.2.4", "1.2.3", "v1.2.3-rc.1", "v1.2.3/extra"])
def test_wrong_tag_is_rejected(release_root, tag):
    with pytest.raises(ValueError, match="Tag"):
        verify_release(release_root, tag)


@pytest.mark.parametrize("filename", ["package.json", "package-lock.json"])
def test_stale_package_version_is_rejected(release_root, filename):
    path = release_root / filename
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = "1.2.2"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=filename):
        verify_release(release_root)


def test_stale_lock_root_is_rejected(release_root):
    path = release_root / "package-lock.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["packages"][""]["version"] = "1.2.2"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="root package"):
        verify_release(release_root)


def test_stale_python_version_is_rejected(release_root):
    (release_root / "custom_components/dashboard_alarms/const.py").write_text(
        'VERSION = "1.2.2"\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="const.py"):
        verify_release(release_root)


@pytest.mark.parametrize("resource", ["", "/dashboard_alarms/dashboard-alarms-card.js?v=1.2.2"])
def test_missing_or_stale_card_resource_is_rejected(release_root, resource):
    (release_root / "README.md").write_text(resource, encoding="utf-8")
    with pytest.raises(ValueError, match="README"):
        verify_release(release_root)


@pytest.mark.parametrize("notes", ["# 1.2.2\nOld notes", "# 1.2.3\n\n"])
def test_missing_or_stale_notes_are_rejected(release_root, notes):
    (release_root / "release-notes.md").write_text(notes, encoding="utf-8")
    with pytest.raises(ValueError, match="release-notes.md"):
        verify_release(release_root)


def test_prerelease_manifest_is_rejected(release_root):
    (release_root / "custom_components/dashboard_alarms/manifest.json").write_text(
        '{"version": "1.2.3-rc.1"}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="stable"):
        verify_release(release_root)
