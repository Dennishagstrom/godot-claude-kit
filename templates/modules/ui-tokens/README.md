# Module: ui-tokens

TL;DR: one file holds the whole look (`scripts/ui/ui_tokens.gd`: colours,
spacing, radii, font sizes) and builds the Theme. Screens are made from a few
components. A test fails when a script or scene hardcodes a colour or size,
so many agents building UI in parallel still produce one consistent game.

## Rules

1. Never hardcode colours or sizes in UI code: `UiTokens.ACCENT`, `UiTokens.S4`,
   `UiTokens.FONT_TITLE`, or a theme type variation.
2. One accent colour per screen says "act here" (primary button, focus,
   selection). `DANGER` only for danger and loss.
3. Focus always shows (keyboard and gamepad are equal to the mouse).
4. Text is English source text; Labels/Buttons auto-translate.
5. Build screens from components; when you need a new pattern twice, make it
   a component in `scenes/ui/components/` instead of copying code.

## API

```gdscript
var modal := UiModal.confirm(self, "Leave the game?", "Unsaved progress is lost.", "Leave", "Stay", true)
modal.confirmed.connect(_leave)

var panel := UiPanel.make("Inventory", "What you carry.")
panel.body.add_child(UiText.label("Empty", UiText.MUTED))
panel.body.add_child(UiButton.make("Close", _close, UiButton.Variant.PRIMARY))
some_root_control.theme = UiTokens.theme()
```

- `UiTokens.theme()` (built once): Button/Primary/Danger, Panel, LineEdit,
  CheckBox, label roles (`HeaderLarge`, `HeaderMedium`, `HeaderSmall`,
  `LabelMuted`, `LabelSmall`, `LabelDisplay`). Set it on your UI root or save
  it as a `.tres` and point `gui/theme/custom` at it.
- `UiTokens.box()`, `panel_box()`, `focus_box()` for custom StyleBoxes.

## Test

`python3 -I tools/test_runner.py ui`: theme variations, components, modal
confirm/Esc, and a scan of UI folders (`ui/`, `hud/`, `menu/` under `scripts/`,
`scenes/`, `autoload/`) for `Color(...)`,
hex colours, numeric font-size/constant overrides and scene colour/font-size
overrides. Opt a line out with `# ui-tokens: ok` (say why).
