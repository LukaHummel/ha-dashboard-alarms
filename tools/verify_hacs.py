"""Check HACS installation layout locally; CI also runs HACS and hassfest."""

import json
from pathlib import Path
import struct
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def verify_hacs(root=ROOT):
    """Reject missing runtime assets and invalid custom-integration metadata."""
    components = root / "custom_components"
    domains = [path.name for path in components.iterdir() if path.is_dir() and path.name != "__pycache__"]
    if domains != ["dashboard_alarms"]:
        raise ValueError("HACS needs exactly one integration under custom_components: dashboard_alarms")
    component = components / domains[0]
    manifest = json.loads((component / "manifest.json").read_text(encoding="utf-8"))
    for key in ("domain", "name", "version", "documentation", "issue_tracker", "codeowners"):
        if not manifest.get(key):
            raise ValueError(f"Missing required integration manifest field: {key}")
    if manifest["domain"] != component.name:
        raise ValueError("Manifest domain must match the integration directory")
    for key in ("documentation", "issue_tracker"):
        url = urlparse(manifest[key])
        if url.scheme != "https" or not url.netloc:
            raise ValueError(f"Manifest {key} must be an HTTPS URL")
    hacs = json.loads((root / "hacs.json").read_text(encoding="utf-8"))
    if not hacs.get("name") or not hacs.get("render_readme") or hacs.get("zip_release"):
        raise ValueError("hacs.json must name the integration, render README, and use the tagged source directory")
    for name in ("README.md", "LICENSE"):
        if not (root / name).read_text(encoding="utf-8").strip():
            raise ValueError(f"{name} must have content")
    for name in ("__init__.py", "config_flow.py", "calendar.py", "strings.json", "services.yaml",
                 "translations/en.json", "frontend/dashboard-alarms-card.js",
                 "frontend/dashboard-alarms-notifications.js", "frontend/chime.wav", "brand/icon.png"):
        path = component / name
        if path.is_symlink() or not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Runtime asset must be a nonempty file inside the integration: {name}")
    icon = (component / "brand/icon.png").read_bytes()
    if len(icon) < 24 or icon[:8] != b"\x89PNG\r\n\x1a\n" or icon[12:16] != b"IHDR" or struct.unpack(
        ">II", icon[16:24]
    ) != (256, 256):
        raise ValueError("The bundled brand icon must be a 256x256 PNG")
    return manifest["domain"]


if __name__ == "__main__":
    print(f"HACS repository layout verified: {verify_hacs()}")
