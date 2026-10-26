extends Node
## Global signal bus for gameplay events that many unrelated systems care about
## (HUD, audio, camera shake, achievements). Emit here instead of wiring nodes
## to each other across the tree.
##
## Rules: signals go up, method calls go down; use this bus only for events that
## really are global. Emitting it does not replicate anything: networked events
## are sent with @rpc by the server and re-emitted here on each peer.
## No class_name on purpose (see autoload/network.gd).

## Example: emitted on every peer when a match/level starts.
@warning_ignore("unused_signal")
signal game_started
## Example: a player-facing message for the HUD (already translated).
@warning_ignore("unused_signal")
signal toast(message: String)
