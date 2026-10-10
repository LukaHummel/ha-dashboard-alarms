"""Repository checks must reject files HACS cannot install or validate."""

import shutil

import pytest

from tools.verify_hacs import ROOT, verify_hacs


@pytest.fixture
def hacs_root(tmp_path):
    component = "custom_components/dashboard_alarms"
    shutil.copytree(ROOT / component, tmp_path / component)
    for name in ("README.md", "LICENSE", "hacs.json"):
        shutil.copyfile(ROOT / name, tmp_path / name)
    return tmp_path


def test_installable_layout(hacs_root):
    assert verify_hacs(hacs_root) == "dashboard_alarms"


def test_multiple_integrations_are_rejected(hacs_root):
    (hacs_root / "custom_components/another_integration").mkdir()
    with pytest.raises(ValueError, match="exactly one integration"):
        verify_hacs(hacs_root)


def test_missing_global_controls_are_rejected(hacs_root):
    path = hacs_root / "custom_components/dashboard_alarms/frontend/dashboard-alarms-notifications.js"
    path.unlink()
    with pytest.raises(ValueError, match="Runtime asset"):
        verify_hacs(hacs_root)


def test_truncated_brand_icon_is_rejected(hacs_root):
    path = hacs_root / "custom_components/dashboard_alarms/brand/icon.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR")
    with pytest.raises(ValueError, match="256x256 PNG"):
        verify_hacs(hacs_root)
