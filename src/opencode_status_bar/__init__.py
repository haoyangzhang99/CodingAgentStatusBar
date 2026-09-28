"""
OpenCode Status Bar - macOS menu bar status for the OpenCode desktop app
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("opencode-status-bar")
except PackageNotFoundError:  # running from a source checkout without install
    __version__ = "0.0.0"
