"""Part/BOM entry dialog with modular geometry and weight/volume calculation."""

from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTextEdit, QPushButton, QMessageBox, QGroupBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QScrollArea, QFrame, QTabWidget, QTableWidget, QTableWidgetItem,
    QFileDialog, QRadioButton, QButtonGroup, QHeaderView, QWidget, QAbstractItemView
)
from PyQt6.QtCore import Qt, QByteArray, QMimeData
from PyQt6.QtGui import QPixmap, QIcon, QDragEnterEvent, QDropEvent

from database import DegateOption, EOATType, PartRevision, SubBOM
from database.connection import session_scope
from database.models import Part, RFQ, Material
from calculations import (
    GeometryFactory, BoxEstimateMode,
    WeightVolumeHelper, auto_calculate_volume, auto_calculate_weight
)


class ImageDropLabel(QLabel):
    """Label that accepts image files via drag-and-drop."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.image_dropped = None  # Callback for when image is dropped

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event."""
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("image/png") or event.mimeData().hasFormat("image/jpeg"):
            event.acceptProposedAction()
            self.setStyleSheet("border: 2px solid #0066cc; background-color: #f0f8ff;")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        self.setStyleSheet("border: 1px solid #ccc;")

    def dropEvent(self, event: QDropEvent):
        """Handle drop event."""
        self.setStyleSheet("border: 1px solid #ccc;")

        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    if self.image_dropped:
                        self.image_dropped(file_path)
                    event.acceptProposedAction()
                    break


