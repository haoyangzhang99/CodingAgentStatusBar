"""Tests for image-related widgets and cache."""

import pytest
import base64
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt


# Minimal valid 1x1 red PNG for testing
MINIMAL_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
VALID_PNG_DATA_URL = f"data:image/png;base64,{MINIMAL_PNG_BASE64}"
INVALID_DATA_URL = "not-a-data-url"


class TestImageThumbnail:
    """Tests for ImageThumbnail widget."""

    def test_valid_image_shows_widget(self, qtbot):
        """Widget should be visible when valid image is set."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url(VALID_PNG_DATA_URL)

        assert thumb.isVisible()
        pixmap = thumb.pixmap()
        assert not pixmap.isNull()
        assert pixmap.width() > 0
        assert pixmap.height() > 0

    def test_invalid_url_hides_widget(self, qtbot):
        """Widget should be hidden for invalid URL."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url(INVALID_DATA_URL)

        assert not thumb.isVisible()

    def test_empty_url_hides_widget(self, qtbot):
        """Widget should be hidden for empty URL."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url("")

        assert not thumb.isVisible()

    def test_none_url_hides_widget(self, qtbot):
        """Widget should be hidden for None URL."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url(None)

        assert not thumb.isVisible()

    def test_data_url_property(self, qtbot):
        """Should return the stored data URL."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url(VALID_PNG_DATA_URL)

        assert thumb.data_url() == VALID_PNG_DATA_URL

    def test_click_emits_signal(self, qtbot):
        """Click should emit signal with data URL."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url(VALID_PNG_DATA_URL)

        with qtbot.waitSignal(thumb.clicked, timeout=1000) as blocker:
            qtbot.mouseClick(thumb, Qt.MouseButton.LeftButton)

        assert blocker.args[0] == VALID_PNG_DATA_URL

    def test_tooltip_shows_image_info(self, qtbot):
        """Tooltip should show image dimensions."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url(VALID_PNG_DATA_URL)

        tooltip = thumb.toolTip()
        assert "Image:" in tooltip or "1x1" in tooltip

    def test_custom_size(self, qtbot):
        """Should respect custom size parameter."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        custom_size = (64, 64)
        thumb = ImageThumbnail(size=custom_size)
        qtbot.addWidget(thumb)

        assert thumb.width() == custom_size[0]
        assert thumb.height() == custom_size[1]


class TestThumbnailCache:
    """Tests for ThumbnailCache."""

    def test_get_thumbnail_returns_none_for_uncached(self):
        """Should return None for uncached images."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            ThumbnailCache,
        )

        cache = ThumbnailCache()
        result = cache.get_thumbnail(VALID_PNG_DATA_URL)
        # Should return None for uncached images
        assert result is None

    def test_cache_stores_thumbnail(self, qapp):
        """Should store and retrieve thumbnails."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            ThumbnailCache,
        )
        from PyQt6.QtGui import QPixmap

        cache = ThumbnailCache()
        pixmap = QPixmap(10, 10)
        cache_key = cache._make_key(VALID_PNG_DATA_URL, (48, 48))

        cache._cache[cache_key] = pixmap
        result = cache.get_thumbnail(VALID_PNG_DATA_URL)

        # Should return the cached pixmap
        assert result == pixmap
        assert not result.isNull()

    def test_make_key_includes_size(self):
        """Cache key should include size for different resolutions."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            ThumbnailCache,
        )

        cache = ThumbnailCache()
        key1 = cache._make_key(VALID_PNG_DATA_URL, (48, 48))
        key2 = cache._make_key(VALID_PNG_DATA_URL, (128, 128))

        assert key1 != key2

    def test_clear_empties_cache(self, qapp):
        """Clear should remove all cached items."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            ThumbnailCache,
        )
        from PyQt6.QtGui import QPixmap

        cache = ThumbnailCache()
        cache._cache["test_key"] = QPixmap(10, 10)
        assert "test_key" in cache._cache

        cache.clear()
        assert len(cache._cache) == 0
        assert "test_key" not in cache._cache


