"""The game's frame for scaffold.py: what the godot-start interview decides, turned into files and settings.

Answer keys (all optional; an empty value changes nothing, so older answers render as before):
    pitch           one or two sentences: what the player does and why it is fun ("genre" is the old name)
    references      games it resembles ("Hades meets Overcooked")
    camera          top-down, side-view, third-person, first-person, isometric, fixed ... (free text)
    platforms       [desktop, steam, web, mobile, console]
    input           [keyboard-mouse, gamepad, touch]
    art             pixel, low-poly, stylised, realistic, hand-drawn, vector ... (free text)
    art_source      [scripts, hand, packs, generated] (3D: where the models come from)
    scope           jam (days), small (1-3 months), large (6+ months)
    team            solo, small (2-4), team (5+)
    saves           none, settings, progress
Design lists, written once into docs/design.md (the project owns it after that) and not saved:
    core_loop, pillars, first_playable, not_doing, questions   ([str, ...])
    (saved instead: designed = true once they were given, for the checkbox in docs/status.md)

The frame decides project settings (pixel art filtering, the renderer for web or mobile, touch
emulation), the milestones in docs/status.md and which modules are recommended (`recommend`).
"""
import kit_modules

FRAME_DEFAULTS = {"pitch": "", "references": "", "camera": "", "platforms": [], "input": [], "art": "",
                  "art_source": [], "scope": "", "team": "", "saves": ""}
DESIGN_KEYS = ("core_loop", "pillars", "first_playable", "not_doing", "questions")
LIST_KEYS = ("platforms", "input", "art_source") + DESIGN_KEYS

SCOPES = {"jam": "a jam or weekend game (days)", "small": "a small game (1-3 months)",
          "large": "a larger game (6+ months)"}
TEAMS = {"solo": "solo", "small": "2-4 people", "team": "5+ people"}
SAVES = {"none": "nothing is saved", "settings": "settings only", "progress": "player progress"}
PLATFORM_NAMES = {"desktop": "PC (Windows, macOS, Linux)", "steam": "Steam", "web": "web (browser)",
                  "mobile": "mobile", "console": "consoles"}
INPUT_NAMES = {"keyboard-mouse": "keyboard + mouse", "gamepad": "gamepad", "touch": "touch"}
SOURCE_NAMES = {"scripts": "scripted in Blender", "hand": "made by hand", "packs": "asset packs",
                "generated": "generators"}
# What each choice means for the code; written into the Frame section of docs/design.md.
PLATFORM_NOTES = {
    "web": "Web: Compatibility renderer (set), single-threaded export (Godot's default) so any host works; "
           "test in a browser early and keep the download small.",
    "mobile": "Mobile: %s renderer (set), touch for every action, UI readable on a phone, "
              "watch battery and heat (perf budgets).",
    "steam": "Steam: GodotSteam (module `steam` for lobbies); a Steamworks app ID before release.",
    "console": "Consoles: Godot needs a third-party port (e.g. W4 Games); keep code free of "
               "desktop-only assumptions (file paths, mouse-only UI).",
}
INPUT_NOTES = {
    "gamepad": "Gamepad: every menu works without a mouse (focus neighbours); input only through actions.",
    "touch": "Touch: on-screen controls for every action; touch is emulated from the mouse for desktop testing.",
}
ART_NOTES = {
    "pixel": "Pixel art: nearest filtering, a 640x360 base resolution scaled by whole numbers, pixel snap "
             "(project settings set). Draw at that resolution.",
}
MILESTONES = {
    "": ["First playable prototype"],
    "jam": ["Core loop playable, ugly is fine (first day)", "One full session from start to end, with a win or loss",
            "Polish pass: sound, feedback, menu", "Build exported and uploaded"],
    "small": ["First playable: the core loop with placeholder art", "Vertical slice: one area at final quality",
              "Content complete", "Release build"],
    "large": ["First playable: the core loop with placeholder art",
              "Vertical slice: one area at final quality (go/no-go decision)",
              "Playtest build for people outside the team", "Content complete (alpha)",
              "Bugs and polish (beta)", "Release"],
}
HINTS = {
    "core_loop": ["1. ...", "", "What the player does again and again, in 3-5 steps (e.g. explore -> fight -> "
                  "loot -> upgrade)."],
    "pillars": ["Two or three rules every feature must serve (e.g. \"every fight lasts under a minute\")."],
    "first_playable": ["The smallest set of features that is fun to play.", "", "- [ ] ..."],
    "not_doing": ["Ideas that are deliberately out (for now), so nobody builds them by accident."],
    "questions": ["The riskiest assumptions: test these first."],
}


