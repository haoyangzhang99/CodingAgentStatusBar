# Project Instructions: OpenCode Status Bar

A macOS menu bar app showing whether the OpenCode desktop app is working, done, or waiting for
the user. Read `DEVELOPMENT.md` for the layout.

## Scope

- The app's runtime path is: `integrations/opencode-status-bar.js` (plugin) → snapshot files →
  `core/monitor/bridge.py` → `app/` and `ui/menu.py`. Codex and Claude Code follow the same path
  through `integrations/opencode-status-bar-codex.py` and `integrations/opencode-status-bar-claude.py`
  (hooks) and `core/monitor/hooks.py`. Prefer changes there.
- Keep runtime dependencies to `rumps` and `loguru`; the app should stay small (about 36 MB).
- The app makes no network requests. The plugin and the Codex and Claude Code hooks must not write prompts, messages,
  tool arguments, tool output, or credentials.
- Menu bar and dropdown icons are monochrome SF Symbol templates, except yellow for attention states.
  Don't add emoji to menu text.

## Commands

```sh
uv run pytest tests/ -q                                  # Python tests
node --test --experimental-test-module-mocks tests/*.test.mjs   # plugin tests
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
