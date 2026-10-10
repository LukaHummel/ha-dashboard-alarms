"""Generate metadata/chime and package a self-contained manual installation.

Run with Python 3.12+; no third-party build dependencies.
"""

import json
import math
import shutil
from pathlib import Path
import struct
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/dashboard_alarms"
VERSION = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))["version"]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


def metadata():
    fields = {"name": "Calendar name", "media_players": "Default media players", "sound": "Default sound URL or media-source URI",
              "snooze_minutes": "Default snooze minutes", "ring_minutes": "Maximum ring minutes"}
    strings = {
        "title": "Dashboard Alarms",
        "config": {"step": {"user": {"title": "Set up Dashboard Alarms", "description": "Create an alarm calendar. Times use Home Assistant's timezone. Leave media players empty for events-only operation.", "data": fields}},
                   "error": {"invalid_settings": "Enter a name, a valid sound path/URL, and whole minutes between 1 and 120."}},
        "options": {"step": {"init": {"title": "Alarm defaults", "data": fields}},
                    "error": {"invalid_settings": "Enter a name, a valid sound path/URL, and whole minutes between 1 and 120."}},
    }
    write_json(COMPONENT / "strings.json", strings)
    write_json(COMPONENT / "translations/en.json", strings)
    services = {}
    descriptions = {
        "create_alarm": "Create a persistent calendar alarm. Returns its UID.",
        "update_alarm": "Update the complete alarm schedule while preserving its UID.",
        "set_enabled": "Enable or disable a schedule without deleting it.",
        "delete_alarm": "Delete the complete alarm schedule.",
        "snooze": "Postpone the ringing occurrence without changing recurrence.",
        "dismiss": "End ringing or cancel a pending snooze; retain the schedule.",
    }
    for name, description in descriptions.items():
        item_fields = {
            "entity_id": {"name": "Alarm calendar", "required": True,
                          "selector": {"entity": {"domain": "calendar", "integration": "dashboard_alarms"}}},
        }
        if name != "create_alarm":
            item_fields["uid"] = {"name": "Alarm UID", "required": True, "selector": {"text": {}}}
        if name in ("create_alarm", "update_alarm", "set_enabled"):
            item_fields["alarm"] = {"name": "Alarm settings", "required": True, "selector": {"object": {}},
                                    "description": "For enable/disable: {enabled: true}. For create/update: start, repeat, weekdays, enabled, description, audio."}
        if name == "snooze":
            item_fields["minutes"] = {"name": "Snooze minutes", "selector": {"number": {"min": 1, "max": 120, "mode": "box"}}}
        services[name] = {"name": name.replace("_", " ").capitalize(), "description": description, "fields": item_fields}
    # JSON is valid YAML and avoids requiring PyYAML to build the release.
    write_json(COMPONENT / "services.yaml", services)


def chime():
    path = COMPONENT / "frontend/chime.wav"
    sample_rate = 22050
    samples = bytearray()
    for index in range(sample_rate * 3):
        time = index / sample_rate
        sample = 0.0
        for begin, frequency in ((0, 660), (0.55, 880), (1.1, 1100)):
            elapsed = time - begin
            if 0 <= elapsed < 1.4:
                envelope = min(1, elapsed / 0.015) * math.exp(-3.3 * elapsed)
                sample += envelope * (math.sin(2 * math.pi * frequency * elapsed)
                                      + .2 * math.sin(2 * math.pi * frequency * 2 * elapsed)) * .22
        samples += struct.pack("<h", int(max(-1, min(1, sample)) * 32767))
    with wave.Wave_write(str(path)) as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(samples)


def package():
    output = ROOT / f"outputs/dashboard-alarms-{VERSION}.zip"
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(COMPONENT.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(ROOT).as_posix())
        for path in (ROOT / "README.md", ROOT / "LICENSE", ROOT / "hacs.json", ROOT / "examples/dashboard.yaml"):
            archive.write(path, path.relative_to(ROOT).as_posix())
    print(f"Built {output}")
    shutil.copyfile(ROOT / "README.md", ROOT / "outputs/Dashboard Alarms setup.md")
    source = ROOT / f"outputs/dashboard-alarms-source-{VERSION}.zip"
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        for directory in ("custom_components/dashboard_alarms", "tests", "tools", "examples", ".github/workflows"):
            for path in sorted((ROOT / directory).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    archive.write(path, path.relative_to(ROOT).as_posix())
        for name in ("README.md", "AGENTS.md", "release-notes.md", "LICENSE", "hacs.json", "pyproject.toml", "requirements-dev.txt",
                     "package.json", "package-lock.json", ".gitignore", ".gitattributes"):
            archive.write(ROOT / name, name)
    print(f"Built {source}")


if __name__ == "__main__":
    metadata()
    chime()
    package()
