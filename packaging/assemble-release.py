#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
PROTOCOL = 2
FLASH_SIZE = 4 * 1024 * 1024


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_image(source: Path, destination: Path, name: str, address: int) -> dict:
    if not source.is_file():
        raise SystemExit(f"missing build artifact: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    size = destination.stat().st_size
    if address + size > FLASH_SIZE:
        raise SystemExit(f"{name} does not fit in 4 MB flash at {address:#x}")
    return {
        "name": name,
        "file": destination.name,
        "address": address,
        "size": size,
        "sha256": digest(destination),
    }


def merge(images: list[dict], directory: Path, output: Path) -> None:
    command = [
        sys.executable, "-m", "esptool", "--chip", "esp32s3", "merge_bin",
        "--output", str(output), "--flash_mode", "dio", "--flash_freq", "80m",
        "--flash_size", "4MB",
    ]
    for image in images:
        command.extend([hex(image["address"]), str(directory / image["file"])])
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--firmware-build", type=Path, required=True)
    parser.add_argument("--recovery-build", type=Path, required=True)
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "release")
    parser.add_argument("--web-root", type=Path)
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    layouts = {}
    specifications = {
        "factory": (
            args.firmware_build,
            [
                ("Bootloader", "bootloader/bootloader.bin", "bootloader.bin", 0x0),
                ("Partition table", "partition_table/partition-table.bin", "partition-table.bin", 0x8000),
                ("Unified firmware", "tiny_touch_unified.bin", "tiny_touch_unified.bin", 0x10000),
            ],
        ),
        "recovery": (
            args.recovery_build,
            [
                ("Bootloader", "bootloader/bootloader.bin", "bootloader.bin", 0x0),
                ("Partition table", "partition_table/partition-table.bin", "partition-table.bin", 0x8000),
                ("Recovery firmware", "tiny_touch_unified.bin", "tiny_touch_recovery.bin", 0x10000),
            ],
        ),
    }
    for kind, (build, files) in specifications.items():
        directory = output / kind
        images = [
            copy_image(build / source, directory / destination, name, address)
            for name, source, destination, address in files
        ]
        full_name = "tiny_touch_factory_full.bin" if kind == "factory" else "tiny_touch_recovery_full.bin"
        merge(images, directory, directory / full_name)
        layouts[kind] = {
            "version": VERSION,
            "protocol": PROTOCOL,
            "flashSize": "4MB",
            "eraseAll": kind == "recovery",
            "compress": False,
            "images": images,
            "fullImage": {
                "file": full_name,
                "size": (directory / full_name).stat().st_size,
                "sha256": digest(directory / full_name),
            },
        }
        (directory / "manifest.json").write_text(
            json.dumps(layouts[kind], indent=2) + "\n", encoding="utf-8"
        )

    release = {"version": VERSION, "protocol": PROTOCOL, "firmware": layouts}
    if args.cli:
        cli_target = output / "tinytouch-macos-arm64"
        shutil.copy2(args.cli, cli_target)
        release["cli"] = {
            "file": cli_target.name,
            "size": cli_target.stat().st_size,
            "sha256": digest(cli_target),
        }
    (output / "release-manifest.json").write_text(
        json.dumps(release, indent=2) + "\n", encoding="utf-8"
    )

    checksum_lines = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "checksums.txt":
            checksum_lines.append(f"{digest(path)}  {path.relative_to(output)}")
    (output / "checksums.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    if args.web_root:
        for kind, site_name in (("factory", "flasher"), ("recovery", "recovery")):
            site = args.web_root / site_name
            firmware = site / "firmware"
            firmware.mkdir(parents=True, exist_ok=True)
            for path in (output / kind).iterdir():
                target = site / "manifest.json" if path.name == "manifest.json" else firmware / path.name
                shutil.copy2(path, target)


if __name__ == "__main__":
    main()
