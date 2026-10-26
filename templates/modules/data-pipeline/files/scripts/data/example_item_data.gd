class_name ExampleItemData
extends Resource
## Example data class for the CSV pipeline (data/db/example_items.csv ->
## data/example_items/<id>.tres). Its exported properties are the table's
## columns; replace it with your own classes.

enum Rarity { COMMON, UNCOMMON, RARE, EPIC }

@export var id: StringName = &""
## Player-facing (English source text, shown through tr()).
@export var display_name: String = ""
@export_multiline var description: String = ""
@export var rarity: Rarity = Rarity.COMMON
@export var value: int = 0
@export var weight: float = 0.0
@export var stackable: bool = true
@export var tags: Array[String] = []
@export var tint: Color = Color.WHITE
