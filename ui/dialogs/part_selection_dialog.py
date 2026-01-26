"""Part Selection Dialog for visual part selection from RFQ BOM."""

from typing import List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QColor

from database.connection import session_scope
from database.models import Part


class PartSelectionDialog(QDialog):
    """Modal dialog for selecting parts from RFQ BOM with visual preview.

    Features:
    - Displays all parts from RFQ with images and metadata
    - Shows assigned parts greyed out at bottom
    - Double-click or button selection to choose a part
    - Returns selected part_id or None if cancelled
    """

    def __init__(
        self,
        rfq_id: int,
        already_assigned_part_ids: List[int],
        parent=None
    ):
        """Initialize Part Selection Dialog.

        Args:
            rfq_id: RFQ ID to load parts from
            already_assigned_part_ids: List of part IDs that are already assigned (shown greyed)
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Select Part from BOM")
        self.setMinimumWidth(800)
        self.setMinimumHeight(500)
        self.setModal(True)

        self.rfq_id = rfq_id
        self.already_assigned_part_ids = set(already_assigned_part_ids)
        self.selected_part_id: Optional[int] = None

        # Load parts data
        self.available_parts: List[dict] = []
        self.assigned_parts: List[dict] = []
        self._load_parts()

        # Build UI
        self._setup_ui()

    def _load_parts(self) -> None:
        """Load parts from database, separated into available and assigned."""
        with session_scope() as session:
            all_parts = (
                session.query(Part)
                .filter(Part.rfq_id == self.rfq_id)
                .order_by(Part.name)
                .all()
            )

            for part in all_parts:
                part_dict = {
                    'id': part.id,
                    'name': part.name,
                    'part_number': part.part_number or '',
                    'volume_cm3': part.volume_cm3 or 0.0,
                    'weight_g': part.weight_g or 0.0,
                    'image_binary': part.image_binary,  # Binary data
                }

                if part.id in self.already_assigned_part_ids:
                    self.assigned_parts.append(part_dict)
                else:
                    self.available_parts.append(part_dict)

    def _setup_ui(self) -> None:
        """Build the dialog UI."""
        layout = QVBoxLayout()

        # Title label
        title_label = QLabel("Select a part from the RFQ BOM:")
        layout.addWidget(title_label)

        # Table widget
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Image", "Part Name", "Part #", "Volume (cm³)", "Weight (g)", "Status"
        ])

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Image
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # Part Name
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Part #
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Volume
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Weight
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Status

        self.table.setRowCount(len(self.available_parts) + 1 + len(self.assigned_parts))
        row = 0

        # Add available parts
        for part in self.available_parts:
            self._add_part_row(row, part, is_assigned=False)
            row += 1

        # Add separator row if there are assigned parts
        if self.assigned_parts:
            separator_item = QTableWidgetItem("─" * 50)
            separator_item.setFlags(separator_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 0, separator_item)
            row += 1

        # Add assigned parts (greyed out)
        for part in self.assigned_parts:
            self._add_part_row(row, part, is_assigned=True)
            row += 1

        # Connect double-click to select
        self.table.doubleClicked.connect(self._on_part_selected)

        layout.addWidget(self.table)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.btn_select = QPushButton("Select")
        self.btn_select.clicked.connect(self._on_part_selected)
        button_layout.addWidget(self.btn_select)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _add_part_row(self, row: int, part: dict, is_assigned: bool) -> None:
        """Add a part to the table.

        Args:
            row: Row index
            part: Part dictionary with id, name, part_number, volume_cm3, weight_g, image_binary
            is_assigned: Whether part is already assigned (greyed out)
        """
        # Image column
        img_label = QLabel()
        if part['image_binary']:
            pixmap = QPixmap()
            pixmap.loadFromData(part['image_binary'])
            scaled = pixmap.scaledToHeight(60, Qt.TransformationMode.SmoothTransformation)
            img_label.setPixmap(scaled)
        img_label.setFixedHeight(60)
        self.table.setCellWidget(row, 0, img_label)

        # Part Name
        name_item = QTableWidgetItem(part['name'])
        name_item.setData(Qt.ItemDataRole.UserRole, part['id'])  # Store part_id
        if is_assigned:
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.table.setItem(row, 1, name_item)

        # Part Number
        part_num_item = QTableWidgetItem(part['part_number'])
        if is_assigned:
            part_num_item.setFlags(part_num_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.table.setItem(row, 2, part_num_item)

        # Volume
        volume_item = QTableWidgetItem(f"{part['volume_cm3']:.2f}")
        if is_assigned:
            volume_item.setFlags(volume_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.table.setItem(row, 3, volume_item)

        # Weight
        weight_item = QTableWidgetItem(f"{part['weight_g']:.2f}")
        if is_assigned:
            weight_item.setFlags(weight_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.table.setItem(row, 4, weight_item)

        # Status
        status_text = "✓ Assigned" if is_assigned else "Available"
        status_item = QTableWidgetItem(status_text)
        if is_assigned:
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.table.setItem(row, 5, status_item)

        # Apply grey styling to assigned parts
        if is_assigned:
            grey_color = QColor(200, 200, 200)
            for col in range(6):
                item = self.table.item(row, col)
                if item:
                    item.setForeground(grey_color)
            img_label.setStyleSheet("color: grey;")

    def _on_part_selected(self) -> None:
        """Handle part selection (double-click or button click)."""
        current_row = self.table.currentRow()
        if current_row < 0:
            return

        # Get part_id from the Part Name cell (column 1)
        name_item = self.table.item(current_row, 1)
        if name_item:
            self.selected_part_id = name_item.data(Qt.ItemDataRole.UserRole)
            if self.selected_part_id is not None:
                self.accept()

    def get_selected_part_id(self) -> Optional[int]:
        """Return the selected part ID or None if cancelled."""
        return self.selected_part_id
