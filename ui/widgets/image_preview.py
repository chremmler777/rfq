"""Shared image preview window utility."""

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap


def show_image_preview(parent, title: str, image_data: bytes):
    """Show image preview in a zoom-capable window.

    Args:
        parent: Parent widget
        title: Window title (e.g., "Part Image: Housing")
        image_data: Binary image data (bytes)
    """
    zoom_window = QMainWindow(parent)
    zoom_window.setWindowTitle(title)
    zoom_window.setMinimumSize(800, 600)

    # Central widget
    central = QWidget()
    layout = QVBoxLayout(central)

    # Zoom buttons
    button_layout = QHBoxLayout()
    btn_zoom_in = QPushButton("🔍+ Zoom In")
    btn_zoom_out = QPushButton("🔍- Zoom Out")
    btn_fit = QPushButton("Fit Window")
    btn_close = QPushButton("Close")

    button_layout.addWidget(btn_zoom_in)
    button_layout.addWidget(btn_zoom_out)
    button_layout.addWidget(btn_fit)
    button_layout.addStretch()
    button_layout.addWidget(btn_close)
    layout.addLayout(button_layout)

    # Scroll area for image
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)

    # Image label
    img_label = QLabel()
    pixmap = QPixmap()
    pixmap.loadFromData(image_data)
    img_label.setPixmap(pixmap)
    img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    img_label.setScaledContents(False)

    scroll.setWidget(img_label)
    layout.addWidget(scroll)

    # Zoom controls
    zoom_factor = 1.0

    def zoom_in():
        nonlocal zoom_factor
        zoom_factor *= 1.2
        pixmap_scaled = pixmap.scaledToWidth(
            int(pixmap.width() * zoom_factor),
            Qt.TransformationMode.SmoothTransformation
        )
        img_label.setPixmap(pixmap_scaled)

    def zoom_out():
        nonlocal zoom_factor
        zoom_factor /= 1.2
        if zoom_factor < 0.1:
            zoom_factor = 0.1
        pixmap_scaled = pixmap.scaledToWidth(
            int(pixmap.width() * zoom_factor),
            Qt.TransformationMode.SmoothTransformation
        )
        img_label.setPixmap(pixmap_scaled)

    def fit_window():
        nonlocal zoom_factor
        zoom_factor = 1.0
        img_label.setPixmap(pixmap)

    btn_zoom_in.clicked.connect(zoom_in)
    btn_zoom_out.clicked.connect(zoom_out)
    btn_fit.clicked.connect(fit_window)
    btn_close.clicked.connect(zoom_window.close)

    zoom_window.setCentralWidget(central)
    zoom_window.show()
