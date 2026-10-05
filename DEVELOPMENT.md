# Development Guide

For installing and using the app, see [README.md](README.md). This guide is for changing it.

## Setup

```sh
uv sync                     # app and test dependencies in .venv
```

## Run From Source

Quit the installed app first (click it, then **Quit**), so two copies don't compete for the menu bar.

```sh
make run                    # run the menu bar app from this folder
make run-debug              # same, with debug logs printed to the terminal
```

To test your changes as the installed app instead, run `./install.sh` again.

## Project Layout

The whole app is these parts:

| Path | Purpose |
|---|---|
| `integrations/opencode-status-bar.js` | OpenCode plugin that writes status snapshots |
| `integrations/opencode-status-bar-codex.py` | Codex hooks that write status files; installs and removes the hooks |
| `integrations/opencode-status-bar-claude.py` | The same for Claude Code |
| `integrations/launcher.m` | Native app executable that embeds Python |
| `src/opencode_status_bar/core/monitor/bridge.py` | Reads snapshots into app state |
| `src/opencode_status_bar/core/monitor/hooks.py` | Reads Codex and Claude Code status files into app state |
| `src/opencode_status_bar/core/models.py` | Session, tool, and state data classes |
| `src/opencode_status_bar/app/` | Menu bar app: status label, icons, dropdown, polling loop |
| `src/opencode_status_bar/ui/menu.py` | Builds the dropdown's session rows |
| `src/opencode_status_bar/utils/logger.py` | Logging |
| `tools/pycode/` | Code navigation and quality CLI for development (see `.opencode/AGENTS.md`) |
| `install.sh`, `uninstall.sh` | Build, install, and remove the app and plugin |
| `assets/make_icon.py` | Draws the app icon; run `uv run python assets/make_icon.py` to regenerate `AppIcon.png` and `AppIcon.icns` |

How the plugin, snapshots, and launcher fit together is described in
[integrations/README.md](integrations/README.md).

### Removed From the Original Project

The original [opencode-monitor](https://github.com/OpenClaudeAgent/opencode-monitor) also had a
dashboard, analytics database, security scanner, local API server, Claude usage tracking, and
port-scanning discovery for older OpenCode versions. This fork removed them; they remain in the
original repository and in this repository's Git history.

## Tests

```sh
make test                   # Python tests (about 270) and plugin tests
make lint                   # ruff and shellcheck
```

Python tests run in parallel and in random order by default.

## Debugging

| File | Contents |
|---|---|
| `~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.log` | Startup, each status change, errors |
| `~/Library/Logs/OpenCodeStatusBar/launcher.log` | Python startup errors from the native launcher |
| `~/.config/opencode-status-bar/bridge/*.json` | Live snapshots written by the plugin |
| `~/.config/opencode-status-bar/codex/*.json` | Codex session status written by the hooks |
| `~/.config/opencode-status-bar/claude/*.json` | Claude Code session status written by the hooks |

**No Codex status:**
- Check that `~/.codex/hooks.json` has hooks running `opencode-status-bar-codex.py`; if not, run
  `./install.sh` again.
- In a new Codex session, run `/hooks`: Codex skips hooks you haven't trusted, and asks again
  after their command changes.
- Check for status files: `ls -l ~/.config/opencode-status-bar/codex/`. One is rewritten on
  every Codex event.

**No Claude Code status:**
- Check that `~/.claude/settings.json` has hooks running `opencode-status-bar-claude.py`; if not,
  run `./install.sh` again. In Claude Code, `/hooks` lists the hooks it has loaded.
- Check for status files: `ls -l ~/.config/opencode-status-bar/claude/`. One is rewritten on
  every Claude Code event.

**Dropdown shows `No OpenCode instances`** (menu bar on `Agents offline` without Codex or
Claude Code):
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
  Changes to the Codex hook script apply on the next Codex event; changes to the hook commands
  need `./install.sh` and trusting them again in Codex's `/hooks`. The Claude Code hook script
  works the same way, without the trust step.
- Keep the app free of network access and the plugin free of prompts, messages, tool arguments,
  and credentials. `README.md`'s Privacy section documents those promises.
- Update the snapshot format in `integrations/README.md` if you change it, and keep the plugin
  and `bridge.py` compatible, since users may update one before restarting the other.
