"""
Pytest configuration and shared fixtures for opencode_status_bar tests.

Provides rumps mocking infrastructure for the menu bar UI tests.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


# =============================================================================
# Rumps Mock Infrastructure (shared by test_app.py and test_menu.py)
# =============================================================================


class MockMenuItem:
    """Mock for rumps.MenuItem with proper menu behavior."""

    def __init__(self, title="", callback=None, **kwargs):
        self.title = title
        self.callback = callback
        self._items = []
        self._items_dict = {}
        self.state = 0
        self._menuitem = MagicMock()
        self.parent = None

    def add(self, item):
        if isinstance(item, MockMenuItem):
            self._items.append(item)
            self._items_dict[item.title] = item
            item.parent = self
        elif item is None:
            self._items.append(None)

    def clear(self):
        self._items = []
        self._items_dict = {}

    def values(self):
        return [item for item in self._items if item is not None]

    def __iter__(self):
        return iter(self._items)

    def __repr__(self):
        return f"MockMenuItem({self.title!r})"


class MockMenu:
    """Mock rumps menu with proper list-like and method behavior."""

    def __init__(self):
        self._items = []
        self._clear_called = False
        self._add_calls = []

    def clear(self):
        self._items = []
        self._clear_called = True

    def add(self, item):
        self._items.append(item)
        self._add_calls.append(item)

    def __setitem__(self, key, value):
        pass

    def __getitem__(self, key):
        return self._items[key] if isinstance(key, int) else None

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class MockApp:
    """Mock rumps.App base class."""

    def __init__(self, name="", title="", quit_button=None, **kwargs):
        self.name = name
        self.title = title
        self._menu = MockMenu()

    @property
    def menu(self):
        return self._menu

    @menu.setter
    def menu(self, value):
        if isinstance(value, list):
            self._menu = MockMenu()
            for item in value:
                self._menu.add(item)
        else:
            self._menu = value

    def run(self):
        pass


@pytest.fixture
def mock_rumps():
    """Provide a mock rumps module for UI tests."""
    rumps_mock = MagicMock()
    rumps_mock.App = MockApp
    rumps_mock.MenuItem = MockMenuItem
    rumps_mock.timer = lambda interval: lambda f: f
    rumps_mock.quit_application = MagicMock()
    return rumps_mock


# Store original rumps module state at conftest import time
_original_rumps = sys.modules.get("rumps")
_rumps_was_real = _original_rumps is not None and hasattr(_original_rumps, "__file__")


def pytest_runtest_setup(item):
    """Reset rumps module before tests that need real/fresh imports.

    test_menu.py modifies sys.modules["rumps"] at import time with a mock.
    This pollutes subsequent tests. We reset it for affected test files.
    """
    # List of test files that need fresh rumps imports (not the mock from test_menu.py)
    needs_fresh_rumps = ["test_tooltips"]

    if any(name in str(item.fspath) for name in needs_fresh_rumps):
        # Remove any mock rumps before these tests
        if "rumps" in sys.modules:
            current = sys.modules["rumps"]
            if not hasattr(current, "__file__"):  # It's a mock
                del sys.modules["rumps"]
                # Only clear modules that actually import rumps (not all ui/app modules)
                rumps_dependent_modules = [
                    "opencode_status_bar.ui.menu",
                    "opencode_status_bar.app",
                    "opencode_status_bar.app.core",
                    "opencode_status_bar.app.menu",
                ]
                for mod in rumps_dependent_modules:
                    if mod in sys.modules:
                        del sys.modules[mod]