class TestImagePreviewDialog:
    """Tests for ImagePreviewDialog."""

    def test_dialog_creates_with_valid_image(self, qtbot):
        """Dialog should create successfully with valid image."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImagePreviewDialog,
        )

        dialog = ImagePreviewDialog(VALID_PNG_DATA_URL)
        qtbot.addWidget(dialog)

        # Dialog should be created successfully
        assert dialog.windowTitle() != ""
        assert dialog.isModal()

    def test_escape_closes_dialog(self, qtbot):
        """ESC key should close the dialog."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImagePreviewDialog,
        )
        from PyQt6.QtCore import Qt

        dialog = ImagePreviewDialog(VALID_PNG_DATA_URL)
        qtbot.addWidget(dialog)
        dialog.show()

        qtbot.keyClick(dialog, Qt.Key.Key_Escape)

        # Dialog should be closed (or closing)
        assert not dialog.isVisible()

    def test_dialog_with_invalid_image(self, qtbot):
        """Dialog should handle invalid image data gracefully."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImagePreviewDialog,
        )

        # Invalid base64 that will fail to decode as image
        invalid_data_url = "data:image/png;base64,invaliddata"
        dialog = ImagePreviewDialog(invalid_data_url)
        qtbot.addWidget(dialog)

        # Dialog should still be created without crashing
        assert dialog.windowTitle() != ""

    def test_dialog_with_large_image(self, qtbot):
        """Dialog should scale large images to fit MAX_SIZE."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImagePreviewDialog,
        )
        from PyQt6.QtGui import QImage, QPixmap
        from PyQt6.QtCore import QBuffer, QIODevice, QByteArray
        import base64

        # Create a large image (1000x1000)
        large_image = QImage(1000, 1000, QImage.Format.Format_RGB32)
        large_image.fill(0xFF0000)  # Red

        # Convert to PNG base64
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        large_image.save(buffer, "PNG")
        buffer.close()

        b64_data = base64.b64encode(buffer.data().data()).decode()
        large_data_url = f"data:image/png;base64,{b64_data}"

        dialog = ImagePreviewDialog(large_data_url)
        qtbot.addWidget(dialog)

        # Dialog should be created and scaled down
        assert dialog.windowTitle() != ""
        # Dialog dimensions should be limited by MAX_SIZE (800x600)
        assert dialog.width() <= 820  # 800 + margin
        assert dialog.height() <= 620  # 600 + margin


class TestImageThumbnailErrorHandling:
    """Tests for error handling in ImageThumbnail."""

    def test_corrupted_base64_hides_widget(self, qtbot):
        """Widget should hide on corrupted base64 data."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)

        # Valid format but invalid base64 that causes decode error
        corrupted_url = "data:image/png;base64,not_valid_base64_!!!"
        thumb.set_image_url(corrupted_url)

        assert not thumb.isVisible()

    def test_valid_base64_invalid_image_hides_widget(self, qtbot):
        """Widget should hide when base64 decodes but isn't a valid image."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )
        import base64

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)

        # Valid base64 of text, not an image
        text_data = base64.b64encode(b"This is not an image").decode()
        invalid_image_url = f"data:image/png;base64,{text_data}"
        thumb.set_image_url(invalid_image_url)

        assert not thumb.isVisible()

    def test_click_without_data_url_does_nothing(self, qtbot):
        """Click on empty thumbnail should not emit signal."""
        from opencode_status_bar.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)

        # Don't set any image - verify signal is NOT emitted
        thumb.show()

        # Use assertNotEmitted to verify signal is NOT emitted
        with qtbot.assertNotEmitted(thumb.clicked, wait=100):
            qtbot.mouseClick(thumb, Qt.MouseButton.LeftButton)


