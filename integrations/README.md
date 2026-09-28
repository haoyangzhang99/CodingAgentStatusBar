# Integration Details

Two pieces connect the OpenCode desktop app to the menu bar. `install.sh` builds and installs both.

## Status Plugin (`opencode-status-bar.js`)

OpenCode Desktop's local server requires a password generated at each launch, so outside
programs can't discover or query it. This plugin runs inside OpenCode and uses the client
OpenCode gives every plugin.

Every 2 seconds, for each open project directory, it:

- reads session status (`busy`, `retry`, `idle`), pending questions (`/question`) and pending
  permission requests (`/permission`), plus sessions updated in the last 60 seconds;
- writes `~/.config/opencode-status-bar/bridge/<pid>-<sha256(directory)>.json` atomically,
  with file mode `0600` in a `0700` directory.

Snapshot format:

```json
{"version": 1, "pid": 1234, "updated": 1790000000000, "directory": "/path/to/project",
 "sessions": [{"id": "ses_...", "title": "...", "directory": "/path/to/project",
               "parentID": "ses_...", "status": "busy", "tools": [],
               "question": false, "permission": true}]}
```

`parentID` appears only for sub-agent sessions. `tools` is always empty: tool names and
arguments are never exported.

Behavior details:

- Polls never overlap, and each has a 5-second timeout.
- A failed poll never refreshes the snapshot's timestamp, so the app treats stale data as offline.
- When OpenCode closes a project context (`dispose` hook or `server.instance.disposed` event), the
  plugin stops polling and deletes its snapshot.
- Plugin startup never fails because the snapshot folder is unavailable.

The injected v1 SDK client has no methods for questions or permissions, so the plugin calls those
endpoints through `client._client.get`, an internal API that may change between OpenCode releases.

### Opening the App

When OpenCode loads the plugin, it runs `open -g -b io.github.haoyangzhang99.OpenCodeStatusBar`,
which starts the menu bar app in the background, or does nothing if it's already running. OpenCode
loads the plugin once per project, so a flag on `globalThis` limits this to the first load in each
OpenCode process. If macOS doesn't know the app's ID yet, the plugin opens
`~/Applications/OpenCode Status Bar.app` directly. Failures are ignored.

Creating `~/.config/opencode-status-bar/no-autolaunch` turns this off. Launching only happens on
macOS; tests replace the launcher (`tests/opencode-status-bar-launch.test.mjs`).

The installed file `~/.config/opencode/plugins/opencode-status-bar.js` only re-exports this file,
so `git pull` updates the plugin the next time OpenCode starts.

## Menu Bar App

`src/opencode_status_bar/core/monitor/bridge.py` reads the snapshots. It skips files that are
malformed, older than 15 seconds, or written by a process that is no longer running, and it
merges duplicate sessions. Busy and retry sessions count as working.

The app redraws and logs only when the status changes. Its footprint is about 36 MB with 5
threads (measured on macOS 26). Its only dependencies are rumps and loguru.

## Native Launcher (`launcher.m`)

The app bundle's executable embeds Python rather than running a separate `python` process.
A script that starts a bare Python interpreter loses the app's identity, and on macOS 26 the
menu bar item then fails to appear.

`install.sh` compiles `launcher.m` against the uv-managed Python in `.venv`, which provides the
required shared `libpython`. Running the executable with `--check` prints the bundle identifier
and verifies the Python imports without starting the app. Launcher output goes to
`~/Library/Logs/OpenCodeStatusBar/launcher.log`.
