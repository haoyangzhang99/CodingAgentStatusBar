"""
Dashboard entry point for subprocess execution.

Usage: python -m opencode_status_bar.dashboard
"""

import sys
from PyQt6.QtWidgets import QApplication
from .window import DashboardWindow


def main():
    """Run the dashboard as a standalone Qt application."""
    app = QApplication(sys.argv)

    window = DashboardWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
