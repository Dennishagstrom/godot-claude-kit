#!/usr/bin/env python3
"""Player-facing patch notes.

Every task branch adds one fragment, data/patch_notes/unreleased/<task>.txt, with one
line per player-visible change:

    new: A second level with moving platforms.
    change: Jumping is a little higher.
    fix: The pause menu no longer opens behind the map.

One file per task, so parallel branches never conflict. A build stamps them into
data/patch_notes/releases.json (newest first), which the game shows as "What's new":

    python3 -I tools/patch_notes.py --check                  # list unreleased notes, validate
    python3 -I tools/patch_notes.py --release 0.3.2 7        # stamp + delete the fragments
    python3 -I tools/patch_notes.py --release 0.3.2 7 --dry  # show what would be stamped
    python3 -I tools/patch_notes.py --dir /tmp/notes --check # another notes folder (tests)

tools/build_release.sh runs --release with the new version/build automatically.
"""

import argparse
import datetime
import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NOTES_DIR = os.path.join(ROOT, "data", "patch_notes")
UNRELEASED = os.path.join(NOTES_DIR, "unreleased")
RELEASES = os.path.join(NOTES_DIR, "releases.json")
KINDS = ["new", "change", "fix"]


def set_notes_dir(path):
    global NOTES_DIR, UNRELEASED, RELEASES
    NOTES_DIR = os.path.abspath(path)
    UNRELEASED = os.path.join(NOTES_DIR, "unreleased")
    RELEASES = os.path.join(NOTES_DIR, "releases.json")


def read_fragments():
    """Returns ({kind: [text]}, [problems], [files])."""
    notes = {k: [] for k in KINDS}
    problems = []
    files = sorted(glob.glob(os.path.join(UNRELEASED, "*.txt")))
    for path in files:
        name = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                kind, sep, text = line.partition(":")
                kind, text = kind.strip().lower(), text.strip()
                if not sep or kind not in KINDS or not text:
                    problems.append(f"{name}:{n}: expected 'new|change|fix: text', got {line!r}")
                    continue
                if text not in notes[kind]:
                    notes[kind].append(text)
    return notes, problems, files


def load_releases():
    if not os.path.exists(RELEASES):
        return []
    with open(RELEASES, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--release", nargs=2, metavar=("VERSION", "BUILD"))
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--dir", help="patch notes folder (default data/patch_notes)")
    args = ap.parse_args()
    if args.dir:
        set_notes_dir(args.dir)

    notes, problems, files = read_fragments()
    for p in problems:
        print("ERROR", p)
    if problems:
        return 1

    if args.release:
        version, build = args.release[0], int(args.release[1])
        if not any(notes.values()):
            print("no unreleased patch notes")
            return 0
        entry = {"version": version, "build": build,
                 "date": datetime.date.today().isoformat(), "notes": notes}
        releases = [r for r in load_releases() if r.get("build") != build]
        releases.insert(0, entry)
        print(json.dumps(entry, indent=2, ensure_ascii=False))
        if args.dry:
            return 0
        with open(RELEASES, "w", encoding="utf-8") as f:
            json.dump(releases, f, indent=2, ensure_ascii=False)
            f.write("\n")
        for path in files:
            os.remove(path)
        print(f"stamped {sum(len(v) for v in notes.values())} notes into {os.path.relpath(RELEASES, ROOT)}")
        return 0

    total = 0
    for kind in KINDS:
        for text in notes[kind]:
            print(f"{kind:7} {text}")
            total += 1
    print(f"{total} unreleased notes in {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
