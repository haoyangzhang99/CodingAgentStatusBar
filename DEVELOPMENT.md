# Development Guide

For installing and using the app, see [README.md](README.md). This guide is for changing it.

## Setup

```sh
uv sync                     # app, test, and legacy dependencies in .venv
```

## Run From Source

Quit the installed app first (click it, then **Quit**), so two copies don't compete for the menu bar.

```sh
make run                    # run the menu bar app from this folder
make run-debug              # same, with debug logs printed to the terminal
```

To test your changes as the installed app instead, run `./install.sh` again.

## Project Layout

The menu bar app uses only these parts:

| Path | Purpose |
|---|---|
| `integrations/opencode-status-bar.js` | OpenCode plugin that writes status snapshots |
| `integrations/launcher.m` | Native app executable that embeds Python |
| `src/opencode_status_bar/core/monitor/bridge.py` | Reads snapshots into app state |
| `src/opencode_status_bar/core/models.py` | Session, tool, and state data classes |
| `src/opencode_status_bar/app/` | Menu bar app: status label, icons, dropdown, polling loop |
| `src/opencode_status_bar/ui/menu.py` | Builds the dropdown's session rows |
| `src/opencode_status_bar/utils/` | Logging and settings |
| `install.sh`, `uninstall.sh` | Build, install, and remove the app and plugin |

How the plugin, snapshots, and launcher fit together is described in
[integrations/README.md](integrations/README.md).

### Inherited Code

These parts come from the original [opencode-monitor](https://github.com/OpenClaudeAgent/opencode-monitor)
and are **not loaded by the menu bar app**. They still have tests, and need the optional `legacy`
dependencies (installed by `uv sync`, or `uv sync --extra legacy` without the dev group):

- `analytics/` (DuckDB), `dashboard/` (PyQt6), `api/` (Flask), `security/` (command risk analysis)
- `core/monitor/fetcher.py`, `ports.py`, `ask_user.py`: port-scanning discovery for older,
  unauthenticated OpenCode servers
- `core/usage.py`: Claude usage polling
- `scripts/`, `tools/profile_*.py`: analytics and dashboard maintenance scripts

`ui/menu.py` still calls the security analyzer to flag risky shell commands, but the plugin never
exports tool arguments, so it has nothing to analyze today.

A test (`tests/unit/app/test_app.py::test_app_import_skips_heavy_optional_features`) fails if the
app starts importing the legacy libraries again.

## Tests

```sh
uv run pytest tests/ -q                                  # Python (about 2,150 tests)
node --test tests/opencode-status-bar-plugin.test.mjs    # plugin
uvx --from shellcheck-py shellcheck install.sh uninstall.sh
```

Tests run in parallel by default. The Qt integration tests need `QT_QPA_PLATFORM=offscreen`
when run without a display.

## Debugging

| File | Contents |
|---|---|
| `~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.log` | Startup, each status change, errors |
| `~/Library/Logs/OpenCodeStatusBar/launcher.log` | Python startup errors from the native launcher |
| `~/.config/opencode-status-bar/bridge/*.json` | Live snapshots written by the plugin |

**Menu bar shows `OpenCode offline`:**
- Check for fresh snapshots: `ls -l ~/.config/opencode-status-bar/bridge/`. Files are rewritten
  every 2 seconds while OpenCode runs.
- If there are none, OpenCode hasn't loaded the plugin. Check that
  `~/.config/opencode/plugins/opencode-status-bar.js` exists, then quit OpenCode with Cmd+Q and reopen it.

**App doesn't appear in the menu bar:**
- Check it's running: `pgrep -fl OpenCodeStatusBar`
- Check `launcher.log` for Python errors, and run the self-check:
  `"$HOME/Applications/OpenCode Status Bar.app/Contents/MacOS/OpenCodeStatusBar" --check`
- The item may be hidden behind the notch; hold Command and drag it further right.

## Making Changes

- After changing Python code, restart the app. After changing the plugin, restart OpenCode.
- Keep the app free of network access and the plugin free of prompts, messages, tool arguments,
  and credentials. `README.md`'s Privacy section documents those promises.
- Update the snapshot format in `integrations/README.md` if you change it, and keep the plugin
  and `bridge.py` compatible, since users may update one before restarting the other.
