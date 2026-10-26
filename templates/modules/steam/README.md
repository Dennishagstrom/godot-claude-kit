# Module: steam

TL;DR: friends join through Steam lobbies and overlay invites instead of IP
addresses. `SteamService` (autoload) creates/joins lobbies with GodotSteam and
hands a `SteamMultiplayerPeer` to `Network.adopt_peer()`, so roster, RPCs and
synchronizers behave exactly as over ENet. ENet stays for development, tests
and direct connect. Without GodotSteam the game runs as before.

## Install GodotSteam (once per machine/project)

1. In the editor: AssetLib → search "GodotSteam GDExtension" (4.x) → download
   into `addons/godotsteam/` (or get a release from
   https://codeberg.org/godotsteam/godotsteam; the GitHub repo moved there).
   Pick the version whose table matches your Godot (4.7 needs GodotSteam 4.20+).
   Don't commit downloaded binaries you didn't intend to ship; follow the
   add-on's own README for what goes into git.
2. Check `ClassDB.class_exists("SteamMultiplayerPeer")`. Recent releases include
   it; otherwise install the GodotSteam MultiplayerPeer add-on as well.
   `SteamService` reports which part is missing.
3. Steam must be running and logged in. App id: `TEST_APP_ID = 480` (Valve's
   Spacewar test app) until you have your own; then set
   `steam/initialization/app_id` in project settings. For editor runs a
   `steam_appid.txt` with the id in the project root also works (git-ignored).
4. Overlay note: in the editor the Steam overlay works with the Compatibility
   renderer, not Forward+; exported builds launched through Steam are fine.

## Use

```gdscript
SteamService.host_lobby(Network.MAX_PLAYERS)      # -> lobby_created(id); you are the host
SteamService.invite_friends()                     # overlay invite dialog
SteamService.join_lobby(id)                       # or accept an invite (join_requested / +connect_lobby)
SteamService.lobby_failed.connect(func(reason): show_toast(reason))
if not SteamService.is_available(): show_direct_connect()
```

Live test: two machines, each logged in to its own Steam account, both
running the build with app 480 first, then with your own (Playtest) app id.

## Steamworks checklist (your own app)

1. Steamworks partner account, then pay the Steam Direct fee (US$100 per app,
   recouped after US$1,000 gross revenue). Tax and bank forms first.
2. Your app id: set it in project settings; also create the **Playtest** app
   (free, its own id) to give friends access without a store page.
3. Builds: upload with SteamPipe (steamcmd + app build VDF); depots for
   Windows/macOS/Linux. Launch options: the exported executable.
4. Store page ("Coming soon") needs review; Valve requires it to be public
   for a while before release, and **you can release at the earliest 30 days
   after paying the fee**. Plan the date around both.
5. Before release: a build review by Valve (a few days), achievements/rich
   presence optional, and test invites with `+connect_lobby` launches.

## Test

`python3 -I tools/test_runner.py steam`: without GodotSteam (the normal CI
case) it checks the graceful path: unavailable reason, every lobby call fails
with a reason and no script errors, ENet still hosts. With Steam available it
checks the init; live lobbies are a manual two-account test.
