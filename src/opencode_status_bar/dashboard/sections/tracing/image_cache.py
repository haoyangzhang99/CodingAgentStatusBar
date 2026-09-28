"""
Image thumbnail cache for tracing section.

Provides caching for decoded image thumbnails to improve performance
when displaying images in the timeline and tree views.
"""

from typing import Optional
import base64

from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import QByteArray, QThread, pyqtSignal, QObject, Qt


class ThumbnailCache(QObject):
    """LRU cache for decoded image thumbnails.

    Design:
    - Cache key: hash of data_url + size
    - Max cache size: 50 images (~5MB at 48x48)
    - Async decoding in worker thread
    """

    thumbnail_ready = pyqtSignal(str, object)  # (cache_key, QPixmap)

    MAX_CACHE_SIZE = 50

    def __init__(self):
        super().__init__()
        self._cache: dict[str, QPixmap] = {}
        self._pending: set[str] = set()
        self._worker: Optional["ThumbnailWorker"] = None

    def get_thumbnail(
        self, data_url: str, size: tuple[int, int] = (48, 48)
    ) -> Optional[QPixmap]:
        """Get cached thumbnail synchronously.

        Args:
            data_url: Base64 data URL
            size: Target thumbnail size

        Returns:
            QPixmap if cached, None otherwise
        """
        cache_key = self._make_key(data_url, size)
        return self._cache.get(cache_key)

    def request_thumbnail(
        self, data_url: str, size: tuple[int, int] = (48, 48)
    ) -> None:
        """Request async thumbnail generation.

        Connect to thumbnail_ready signal for result.

        Args:
            data_url: Base64 data URL
            size: Target thumbnail size
        """
        cache_key = self._make_key(data_url, size)

        # Already cached or pending
        if cache_key in self._cache or cache_key in self._pending:
            if cache_key in self._cache:
                self.thumbnail_ready.emit(cache_key, self._cache[cache_key])
            return

        # Start worker if needed
        if self._worker is None or not self._worker.isRunning():
            self._worker = ThumbnailWorker()
            self._worker.decoded.connect(self._on_decoded)
            self._worker.start()

        self._pending.add(cache_key)
        self._worker.add_task(cache_key, data_url, size)

    def _on_decoded(self, cache_key: str, pixmap: QPixmap) -> None:
        """Handle decoded thumbnail from worker."""
        self._pending.discard(cache_key)

        if pixmap and not pixmap.isNull():
            # Evict oldest if cache full
            if len(self._cache) >= self.MAX_CACHE_SIZE:
                oldest = next(iter(self._cache))
                del self._cache[oldest]

            self._cache[cache_key] = pixmap

        self.thumbnail_ready.emit(cache_key, pixmap)

    def _make_key(self, data_url: str, size: tuple[int, int]) -> str:
        """Create cache key from data_url and size.

        Args:
            data_url: Base64 data URL
            size: Thumbnail size

        Returns:
            Unique cache key string
        """
        # Use hash of URL prefix (first 100 chars) + size
        url_hash = hash(data_url[:100] if data_url else "")
        return f"{url_hash}_{size[0]}x{size[1]}"

    def clear(self) -> None:
        """Clear all cached thumbnails."""
        self._cache.clear()


class ThumbnailWorker(QThread):
    """Background worker for decoding images."""

    decoded = pyqtSignal(str, object)  # (cache_key, QPixmap)

    def __init__(self):
        super().__init__()
        self._tasks: list[tuple[str, str, tuple[int, int]]] = []
        self._running = True

    def add_task(self, cache_key: str, data_url: str, size: tuple[int, int]) -> None:
        """Add decoding task to queue."""
        self._tasks.append((cache_key, data_url, size))

    def run(self) -> None:
        """Process tasks in background."""
        while self._running and self._tasks:
            cache_key, data_url, size = self._tasks.pop(0)

            try:
                pixmap = self._decode_thumbnail(data_url, size)
                self.decoded.emit(cache_key, pixmap)
            except Exception:
                self.decoded.emit(cache_key, QPixmap())

    def _decode_thumbnail(self, data_url: str, size: tuple[int, int]) -> QPixmap:
        """Decode base64 image to scaled pixmap.

        Args:
            data_url: Base64 data URL
            size: Target size

        Returns:
            Scaled QPixmap
        """
        _, b64_data = data_url.split(",", 1)
        image_data = base64.b64decode(b64_data)

        image = QImage()
        image.loadFromData(QByteArray(image_data))

        if image.isNull():
            return QPixmap()

        pixmap = QPixmap.fromImage(image)
        return pixmap.scaled(
            *size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def stop(self) -> None:
        """Stop worker thread."""
        self._running = False


# Global cache instance
_thumbnail_cache: Optional[ThumbnailCache] = None


def get_thumbnail_cache() -> ThumbnailCache:
    """Get or create global thumbnail cache."""
    global _thumbnail_cache
    if _thumbnail_cache is None:
        _thumbnail_cache = ThumbnailCache()
    return _thumbnail_cache
