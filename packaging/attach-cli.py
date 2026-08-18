#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("release", type=Path)
    parser.add_argument("cli", type=Path)
    args = parser.parse_args()
    release = args.release.resolve()
    target = release / "tinytouch-macos-arm64"
    shutil.copy2(args.cli, target)
    target.chmod(0o755)
    manifest_path = release / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["cli"] = {
        "file": target.name,
        "size": target.stat().st_size,
        "sha256": digest(target),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    lines = []
    for path in sorted(release.rglob("*")):
        if path.is_file() and path.name != "checksums.txt":
            lines.append(f"{digest(path)}  {path.relative_to(release)}")
    (release / "checksums.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
