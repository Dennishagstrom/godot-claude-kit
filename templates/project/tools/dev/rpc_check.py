#!/usr/bin/env python3
"""RPC parity check: lists every @rpc function (file, name, annotation, parameters, order)
in two git revisions and reports what was removed, moved or changed.

Godot matches RPCs by node path and by the node script's RPC list, so every peer must
declare the same RPCs in the same scripts. A refactor that drops or moves one (a
split, a rename) breaks multiplayer silently: no error on the host, a desync or
"RPC not found" on clients, and only for late joiners or rare paths.

    python3 -I tools/dev/rpc_check.py                    # working tree vs HEAD
    python3 -I tools/dev/rpc_check.py --base main --head task/x
    python3 -I tools/dev/rpc_check.py --list             # the RPCs of the working tree

Exit 1 when an RPC was removed, moved to another script or changed. That is fine when
it is the point of the change: say so in the commit/handoff (every player then needs
the new build). tools/dev/finish_worktree.sh runs it before merging (RPC_OK=1 to accept).
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RPC = re.compile(r"^@rpc(\([^)]*\))?\s*(?:\n|\s)*(?:static\s+)?func\s+(\w+)\s*\(([^)]*)\)", re.M)
SKIP = ("tests/", "addons/", ".godot/")


def git(*args):
    return subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True, text=True)


def files_at(rev):
    if rev is None:
        out = git("ls-files", "--cached", "--others", "--exclude-standard").stdout
        return [f for f in out.splitlines() if f.endswith(".gd") and os.path.exists(os.path.join(ROOT, f))]
    out = git("ls-tree", "-r", "--name-only", rev).stdout
    return [f for f in out.splitlines() if f.endswith(".gd")]


def read_at(rev, path):
    if rev is None:
        with open(os.path.join(ROOT, path), encoding="utf-8", errors="replace") as f:
            return f.read()
    return git("show", "%s:%s" % (rev, path)).stdout


def rpcs(rev):
    """{(file, name): (annotation, params, index)}"""
    found = {}
    for path in files_at(rev):
        if path.startswith(SKIP):
            continue
        text = read_at(rev, path)
        if "@rpc" not in text:
            continue
        for i, m in enumerate(RPC.finditer(text)):
            params = re.sub(r"\s+", " ", m.group(3)).strip()
            found[(path, m.group(2))] = (re.sub(r"\s+", "", m.group(1) or "()"), params, i)
    return found


def compare(base, head):
    problems = []
    by_name = {}
    for (path, name) in head:
        by_name.setdefault(name, []).append(path)
    for key, (ann, params, idx) in sorted(base.items()):
        path, name = key
        if key not in head:
            moved = by_name.get(name)
            problems.append("%s %s.%s%s" % ("MOVED  " if moved else "REMOVED", path, name,
                                            " -> " + ", ".join(moved) if moved else ""))
            continue
        h_ann, h_params, h_idx = head[key]
        if (ann, params) != (h_ann, h_params):
            problems.append("CHANGED %s.%s: @rpc%s (%s) -> @rpc%s (%s)" % (path, name, ann, params, h_ann, h_params))
    for path in sorted({p for p, _ in base} & {p for p, _ in head}):
        order_b = [n for (p, n), v in sorted(base.items(), key=lambda kv: kv[1][2]) if p == path]
        order_h = [n for (p, n), v in sorted(head.items(), key=lambda kv: kv[1][2]) if p == path]
        common = [n for n in order_b if n in order_h]
        if common != [n for n in order_h if n in order_b]:
            problems.append("ORDER   %s: %s -> %s" % (path, ", ".join(order_b), ", ".join(order_h)))
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="HEAD", help="revision to compare against (default HEAD)")
    ap.add_argument("--head", help="revision to check (default: the working tree)")
    ap.add_argument("--list", action="store_true", help="print the RPCs of --head and exit")
    opts = ap.parse_args()
    head = rpcs(opts.head)
    if opts.list:
        for (path, name), (ann, params, _) in sorted(head.items()):
            print("%s %s(%s) @rpc%s" % (path, name, params, ann))
        return 0
    if git("rev-parse", "--verify", "-q", opts.base).returncode != 0:
        print("RPC CHECK SKIP: no revision %s" % opts.base)
        return 0
    base = rpcs(opts.base)
    problems = compare(base, head)
    added = sorted("%s.%s" % k for k in head if k not in base)
    for line in problems:
        print(line)
    if added:
        print("added: " + ", ".join(added))
    if problems:
        print("RPC CHECK FAIL: %d RPC(s) removed/moved/changed vs %s. Intended? Then every player needs the "
              "new build; say so in the handoff (finish_worktree.sh: RPC_OK=1)." % (len(problems), opts.base))
        return 1
    print("RPC CHECK PASS: %d RPCs, none removed or changed vs %s" % (len(head), opts.base))
    return 0


if __name__ == "__main__":
    sys.exit(main())
