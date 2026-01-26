"""Widget for assigning parts to tools with cavities, lifters, and sliders configuration."""

from typing import List, Dict, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QSpinBox, QHeaderView, QMessageBox,
    QAbstractItemView
)
from PyQt6.QtCore import Qt

from database import ToolPartConfiguration
from database.connection import session_scope
from database.models import Part
from ..dialogs.part_selection_dialog import PartSelectionDialog


class PartAssignmentWidget(QWidget):
    """Widget for managing tool-part assignments with per-part cavities, lifters, sliders."""

    def __init__(self, rfq_id: int, parent=None, on_config_changed=None):
        super().__init__(parent)
        self.rfq_id = rfq_id
        self.part_configs = []  # List of ToolPartConfiguration-like dicts
        self.on_config_changed = on_config_changed  # Callback when parts change

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI layout."""
        layout = QVBoxLayout(self)

        # Configuration inputs (for the part to be added)
        config_label = QLabel("Configuration (for next part to add):")
        config_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(config_label)

        # Cavities and Lifters on same row
        cav_lift_layout = QHBoxLayout()
        cav_lift_layout.addWidget(QLabel("Cavities:"))
        self.cavities_spin = QSpinBox()
        self.cavities_spin.setRange(1, 100)
        self.cavities_spin.setValue(1)
        cav_lift_layout.addWidget(self.cavities_spin)
        cav_lift_layout.addSpacing(20)
        cav_lift_layout.addWidget(QLabel("Lifters:"))
        self.lifters_spin = QSpinBox()
        self.lifters_spin.setRange(0, 50)
        self.lifters_spin.setValue(0)
        cav_lift_layout.addWidget(self.lifters_spin)
        cav_lift_layout.addStretch()
        layout.addLayout(cav_lift_layout)

        # Sliders on its own row
        sld_layout = QHBoxLayout()
        sld_layout.addWidget(QLabel("Sliders:"))
        self.sliders_spin = QSpinBox()
        self.sliders_spin.setRange(0, 50)
        self.sliders_spin.setValue(0)
        sld_layout.addWidget(self.sliders_spin)
        sld_layout.addStretch()
        layout.addLayout(sld_layout)

        # Select part button
        self.btn_select_part = QPushButton("Select Part from BOM...")
        self.btn_select_part.clicked.connect(self._on_select_part_clicked)
        layout.addWidget(self.btn_select_part)

        layout.addSpacing(15)

        # Separator
        separator = QLabel("─" * 60)
        separator.setStyleSheet("color: #cccccc;")
        layout.addWidget(separator)

        layout.addSpacing(5)

        # Assigned parts table
        assigned_label = QLabel("Assigned to This Tool:")
        assigned_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(assigned_label)

        self.assignments_table = QTableWidget()
        self.assignments_table.setColumnCount(5)
        self.assignments_table.setHorizontalHeaderLabels(["Part", "Cavities", "Lifters", "Sliders", ""])
        self.assignments_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.assignments_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.assignments_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.assignments_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.assignments_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.assignments_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.assignments_table)

        # Remove button
        self.btn_remove = QPushButton("← Remove Selected")
        self.btn_remove.clicked.connect(self._on_remove_part)
        layout.addWidget(self.btn_remove)

        # Totals display
        self.totals_label = QLabel("Totals: 0 cavities, 0 lifters, 0 sliders")
        self.totals_label.setStyleSheet("font-weight: bold; padding: 5px; background-color: #f0f0f0;")
        layout.addWidget(self.totals_label)

    def _on_select_part_clicked(self):
        """Open part selection dialog and add selected part to assignments."""
        # Get currently assigned part IDs
        assigned_ids = [c['part_id'] for c in self.part_configs]

        # Open part selection dialog
        dialog = PartSelectionDialog(self.rfq_id, assigned_ids, self)
        if dialog.exec() == PartSelectionDialog.DialogCode.Accepted:
            selected_part_id = dialog.get_selected_part_id()
            if selected_part_id:
                # Load part details from database
                with session_scope() as session:
                    part = session.query(Part).get(selected_part_id)
                    if part:
                        part_name = part.name
                    else:
                        QMessageBox.warning(self, "Error", "Could not load part details")
                        return

                # Get configuration from spinboxes
                cavities = self.cavities_spin.value()
                lifters = self.lifters_spin.value()
                sliders = self.sliders_spin.value()

                # Check for duplicates
                for config in self.part_configs:
                    if config['part_id'] == selected_part_id:
                        QMessageBox.warning(self, "Duplicate", f"'{part_name}' is already assigned")
                        return

                # Add to configuration list
                self.part_configs.append({
                    'part_id': selected_part_id,
                    'part_name': part_name,
                    'cavities': cavities,
                    'lifters_count': lifters,
                    'sliders_count': sliders,
                    'config_group_id': None  # Reserved for future alternative configurations
                })

                self._refresh_assignments_table()

                # Trigger callback if set
                if self.on_config_changed:
                    self.on_config_changed()

    def _on_remove_part(self):
        """Remove selected part from assignments."""
        selected = self.assignments_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a part to remove")
            return

        row = selected[0].row()
        if 0 <= row < len(self.part_configs):
            self.part_configs.pop(row)
            self._refresh_assignments_table()

            # Trigger callback if set
            if self.on_config_changed:
                self.on_config_changed()

    def _refresh_assignments_table(self):
        """Refresh the assignments table display."""
        self.assignments_table.setRowCount(len(self.part_configs))

        total_cavities = 0
        total_lifters = 0
        total_sliders = 0

        for row, config in enumerate(self.part_configs):
            self.assignments_table.setItem(row, 0, QTableWidgetItem(config['part_name']))
            self.assignments_table.setItem(row, 1, QTableWidgetItem(str(config['cavities'])))
            self.assignments_table.setItem(row, 2, QTableWidgetItem(str(config['lifters_count'])))
            self.assignments_table.setItem(row, 3, QTableWidgetItem(str(config['sliders_count'])))

            total_cavities += config['cavities']
            total_lifters += config['lifters_count']
            total_sliders += config['sliders_count']

        self.totals_label.setText(
            f"Totals: {total_cavities} cavities, {total_lifters} lifters, {total_sliders} sliders"
        )

    def get_part_configurations(self) -> List[Dict]:
        """Get configured parts for saving."""
        return self.part_configs

    def set_part_configurations(self, configs: List[Dict]):
        """Load existing configurations."""
        self.part_configs = configs
        self._refresh_assignments_table()
