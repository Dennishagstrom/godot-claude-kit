# Assets

Imported art, audio and fonts (Godot imports everything in here):

- `art/<feature>/` textures, sprites, models (`.glb`)
- `audio/music/`, `audio/sfx/` (play music on the Music bus, effects on SFX)
- `fonts/`

Source files (`.blend`, `.psd`, `.kra`, project files of audio tools) do not belong in
`res://`: keep them outside the project or in a folder with a `.gdignore`. Name files
`snake_case`, one asset per file, and reference them from the scene that uses them.
