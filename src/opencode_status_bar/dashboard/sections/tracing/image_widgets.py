"""
Image widgets for tracing section.

Provides ImageThumbnail for inline display and ImagePreviewDialog
for full-size image viewing.
"""

from typing import Optional
import base64

from PyQt6.QtWidgets import QLabel, QWidget, QDialog, QVBoxLayout, QScrollArea
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, pyqtSignal, QByteArray

from opencode_status_bar.dashboard.styles import COLORS, RADIUS


class ImageThumbnail(QLabel):
    """Clickable image thumbnail with lazy loading.

    Visual:
        +--------+
        |  IMG   |  <- 48x48 thumbnail
        |        |     Click to expand
        +--------+

    Usage:
        thumb = ImageThumbnail()
        thumb.set_image_url("data:image/png;base64,...")
        thumb.clicked.connect(self._show_full_image)
    """

    clicked = pyqtSignal(str)  # Emits data_url when clicked

    DEFAULT_SIZE = (48, 48)
    DETAIL_SIZE = (128, 128)

    def __init__(
        self,
        size: tuple[int, int] = DEFAULT_SIZE,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._data_url: str = ""
        self._size = size
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup widget appearance."""
        self.setFixedSize(*self._size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS["bg_hover"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["sm"]}px;
            }}
            QLabel:hover {{
                border-color: {COLORS["border_strong"]};
            }}
        """)
        self.setText("...")  # Placeholder
        self.hide()  # Hidden by default

    def set_image_url(self, data_url: Optional[str]) -> None:
        """Set image from base64 data URL.

        Args:
            data_url: Data URL (data:image/png;base64,...) or None
        """
        if not data_url or not data_url.startswith("data:image"):
            self.hide()
            return

        self._data_url = data_url

        # Parse data URL
        try:
            # Format: data:image/png;base64,<data>
            header, b64_data = data_url.split(",", 1)
            image_data = base64.b64decode(b64_data)

            # Create QImage from data
            image = QImage()
            image.loadFromData(QByteArray(image_data))

            if image.isNull():
                self.setText("?")
                self.hide()
                return

            # Scale to thumbnail size
            pixmap = QPixmap.fromImage(image)
            scaled = pixmap.scaled(
                *self._size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            self.setPixmap(scaled)

            # Set tooltip with image info
            self.setToolTip(
                f"Image: {image.width()}x{image.height()}\nClick to view full size"
            )
            self.show()

        except Exception:
            self.setText("!")
            self.setToolTip("Failed to load image")
            self.hide()

    def mousePressEvent(self, event) -> None:
        """Handle click to expand image."""
        if event.button() == Qt.MouseButton.LeftButton and self._data_url:
            self.clicked.emit(self._data_url)
        super().mousePressEvent(event)

    def data_url(self) -> str:
        """Return current data URL."""
        return self._data_url


class ImagePreviewDialog(QDialog):
    """Full-size image preview dialog.

    Usage:
        dialog = ImagePreviewDialog(data_url, parent)
        dialog.exec()
    """

    MAX_SIZE = (800, 600)

    def __init__(self, data_url: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Image Preview")
        self.setModal(True)
        self._setup_ui(data_url)

    def _setup_ui(self, data_url: str) -> None:
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for large images
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background-color: {COLORS['bg_base']};")

        # Image label
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        try:
            _, b64_data = data_url.split(",", 1)
            image_data = base64.b64decode(b64_data)

            image = QImage()
            image.loadFromData(QByteArray(image_data))

            pixmap = QPixmap.fromImage(image)

            # Scale if too large
            if pixmap.width() > self.MAX_SIZE[0] or pixmap.height() > self.MAX_SIZE[1]:
                pixmap = pixmap.scaled(
                    *self.MAX_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

            image_label.setPixmap(pixmap)
            self.resize(pixmap.width() + 20, pixmap.height() + 20)

        except Exception:
            image_label.setText("Failed to load image")

        scroll.setWidget(image_label)
        layout.addWidget(scroll)

    def keyPressEvent(self, event) -> None:
        """Close on ESC."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)
