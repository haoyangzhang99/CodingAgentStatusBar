# Integration Details

Two pieces connect the OpenCode desktop app to the menu bar, and Codex and Claude Code hooks add
those apps' status. `install.sh` builds and installs all four.

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

## Codex Hooks (`opencode-status-bar-codex.py`)

Codex runs this script on its lifecycle events, as
`<repo>/.venv/bin/python -I -S opencode-status-bar-codex.py <argument>`, with the event's JSON on
stdin. The script uses only the standard library, never prints, and always exits 0, so it can't
block or change anything Codex does.

| Codex event | Argument | Status file |
|---|---|---|
| `SessionStart` | `start` | Opens the app; writes `ready` unless this Codex process already wrote a status (skipped for `compact`) |
| `UserPromptSubmit`, `PreToolUse`, `PostToolUse` | `prompt`, `tool` | `busy`, approval cleared |
| `PermissionRequest` | `permission` | `busy`, waiting for approval |
| `Stop`, `Interrupt` | `stop` | `idle` |
| `SessionEnd` | `end` | Deleted |

Codex runs `SessionStart` lazily inside a session's first turn, so it keeps a status the same
Codex process already wrote. A file left by an earlier process, for example after Codex crashed
and the session was resumed, is replaced, because the app ignores files whose process has
exited. Each session writes `~/.config/opencode-status-bar/codex/<session id>.json` atomically, with
file mode `0600` in a `0700` directory:

```json
{"version": 1, "pid": 1234, "updated": 1790000000000, "directory": "/path/to/project",
 "status": "busy", "permission": false}
```

`pid` is the Codex process that ran the hook (a shell between them is skipped). `status` is
`ready`, `busy` or `idle`. Files untouched for a day are removed at the next session start.

`python opencode-status-bar-codex.py install` adds one hook group per event to the end of
`~/.codex/hooks.json`, with a 3-second timeout, and backs the file up once to
`hooks.json.bak-opencode-status-bar`. Codex trusts hooks by their position and exact command, so
existing hooks are never moved, and re-running it changes nothing unless the command changed
(for example, after moving this folder). `uninstall` removes only hooks whose command contains
`opencode-status-bar-codex.py`. Both refuse to rewrite a file they can't parse.

`SessionStart` opens the app the same way the OpenCode plugin does, unless
`~/.config/opencode-status-bar/no-autolaunch` exists.

## Claude Code Hooks (`opencode-status-bar-claude.py`)

A standalone script that works like the Codex one, run as
`<repo>/.venv/bin/python -I -S opencode-status-bar-claude.py <argument>`. Claude Code reports more
than Codex, so its status files add `"question": true` while Claude waits for an answer:

| Claude Code event | Argument | Status file |
|---|---|---|
| `SessionStart` | `start` | Opens the app; writes `ready` unless this Claude Code process already wrote a status (skipped for `compact`) |
| `UserPromptSubmit`, `PostToolUse`, `PostToolUseFailure` | `prompt`, `post` | `busy`, approval and question cleared |
| `PreToolUse` | `pre` | `busy`, keeping a pending approval or question; `AskUserQuestion` sets the question |
| `PermissionRequest` | `permission` | `busy`, waiting for approval (or for an answer, for `AskUserQuestion`) |
| `Notification` | `notify` | `permission_prompt`: waiting for approval; `elicitation_dialog`, `elicitation_url_dialog`: waiting for an answer; `idle_prompt`: `ready` unless the turn already finished |
| `Stop`, `StopFailure` | `stop` | `idle` |
| `SessionEnd` | `end` | Deleted |

`PreToolUse` keeps pending flags because a sub-agent's tools can start while the main session
waits for you. Pressing Esc fires no event, so `idle_prompt`, which Claude Code sends about a
minute after a turn ends, clears interrupted turns; it never resets a `Done` that is already
showing.

`install` adds one hook group per event to the end of the `hooks` object in
`~/.claude/settings.json`, keeping every other setting and the file's permissions, and backs the
file up once to `settings.json.bak-opencode-status-bar`. Claude Code needs no trust step and picks
up changes on its own. `uninstall` removes only hooks whose command contains
`opencode-status-bar-claude.py`, and the `hooks` object too if nothing else is left in it.

## Menu Bar App

`src/opencode_status_bar/core/monitor/hooks.py` reads the Codex and Claude Code status files. It
skips malformed files and files whose process has exited. Each app counts as running while its
desktop app (`com.openai.codex`, `com.anthropic.claudefordesktop`) is open or any of its status
files has a live process. Idle sessions are listed for 60 seconds, `ready` sessions aren't listed,
and a `busy` session without an event for 15 minutes counts as idle unless it's waiting for an
approval or an answer.

`src/opencode_status_bar/core/monitor/bridge.py` reads the OpenCode snapshots. It skips files that are
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
