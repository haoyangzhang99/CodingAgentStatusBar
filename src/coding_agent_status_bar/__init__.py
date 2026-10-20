"""
Coding Agent Status Bar - macOS menu bar status for OpenCode, Codex, Claude Code and Cursor
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("coding-agent-status-bar")
except PackageNotFoundError:  # running from a source checkout without install
    __version__ = "0.0.0"
