#!/usr/bin/env python3
"""Update selected Debian packages in this Cydia repository, preserving others.

Usage:
  python3 cydia/update_game_packages.py \
      cydia/debs/MJSLocalAppearance_0.5.3_iphoneos-arm64.deb \
      cydia/debs/SGSLocalAppearance_0.4.0_iphoneos-arm64.deb

The package files must already be present. This script does not publish/push.
"""
from __future__ import annotations

import bz2
import hashlib
import io
import plistlib
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALLOWED = {
    "local.mjs.appearance": ("com.ztgame.mjs", "名将杀本地外观（Rootless）"),
    "local.sgs.appearance": ("com.yoka.newsgs", "三国杀本地外观（Rootless 测试版）"),
}
FIELDS = (
    "Package", "Version", "Architecture", "Maintainer", "Depends", "Filename",
    "Size", "MD5sum", "SHA1", "SHA256", "Section", "Priority", "Description",
    "Author", "Name"
)


def parse_control(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    key = None
    for line in text.splitlines():
        if not line:
            continue
        if line[0] in " \t":
            if key is None:
                raise ValueError("Orphan continuation line")
            result[key] += "\n" + line
        else:
            if ": " not in line:
                raise ValueError(f"Invalid Debian metadata: {line[:60]}")
            key, value = line.split(": ", 1)
            if key in result:
                raise ValueError(f"Duplicate metadata field {key}")
            result[key] = value
    return result


def extract_deb(binary: bytes) -> tuple[dict[str, str], dict[str, bytes]]:
    if not binary.startswith(b"!<arch>\n"):
        raise ValueError("Not an ar/Debian package")
    pos, members = 8, {}
    while pos < len(binary):
        hdr = binary[pos : pos + 60]
        if len(hdr) != 60 or hdr[58:60] != bytes((96, 10)):
            raise ValueError("Malformed ar member header")
        name = hdr[:16].decode("ascii").strip().rstrip("/")
        size = int(hdr[48:58].decode("ascii").strip())
        start = pos + 60
        if start + size > len(binary) or name in members:
            raise ValueError(f"Invalid/duplicate ar member: {name}")
        members[name] = binary[start : start + size]
        pos = start + size + size % 2
    if pos != len(binary) or members.get("debian-binary") != b"2.0\n":
        raise ValueError("Invalid Debian archive")
    control_part = next((v for k, v in members.items() if k.startswith("control.tar.")), None)
    data_part = next((v for k, v in members.items() if k.startswith("data.tar.")), None)
    if control_part is None or data_part is None:
        raise ValueError("Missing .deb control/data archive")

    control_bytes = None
    with tarfile.open(fileobj=io.BytesIO(control_part), mode="r:*") as archive:
        for info in archive:
            if info.isfile() and info.name.lstrip("./") == "control":
                control_bytes = archive.extractfile(info).read()
    if control_bytes is None:
        raise ValueError("No DEBIAN/control")
    filters = {}
    with tarfile.open(fileobj=io.BytesIO(data_part), mode="r:*") as archive:
        for info in archive:
            if info.isfile():
                name = info.name.removeprefix("./")
                if name.endswith(".plist") and "TweakInject/" in name:
                    filters[name] = archive.extractfile(info).read()
    return parse_control(control_bytes.decode("utf-8")), filters


def index_package(path: Path) -> tuple[str, str]:
    if path.parent.resolve() != (ROOT / "debs").resolve():
        raise ValueError("Only DEBs inside cydia/debs may be indexed")
    payload = path.read_bytes()
    meta, filters = extract_deb(payload)
    package = meta.get("Package", "")
    if package not in ALLOWED:
        raise ValueError(f"Not an approved local-appearance package: {package}")
    target, display_name = ALLOWED[package]
    if meta.get("Architecture") != "iphoneos-arm64":
        raise ValueError(f"Expected rootless arm64 package: {package}")
    if "ellekit" not in meta.get("Depends", ""):
        raise ValueError(f"Missing ElleKit dependency: {package}")
    if not filters:
        raise ValueError(f"No tweak injection filter in {package}")
    for name, content in filters.items():
        if "/var/jb/" not in "/" + name:
            raise ValueError(f"Not a rootless tweak: {name}")
        plist = plistlib.loads(content)
        if plist.get("Filter", {}).get("Bundles") != [target]:
            raise ValueError(f"Incorrect target bundle: {package} {name}")

    meta.update({
        "Filename": "debs/" + path.name,
        "Size": str(len(payload)),
        "MD5sum": hashlib.md5(payload).hexdigest(),
        "SHA1": hashlib.sha1(payload).hexdigest(),
        "SHA256": hashlib.sha256(payload).hexdigest(),
        "Priority": "optional",
        "Name": display_name,
    })
    if not meta.get("Version"):
        raise ValueError(f"Package version missing: {package}")
    if package == "local.sgs.appearance":
        meta["Description"] += "\n Rootless 0.4.0 has not been verified on 14pm; back up game data before testing."
    stanza = "\n".join(f"{k}: {meta[k]}" for k in FIELDS if k in meta)
    return package, stanza


def validate_all_indexed(data: bytes) -> tuple[int, set[str]]:
    blocks = [x for x in data.decode("utf-8").strip().split("\n\n") if x.strip()]
    packages = set()
    for block in blocks:
        meta = parse_control(block)
        package = meta.get("Package")
        if not package or package in packages:
            raise ValueError(f"Duplicate or missing package {package}")
        packages.add(package)
        filename = meta.get("Filename", "")
        file = ROOT / filename
        if file.parent.resolve() != (ROOT / "debs").resolve() or not file.is_file():
            raise ValueError(f"Invalid package file: {filename}")
        payload = file.read_bytes()
        for key, expected in (
            ("Size", str(len(payload))),
            ("MD5sum", hashlib.md5(payload).hexdigest()),
            ("SHA1", hashlib.sha1(payload).hexdigest()),
            ("SHA256", hashlib.sha256(payload).hexdigest()),
        ):
            if meta.get(key) != expected:
                raise ValueError(f"Package {package} {key} mismatch")
    return len(blocks), packages


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit("Provide one or more DEBs already inside cydia/debs")
    entries = {}
    for name in argv:
        path = Path(name).resolve()
        package, stanza = index_package(path)
        if package in entries:
            raise ValueError(f"Repeated package argument: {package}")
        entries[package] = stanza
    index_path = ROOT / "Packages"
    old = index_path.read_text("utf-8")
    if bz2.decompress((ROOT / "Packages.bz2").read_bytes()) != old.encode():
        raise ValueError("Existing compressed source index is out of sync")

    preserved = []
    for old_stanza in [x for x in old.strip().split("\n\n") if x.strip()]:
        package = parse_control(old_stanza)["Package"]
        if package not in entries:
            preserved.append(old_stanza)
    # Keep unrelated stanzas in their original order. Update these IDs only.
    blocks = preserved + [entries[p] for p in sorted(entries)]
    output = ("\n\n".join(blocks) + "\n").encode("utf-8")
    before, _ = validate_all_indexed(old.encode())
    after, ids = validate_all_indexed(output)
    if not set(entries).issubset(ids):
        raise AssertionError("Indexed packages missing after rebuild")
    if after < before:
        raise AssertionError("Unrelated packages were lost")
    compressed = bz2.compress(output, compresslevel=9)
    if bz2.decompress(compressed) != output:
        raise AssertionError("bz2 round-trip failed")
    index_path.write_bytes(output)
    (ROOT / "Packages.bz2").write_bytes(compressed)
    print(f"Indexed {after} total packages ({before} existing), added/updated: {list(sorted(entries))}")
    print(f"Packages {len(output)} bytes, Packages.bz2 {len(compressed)} bytes")
    print("All recorded DEB sizes and hashes verified")


if __name__ == "__main__":
    main(sys.argv[1:])