class TestThumbnailCacheAdvanced:
    """Advanced tests for ThumbnailCache functionality."""

    def test_get_thumbnail_cache_returns_singleton(self):
        """get_thumbnail_cache should return same instance."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            get_thumbnail_cache,
        )

        cache1 = get_thumbnail_cache()
        cache2 = get_thumbnail_cache()

        assert cache1 is cache2

    def test_cache_evicts_oldest_when_full(self, qtbot):
        """Cache should evict oldest entries when MAX_CACHE_SIZE exceeded."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            ThumbnailCache,
        )
        from PyQt6.QtGui import QPixmap

        cache = ThumbnailCache()
        original_max = cache.MAX_CACHE_SIZE
        cache.MAX_CACHE_SIZE = 3  # Small limit for testing

        try:
            # Add 3 items (at capacity)
            for i in range(3):
                cache._cache[f"key_{i}"] = QPixmap(10, 10)

            assert len(cache._cache) == 3
            assert "key_0" in cache._cache
            assert "key_1" in cache._cache
            assert "key_2" in cache._cache

            # Simulate _on_decoded adding a 4th item (emits signal)
            new_pixmap = QPixmap(10, 10)
            with qtbot.waitSignal(cache.thumbnail_ready, timeout=1000):
                cache._on_decoded("key_3", new_pixmap)

            # Should have evicted oldest (key_0) and kept the rest
            assert len(cache._cache) == 3
            assert "key_0" not in cache._cache
            assert "key_1" in cache._cache
            assert "key_2" in cache._cache
            assert "key_3" in cache._cache
        finally:
            cache.MAX_CACHE_SIZE = original_max

    def test_on_decoded_emits_signal(self, qtbot):
        """_on_decoded should emit thumbnail_ready signal."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            ThumbnailCache,
        )
        from PyQt6.QtGui import QPixmap

        cache = ThumbnailCache()
        test_pixmap = QPixmap(10, 10)

        with qtbot.waitSignal(cache.thumbnail_ready, timeout=1000) as blocker:
            cache._on_decoded("test_key", test_pixmap)

        assert blocker.signal_triggered
        assert blocker.args[0] == "test_key"

    def test_on_decoded_handles_null_pixmap(self):
        """_on_decoded should handle null pixmap gracefully."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            ThumbnailCache,
        )
        from PyQt6.QtGui import QPixmap

        cache = ThumbnailCache()
        null_pixmap = QPixmap()  # Null pixmap

        # Should not crash
        cache._on_decoded("null_key", null_pixmap)

        # Should not be cached
        assert "null_key" not in cache._cache

    def test_make_key_handles_empty_data_url(self):
        """_make_key should handle empty/None data URLs."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            ThumbnailCache,
        )

        cache = ThumbnailCache()

        key1 = cache._make_key("", (48, 48))
        key2 = cache._make_key("", (48, 48))

        # Same empty URL should produce same key
        assert key1 == key2

    def test_request_thumbnail_skips_if_already_cached(self, qtbot):
        """request_thumbnail should emit immediately if already cached."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            ThumbnailCache,
        )
        from PyQt6.QtGui import QPixmap

        cache = ThumbnailCache()

        # Pre-cache the thumbnail
        cache_key = cache._make_key(VALID_PNG_DATA_URL, (48, 48))
        cached_pixmap = QPixmap(48, 48)
        cache._cache[cache_key] = cached_pixmap

        # Request should emit immediately
        with qtbot.waitSignal(cache.thumbnail_ready, timeout=1000) as blocker:
            cache.request_thumbnail(VALID_PNG_DATA_URL)

        assert blocker.signal_triggered
        assert blocker.args[0] == cache_key


class TestThumbnailWorker:
    """Tests for ThumbnailWorker thread."""

    def test_worker_stop(self):
        """Worker stop() should set _running to False."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            ThumbnailWorker,
        )

        worker = ThumbnailWorker()
        # Worker should start in running state
        assert worker._running is True

        worker.stop()
        # After stop, worker should not be running
        assert worker._running is False

    def test_worker_add_task(self):
        """add_task should add to task queue."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            ThumbnailWorker,
        )

        worker = ThumbnailWorker()
        # Initially no tasks
        assert len(worker._tasks) == 0

        worker.add_task("key1", VALID_PNG_DATA_URL, (48, 48))

        # After adding task, should have exactly 1 task
        assert len(worker._tasks) == 1
        assert worker._tasks[0][0] == "key1"
        assert worker._tasks[0][1] == VALID_PNG_DATA_URL
        assert worker._tasks[0][2] == (48, 48)

    def test_worker_decode_thumbnail_valid(self, qtbot):
        """_decode_thumbnail should decode valid PNG (needs Qt context)."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            ThumbnailWorker,
        )
        from PyQt6.QtWidgets import QWidget

        # Create a widget to ensure Qt context
        widget = QWidget()
        qtbot.addWidget(widget)

        worker = ThumbnailWorker()
        pixmap = worker._decode_thumbnail(VALID_PNG_DATA_URL, (48, 48))

        assert not pixmap.isNull()

    def test_worker_decode_thumbnail_invalid(self, qtbot):
        """_decode_thumbnail should return null pixmap for invalid data."""
        from opencode_status_bar.dashboard.sections.tracing.image_cache import (
            ThumbnailWorker,
        )
        from PyQt6.QtWidgets import QWidget
        import base64

        # Create a widget to ensure Qt context
        widget = QWidget()
        qtbot.addWidget(widget)

        worker = ThumbnailWorker()

        # Valid base64 but not an image
        text_data = base64.b64encode(b"not an image").decode()
        invalid_url = f"data:image/png;base64,{text_data}"

        pixmap = worker._decode_thumbnail(invalid_url, (48, 48))

        assert pixmap.isNull()
