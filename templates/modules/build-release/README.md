# Module: build-release

TL;DR: `tools/build_release.sh` bumps the build number, stamps the patch notes,
exports, zips and smoke-tests the export headless. Players see "What's new"
once per new build.{{#MULTIPLAYER}} Joining checks version + build, so friends on
different zips get a clear message instead of desyncs.{{/MULTIPLAYER}}

## Release

```bash
tools/build_release.sh --check     # setup ok? (version, presets, main scene, notes, export templates)
tools/build_release.sh             # bump build, stamp notes, export Windows, zip, smoke test
tools/build_release.sh --mac       # also the macOS preset; --no-bump, --no-smoke
```

- Version: `application/config/version` in project.godot (you change it).
  Build number: `scripts/build_info.gd` (`BuildInfo.NUMBER`, the script bumps it;
  0 = running from source, shown as "dev"). Commit both after a release.
- Presets: `export_presets.cfg` ("Windows", "macOS"; edit in Project > Export).
  Needs the export templates (Editor > Manage Export Templates).
- Output: `build/{{GAME_SLUG}}_<Preset>_<version>-b<build>.zip`.
- Smoke test: boots the exported pack headless from an empty folder{{#MULTIPLAYER}},
  then hosts and joins with it (`--host` / `--join`, port 7886){{/MULTIPLAYER}}. A failed export
  restores the build number and the notes.

## Patch notes

Every task the player notices adds `data/patch_notes/unreleased/<task>.txt`:

```
new: A second level with moving platforms.
change: Jumping is a little higher.
fix: The pause menu no longer opens behind the map.
```

One file per task, so parallel branches never conflict. The release stamps them
into `data/patch_notes/releases.json` (`python3 -I tools/patch_notes.py --check`
lists them). In game: `PatchNotesPanel.open_if_new(self)` from the main menu
shows the notes once per new build; `PatchNotesPanel.new()` shows them on demand.
English source text; lines go through translation.
{{#MULTIPLAYER}}
## Join check

`scripts/net/version_check.gd` is installed by the `Network` autoload when the
file exists (SceneMultiplayer auth: the client sends version + build, the host
accepts or refuses with a reason; refused peers never see game state).
{{/MULTIPLAYER}}
## Tests

`python3 -I tools/test_runner.py release`: notes data + panel, the tools on a
scratch copy and `--check`{{#MULTIPLAYER}}, and the join check with a matching and a faked build{{/MULTIPLAYER}}.
