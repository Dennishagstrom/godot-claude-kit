class_name UiTokens
extends RefCounted
## Design tokens: every colour, spacing step, radius and font size the UI may
## use, plus the project Theme built from them. UI code never hardcodes a
## colour or a size; it uses these constants, the theme, or the components in
## scenes/ui/components/ (docs/modules/ui-tokens.md). Change the look here.

# --- Colours (dark theme) -----------------------------------------------------
const BG_0: Color = Color("#0E0F12")
const BG_1: Color = Color("#16181D")
const BG_2: Color = Color("#20232A")
const BG_3: Color = Color("#2B2F38")
const LINE: Color = Color("#3A3F4B")
const LINE_STRONG: Color = Color("#565D6D")
const TEXT_HI: Color = Color("#F2F4F8")
const TEXT: Color = Color("#C9CED8")
const TEXT_LO: Color = Color("#8C93A1")
const TEXT_OFF: Color = Color("#5D6370")
## The one colour that says "act here" (primary buttons, focus, selection).
const ACCENT: Color = Color("#E8A33D")
const ACCENT_HI: Color = Color("#FFC266")
const ACCENT_LO: Color = Color("#A86E1F")
## Information, magic, links.
const INFO: Color = Color("#5CC8E6")
const SUCCESS: Color = Color("#77C46A")
## Danger and loss only.
const DANGER: Color = Color("#E0503F")
const BACKDROP: Color = Color(0.0, 0.0, 0.0, 0.6)
const DISABLED_ALPHA: float = 0.5
## Hover / pressed shading of button backgrounds.
const HOVER_LIGHTEN: float = 0.12
const PRESSED_DARKEN: float = 0.15

# --- Spacing (4 px grid) ------------------------------------------------------
const S1: int = 4
const S2: int = 8
const S3: int = 12
const S4: int = 16
const S5: int = 24
const S6: int = 32
const S7: int = 48
const S8: int = 64

# --- Shape --------------------------------------------------------------------
const RADIUS: int = 6
const RADIUS_SMALL: int = 3
const BORDER: int = 1
const FOCUS_RING: int = 2
const BUTTON_HEIGHT: int = 40
const BUTTON_PAD_X: int = 16
const PANEL_PADDING: int = S5
const SAFE_MARGIN: int = S6

# --- Type ---------------------------------------------------------------------
const FONT_SMALL: int = 13
const FONT_BODY: int = 16
const FONT_LARGE: int = 20
const FONT_TITLE: int = 26
const FONT_DISPLAY: int = 40

## Theme type variations (set Control.theme_type_variation).
const VAR_PRIMARY: StringName = &"ButtonPrimary"
const VAR_DANGER: StringName = &"ButtonDanger"
const VAR_TITLE: StringName = &"HeaderLarge"
const VAR_HEADING: StringName = &"HeaderMedium"
const VAR_SUBHEADING: StringName = &"HeaderSmall"
const VAR_MUTED: StringName = &"LabelMuted"
const VAR_SMALL: StringName = &"LabelSmall"
const VAR_DISPLAY: StringName = &"LabelDisplay"

static var _theme: Theme = null


## The project theme (built once). Set it on a root Control, or as
## gui/theme/custom in project settings via a saved copy.
static func theme() -> Theme:
	if _theme == null:
		_theme = build_theme()
	return _theme


static func build_theme() -> Theme:
	var t := Theme.new()
	t.default_font_size = FONT_BODY
	_label_styles(t)
	_button_styles(t, &"Button", BG_3, TEXT_HI)
	_button_styles(t, VAR_PRIMARY, ACCENT, BG_0)
	_button_styles(t, VAR_DANGER, DANGER, TEXT_HI)
	t.set_type_variation(VAR_PRIMARY, &"Button")
	t.set_type_variation(VAR_DANGER, &"Button")
	t.set_stylebox(&"panel", &"PanelContainer", panel_box(BG_1, LINE))
	t.set_stylebox(&"panel", &"Panel", panel_box(BG_1, LINE))
	t.set_stylebox(&"normal", &"LineEdit", box(BG_0, LINE, RADIUS_SMALL, S2))
	t.set_stylebox(&"focus", &"LineEdit", focus_box())
	t.set_color(&"font_color", &"LineEdit", TEXT_HI)
	t.set_color(&"font_placeholder_color", &"LineEdit", TEXT_OFF)
	for type: StringName in [&"CheckBox", &"CheckButton"]:
		t.set_color(&"font_color", type, TEXT)
		t.set_color(&"font_hover_color", type, TEXT_HI)
		t.set_stylebox(&"focus", type, focus_box())
	t.set_constant(&"separation", &"VBoxContainer", S2)
	t.set_constant(&"separation", &"HBoxContainer", S2)
	return t


## A flat box with optional border and padding.
static func box(bg: Color, border: Color = Color.TRANSPARENT, radius: int = RADIUS, padding: int = S3) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.set_corner_radius_all(radius)
	sb.set_content_margin_all(padding)
	if border.a > 0.0:
		sb.border_color = border
		sb.set_border_width_all(BORDER)
	return sb


static func panel_box(bg: Color = BG_1, border: Color = LINE) -> StyleBoxFlat:
	return box(bg, border, RADIUS, PANEL_PADDING)


## Focus ring: transparent inside, accent outline (keyboard/gamepad focus always shows).
static func focus_box() -> StyleBoxFlat:
	var sb := box(Color.TRANSPARENT, ACCENT, RADIUS, 0)
	sb.set_border_width_all(FOCUS_RING)
	sb.draw_center = false
	return sb


static func _label_styles(t: Theme) -> void:
	t.set_color(&"font_color", &"Label", TEXT)
	var variations: Dictionary = {
		VAR_DISPLAY: [FONT_DISPLAY, TEXT_HI], VAR_TITLE: [FONT_TITLE, TEXT_HI],
		VAR_HEADING: [FONT_LARGE, TEXT_HI], VAR_SUBHEADING: [FONT_BODY, ACCENT],
		VAR_MUTED: [FONT_BODY, TEXT_LO], VAR_SMALL: [FONT_SMALL, TEXT_LO],
	}
	for variation: StringName in variations:
		t.set_type_variation(variation, &"Label")
		t.set_font_size(&"font_size", variation, int(variations[variation][0]))
		t.set_color(&"font_color", variation, variations[variation][1])


static func _button_styles(t: Theme, type: StringName, bg: Color, fg: Color) -> void:
	var normal := box(bg, LINE if type == &"Button" else Color.TRANSPARENT, RADIUS, S2)
	normal.content_margin_left = BUTTON_PAD_X
	normal.content_margin_right = BUTTON_PAD_X
	var hover: StyleBoxFlat = normal.duplicate()
	hover.bg_color = bg.lightened(HOVER_LIGHTEN)
	var pressed: StyleBoxFlat = normal.duplicate()
	pressed.bg_color = bg.darkened(PRESSED_DARKEN)
	var disabled: StyleBoxFlat = normal.duplicate()
	disabled.bg_color = Color(bg, DISABLED_ALPHA)
	t.set_stylebox(&"normal", type, normal)
	t.set_stylebox(&"hover", type, hover)
	t.set_stylebox(&"pressed", type, pressed)
	t.set_stylebox(&"disabled", type, disabled)
	t.set_stylebox(&"focus", type, focus_box())
	for state: StringName in [&"font_color", &"font_hover_color", &"font_pressed_color", &"font_focus_color"]:
		t.set_color(state, type, fg)
	t.set_color(&"font_disabled_color", type, Color(fg, DISABLED_ALPHA))
