"""
OpenCode instance monitoring module.

The menu bar app only needs the lightweight desktop bridge reader. The legacy
port-scanning fetcher pulls in aiohttp (~15 MB), so every export is resolved
lazily on first access instead of at package import.
"""

import importlib

_EXPORTS = {
    # Desktop bridge (used by the menu bar app)
    "read_bridge_instances": ".bridge",
    "read_bridge_state": ".bridge",
    # Legacy unauthenticated port discovery
    "find_opencode_ports": ".ports",
    "get_tty_for_port": ".ports",
    # Legacy on-disk ask_user detection
    "OPENCODE_STORAGE_PATH": ".ask_user",
    "AskUserResult": ".ask_user",
    "check_pending_ask_user_from_disk": ".ask_user",
    "_find_latest_notify_ask_user": ".ask_user",
    "_has_activity_after_notify": ".ask_user",
    # Message/todo helpers
    "extract_tools_from_messages": ".helpers",
    "count_todos": ".helpers",
    # Legacy instance fetching
    "fetch_instance": ".fetcher",
    "fetch_all_instances": ".fetcher",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(module, __name__), name)
    globals()[name] = value
    return value
