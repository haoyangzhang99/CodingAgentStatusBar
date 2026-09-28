"""
Dashboard launcher for spawning the dashboard as a subprocess.

Since rumps has its own event loop, we launch the PyQt dashboard
as a subprocess to avoid conflicts between event loops.
"""

import subprocess  # nosec B404 - required for dashboard subprocess
import sys

# Global reference to dashboard subprocess
_dashboard_process = None


def show_dashboard() -> None:
    """Show the dashboard window in a separate process.

    Since rumps has its own event loop, we launch the PyQt dashboard
    as a subprocess to avoid conflicts between event loops.
    """
    global _dashboard_process

    # Kill existing dashboard if running
    if _dashboard_process is not None:
        poll_result = _dashboard_process.poll()
        if poll_result is None:
            _dashboard_process.terminate()
            try:
                _dashboard_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                _dashboard_process.kill()
        _dashboard_process = None

    # Launch dashboard as a separate process
    _dashboard_process = subprocess.Popen(  # nosec B603 - trusted sys.executable
        [sys.executable, "-m", "opencode_status_bar.dashboard"],
        start_new_session=True,
    )
