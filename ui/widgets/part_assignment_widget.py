"""Widget for assigning parts to tools with cavities, lifters, and sliders configuration."""

from typing import List, Dict, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QSpinBox, QHeaderView, QMessageBox, QComboBox,
    QAbstractItemView
)
from PyQt6.QtCore import Qt

from database import ToolPartConfiguration
from database.connection import session_scope
from database.models import Part, RFQ


class PartAssignmentWidget(QWidget):
    """Widget for managing tool-part assignments with per-part cavities, lifters, sliders."""

    def __init__(self, rfq_id: int, parent=None, on_config_changed=None):
        super().__init__(parent)
        self.rfq_id = rfq_id
        self.part_configs = []  # List of ToolPartConfiguration-like dicts
        self.on_config_changed = on_config_changed  # Callback when parts change

        self._setup_ui()
        self._load_available_parts()

    def _setup_ui(self):
        """Setup the UI layout."""
        layout = QVBoxLayout(self)

        # Available parts list (left side)
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Available Parts (from BOM):"))

        self.available_parts_combo = QComboBox()
        self.available_parts_combo.addItem("- Select a part -", None)
        left_layout.addWidget(self.available_parts_combo)

        # Configuration inputs (for the selected part)
        config_layout = QVBoxLayout()
        config_layout.addWidget(QLabel("Configuration:"))

        cav_layout = QHBoxLayout()
        cav_layout.addWidget(QLabel("Cavities:"))
        self.cavities_spin = QSpinBox()
        self.cavities_spin.setRange(1, 100)
        self.cavities_spin.setValue(1)
        cav_layout.addWidget(self.cavities_spin)
        cav_layout.addStretch()
        config_layout.addLayout(cav_layout)

        lift_layout = QHBoxLayout()
        lift_layout.addWidget(QLabel("Lifters:"))
        self.lifters_spin = QSpinBox()
        self.lifters_spin.setRange(0, 50)
        self.lifters_spin.setValue(0)
        lift_layout.addWidget(self.lifters_spin)
        lift_layout.addStretch()
        config_layout.addLayout(lift_layout)

        sld_layout = QHBoxLayout()
        sld_layout.addWidget(QLabel("Sliders:"))
        self.sliders_spin = QSpinBox()
        self.sliders_spin.setRange(0, 50)
        self.sliders_spin.setValue(0)
        sld_layout.addWidget(self.sliders_spin)
        sld_layout.addStretch()
        config_layout.addLayout(sld_layout)

        grp_layout = QHBoxLayout()
        grp_layout.addWidget(QLabel("Config Group (for OR):"))
        self.config_group_spin = QSpinBox()
        self.config_group_spin.setRange(0, 10)
        self.config_group_spin.setValue(0)
        grp_layout.addWidget(self.config_group_spin)
        grp_layout.addStretch()
        config_layout.addLayout(grp_layout)

        left_layout.addLayout(config_layout)

        # Add button
        self.btn_add = QPushButton("Add Part →")
        self.btn_add.clicked.connect(self._on_add_part)
        left_layout.addWidget(self.btn_add)

        left_layout.addStretch()

        # Assigned parts table (right side)
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Assigned to Tool:"))

        self.assignments_table = QTableWidget()
        self.assignments_table.setColumnCount(6)
        self.assignments_table.setHorizontalHeaderLabels(["Part", "Cavities", "Lifters", "Sliders", "Group", ""])
        self.assignments_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.assignments_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.assignments_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.assignments_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.assignments_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.assignments_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.assignments_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        right_layout.addWidget(self.assignments_table)

        # Remove button
        self.btn_remove = QPushButton("← Remove Selected")
        self.btn_remove.clicked.connect(self._on_remove_part)
        right_layout.addWidget(self.btn_remove)

        # Totals display
        self.totals_label = QLabel("Totals: 0 cavities, 0 lifters, 0 sliders")
        self.totals_label.setStyleSheet("font-weight: bold; padding: 5px; background-color: #f0f0f0;")
        right_layout.addWidget(self.totals_label)

        # Main horizontal layout
        main_layout = QHBoxLayout()
        main_layout.addLayout(left_layout, 0)
        main_layout.addLayout(right_layout, 1)

        layout.addLayout(main_layout)

    def _load_available_parts(self):
        """Load available parts from RFQ, greying out already assigned ones."""
        with session_scope() as session:
            parts = session.query(Part).filter(Part.rfq_id == self.rfq_id).order_by(Part.name).all()

            # Separate assigned and unassigned parts
            assigned_parts = []
            unassigned_parts = []

            for part in parts:
                # Check if already in our config list
                is_in_config = any(c['part_id'] == part.id for c in self.part_configs)

                if is_in_config:
                    assigned_parts.append(part)
                else:
                    unassigned_parts.append(part)

            # Add unassigned parts first (normal)
            for part in unassigned_parts:
                self.available_parts_combo.addItem(part.name, part.id)

            # Add separator
            if assigned_parts:
                self.available_parts_combo.insertSeparator(self.available_parts_combo.count())

            # Add assigned parts (greyed out)
            for part in assigned_parts:
                index = self.available_parts_combo.count()
                self.available_parts_combo.addItem(f"✓ {part.name} (assigned)", part.id)
                # Make the item disabled/greyed
                model = self.available_parts_combo.model()
                item = model.item(index)
                from PyQt6.QtGui import QColor
                item.setForeground(QColor("#999999"))
                item.setEnabled(False)

    def _on_add_part(self):
        """Add selected part to assignments."""
        part_id = self.available_parts_combo.currentData()
        if part_id is None:
            QMessageBox.warning(self, "No Selection", "Please select a part")
            return

        part_name = self.available_parts_combo.currentText()
        cavities = self.cavities_spin.value()
        lifters = self.lifters_spin.value()
        sliders = self.sliders_spin.value()
        config_group = self.config_group_spin.value() or None

        # Check for duplicates
        for config in self.part_configs:
            if config['part_id'] == part_id:
                QMessageBox.warning(self, "Duplicate", f"'{part_name}' is already assigned")
                return

        # Add to list
        self.part_configs.append({
            'part_id': part_id,
            'part_name': part_name,
            'cavities': cavities,
            'lifters_count': lifters,
            'sliders_count': sliders,
            'config_group_id': config_group
        })

        self._refresh_assignments_table()
        self._refresh_parts_list()  # Update combo list with greyed out

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
            self._refresh_parts_list()  # Update combo list (ungreyed)

            # Trigger callback if set
            if self.on_config_changed:
                self.on_config_changed()

    def _refresh_parts_list(self):
        """Refresh the available parts combo (move assigned to bottom, grey out)."""
        # Temporarily disconnect signal to avoid triggering during rebuild
        self.available_parts_combo.blockSignals(True)

        # Clear and rebuild
        self.available_parts_combo.clear()
        self._load_available_parts()

        self.available_parts_combo.blockSignals(False)

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

            group_text = str(config['config_group_id']) if config['config_group_id'] else "-"
            self.assignments_table.setItem(row, 4, QTableWidgetItem(group_text))

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
