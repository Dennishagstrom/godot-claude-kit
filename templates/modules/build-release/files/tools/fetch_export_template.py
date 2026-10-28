#!/usr/bin/env python3
"""Installs only the export templates a preset needs, not the whole 1.3 GB pack.

Godot's export templates come as one .tpz (a zip) with every platform inside. This
reads the zip's index over HTTP range requests and downloads just the files you ask
for (macOS: ~125 MB instead of 1.3 GB, about 15 s), into the folder Godot looks in.

  python3 -I tools/fetch_export_template.py macOS            # what the macOS preset needs
  python3 -I tools/fetch_export_template.py Windows macOS
  python3 -I tools/fetch_export_template.py --list           # what the pack holds
  options: --godot-version 4.7.2.stable  --dest DIR  --dry-run

The Godot version comes from `$GODOT --version` (tools/dev/godot_env.sh) unless given.
Uses curl (macOS, Linux and Windows 10+ have it), so no Python certificates are needed.
"""
import argparse
import io
import os
import platform
import re
import subprocess
import sys
import zipfile
from pathlib import Path

# Preset name -> files inside the pack's templates/ folder.
PRESET_FILES = {
    "windows": ["windows_release_x86_64.exe", "windows_debug_x86_64.exe"],
    "macos": ["macos.zip"],
    "linux": ["linux_release.x86_64", "linux_debug.x86_64"],
    "web": ["web_release.zip", "web_debug.zip", "web_nothreads_release.zip", "web_nothreads_debug.zip"],
    "android": ["android_release.apk", "android_debug.apk", "android_source.zip"],
}
# Bytes per HTTP request; zipfile reads in small pieces, so reads are cached per block.
BLOCK = 8 * 1024 * 1024


def curl(*args: str) -> bytes:
    out = subprocess.run(["curl", "-sSfL", "--retry", "3", *args], capture_output=True)
    if out.returncode != 0:
        raise SystemExit("curl failed (%d): %s" % (out.returncode, out.stderr.decode(errors="replace").strip()))
    return out.stdout


class RemoteFile(io.RawIOBase):
    """A read-only, seekable view of a file on a server that supports Range requests."""

    def __init__(self, url: str) -> None:
        super().__init__()
        meta = subprocess.run(["curl", "-sSIL", "-o", os.devnull, "-w", "%{url_effective} %{http_code}", url],
                              capture_output=True, text=True).stdout.split()
        if len(meta) != 2 or meta[1] != "200":
            raise SystemExit("not found: %s (HTTP %s)" % (url, meta[-1] if meta else "?"))
        self.url = meta[0]
        head = curl("-I", self.url).decode(errors="replace")
        sizes = re.findall(r"(?im)^content-length:\s*(\d+)", head)
        if not sizes:
            raise SystemExit("server gave no size for %s" % url)
        self.size = int(sizes[-1])
        self.pos = 0
        self.requests = 0
        self._cache: dict[int, bytes] = {}

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def _block(self, index: int) -> bytes:
        if index not in self._cache:
            if len(self._cache) > 4:
                self._cache.clear()
            start = index * BLOCK
            end = min(start + BLOCK, self.size) - 1
            self._cache[index] = curl("-r", "%d-%d" % (start, end), self.url)
            self.requests += 1
        return self._cache[index]

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        parts = []
        while n > 0:
            block = self._block(self.pos // BLOCK)
            offset = self.pos % BLOCK
            piece = block[offset:offset + n]
            if not piece:
                break
            parts.append(piece)
            self.pos += len(piece)
            n -= len(piece)
        return b"".join(parts)

    def readinto(self, buffer) -> int:
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)


def godot_version() -> str:
    godot = os.environ.get("GODOT", "")
    if not godot:
        here = Path(__file__).resolve().parent
        out = subprocess.run(["bash", "-c", "source '%s' >/dev/null && printf %%s \"$GODOT\"" % (here / "dev" / "godot_env.sh")],
                             capture_output=True, text=True)
        godot = out.stdout.strip()
    if not godot:
        raise SystemExit("Godot not found: set GODOT=/path/to/godot or pass --godot-version 4.x.y.stable")
    return subprocess.run([godot, "--version"], capture_output=True, text=True).stdout.strip()


def parse_version(raw: str) -> tuple[str, str, bool]:
    """'4.7.2.stable.official.abc' -> ('4.7.2.stable', '4.7.2-stable', mono?)."""
    m = re.match(r"^(\d+\.\d+(?:\.\d+)?)\.([a-z0-9]+)", raw)
    if not m:
        raise SystemExit("can't read a Godot version from %r" % raw)
    mono = ".mono" in raw
    folder = "%s.%s%s" % (m.group(1), m.group(2), ".mono" if mono else "")
    return folder, "%s-%s" % (m.group(1), m.group(2)), mono


def pack_url(tag: str, mono: bool) -> str:
    repo = "godot" if tag.endswith("-stable") else "godot-builds"
    return "https://github.com/godotengine/%s/releases/download/%s/Godot_v%s%s_export_templates.tpz" % (
        repo, tag, tag, "_mono" if mono else "")


def templates_root() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/Godot/export_templates"
    if system == "Windows" or os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "Godot/export_templates"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "godot/export_templates"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("presets", nargs="*", help="preset or platform names: Windows, macOS, Linux, Web, Android")
    ap.add_argument("--godot-version", help="e.g. 4.7.2.stable (default: $GODOT --version)")
    ap.add_argument("--dest", help="templates folder (default: where Godot looks, plus the version)")
    ap.add_argument("--list", action="store_true", help="list the pack's files and exit")
    ap.add_argument("--dry-run", action="store_true", help="say what would be downloaded")
    args = ap.parse_args()
    if not args.presets and not args.list:
        ap.error("name at least one preset (e.g. macOS) or use --list")
    folder, tag, mono = parse_version(args.godot_version or godot_version())
    dest = Path(args.dest) if args.dest else templates_root() / folder
    url = pack_url(tag, mono)
    remote = RemoteFile(url)
    pack = zipfile.ZipFile(io.BufferedReader(remote, BLOCK))
    entries = {Path(i.filename).name: i for i in pack.infolist() if not i.is_dir()}
    if args.list:
        for name, info in sorted(entries.items()):
            print("%8.1f MB  %s" % (info.file_size / 1e6, name))
        return 0
    wanted = ["version.txt"]
    for preset in args.presets:
        files = PRESET_FILES.get(preset.lower())
        if files is None:
            raise SystemExit("unknown preset %r (known: %s)" % (preset, ", ".join(PRESET_FILES)))
        wanted += [f for f in files if f in entries]
    print("Godot %s templates from %s" % (folder, url))
    print("pack %.0f MB; fetching %.0f MB into %s" % (
        remote.size / 1e6, sum(entries[f].file_size for f in wanted) / 1e6, dest))
    if args.dry_run:
        print("\n".join("  " + f for f in wanted))
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    for name in wanted:
        target = dest / name
        if target.exists() and target.stat().st_size == entries[name].file_size:
            print("  %s: already there" % name)
            continue
        tmp = target.with_name(target.name + ".part")
        with pack.open(entries[name]) as src, open(tmp, "wb") as out:
            while chunk := src.read(BLOCK):
                out.write(chunk)
        tmp.replace(target)
        print("  %s: %.1f MB" % (name, entries[name].file_size / 1e6))
    print("done in %d requests" % remote.requests)
    return 0


if __name__ == "__main__":
    sys.exit(main())
