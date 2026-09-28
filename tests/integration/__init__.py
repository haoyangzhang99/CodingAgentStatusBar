"""
Integration tests for the OpenCode Status Bar dashboard.

This package contains end-to-end tests for the PyQt dashboard UI
using pytest-qt. Tests can run in both headless and visible modes.

Structure:
- conftest.py: Shared fixtures (mock API, qtbot, etc.)
- fixtures/: Test data and API response mocks
- test_dashboard_launch.py: Window creation and lifecycle tests
- test_dashboard_navigation.py: Sidebar and page switching tests
- test_dashboard_sections.py: Section-specific functionality tests
"""
