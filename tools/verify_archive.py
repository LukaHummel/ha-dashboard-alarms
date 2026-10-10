"""Check release contents and syntax without importing Home Assistant."""

import ast
from io import BytesIO
import json
from pathlib import Path
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[1]
version = json.loads((ROOT / "custom_components/dashboard_alarms/manifest.json").read_text(encoding="utf-8"))["version"]
path = ROOT / f"outputs/dashboard-alarms-{version}.zip"
with zipfile.ZipFile(path) as archive:
    names = archive.namelist()
    assert archive.testzip() is None
    assert not any("work/" in name or "__pycache__" in name for name in names)
    prefix = "custom_components/dashboard_alarms/"
    for name in ("manifest.json", "config_flow.py", "calendar.py", "api.py", "model.py", "manager.py", "audio.py",
                 "frontend/dashboard-alarms-card.js", "frontend/dashboard-alarms-notifications.js", "frontend/chime.wav",
                 "brand/icon.png", "translations/en.json", "services.yaml"):
        assert prefix + name in names, name
    for name in names:
        if name.endswith(".py"):
            ast.parse(archive.read(name).decode(), filename=name)
        if name.endswith(".json") or name.endswith("services.yaml"):
            json.loads(archive.read(name))
    manifest = json.loads(archive.read(prefix + "manifest.json"))
    assert manifest["version"] == version and manifest["domain"] == "dashboard_alarms"
    with wave.open(BytesIO(archive.read(prefix + "frontend/chime.wav"))) as chime:
        assert chime.getnframes() / chime.getframerate() == 3
        assert chime.getnchannels() == 1
print(f"Release archive verified: {len(names)} files, valid Python/JSON metadata, bundled 3-second WAV chime.")
