# OpenCode Status Bar

A small macOS menu bar item that shows what the [OpenCode](https://opencode.ai) desktop app is doing.
Check it while you work in other apps to see whether OpenCode is still working, has finished,
or is waiting for you to approve something or answer a question.

This is a fork of [OpenClaudeAgent/opencode-monitor](https://github.com/OpenClaudeAgent/opencode-monitor)
(MIT licensed, now archived). It is a community project, not an official OpenCode product.

## What You'll See

The menu bar shows an icon and a short status. The icon turns yellow only when OpenCode needs you;
otherwise the icon and text follow your menu bar's light or dark appearance, like other menu bar items.

| Status | Icon | Meaning |
|---|---|---|
| `Working...` / `2 working` | Terminal | One or more sessions are generating a response |
| `Done` | Checkmark | A session finished within the last minute |
| `Awaiting approval` | Hand (yellow) | OpenCode is waiting for you to approve a permission request |
| `Awaiting answer` | Question mark (yellow) | OpenCode asked you a question |
| `Needs attention` | Exclamation mark (yellow) | Both an approval and a question are pending |
| `OpenCode idle` | Terminal | OpenCode is running, with no recent activity |
| `OpenCode offline` | Terminal | OpenCode isn't running, or hasn't loaded the plugin yet |

Attention states take priority over working states. Counts are active sessions, not open windows.

Click the item for a dropdown with **Show OpenCode** (brings OpenCode to the front, or opens it),
each recent session and what it's waiting for, **Refresh**, and **Quit**.

## Requirements

- macOS (tested on macOS 26 with an Apple silicon Mac)
- The OpenCode desktop app (tested with 1.18)
- [uv](https://docs.astral.sh/uv/): `brew install uv`
- Xcode Command Line Tools: `xcode-select --install`

## Install

```sh
git clone https://github.com/haoyangzhang99/OpenCodeStatusBar.git
cd OpenCodeStatusBar
./install.sh
```

The installer:

1. Installs Python 3.12 and the app's two dependencies in `.venv` inside this folder.
2. Builds `~/Applications/OpenCode Status Bar.app` and checks that it starts correctly.
3. Adds the plugin `~/.config/opencode/plugins/opencode-status-bar.js`, which loads
   `integrations/opencode-status-bar.js` from this folder.
4. Opens the app.

Then **fully quit OpenCode (Cmd+Q) and reopen it** so it loads the plugin. Until then the
menu bar shows `OpenCode offline`.

Keep the project folder where it is: the app and plugin run from it. If you move the folder,
run `./install.sh` again.

To start the app at login, add **OpenCode Status Bar** in System Settings > General > Login Items.

## Update

```sh
git pull
./install.sh
```

Restart OpenCode afterwards if the plugin changed.

## Uninstall

```sh
./uninstall.sh          # removes the app, plugin, and status files
./uninstall.sh --purge  # also removes logs, settings, and .venv
```

Then restart OpenCode to unload the plugin, and delete this folder if you no longer need it.

## How It Works

OpenCode's desktop app protects its local server with a password that changes every launch,
so outside programs can't query it directly. Instead, a small OpenCode plugin runs inside
OpenCode and every 2 seconds writes a status snapshot for each open project to
`~/.config/opencode-status-bar/bridge/`. The menu bar app reads those files and never
connects to OpenCode.

- Snapshots older than 15 seconds, or from an OpenCode process that has exited, are ignored.
- Finished sessions stay listed for 60 seconds, which is how `Done` appears.
- Approval and question states come from OpenCode's own pending-request lists, not timing guesses.

Technical details are in [`integrations/README.md`](integrations/README.md).

## Privacy

- **Stays on your Mac.** The app makes no network requests.
- **Written by the plugin:** session IDs, titles, project folder paths, and status flags.
  Files are readable only by your user account.
- **Not written:** prompts, messages, tool inputs or output, API keys, or OpenCode's server password.
- **Logs** (`~/Library/Logs/OpenCodeStatusBar/`) get one line per status change, with counts
  only: no session titles or paths.

## Limitations

- macOS only. Made for the OpenCode desktop app; the terminal version of OpenCode is untested.
- The plugin reads approvals and questions through an internal part of OpenCode's plugin client,
  so a future OpenCode update could break those two indicators.
- On a crowded menu bar, macOS may hide the item behind the notch. Hold Command and drag it
  further right.
- The app links against the Python that `install.sh` set up. If you delete uv's Python
  installations, run `./install.sh` again.

## Development

```sh
uv sync                                  # includes test and legacy dependencies
uv run pytest tests/ -q                  # Python tests
node --test tests/opencode-status-bar-plugin.test.mjs   # plugin tests
```

After changing Python code, quit the app from its menu and reopen it. After changing the plugin,
restart OpenCode.

See [DEVELOPMENT.md](DEVELOPMENT.md) for the project layout, running from source, and debugging.

This fork keeps the original project's dashboard, analytics, security scanner, and local API code
(under `src/opencode_status_bar/`), but the menu bar app no longer loads any of it. Running those
parts needs the optional `legacy` dependencies (`uv sync --extra legacy`). The original project's
design notes are in its [repository](https://github.com/OpenClaudeAgent/opencode-monitor) and in
this repository's Git history.

## Credits and License

Based on [opencode-monitor](https://github.com/OpenClaudeAgent/opencode-monitor) by OpenClaudeAgent.
MIT License; see [LICENSE](LICENSE).