def normalise(answers):
    """Fills frame defaults in place; lists given as "a, b" strings become lists."""
    for key, empty in FRAME_DEFAULTS.items():
        answers.setdefault(key, list(empty) if isinstance(empty, list) else empty)
    for key in LIST_KEYS:
        val = answers.get(key)
        if isinstance(val, str):
            answers[key] = [v.strip() for v in val.split(",") if v.strip()]
    for key in ("camera", "art", "scope", "team", "saves"):
        answers[key] = str(answers.get(key) or "").strip().lower()
    genre = answers.pop("genre", "")  # the name before 0.8.0
    answers["pitch"] = str(answers["pitch"]).strip() or str(genre).strip() or "A game"
    return answers


def saved(answers):
    """The answers to keep in .claude/godot-kit.json: design lists live in docs/design.md only."""
    out = {k: v for k, v in answers.items() if k not in DESIGN_KEYS}
    out["designed"] = _designed(answers)
    return out


def _designed(answers):
    return bool(answers.get("designed") or answers.get("core_loop") or answers.get("first_playable"))


def is_2d(answers):
    return str(answers.get("dimension", "3D")).upper() == "2D"


def renderer(answers):
    """Godot's rendering_method for the frame, or "" to keep the project's own."""
    plats = answers.get("platforms") or []
    if "web" in plats:
        return "gl_compatibility"
    if "mobile" in plats:
        return "mobile"
    return ""


def settings(answers):
    """{"section": {"key": "raw value"}} for project.godot, added when missing (before module settings)."""
    out = {}
    method = renderer(answers)
    if method:
        out["rendering"] = {"renderer/rendering_method": '"%s"' % method,
                            "renderer/rendering_method.mobile": '"%s"' % method}
    if "touch" in (answers.get("input") or []) or "mobile" in (answers.get("platforms") or []):
        out["input_devices"] = {"pointing/emulate_touch_from_mouse": "true"}
    if is_2d(answers) and answers.get("art") == "pixel":
        out.setdefault("rendering", {}).update({"textures/canvas_textures/default_texture_filter": "0",
                                                "2d/snap/snap_2d_transforms_to_pixel": "true"})
        out["display"] = {"window/size/viewport_width": "640", "window/size/viewport_height": "360",
                          "window/size/window_width_override": "1280", "window/size/window_height_override": "720",
                          "window/stretch/mode": '"viewport"', "window/stretch/scale_mode": '"integer"'}
    return out


def recommend(answers):
    """[(module name, "on" | "off" | "optional", reason)] in kit order, for this game."""
    on = set(kit_modules.default_names(answers))
    why = {}
    scope, plats = answers.get("scope", ""), answers.get("platforms") or []

    def turn(name, state, reason):
        mod = kit_modules.by_name().get(name)
        if mod and kit_modules.fits(mod, answers):
            (on.add if state else on.discard)(name)
            why[name] = reason

    if scope == "jam":
        for name in ("ci", "perf-tests", "l10n-check"):
            turn(name, False, "a jam: fewer moving parts; add it later if the game lives on")
    if answers.get("saves") == "none":
        turn("safe-saves", False, "nothing is saved")
    if "steam" in plats:
        turn("steam", True, "Steam is a target")
    if "scripts" in (answers.get("art_source") or []):
        turn("blender-pipeline", True, "models are scripted in Blender")
    if scope == "large" or answers.get("team") == "team":
        turn("ui-tokens", True, "a larger game: one place for UI colours and sizes")
        turn("sandbox", True, "a larger game: a test arena pays for itself")
    if "mobile" in plats and scope != "jam":
        turn("ui-tokens", True, "mobile: UI sizes in one place")
    out = []
    for m in kit_modules.all_modules():
        if not kit_modules.fits(m, answers):
            continue
        state = "on" if m["name"] in on else ("off" if m["default"] else "optional")
        out.append((m["name"], state, why.get(m["name"], m["summary"])))
    return out


