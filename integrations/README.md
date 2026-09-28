# Local Desktop Status Bridge

The current desktop backend requires private, per-launch API credentials.
The bundled monitor cannot discover it through unauthenticated port probes.

`opencode-monitor.js` is a local OpenCode plugin. It uses OpenCode's injected
client to query session status and pending questions/permissions, then writes
owner-only snapshots under `~/.config/opencode-monitor/bridge/`. It does not
export credentials, prompts, messages, tool arguments, or tool output.
Snapshots include session IDs, titles, directories, activity and attention flags.

The monitor reads snapshots without connecting to the protected desktop API.
It ignores snapshots older than 15 seconds or belonging to a stopped process.
Busy and retry sessions count as working. Recently active idle sessions remain
visible for 60 seconds. Native pending questions and approvals supply the bell
and lock indicators. This bridge does not populate analytics or running tools.

The installed entry point is:
`~/.config/opencode/plugins/opencode-monitor.js`

Fully quit and restart OpenCode after installing or updating the plugin.
Restart Monitor after updating its Python code. This integration does not
configure automatic launching or login items.

## Trimmed Menu Bar Build

The menu bar app reads only these bridge snapshots. It no longer starts or
imports the PyQt6 dashboard, DuckDB analytics indexer, security auditor and
enrichment worker, local API server (port 19876), Claude usage polling, or
legacy port scanning. The dropdown's Dashboard and Preferences entries were
removed with them. Their source remains in the repository, unloaded.

Measured on macOS 26 with one active session: footprint fell from 79 MB to
36 MB, and threads from 36 to 5.

Logging records startup, each change of the menu bar status (with session,
working, and attention counts, but no titles or paths), and errors. A repeated
identical error is logged once until polling succeeds again.

## Native Launcher

`launcher.m` embeds the existing virtual environment's Python runtime inside
the app bundle's native executable. A shell launcher that executes a bare
Python binary loses the bundle identity and can fail to create status-item
scenes on macOS 26. The launcher supports `--check` to verify its bundle
identity and Python imports without starting another monitor.

The installed binary links to the uv-managed Python 3.12.14 runtime. If that
runtime is removed or replaced, rebuild the launcher against the new runtime.

To disable the bridge, remove its installed entry point and restart OpenCode.
The plugin's disposal hook removes its live snapshot; stale files are ignored
even if a process exits without cleanup.

Verification:

```sh
node --test tests/opencode-monitor-plugin.test.mjs
uv run --with pytest --with pytest-asyncio --with pytest-xdist --with pytest-qt --with pytest-timeout --with faker --with aioresponses --with pytest-mock --no-dev pytest tests/unit/core/test_monitor_bridge.py tests/unit/core/test_monitor.py tests/unit/core/test_models.py tests/unit/app/test_app.py -q -n 2
```
