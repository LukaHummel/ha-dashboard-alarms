"""Validate versions and release notes without importing Home Assistant."""

import argparse
import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def verify_release(root=ROOT, tag=None):
    """Return a consistent stable version and its release notes, or fail."""
    component = root / "custom_components/dashboard_alarms"
    version = json.loads((component / "manifest.json").read_text(encoding="utf-8"))["version"]
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("Use a stable X.Y.Z version in manifest.json")
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"Tag {tag!r} must match manifest version v{version}")

    constants = ast.parse((component / "const.py").read_text(encoding="utf-8"))
    constant_version = next(
        ast.literal_eval(node.value) for node in constants.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets)
    )
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    versions = {
        "const.py": constant_version,
        "package.json": package["version"],
        "package-lock.json": lock["version"],
        "package-lock.json root package": lock["packages"][""]["version"],
        "Release Please manifest": json.loads(
            (root / ".release-please-manifest.json").read_text(encoding="utf-8")
        )["."],
    }
    for name, value in versions.items():
        if value != version:
            raise ValueError(f"{name} version {value!r} must match manifest version {version}")
    readme = (root / "README.md").read_text(encoding="utf-8")
    resource_versions = re.findall(r"/dashboard_alarms/dashboard-alarms-card\.js\?v=([^\s`]+)", readme)
    if not resource_versions or any(value != version for value in resource_versions):
        raise ValueError("README card resource versions must match manifest.json")

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    sections = list(re.finditer(r"^## \[?([0-9]+\.[0-9]+\.[0-9]+)(?:\]|[ \t]|$).*", changelog, re.MULTILINE))
    if not sections or sections[0].group(1) != version:
        raise ValueError(f"CHANGELOG.md must start with release notes for {version}")
    end = sections[1].start() if len(sections) > 1 else len(changelog)
    notes = changelog[sections[0].end():end].strip()
    if not notes:
        raise ValueError(f"CHANGELOG.md must contain release notes for {version}")
    return version, notes.strip() + "\n"


def main():
    """Check local or tagged metadata and optionally prepare workflow outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Expected release tag, in vX.Y.Z form")
    parser.add_argument("--notes-output", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        version, notes = verify_release(tag=args.tag)
    except (ValueError, KeyError, OSError, StopIteration) as err:
        parser.exit(1, f"Release metadata invalid: {err}\n")
    if args.notes_output:
        args.notes_output.parent.mkdir(parents=True, exist_ok=True)
        args.notes_output.write_text(notes, encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"version={version}\n")
    print(f"Release metadata verified: {version}")


if __name__ == "__main__":
    main()