def recommended_names(answers):
    return [name for name, state, _ in recommend(answers) if state == "on"]


# --- text for the templates ---------------------------------------------------------

def _art(answers):
    art = answers.get("art", "")
    return art + " art" if art and not art.endswith("art") else art


def _names(keys, table):
    return ", ".join(table.get(k, k) for k in keys)


def claude_md_line(answers):
    """One short line for CLAUDE.md ("" when the interview chose nothing)."""
    parts = [answers.get("camera", "")]
    parts.append(_names(answers.get("platforms") or [], {"desktop": "PC", "steam": "Steam"}))
    parts.append(_names(answers.get("input") or [], {"keyboard-mouse": "keyboard+mouse"}))
    parts.append(_art(answers))
    parts = [p for p in parts if p]
    return "Frame: %s." % " · ".join(parts) if parts else ""


def design_frame(answers):
    rows = [("Players", "up to %s online" % answers["max_players"] if answers["multiplayer"] else "single player"),
            ("View", " ".join(p for p in (answers["dimension"], answers.get("camera", "")) if p)),
            ("Platforms", _names(answers.get("platforms") or [], PLATFORM_NAMES)),
            ("Input", _names(answers.get("input") or [], INPUT_NAMES)),
            ("Look", _art(answers)),
            ("Models from", _names(answers.get("art_source") or [], SOURCE_NAMES)),
            ("Scope", SCOPES.get(answers.get("scope", ""), answers.get("scope", ""))),
            ("Team", TEAMS.get(answers.get("team", ""), answers.get("team", ""))),
            ("Saves", SAVES.get(answers.get("saves", ""), answers.get("saves", ""))),
            ("Player text", answers.get("text_language", ""))]
    rows = [(k, v) for k, v in rows if v]
    lines = ["| | |", "|---|---|"] + ["| %s | %s |" % row for row in rows]
    notes = [PLATFORM_NOTES[p] % ("Compatibility" if "web" in answers["platforms"] else "Mobile")
             if p == "mobile" else PLATFORM_NOTES[p] for p in answers.get("platforms") or [] if p in PLATFORM_NOTES]
    notes += [INPUT_NOTES[i] for i in answers.get("input") or [] if i in INPUT_NOTES]
    if is_2d(answers) and answers.get("art") in ART_NOTES:
        notes.append(ART_NOTES[answers["art"]])
    return lines + ([""] + ["- " + n for n in notes] if notes else [])


def _listed(answers, key, numbered=False, checkbox=False):
    items = [str(i).strip() for i in answers.get(key) or [] if str(i).strip()]
    if not items:
        return HINTS[key]
    if numbered:
        return ["%d. %s" % (n, i) for n, i in enumerate(items, 1)]
    return [("- [ ] " if checkbox else "- ") + i for i in items]


def blocks(answers):
    """Block placeholders (a line of their own; an empty list removes the line)."""
    refs = str(answers.get("references", "")).strip()
    return {
        "FRAME_CLAUDE_MD": [l for l in [claude_md_line(answers)] if l],
        "DESIGN_REFERENCES": ["", "Like: " + refs] if refs else [],
        "DESIGN_FRAME": design_frame(answers),
        "DESIGN_CORE_LOOP": _listed(answers, "core_loop", numbered=True),
        "DESIGN_PILLARS": _listed(answers, "pillars", numbered=True),
        "DESIGN_FIRST_PLAYABLE": _listed(answers, "first_playable", checkbox=True),
        "DESIGN_NOT_DOING": _listed(answers, "not_doing"),
        "DESIGN_QUESTIONS": _listed(answers, "questions"),
        "STATUS_DESIGN": ["- [%s] Pitch, core loop and scope in docs/design.md" % ("x" if _designed(answers) else " ")],
        "STATUS_MILESTONES": ["- [ ] " + m for m in MILESTONES.get(answers.get("scope", ""), MILESTONES[""])],
    }


def project_feature(answers):
    """The renderer name for config/features in a new project.godot."""
    method = renderer(answers) or ("gl_compatibility" if is_2d(answers) else "forward_plus")
    return {"gl_compatibility": "GL Compatibility", "mobile": "Mobile", "forward_plus": "Forward Plus"}[method]
