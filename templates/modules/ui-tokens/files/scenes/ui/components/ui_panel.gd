class_name UiPanel
extends PanelContainer
## A panel with an optional title and subtitle and a body to add content to.
## Padding, colours and type come from the theme (UiTokens).
##   var panel := UiPanel.make("Inventory"); panel.body.add_child(...)

var title: String = "":
	set(value):
		title = value
		if _title_label:
			_title_label.text = value
			_title_label.visible = not value.is_empty()
var subtitle: String = "":
	set(value):
		subtitle = value
		if _subtitle_label:
			_subtitle_label.text = value
			_subtitle_label.visible = not value.is_empty()
## Add content here.
var body: VBoxContainer = null

var _title_label: Label = null
var _subtitle_label: Label = null


static func make(panel_title: String = "", panel_subtitle: String = "") -> UiPanel:
	var panel := UiPanel.new()
	panel.title = panel_title
	panel.subtitle = panel_subtitle
	return panel


func _init() -> void:
	var column := VBoxContainer.new()
	column.add_theme_constant_override(&"separation", UiTokens.S3)
	add_child(column)
	_title_label = UiText.label(title, UiText.TITLE)
	_subtitle_label = UiText.label(subtitle, UiText.MUTED, true)
	column.add_child(_title_label)
	column.add_child(_subtitle_label)
	body = VBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(body)
	title = title
	subtitle = subtitle
