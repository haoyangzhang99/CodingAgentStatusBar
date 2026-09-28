# Project Instructions: OpenCode Status Bar

A macOS menu bar app showing whether the OpenCode desktop app is working, done, or waiting for
the user. Read `DEVELOPMENT.md` for the layout; most of `src/opencode_status_bar/` is inherited
code that the app does not load.

## Scope

- The app's runtime path is: `integrations/opencode-status-bar.js` (plugin) → snapshot files →
  `core/monitor/bridge.py` → `app/` and `ui/menu.py`. Prefer changes there.
- Don't make the app import `analytics`, `dashboard`, `api`, `aiohttp`, `PyQt6`, `duckdb`, `flask`,
  or `watchdog`. A test enforces this.
- The app makes no network requests. The plugin must not write prompts, messages, tool arguments,
  tool output, or credentials.
- Menu bar and dropdown icons are monochrome SF Symbol templates, except yellow for attention states.
  Don't add emoji to menu text.

## Commands

```sh
uv run pytest tests/ -q                                  # Python tests
node --test tests/opencode-status-bar-plugin.test.mjs    # plugin tests
make run                                                 # run from source
./install.sh                                             # rebuild and reinstall the app
```

## Code Analysis Tools

`tools/pycode` wraps jedi, ruff, radon, and vulture. Add `--json` for machine-readable output.

```sh
uv run python -m tools.pycode goto <file>:<line>:<col>   # also: refs, hover
uv run python -m tools.pycode symbols <file>
uv run python -m tools.pycode lint [--fix] <path>        # also: check (formatting)
uv run python -m tools.pycode complexity <path>          # also: maintainability, dead-code
uv run python -m tools.pycode report <path>
```