class PartDialog(QDialog):
    """Dialog for creating/editing parts (BOM entries)."""

    def __init__(self, parent=None, rfq_id: int = None, part_id: int = None):
        super().__init__(parent)
        self.rfq_id = rfq_id
        self.part_id = part_id
        self.part = None
        self.image_data = None  # Store binary image data
        self.image_filename = None
        self._saved_part_id = None  # Track saved part ID to avoid detached object access
        self._wall_thickness_source = "given"  # Track if wall thickness was given or estimated

        self.setWindowTitle("Add Part to BOM" if not part_id else "Edit Part")
        self.setMinimumWidth(900)
        self.setMinimumHeight(900)
        self.setModal(True)

        self._load_part()
        self._load_materials()
        self._setup_ui()

    def _load_part(self):
        """Load existing part if editing."""
        if self.part_id:
            with session_scope() as session:
                self.part = session.query(Part).get(self.part_id)
                if self.part:
                    if self.part.image_binary:
                        self.image_data = self.part.image_binary
                        self.image_filename = self.part.image_filename
                    # Track wall thickness source
                    if hasattr(self.part, 'wall_thickness_source'):
                        self._wall_thickness_source = self.part.wall_thickness_source
                # Detach from session
                if self.part:
                    session.expunge(self.part)

    def _load_materials(self):
        """Load materials list."""
        with session_scope() as session:
            # Load all materials and detach them
            self.materials = session.query(Material).order_by(Material.family, Material.short_name).all()
            for mat in self.materials:
                session.expunge(mat)

    def _setup_ui(self):
        """Setup the dialog UI."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        main_widget = QFrame()
        layout = QVBoxLayout(main_widget)

        # Tab widget for organized sections
        tabs = QTabWidget()

        # ===== TAB 1: Basic Info =====
        basic_widget = self._create_basic_tab()
        tabs.addTab(basic_widget, "Basic Info")

        # ===== TAB 2: Geometry & Dimensions =====
        geometry_widget = self._create_geometry_tab()
        tabs.addTab(geometry_widget, "Geometry")

        # ===== TAB 3: Manufacturing Options =====
        mfg_widget = self._create_mfg_tab()
        tabs.addTab(mfg_widget, "Manufacturing")

        # ===== TAB 4: Demand & Notes =====
        demand_widget = self._create_demand_tab()
        tabs.addTab(demand_widget, "Demand & Notes")

        # ===== TAB 5: Revisions (if editing) =====
        if self.part_id:
            revisions_widget = self._create_revisions_tab()
            tabs.addTab(revisions_widget, "Revisions")

        layout.addWidget(tabs)
        scroll.setWidget(main_widget)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        # Buttons
        button_layout = QHBoxLayout()

        self.btn_save = QPushButton("Save Part")
        self.btn_save.clicked.connect(self._on_save)
        button_layout.addWidget(self.btn_save)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(button_layout)

    def _create_basic_tab(self) -> QWidget:
        """Create basic information tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("Part Name *"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Housing")
        if self.part:
            self.name_input.setText(self.part.name)
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Part Number"))
        self.part_number_input = QLineEdit()
        if self.part:
            self.part_number_input.setText(self.part.part_number or "")
        layout.addWidget(self.part_number_input)

        layout.addWidget(QLabel("Material"))
        self.material_combo = QComboBox()
        self.material_combo.addItem("- Select Material -", None)
        for mat in self.materials:
            self.material_combo.addItem(f"{mat.short_name} ({mat.family})", mat.id)
        if self.part and self.part.material_id:
            index = self.material_combo.findData(self.part.material_id)
            if index >= 0:
                self.material_combo.setCurrentIndex(index)
        self.material_combo.currentIndexChanged.connect(self._on_material_changed)
        layout.addWidget(self.material_combo)

        # Image upload
        layout.addWidget(QLabel("<b>Part Image (drag-drop or upload)</b>"))
        image_layout = QHBoxLayout()

        self.btn_upload_image = QPushButton("Upload Image")
        self.btn_upload_image.clicked.connect(self._on_upload_image)
        image_layout.addWidget(self.btn_upload_image)

        self.image_label = ImageDropLabel()
        self.image_label.setMinimumHeight(150)
        self.image_label.setStyleSheet("border: 1px solid #ccc;")
        self.image_label.image_dropped = self._process_dropped_image
        if self.image_data:
            pixmap = QPixmap()
            pixmap.loadFromData(self.image_data)
            self.image_label.setPixmap(pixmap.scaledToHeight(150, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(self.image_label)

        layout.addStretch()
        return tab

    def _create_geometry_tab(self) -> QWidget:
        """Create geometry/dimensions tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Geometry mode selector
        mode_group = QGroupBox("Geometry Input Mode")
        mode_layout = QVBoxLayout()

        self.geometry_mode_group = QButtonGroup()

        self.radio_direct = QRadioButton("Direct Projected Surface (cm²)")
        self.radio_box = QRadioButton("Box Estimate (L × W × Effective %)")
        self.geometry_mode_group.addButton(self.radio_direct, 0)
        self.geometry_mode_group.addButton(self.radio_box, 1)

        # Connect to toggle visibility
        self.radio_direct.toggled.connect(self._on_geometry_mode_changed)
        self.radio_box.toggled.connect(self._on_geometry_mode_changed)

        mode_layout.addWidget(self.radio_direct)
        mode_layout.addWidget(self.radio_box)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Direct mode
        self.direct_frame = QGroupBox("Direct Projected Surface Input")
        direct_layout = QVBoxLayout()
        direct_layout.addWidget(QLabel("Projected Surface (cm²)"))
        self.proj_area_spin = QDoubleSpinBox()
        self.proj_area_spin.setRange(0.1, 10000)
        self.proj_area_spin.setDecimals(2)
        if self.part and self.part.projected_area_cm2:
            self.proj_area_spin.setValue(self.part.projected_area_cm2)
        direct_layout.addWidget(self.proj_area_spin)
        self.direct_frame.setLayout(direct_layout)
        layout.addWidget(self.direct_frame)

        # Box mode
        self.box_frame = QGroupBox("Box Estimate Input")
        box_layout = QVBoxLayout()

        # Length input
        self.box_length_spin = self._create_dimension_input(
            box_layout, "Length (mm) - X dimension", 0.1, 10000,
            self.part.box_length_mm if self.part else None
        )

        # Width input
        self.box_width_spin = self._create_dimension_input(
            box_layout, "Width (mm) - Y dimension", 0.1, 10000,
            self.part.box_width_mm if self.part else None
        )

        # Effective % input with calculate button
        eff_row = QHBoxLayout()
        eff_row.addWidget(QLabel("Effective Surface %"))
        self.box_effective_spin = QDoubleSpinBox()
        self.box_effective_spin.setRange(0, 100)
        self.box_effective_spin.setDecimals(0)
        self.box_effective_spin.setValue(100)
        if self.part and self.part.box_effective_percent:
            self.box_effective_spin.setValue(self.part.box_effective_percent)
        eff_row.addWidget(self.box_effective_spin)
        eff_row.addWidget(QLabel("%"))

        self.btn_calc_area = QPushButton("Calculate Area")
        self.btn_calc_area.clicked.connect(self._on_calculate_box_area)
        eff_row.addWidget(self.btn_calc_area)
        box_layout.addLayout(eff_row)

        self.box_frame.setLayout(box_layout)
        layout.addWidget(self.box_frame)

        # Set initial mode
        if self.part and self.part.geometry_mode == "box":
            self.radio_box.setChecked(True)
        else:
            self.radio_direct.setChecked(True)

        # Apply initial visibility
        self._on_geometry_mode_changed()

        # Weight & Volume
        phys_frame = QGroupBox("Weight & Volume")
        phys_layout = QVBoxLayout()

        phys_row1 = QHBoxLayout()
        phys_row1.addWidget(QLabel("Weight (g)"))
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0.1, 100000)
        self.weight_spin.setDecimals(2)
        if self.part and self.part.weight_g:
            self.weight_spin.setValue(self.part.weight_g)
        phys_row1.addWidget(self.weight_spin)

        self.btn_vol_from_weight = QPushButton("→ Volume")
        self.btn_vol_from_weight.clicked.connect(self._on_calc_volume_from_weight)
        self.btn_vol_from_weight.setMaximumWidth(100)
        phys_row1.addWidget(self.btn_vol_from_weight)

        phys_layout.addLayout(phys_row1)

        phys_row2 = QHBoxLayout()
        phys_row2.addWidget(QLabel("Volume (cm³)"))
        self.volume_spin = QDoubleSpinBox()
        self.volume_spin.setRange(0.1, 1000000)
        self.volume_spin.setDecimals(2)
        if self.part and self.part.volume_cm3:
            self.volume_spin.setValue(self.part.volume_cm3)
        phys_row2.addWidget(self.volume_spin)

        self.btn_weight_from_vol = QPushButton("← Weight")
        self.btn_weight_from_vol.clicked.connect(self._on_calc_weight_from_volume)
        self.btn_weight_from_vol.setMaximumWidth(100)
        phys_row2.addWidget(self.btn_weight_from_vol)

        phys_layout.addLayout(phys_row2)

        phys_row3 = QHBoxLayout()
        phys_row3.addWidget(QLabel("Wall Thickness (mm)"))
        self.wall_thick_spin = QDoubleSpinBox()
        self.wall_thick_spin.setRange(0.5, 10)
        self.wall_thick_spin.setDecimals(2)
        if self.part and self.part.wall_thickness_mm:
            self.wall_thick_spin.setValue(self.part.wall_thickness_mm)
        phys_row3.addWidget(self.wall_thick_spin)

        # Wall thickness source tracking
        self.wall_thick_label = QLabel()
        self._update_wall_thickness_label()
        phys_row3.addWidget(self.wall_thick_label)

        self.btn_estimate_wall = QPushButton("Estimate (2.5mm)")
        self.btn_estimate_wall.clicked.connect(self._on_estimate_wall_thickness)
        self.btn_estimate_wall.setMaximumWidth(130)
        phys_row3.addWidget(self.btn_estimate_wall)
        phys_row3.addStretch()
        phys_layout.addLayout(phys_row3)

        phys_frame.setLayout(phys_layout)
        layout.addWidget(phys_frame)

        layout.addStretch()
        return tab

    def _create_mfg_tab(self) -> QWidget:
        """Create manufacturing options tab with sub-BOM support."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Assembly sub-BOM (at top)
        self.assembly_bom_group, self.assembly_bom_table = self._create_bom_section(
            layout, "Assembly Sub-BOM (Components)", ["Item Name", "Qty", "Notes"],
            self._on_add_assembly_item, self._on_remove_assembly_item
        )

        # Overmold sub-BOM
        self.overmold_bom_group, self.overmold_bom_table = self._create_bom_section(
            layout, "Overmold Sub-BOM (Materials)", ["Material/Item", "Qty", "Notes"],
            self._on_add_overmold_item, self._on_remove_overmold_item
        )

        layout.addSpacing(10)

        # Manufacturing options (at bottom)
        mfg_group = QGroupBox("Manufacturing Options")
        mfg_layout = QVBoxLayout()

        mfg_row1 = QHBoxLayout()
        self.assembly_check = QCheckBox("Assembly required")
        self.assembly_check.setChecked(self.part.assembly if self.part else False)
        self.assembly_check.toggled.connect(self._on_assembly_toggled)
        mfg_row1.addWidget(self.assembly_check)

        mfg_row1.addWidget(QLabel("Degate"))
        self.degate_combo = QComboBox()
        self.degate_combo.addItems([d.value for d in DegateOption])
        if self.part:
            self.degate_combo.setCurrentText(self.part.degate)
        mfg_row1.addWidget(self.degate_combo)

        self.overmold_check = QCheckBox("Overmold")
        self.overmold_check.setChecked(self.part.overmold if self.part else False)
        self.overmold_check.toggled.connect(self._on_overmold_toggled)
        mfg_row1.addWidget(self.overmold_check)

        mfg_layout.addLayout(mfg_row1)

        mfg_row2 = QHBoxLayout()
        mfg_row2.addWidget(QLabel("EOAT Type"))
        self.eoat_combo = QComboBox()
        self.eoat_combo.addItems([e.value for e in EOATType])
        if self.part:
            self.eoat_combo.setCurrentText(self.part.eoat_type)
        mfg_row2.addWidget(self.eoat_combo)
        mfg_row2.addStretch()
        mfg_layout.addLayout(mfg_row2)

        mfg_group.setLayout(mfg_layout)
        layout.addWidget(mfg_group)

        # Load existing sub-BOM items
        self._load_sub_bom_items()

        # Update visibility based on current state
        self._on_assembly_toggled()
        self._on_overmold_toggled()

        layout.addStretch()
        return tab

    def _create_demand_tab(self) -> QWidget:
        """Create demand and notes tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Demand planning (project-level SOP/EAOP note)
        demand_group = QGroupBox("Demand Planning (Part-Level)")
        demand_layout = QVBoxLayout()

        info_label = QLabel(
            "<i>Note: SOP (Start of Production) and EAOP (End Adjusted Operating Period) "
            "are now set at the project level in the RFQ details.\n"
            "Below are part-specific demand values.</i>"
        )
        info_label.setWordWrap(True)
        demand_layout.addWidget(info_label)

        demand_layout.addSpacing(10)

        demand_row1 = QHBoxLayout()
        demand_row1.addWidget(QLabel("Total Demand (pcs)"))
        self.demand_peak_spin = QSpinBox()
        self.demand_peak_spin.setRange(0, 10000000)
        if self.part and self.part.parts_over_runtime:
            self.demand_peak_spin.setValue(self.part.parts_over_runtime)
        else:
            self.demand_peak_spin.setValue(0)
        demand_row1.addWidget(self.demand_peak_spin)
        demand_row1.addStretch()

        demand_layout.addLayout(demand_row1)
        demand_group.setLayout(demand_layout)
        layout.addWidget(demand_group)

        # Notes & Remarks
        notes_group = QGroupBox("Notes & Remarks")
        notes_layout = QVBoxLayout()

        notes_layout.addWidget(QLabel("Engineering Notes"))
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        self.notes_input.setPlaceholderText("Technical notes...")
        if self.part and self.part.notes:
            self.notes_input.setPlainText(self.part.notes)
        notes_layout.addWidget(self.notes_input)

        notes_layout.addWidget(QLabel("Sales Remarks"))
        self.remarks_input = QTextEdit()
        self.remarks_input.setMaximumHeight(80)
        self.remarks_input.setPlaceholderText("Sales notes (will appear on quote)...")
        if self.part and self.part.remarks:
            self.remarks_input.setPlainText(self.part.remarks)
        notes_layout.addWidget(self.remarks_input)

        notes_group.setLayout(notes_layout)
        layout.addWidget(notes_group)

        layout.addStretch()
        return tab

    def _create_revisions_tab(self) -> QWidget:
        """Create revisions/audit log tab (read-only)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("<b>Change History</b>"))

        self.revisions_table = QTableWidget()
        self.revisions_table.setColumnCount(5)
        self.revisions_table.setHorizontalHeaderLabels([
            "Date & Time", "Changed By", "Field", "Old Value", "New Value"
        ])
        self.revisions_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.revisions_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.revisions_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.revisions_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.revisions_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        # Make table read-only
        self.revisions_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Load revisions
        if self.part:
            with session_scope() as session:
                revisions = session.query(PartRevision).filter(
                    PartRevision.part_id == self.part_id
                ).order_by(PartRevision.changed_at.desc()).all()

                self.revisions_table.setRowCount(len(revisions))
                for row, rev in enumerate(revisions):
                    self.revisions_table.setItem(row, 0, QTableWidgetItem(
                        rev.changed_at.strftime("%Y-%m-%d %H:%M:%S") if rev.changed_at else "-"
                    ))
                    self.revisions_table.setItem(row, 1, QTableWidgetItem(rev.changed_by or "-"))
                    self.revisions_table.setItem(row, 2, QTableWidgetItem(rev.field_name))
                    self.revisions_table.setItem(row, 3, QTableWidgetItem(rev.old_value or "-"))
                    self.revisions_table.setItem(row, 4, QTableWidgetItem(rev.new_value or "-"))

        layout.addWidget(self.revisions_table)
        return tab

    def _create_dimension_input(self, layout: QVBoxLayout, label: str, min_val: float, max_val: float, initial_val=None) -> QDoubleSpinBox:
        """Create a dimension input spinbox with label and add to layout."""
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setDecimals(1)
        if initial_val:
            spin.setValue(initial_val)
        row.addWidget(spin)
        layout.addLayout(row)
        return spin

    def _create_bom_section(self, parent_layout: QVBoxLayout, title: str, headers: list, add_callback, remove_callback) -> tuple:
        """Create a BOM section with table and buttons. Returns (group, table)."""
        group = QGroupBox(title)
        layout = QVBoxLayout()

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setMaximumHeight(150)
        layout.addWidget(table)

        buttons_layout = QHBoxLayout()
        btn_add = QPushButton("Add Item")
        btn_add.clicked.connect(add_callback)
        buttons_layout.addWidget(btn_add)

        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(remove_callback)
        buttons_layout.addWidget(btn_remove)
        buttons_layout.addStretch()

        layout.addLayout(buttons_layout)
        group.setLayout(layout)
        parent_layout.addWidget(group)

        # Store button references on the object for access
        if "assembly" in title.lower():
            self.btn_add_assembly_item = btn_add
            self.btn_remove_assembly_item = btn_remove
        else:
            self.btn_add_overmold_item = btn_add
            self.btn_remove_overmold_item = btn_remove

        return group, table

    def _on_geometry_mode_changed(self):
        """Handle geometry mode selection change - show/hide relevant fields."""
        is_box_mode = self.radio_box.isChecked()

        # Show box frame, hide direct frame when box is selected
        self.box_frame.setVisible(is_box_mode)
        self.direct_frame.setVisible(not is_box_mode)

    def _on_material_changed(self):
        """Handle material selection change."""
        # This could be used to update density for calculations in future
        pass

    def _on_upload_image(self):
        """Handle image upload via file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Part Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )

        if file_path:
            self._process_dropped_image(file_path)

    def _process_dropped_image(self, file_path: str):
        """Process image from file path (upload or drag-drop)."""
        try:
            with open(file_path, 'rb') as f:
                self.image_data = f.read()
            self.image_filename = Path(file_path).name

            # Show preview
            pixmap = QPixmap(file_path)
            self.image_label.setPixmap(pixmap.scaledToHeight(150, Qt.TransformationMode.SmoothTransformation))
            QMessageBox.information(self, "Image Loaded", f"Image '{self.image_filename}' loaded successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image: {str(e)}")

    def _on_calculate_box_area(self):
        """Calculate projected area from box dimensions."""
        length = self.box_length_spin.value()
        width = self.box_width_spin.value()
        effective = self.box_effective_spin.value()

        if length <= 0 or width <= 0:
            QMessageBox.warning(self, "Invalid Input", "Length and width must be positive")
            return

        mode = BoxEstimateMode(length, width, effective)
        area = mode.calculate_projected_area()

        if area:
            self.proj_area_spin.setValue(area)
            QMessageBox.information(self, "Calculated", f"Projected area: {area} cm²")

    def _get_material_density(self) -> float:
        """Get density of selected material. Returns None if invalid."""
        material_id = self.material_combo.currentData()
        if not material_id:
            QMessageBox.warning(self, "No Material", "Please select a material first")
            return None

        with session_scope() as session:
            material = session.query(Material).get(material_id)
            if not material or not material.density_g_cm3:
                QMessageBox.warning(self, "No Density", "Material has no density data")
                return None
            return material.density_g_cm3

    def _on_calc_volume_from_weight(self):
        """Calculate volume from weight using material density."""
        weight = self.weight_spin.value()
        if weight <= 0:
            QMessageBox.warning(self, "Invalid Weight", "Weight must be positive")
            return

        density = self._get_material_density()
        if density is None:
            return

        volume = auto_calculate_volume(weight, density)
        if volume:
            self.volume_spin.setValue(volume)
            QMessageBox.information(self, "Calculated", f"Volume: {volume} cm³")

    def _on_calc_weight_from_volume(self):
        """Calculate weight from volume using material density."""
        volume = self.volume_spin.value()
        if volume <= 0:
            QMessageBox.warning(self, "Invalid Volume", "Volume must be positive")
            return

        density = self._get_material_density()
        if density is None:
            return

        weight = auto_calculate_weight(volume, density)
        if weight:
            self.weight_spin.setValue(weight)
            QMessageBox.information(self, "Calculated", f"Weight: {weight} g")

    def _on_estimate_wall_thickness(self):
        """Estimate wall thickness with standard 2.5mm value."""
        self.wall_thick_spin.setValue(2.5)
        self._wall_thickness_source = "estimated"
        self._update_wall_thickness_label()
        QMessageBox.information(self, "Estimated", "Wall thickness set to standard 2.5mm (marked as estimated)")

    def _update_wall_thickness_label(self):
        """Update the wall thickness source label."""
        source_text = " (est.)" if self._wall_thickness_source == "estimated" else " (given)"
        self.wall_thick_label.setText(source_text)

    def _load_sub_bom_items(self):
        """Load existing sub-BOM items from part."""
        if self.part:
            with session_scope() as session:
                part = session.query(Part).get(self.part.id)
                if part and part.sub_boms:
                    for sub_bom in part.sub_boms:
                        if sub_bom.item_type == "assembly":
                            row = self.assembly_bom_table.rowCount()
                            self.assembly_bom_table.insertRow(row)
                            self.assembly_bom_table.setItem(row, 0, QTableWidgetItem(sub_bom.item_name))
                            self.assembly_bom_table.setItem(row, 1, QTableWidgetItem(str(sub_bom.quantity)))
                            self.assembly_bom_table.setItem(row, 2, QTableWidgetItem(sub_bom.notes or ""))
                        elif sub_bom.item_type == "overmold":
                            row = self.overmold_bom_table.rowCount()
                            self.overmold_bom_table.insertRow(row)
                            self.overmold_bom_table.setItem(row, 0, QTableWidgetItem(sub_bom.item_name))
                            self.overmold_bom_table.setItem(row, 1, QTableWidgetItem(str(sub_bom.quantity)))
                            self.overmold_bom_table.setItem(row, 2, QTableWidgetItem(sub_bom.notes or ""))

    def _on_assembly_toggled(self):
        """Handle assembly checkbox toggle."""
        self.assembly_bom_group.setVisible(self.assembly_check.isChecked())

    def _on_overmold_toggled(self):
        """Handle overmold checkbox toggle."""
        self.overmold_bom_group.setVisible(self.overmold_check.isChecked())

    def _on_add_assembly_item(self):
        """Add a new assembly sub-BOM item."""
        row = self.assembly_bom_table.rowCount()
        self.assembly_bom_table.insertRow(row)
        self.assembly_bom_table.setItem(row, 0, QTableWidgetItem(""))
        self.assembly_bom_table.setItem(row, 1, QTableWidgetItem("1"))
        self.assembly_bom_table.setItem(row, 2, QTableWidgetItem(""))

    def _on_remove_assembly_item(self):
        """Remove selected assembly sub-BOM item."""
        selected = self.assembly_bom_table.selectedIndexes()
        if selected:
            row = selected[0].row()
            self.assembly_bom_table.removeRow(row)

    def _on_add_overmold_item(self):
        """Add a new overmold sub-BOM item."""
        row = self.overmold_bom_table.rowCount()
        self.overmold_bom_table.insertRow(row)
        self.overmold_bom_table.setItem(row, 0, QTableWidgetItem(""))
        self.overmold_bom_table.setItem(row, 1, QTableWidgetItem("1"))
        self.overmold_bom_table.setItem(row, 2, QTableWidgetItem(""))

    def _on_remove_overmold_item(self):
        """Remove selected overmold sub-BOM item."""
        selected = self.overmold_bom_table.selectedIndexes()
        if selected:
            row = selected[0].row()
            self.overmold_bom_table.removeRow(row)

    def _on_save(self):
        """Save part."""
        name = self.name_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Validation", "Part name is required")
            return

        material_id = self.material_combo.currentData()
        geometry_mode = "box" if self.radio_box.isChecked() else "direct"

        try:
            with session_scope() as session:
                if self.part:
                    # Update existing - get fresh instance from DB
                    part = session.query(Part).get(self.part.id)

                    # Track changes for audit log
                    changes = []

                    # Check each field for changes
                    if part.name != name:
                        changes.append(("name", part.name, name))
                    if part.weight_g != self.weight_spin.value():
                        changes.append(("weight_g", str(part.weight_g), str(self.weight_spin.value())))
                    if part.volume_cm3 != self.volume_spin.value():
                        changes.append(("volume_cm3", str(part.volume_cm3), str(self.volume_spin.value())))
                    if part.projected_area_cm2 != self.proj_area_spin.value():
                        changes.append(("projected_area_cm2", str(part.projected_area_cm2), str(self.proj_area_spin.value())))
                    if part.image_filename != self.image_filename:
                        changes.append(("image_filename", part.image_filename or "None", self.image_filename or "None"))

                    # Update all fields
                    part.name = name
                    part.part_number = self.part_number_input.text().strip() or None
                    part.material_id = material_id
                    part.weight_g = self.weight_spin.value() or None
                    part.volume_cm3 = self.volume_spin.value() or None
                    part.projected_area_cm2 = self.proj_area_spin.value() or None
                    part.wall_thickness_mm = self.wall_thick_spin.value() or None
                    part.wall_thickness_source = self._wall_thickness_source
                    # Note: demand_sop and demand_eaop are now at RFQ level (project-level)
                    # demand_peak_spin now holds total demand (saved to parts_over_runtime)
                    part.parts_over_runtime = self.demand_peak_spin.value() or None
                    part.assembly = self.assembly_check.isChecked()
                    part.degate = self.degate_combo.currentText()
                    part.overmold = self.overmold_check.isChecked()
                    part.eoat_type = self.eoat_combo.currentText()
                    part.notes = self.notes_input.toPlainText().strip() or None
                    part.remarks = self.remarks_input.toPlainText().strip() or None
                    part.geometry_mode = geometry_mode
                    if geometry_mode == "box":
                        part.box_length_mm = self.box_length_spin.value() or None
                        part.box_width_mm = self.box_width_spin.value() or None
                        part.box_effective_percent = self.box_effective_spin.value()

                    # Update image if new one uploaded
                    if self.image_data:
                        part.image_binary = self.image_data
                        part.image_filename = self.image_filename
                        part.image_updated_date = datetime.now()

                    # Record changes
                    for field_name, old_val, new_val in changes:
                        rev = PartRevision(
                            part_id=part.id,
                            field_name=field_name,
                            old_value=str(old_val)[:500] if old_val else None,
                            new_value=str(new_val)[:500] if new_val else None,
                            changed_by="user",
                            change_type="image" if field_name == "image_filename" else "value"
                        )
                        session.add(rev)

                    self._saved_part_id = part.id
                else:
                    # Create new
                    part = Part(
                        rfq_id=self.rfq_id,
                        name=name,
                        part_number=self.part_number_input.text().strip() or None,
                        material_id=material_id,
                        weight_g=self.weight_spin.value() or None,
                        volume_cm3=self.volume_spin.value() or None,
                        projected_area_cm2=self.proj_area_spin.value() or None,
                        wall_thickness_mm=self.wall_thick_spin.value() or None,
                        wall_thickness_source=self._wall_thickness_source,
                        # Note: demand_sop and demand_eaop are now at RFQ level (project-level)
                        # demand_peak_spin now holds total demand (saved to parts_over_runtime)
                        parts_over_runtime=self.demand_peak_spin.value() or None,
                        assembly=self.assembly_check.isChecked(),
                        degate=self.degate_combo.currentText(),
                        overmold=self.overmold_check.isChecked(),
                        eoat_type=self.eoat_combo.currentText(),
                        notes=self.notes_input.toPlainText().strip() or None,
                        remarks=self.remarks_input.toPlainText().strip() or None,
                        geometry_mode=geometry_mode,
                        box_length_mm=self.box_length_spin.value() if geometry_mode == "box" else None,
                        box_width_mm=self.box_width_spin.value() if geometry_mode == "box" else None,
                        box_effective_percent=self.box_effective_spin.value() if geometry_mode == "box" else 100.0,
                        image_binary=self.image_data,
                        image_filename=self.image_filename,
                        image_updated_date=datetime.now() if self.image_data else None,
                    )
                    session.add(part)
                    session.flush()
                    self._saved_part_id = part.id

            # Save sub-BOM items
            self._save_sub_bom_items(self._saved_part_id)

            self.accept()
        except AttributeError as e:
            QMessageBox.critical(self, "Error", f"Failed to save part - missing attribute: {str(e)}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save part: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()

    def get_part(self) -> Part:
        """Return the created/edited part. If it was just saved, refetch from DB to avoid detached instance error."""
        if self._saved_part_id:
            # Refetch from DB since the object became detached after save
            with session_scope() as session:
                part = session.query(Part).get(self._saved_part_id)
                session.expunge(part)
                return part
        return self.part

    def _save_sub_bom_items(self, part_id: int):
        """Save sub-BOM items (assembly and overmold components) to the database."""
        with session_scope() as session:
            # Clear existing sub-BOM items for this part
            session.query(SubBOM).filter(SubBOM.part_id == part_id).delete()

            # Save both assembly and overmold items
            self._save_bom_table_items(session, part_id, self.assembly_bom_table, "assembly")
            self._save_bom_table_items(session, part_id, self.overmold_bom_table, "overmold")

    def _save_bom_table_items(self, session, part_id: int, table, item_type: str):
        """Helper to save BOM items from a table."""
        for row in range(table.rowCount()):
            item_name = table.item(row, 0)
            qty_item = table.item(row, 1)
            notes_item = table.item(row, 2)

            if item_name and item_name.text().strip():
                try:
                    qty = int(qty_item.text()) if qty_item and qty_item.text() else 1
                except ValueError:
                    qty = 1

                sub_bom = SubBOM(
                    part_id=part_id,
                    item_name=item_name.text().strip(),
                    quantity=qty,
                    item_type=item_type,
                    notes=notes_item.text() if notes_item else None
                )
                session.add(sub_bom)
