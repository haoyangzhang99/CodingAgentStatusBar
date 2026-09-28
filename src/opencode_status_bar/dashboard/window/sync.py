"""Sync checker for detecting when menubar has synced new data."""

import time
from datetime import datetime
from typing import Callable, Optional

from PyQt6.QtCore import QTimer


class SyncChecker:
    """Polls API to detect when new data is available."""

    POLL_FAST_MS = 2000
    POLL_SLOW_MS = 5000
    IDLE_THRESHOLD_S = 30

    def __init__(self, on_sync_detected: Callable[[], None]):
        self._on_sync = on_sync_detected
        self._known_sync: Optional[datetime] = None
        self._last_change_time = time.time()

        self._timer = QTimer()
        self._timer.timeout.connect(self._check)
        self._timer.start(self.POLL_FAST_MS)

    def _check(self) -> None:
        try:
            from ...api import get_api_client

            client = get_api_client()

            if client.is_available:
                stats = client.get_stats()
                if stats:
                    current = stats.get("sessions", 0)

                    if current != self._known_sync:
                        first_check = self._known_sync is None
                        self._known_sync = current
                        self._last_change_time = time.time()
                        self._timer.setInterval(self.POLL_FAST_MS)
                        if not first_check:
                            self._on_sync()
                    elif time.time() - self._last_change_time > self.IDLE_THRESHOLD_S:
                        self._timer.setInterval(self.POLL_SLOW_MS)
        except Exception:
            pass

    def stop(self) -> None:
        self._timer.stop()
