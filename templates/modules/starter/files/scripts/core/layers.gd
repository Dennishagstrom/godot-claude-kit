class_name Layers
extends RefCounted
## Physics layer registry. NAMES match project.godot (layer_names/{{#3D}}3d{{/3D}}{{^3D}}2d{{/3D}}_physics) and MASKS
## say what each layer may detect. Use the constants, never numbers (lint: layer-number):
##   collision_layer = Layers.PICKUPS
##   collision_mask = Layers.MASKS[Layers.PICKUPS]
## tests/starter/test_layers.gd fails on a scene whose body or area detects more than
## MASKS allows (e.g. an enemy hurtbox on the pickup layer). Add a layer: a constant,
## a NAMES entry, a MASKS entry and the name in Project Settings > Layer Names.

const WORLD: int = 1 << 0
const PLAYERS: int = 1 << 1
const ENEMIES: int = 1 << 2
const PICKUPS: int = 1 << 3
const PROJECTILES: int = 1 << 4
## Areas that only detect: hitboxes, zones, interact ranges.
const TRIGGERS: int = 1 << 5

const NAMES: Dictionary = {
	WORLD: "world", PLAYERS: "players", ENEMIES: "enemies", PICKUPS: "pickups",
	PROJECTILES: "projectiles", TRIGGERS: "triggers",
}
## layer -> the layers a node on it may detect (its collision_mask, at most).
const MASKS: Dictionary = {
	WORLD: WORLD,
	PLAYERS: WORLD | ENEMIES,
	ENEMIES: WORLD | PLAYERS | ENEMIES,
	PICKUPS: WORLD | PLAYERS,
	PROJECTILES: WORLD | PLAYERS | ENEMIES,
	TRIGGERS: PLAYERS | ENEMIES,
}


## Every layer bit that is registered.
static func all() -> int:
	var bits: int = 0
	for bit: int in NAMES:
		bits |= bit
	return bits


## The most a node on `layer` (one or more bits) may detect.
static func allowed_mask(layer: int) -> int:
	var mask: int = 0
	for bit: int in MASKS:
		if layer & bit:
			mask |= MASKS[bit]
	return mask
