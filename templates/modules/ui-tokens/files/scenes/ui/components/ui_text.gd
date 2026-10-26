class_name UiText
extends RefCounted
## Labels in a type role, so text sizes and colours come from UiTokens:
##   UiText.label("Settings", UiText.TITLE)   UiText.label("Saved.", UiText.MUTED)

const DISPLAY: StringName = &"display"
const TITLE: StringName = &"title"
const HEADING: StringName = &"heading"
const SUBHEADING: StringName = &"subheading"
const BODY: StringName = &"body"
const MUTED: StringName = &"muted"
const SMALL: StringName = &"small"
const VARIATIONS: Dictionary = {
	DISPLAY: UiTokens.VAR_DISPLAY, TITLE: UiTokens.VAR_TITLE, HEADING: UiTokens.VAR_HEADING,
	SUBHEADING: UiTokens.VAR_SUBHEADING, BODY: &"", MUTED: UiTokens.VAR_MUTED, SMALL: UiTokens.VAR_SMALL,
}


static func label(text: String, role: StringName = BODY, wrap: bool = false) -> Label:
	var l := Label.new()
	l.text = text
	l.theme_type_variation = VARIATIONS.get(role, &"")
	if wrap:
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return l
