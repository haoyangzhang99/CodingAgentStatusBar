# Project Instructions: Coding Agent Status Bar

A macOS menu bar app showing whether OpenCode, Codex and Claude Code are working, done, or waiting
for the user. Read `DEVELOPMENT.md` for the layout.

## Scope

- The app's runtime path is: `integrations/coding-agent-status-bar.js` (plugin) → snapshot files →
  `core/monitor/bridge.py` → `app/` and `ui/menu.py`. Codex and Claude Code follow the same path
  through `integrations/coding-agent-status-bar-codex.py` and `integrations/coding-agent-status-bar-claude.py`
  (hooks) and `core/monitor/hooks.py`. Prefer changes there.
- Keep runtime dependencies to `rumps` and `loguru`; the app should stay small (about 36 MB).
- The app makes no network requests, and reads Codex's session files only for their usage records.
  The plugin, the Codex and Claude Code hooks, and the Claude status line must not write prompts,
  messages, tool arguments, tool output, or credentials.
- Menu bar and dropdown icons are monochrome SF Symbol templates, except yellow for attention states.
  Usage bars follow the same rule: gray, or yellow when a limit is low.
  Don't add emoji to menu text.

## Git Workflow

- Never commit or push directly to `main`. Make every change on a new branch from an up-to-date
  `main`, named for the change (such as `settings-window` or `fix-idle-label`).
- Run the Python and plugin tests and `make lint` before committing.
- Push the branch and open a pull request against `main` in
  `haoyangzhang99/CodingAgentStatusBar` (pass `--repo`; the `upstream` remote is the original
  project and must never get pull requests).
- Merge only when the user asks. Delete the branch after merging, then update local `main`.

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
