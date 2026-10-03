# Integration Details

Two pieces connect the OpenCode desktop app to the menu bar. `install.sh` builds and installs both.

## Status Plugin (`opencode-status-bar.js`)

OpenCode Desktop's local server requires a password generated at each launch, so outside
programs can't discover or query it. This plugin runs inside OpenCode and uses the context
OpenCode gives every plugin. It is an OpenCode 2 plugin (a default export with `id` and
`setup(ctx)`); OpenCode 1 can't load it.

The V2 plugin context can't list sessions, their status or pending questions, so for each open
project directory the plugin follows OpenCode's event stream (`ctx.event.subscribe`):

- execution started/succeeded/failed/interrupted, step started, retry scheduled and status
  events give each session's status (`busy`, `retry`, `idle`);
- `permission.asked`/`permission.replied` and `form.created`/`form.replied`/`form.cancelled`
  track pending permission requests and questions. A finished run clears both, and every 2
  seconds flagged sessions are checked against `ctx.permission.list`;
- sessions are matched to the directory from the event's location or, when an event has none,
  one `ctx.session.get` lookup, which also supplies the title and `parentID`.

Every 2 seconds it writes `~/.config/opencode-status-bar/bridge/<pid>-<sha256(directory)>.json`
atomically, with file mode `0600` in a `0700` directory. Idle sessions stay listed for 60 seconds
after their last event.

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

- Snapshot writes never overlap.
- While the event stream is down the snapshot's timestamp isn't refreshed, so the app treats
  stale data as offline. The plugin resubscribes every second until the stream is back.
- When OpenCode unloads the plugin for a project, the cleanup function returned by `setup` stops
  the stream and deletes its snapshot.
- Plugin startup never fails because the snapshot folder is unavailable.
- A session that was already running when the plugin loaded appears at its next step.

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
