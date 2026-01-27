"""Part/BOM entry dialog with modular geometry and weight/volume calculation."""

from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTextEdit, QPushButton, QMessageBox, QGroupBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QScrollArea, QFrame, QTabWidget, QTableWidget, QTableWidgetItem,
    QFileDialog, QRadioButton, QButtonGroup, QHeaderView, QWidget, QAbstractItemView, QSplitter,
    QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import Qt, QByteArray, QMimeData
from PyQt6.QtGui import QPixmap, QIcon, QDragEnterEvent, QDropEvent, QFont

from database import DegateOption, EOATType, PartRevision, SubBOM
from database.connection import session_scope
from database.models import Part, RFQ, Material
from calculations import (
    GeometryFactory, BoxEstimateMode,
    WeightVolumeHelper, auto_calculate_volume, auto_calculate_weight
)
from ui.widgets.image_preview import show_image_preview
from ui.color_coding import get_missing_fields, is_part_complete


class ImageDropLabel(QLabel):
    """Label that accepts image files via drag-and-drop and supports clicking to zoom."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.image_dropped = None  # Callback for when image is dropped
        self.image_clicked = None  # Callback for when image is clicked

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

    def mousePressEvent(self, event):
        """Handle mouse click to show image zoom."""
        if self.pixmap() and not self.pixmap().isNull() and self.image_clicked:
            self.image_clicked()
        super().mousePressEvent(event)


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
        self._wall_thickness_source = "data"  # Track if wall thickness was "data", "bom", or "estimated"
        self._projected_area_source = "data"  # Track if projected area was "data", "bom", or "estimated"
        # Track HOW values were created: "manual" | "from_weight" | "from_volume" | "from_box"
        self._volume_origin = "manual"  # Default to manual entry
        self._weight_origin = "manual"  # Default to manual entry
        self._proj_area_origin = "manual"  # Default to manual entry

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
                    # Track projected area source
                    if hasattr(self.part, 'projected_area_source'):
                        self._projected_area_source = self.part.projected_area_source
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
        """Setup the dialog UI with tabs on left and properties panel on right."""
        # Main layout (vertical)
        main_layout = QVBoxLayout(self)

        # Content area (horizontal split: tabs | properties)
        content_layout = QHBoxLayout()

        # LEFT: Tab widget for organized sections
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

        # ===== TAB 5: Revisions (always add, will have data after save) =====
        revisions_widget = self._create_revisions_tab()
        tabs.addTab(revisions_widget, "Revisions")

        content_layout.addWidget(tabs, stretch=1)

        # RIGHT: Properties panel (persistent, non-scrolling)
        self.properties_panel = self._create_properties_panel()
        content_layout.addWidget(self.properties_panel, stretch=0)

        main_layout.addLayout(content_layout)

        # Apply colors after basic tab is created
        self._update_material_color()
        self._update_surface_finish_colors()

        # Buttons (bottom)
        button_layout = QHBoxLayout()

        self.btn_save = QPushButton("Save Part")
        self.btn_save.clicked.connect(self._on_save)
        button_layout.addWidget(self.btn_save)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(button_layout)

        # Connect all signals to update properties panel
        self._connect_properties_signals()

        # Initial properties update
        self._update_validation_status()

    def _connect_properties_signals(self):
        """Connect all input signals to properties panel update."""
        self.name_input.textChanged.connect(self._update_validation_status)
        # NOTE: volume_input and proj_area_input do NOT auto-update - require Submit button click
        self.material_combo.currentIndexChanged.connect(self._update_validation_status)
        self.demand_peak_spin.valueChanged.connect(self._update_validation_status)
        # NOTE: weight_input auto-updates only if no calculation - no Submit button
        self.weight_input.textChanged.connect(self._update_validation_status)
        # proj_area_input does NOT auto-update - requires Submit button
        self.wall_thick_input.textChanged.connect(self._update_validation_status)
        self.surface_finish_combo.currentIndexChanged.connect(self._update_validation_status)

    def _create_properties_panel(self) -> QFrame:
        """Create right-side properties display panel (persistent across tabs)."""
        panel = QFrame()
        # Dark theme with subtle borders
        panel.setStyleSheet(
            "QFrame { "
            "background-color: #2c3e50; "
            "border-left: 1px solid #34495e; "
            "border-radius: 0px; "
            "} "
        )
        panel.setMinimumWidth(310)
        panel.setMaximumWidth(360)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Title
        title = QLabel("Part Properties")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title.setFont(title_font)
        title.setStyleSheet("color: #ecf0f1;")
        layout.addWidget(title)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #34495e;")
        layout.addWidget(sep)

        # Property labels (will be updated dynamically)
        # Order matters: Name, Volume (above weight), Material, Demand, Weight, Proj Area, Wall Thick, Surface Finish
        self.prop_labels = {
            'name': self._create_prop_label('Name', ''),
            'volume': self._create_prop_label('Volume (cm³)', ''),
            'weight': self._create_prop_label('Weight (g)', ''),
            'material': self._create_prop_label('Material', ''),
            'demand': self._create_prop_label('Total Demand', ''),
            'proj_area': self._create_prop_label('Proj. Area (cm²)', ''),
            'wall_thick': self._create_prop_label('Wall Thick (mm)', ''),
            'surface_finish': self._create_prop_label('Surface Finish', ''),
        }

        # Add labels in explicit order
        layout.addWidget(self.prop_labels['name'])
        layout.addWidget(self.prop_labels['volume'])
        layout.addWidget(self.prop_labels['weight'])
        layout.addWidget(self.prop_labels['material'])
        layout.addWidget(self.prop_labels['demand'])
        layout.addWidget(self.prop_labels['proj_area'])
        layout.addWidget(self.prop_labels['wall_thick'])
        layout.addWidget(self.prop_labels['surface_finish'])

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #34495e;")
        layout.addWidget(sep2)

        # Missing fields indicator
        self.missing_label = QLabel()
        self.missing_label.setWordWrap(True)
        self.missing_label.setStyleSheet("color: #ecf0f1;")
        layout.addWidget(self.missing_label)

        # Color legend (NEW)
        layout.addSpacing(5)
        self._add_color_legend(layout)

        # Article image at bottom
        layout.addSpacing(10)
        self._add_article_image_section(layout)

        layout.addStretch()
        return panel

    def _add_article_image_section(self, layout: QVBoxLayout):
        """Add article/part image display section at bottom of properties panel."""
        img_label = QLabel("Part Image")
        img_label_font = QFont()
        img_label_font.setBold(True)
        img_label_font.setPointSize(9)
        img_label.setFont(img_label_font)
        img_label.setStyleSheet("color: #bdc3c7;")
        layout.addWidget(img_label)

        # Image display frame
        self.props_image_label = QLabel()
        self.props_image_label.setMinimumHeight(80)
        self.props_image_label.setMaximumHeight(100)
        self.props_image_label.setStyleSheet(
            "QLabel { "
            "background-color: #1c2833; "
            "border: 1px solid #34495e; "
            "border-radius: 4px; "
            "padding: 4px; "
            "} "
        )
        self.props_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.props_image_label.setText("No image")
        self.props_image_label.setStyleSheet(
            "QLabel { "
            "background-color: #1c2833; "
            "border: 1px solid #34495e; "
            "border-radius: 4px; "
            "padding: 4px; "
            "color: #7f8c8d; "
            "} "
        )
        layout.addWidget(self.props_image_label)

        # Update image display if part exists
        if self.part and self.part.image_binary:
            self._update_properties_image()

    def _add_color_legend(self, layout: QVBoxLayout):
        """Add color legend to show meaning of colors."""
        legend_label = QLabel("Color Legend")
        legend_label_font = QFont()
        legend_label_font.setBold(True)
        legend_label_font.setPointSize(9)
        legend_label.setFont(legend_label_font)
        legend_label.setStyleSheet("color: #bdc3c7;")
        layout.addWidget(legend_label)

        # Yellow - Estimated
        yellow_item = QLabel()
        yellow_item.setStyleSheet(
            "QLabel { "
            "background-color: #FFD54F; "
            "color: #000000; "
            "padding: 4px 6px; "
            "border-radius: 3px; "
            "font-weight: bold; "
            "font-size: 10px; "
            "} "
        )
        yellow_item.setText("■ Estimated")
        yellow_item.setToolTip("Value is estimated (not from design or BOM)")
        layout.addWidget(yellow_item)

        # Blue - BOM
        blue_item = QLabel()
        blue_item.setStyleSheet(
            "QLabel { "
            "background-color: #64B5F6; "
            "color: #000000; "
            "padding: 4px 6px; "
            "border-radius: 3px; "
            "font-weight: bold; "
            "font-size: 10px; "
            "} "
        )
        blue_item.setText("■ BOM Sourced")
        blue_item.setToolTip("Value comes from Bill of Materials")
        layout.addWidget(blue_item)

        # Grey - Calculated
        grey_item = QLabel()
        grey_item.setStyleSheet(
            "QLabel { "
            "background-color: #B0BEC5; "
            "color: #000000; "
            "padding: 4px 6px; "
            "border-radius: 3px; "
            "font-weight: bold; "
            "font-size: 10px; "
            "} "
        )
        grey_item.setText("■ Calculated")
        grey_item.setToolTip("Value was calculated from another field")
        layout.addWidget(grey_item)

        # Red - Missing
        red_item = QLabel()
        red_item.setStyleSheet(
            "QLabel { "
            "background-color: #FFE0E0; "
            "color: #FF5050; "
            "padding: 4px 6px; "
            "border-radius: 3px; "
            "font-weight: bold; "
            "font-size: 10px; "
            "} "
        )
        red_item.setText("■ Missing Required")
        red_item.setToolTip("This field is required but not filled")
        layout.addWidget(red_item)

    def _create_prop_label(self, label: str, value: str) -> QLabel:
        """Create a property label with name and value."""
        label_widget = QLabel(f"<b>{label}:</b> {value}")
        label_widget.setWordWrap(True)
        label_widget.setStyleSheet("color: #ecf0f1;")
        label_widget.setToolTip(f"Current value of {label}")
        return label_widget

    def _create_basic_tab(self) -> QWidget:
        """Create basic information tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)  # More space between sections

        # Part Name
        name_label = QLabel("Part Name *")
        name_font = QFont()
        name_font.setBold(True)
        name_label.setFont(name_font)
        layout.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Housing")
        if self.part:
            self.name_input.setText(self.part.name)
        layout.addWidget(self.name_input)

        # Part Number
        pn_label = QLabel("Part Number")
        pn_font = QFont()
        pn_font.setBold(True)
        pn_label.setFont(pn_font)
        layout.addWidget(pn_label)
        self.part_number_input = QLineEdit()
        if self.part:
            self.part_number_input.setText(self.part.part_number or "")
        layout.addWidget(self.part_number_input)

        # Material (REQUIRED)
        mat_label = QLabel("Material *")
        mat_font = QFont()
        mat_font.setBold(True)
        mat_font.setPointSize(10)
        mat_label.setFont(mat_font)
        layout.addWidget(mat_label)

        mat_row = QHBoxLayout()
        mat_row.setSpacing(10)

        self.material_estimated_check = QCheckBox("Estimated")
        self.material_estimated_check.setChecked(False)  # Default to not estimated
        self.material_estimated_check.setMaximumWidth(110)
        self.material_estimated_check.toggled.connect(self._on_material_estimated_toggled)
        mat_row.addWidget(self.material_estimated_check)

        # Visual separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.VLine)
        separator1.setLineWidth(2)
        separator1.setStyleSheet("color: #cccccc;")
        mat_row.addWidget(separator1)

        self.material_combo = QComboBox()
        self.material_combo.addItem("", None)  # Empty default for new parts
        for mat in self.materials:
            self.material_combo.addItem(f"{mat.short_name} ({mat.family})", mat.id)
        if self.part and self.part.material_id:
            # Only autofill when editing existing part
            index = self.material_combo.findData(self.part.material_id)
            if index >= 0:
                self.material_combo.setCurrentIndex(index)
        self.material_combo.currentIndexChanged.connect(self._on_material_changed)
        mat_row.addWidget(self.material_combo)
        mat_row.addStretch()
        layout.addLayout(mat_row)

        # Surface Finish (REQUIRED)
        sf_label = QLabel("Surface Finish *")
        sf_font = QFont()
        sf_font.setBold(True)
        sf_font.setPointSize(10)
        sf_label.setFont(sf_font)
        layout.addWidget(sf_label)

        sf_row = QHBoxLayout()
        sf_row.setSpacing(10)

        self.surface_finish_estimated_check = QCheckBox("Estimated")
        self.surface_finish_estimated_check.setChecked(self.part.surface_finish_estimated if self.part else False)
        self.surface_finish_estimated_check.toggled.connect(self._on_surface_finish_estimated_toggled)
        self.surface_finish_estimated_check.setMaximumWidth(110)
        sf_row.addWidget(self.surface_finish_estimated_check)

        # Visual separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.VLine)
        separator2.setLineWidth(2)
        separator2.setStyleSheet("color: #cccccc;")
        sf_row.addWidget(separator2)

        self.surface_finish_combo = QComboBox()
        self.surface_finish_combo.addItem("", None)  # Empty default for new parts
        from database import SurfaceFinish
        for sf in SurfaceFinish:
            display_name = sf.value.replace("_", " ").title()
            self.surface_finish_combo.addItem(display_name, sf.value)
        if self.part and self.part.surface_finish:
            # Only autofill when editing existing part
            index = self.surface_finish_combo.findData(self.part.surface_finish)
            if index >= 0:
                self.surface_finish_combo.setCurrentIndex(index)
        # Connect dropdown to update properties
        self.surface_finish_combo.currentIndexChanged.connect(self._update_validation_status)
        sf_row.addWidget(self.surface_finish_combo)

        self.surface_finish_detail_input = QLineEdit()
        self.surface_finish_detail_input.setPlaceholderText("e.g., grid 800 or Ra 1.6 μm")
        if self.part and self.part.surface_finish_detail:
            self.surface_finish_detail_input.setText(self.part.surface_finish_detail)
        # Connect detail textbox to update properties when text changes
        self.surface_finish_detail_input.textChanged.connect(self._update_validation_status)
        sf_row.addWidget(self.surface_finish_detail_input)
        sf_row.addStretch()

        layout.addLayout(sf_row)
        self._update_surface_finish_colors()

        # Image upload (compact: single image only)
        layout.addSpacing(15)
        img_label = QLabel("Part Image")
        img_font = QFont()
        img_font.setBold(True)
        img_label.setFont(img_font)
        layout.addWidget(img_label)

        image_layout = QHBoxLayout()
        image_layout.setSpacing(8)

        self.btn_upload_image = QPushButton("Upload")
        self.btn_upload_image.clicked.connect(self._on_upload_image)
        self.btn_upload_image.setMaximumWidth(80)
        image_layout.addWidget(self.btn_upload_image)

        self.btn_delete_image = QPushButton("Delete")
        self.btn_delete_image.clicked.connect(self._on_delete_image)
        self.btn_delete_image.setEnabled(bool(self.image_data))
        self.btn_delete_image.setMaximumWidth(80)
        image_layout.addWidget(self.btn_delete_image)

        image_layout.addStretch()
        layout.addLayout(image_layout)

        # Image preview (bigger - 120px for better visibility)
        self.image_label = ImageDropLabel()
        self.image_label.setMinimumHeight(120)
        self.image_label.setMaximumHeight(120)
        self.image_label.setStyleSheet("border: 1px solid #ccc;")
        self.image_label.image_dropped = self._process_dropped_image
        self.image_label.image_clicked = self._on_image_clicked
        if self.image_data:
            pixmap = QPixmap()
            pixmap.loadFromData(self.image_data)
            self.image_label.setPixmap(pixmap.scaledToHeight(80, Qt.TransformationMode.SmoothTransformation))
            self.image_label.setText("")
        else:
            self.image_label.setText("Drag-drop or Upload")
            self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label)

        layout.addStretch()
        return tab

    def _create_geometry_tab(self) -> QWidget:
        """Create geometry/dimensions tab with box dimensions and projected surface choice."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Box dimensions section (ALWAYS VISIBLE)
        box_group = QGroupBox("Box Dimensions")
        box_layout = QVBoxLayout()

        # Length (X) input
        self.box_length_input = self._create_dimension_input(
            box_layout, "Length (mm) - X (tool plane)", 0.1, 10000,
            self.part.box_length_mm if self.part else None
        )

        # Width (Y) input
        self.box_width_input = self._create_dimension_input(
            box_layout, "Width (mm) - Y (tool plane)", 0.1, 10000,
            self.part.box_width_mm if self.part else None
        )

        # Height (Z) input (for reference, ignored in calculations)
        self.box_height_input = self._create_dimension_input(
            box_layout, "Height (mm) - Z (reference only, not used)", 0.1, 10000,
            self.part.box_height_mm if self.part and hasattr(self.part, 'box_height_mm') else None
        )

        box_group.setLayout(box_layout)
        layout.addWidget(box_group)

        # Projected surface mode selector
        proj_mode_group = QGroupBox("Projected Surface Calculation")
        proj_mode_layout = QVBoxLayout()

        self.proj_surface_mode_group = QButtonGroup()
        self.radio_proj_box = QRadioButton("Calculate from Box (X × Y × Effective %)")
        self.radio_proj_direct = QRadioButton("Direct Entry from CAD")
        self.proj_surface_mode_group.addButton(self.radio_proj_box, 0)
        self.proj_surface_mode_group.addButton(self.radio_proj_direct, 1)

        # Connect to toggle visibility
        self.radio_proj_box.toggled.connect(self._on_proj_surface_mode_changed)
        self.radio_proj_direct.toggled.connect(self._on_proj_surface_mode_changed)

        proj_mode_layout.addWidget(self.radio_proj_box)
        proj_mode_layout.addWidget(self.radio_proj_direct)
        proj_mode_group.setLayout(proj_mode_layout)
        layout.addWidget(proj_mode_group)

        # Box calculation mode frame
        self.proj_box_frame = QGroupBox("Calculate from Box Dimensions")
        proj_box_layout = QVBoxLayout()

        # Effective % input with calculate button
        eff_row = QHBoxLayout()
        eff_row.addWidget(QLabel("Effective Surface %"))
        self.box_effective_input = QLineEdit()
        self.box_effective_input.setPlaceholderText("100")
        eff_row.addWidget(self.box_effective_input)
        eff_row.addWidget(QLabel("%"))

        self.btn_calc_area = QPushButton("Calculate")
        self.btn_calc_area.clicked.connect(self._on_calculate_box_area)
        eff_row.addWidget(self.btn_calc_area)
        proj_box_layout.addLayout(eff_row)

        self.proj_box_frame.setLayout(proj_box_layout)
        layout.addWidget(self.proj_box_frame)

        # Direct entry mode frame
        self.proj_direct_frame = QGroupBox("Direct Projected Surface Input")
        proj_direct_layout = QVBoxLayout()

        # Projected area with source dropdown
        proj_row = QHBoxLayout()
        proj_label = QLabel("Projected Surface (cm²)")
        proj_font = QFont()
        proj_font.setBold(True)
        proj_label.setFont(proj_font)
        proj_row.addWidget(proj_label)

        self.proj_area_input = QLineEdit()
        self.proj_area_input.setPlaceholderText("Enter value (e.g., 100.5)")
        self.proj_area_input.textChanged.connect(self._on_proj_area_input_changed)
        proj_row.addWidget(self.proj_area_input)

        self.proj_area_source_combo = QComboBox()
        self.proj_area_source_combo.addItem("Part Data (CAD)", "data")
        self.proj_area_source_combo.addItem("BOM", "bom")
        if self.part and self.part.projected_area_source:
            index = self.proj_area_source_combo.findData(self.part.projected_area_source)
            if index >= 0:
                self.proj_area_source_combo.setCurrentIndex(index)
                self._projected_area_source = self.part.projected_area_source
        self.proj_area_source_combo.currentIndexChanged.connect(self._on_proj_area_source_changed)
        proj_row.addWidget(self.proj_area_source_combo)

        # Submit button for projected area
        self.btn_submit_proj_area = QPushButton("Submit")
        self.btn_submit_proj_area.setMaximumWidth(80)
        self.btn_submit_proj_area.clicked.connect(self._on_submit_proj_area)
        proj_row.addWidget(self.btn_submit_proj_area)

        proj_row.addStretch()

        proj_direct_layout.addLayout(proj_row)
        self.proj_direct_frame.setLayout(proj_direct_layout)
        layout.addWidget(self.proj_direct_frame)

        # Set initial mode
        if self.part and self.part.geometry_mode == "box":
            self.radio_proj_box.setChecked(True)
        else:
            self.radio_proj_direct.setChecked(True)

        # Apply initial visibility
        self._on_proj_surface_mode_changed()

        # Weight & Volume
        phys_frame = QGroupBox("Weight & Volume")
        phys_layout = QVBoxLayout()

        # Single source selector for both weight and volume
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Source:"))
        self.weight_volume_source_combo = QComboBox()
        self.weight_volume_source_combo.addItem("Part Data", "data")
        self.weight_volume_source_combo.addItem("BOM", "bom")
        self.weight_volume_source_combo.currentIndexChanged.connect(self._update_validation_status)
        source_row.addWidget(self.weight_volume_source_combo)
        source_row.addStretch()
        phys_layout.addLayout(source_row)

        # Volume input (FIRST - Priority)
        phys_row1 = QHBoxLayout()
        volume_label = QLabel("Volume (cm³)")
        volume_font = QFont()
        volume_font.setBold(True)
        volume_label.setFont(volume_font)
        phys_row1.addWidget(volume_label)

        self.volume_input = QLineEdit()
        self.volume_input.setPlaceholderText("Enter value (e.g., 50.5)")
        # Do NOT prefill - user must enter manually
        # Track when user edits (reset origin flag)
        self.volume_input.textChanged.connect(self._on_volume_input_changed)
        phys_row1.addWidget(self.volume_input)

        self.btn_calc_weight_from_volume = QPushButton("Calculate Weight")
        self.btn_calc_weight_from_volume.clicked.connect(self._on_calc_weight_from_volume)
        self.btn_calc_weight_from_volume.setMaximumWidth(150)
        phys_row1.addWidget(self.btn_calc_weight_from_volume)

        phys_layout.addLayout(phys_row1)

        # Weight input
        phys_row2 = QHBoxLayout()
        weight_label = QLabel("Weight (g)")
        weight_font = QFont()
        weight_font.setBold(True)
        weight_label.setFont(weight_font)
        phys_row2.addWidget(weight_label)

        self.weight_input = QLineEdit()
        self.weight_input.setPlaceholderText("Enter value (e.g., 125.5)")
        # Do NOT prefill - user must enter manually
        # Track when user edits (reset origin flag)
        self.weight_input.textChanged.connect(self._on_weight_input_changed)
        phys_row2.addWidget(self.weight_input)

        self.btn_calc_volume_from_weight = QPushButton("Calculate Volume")
        self.btn_calc_volume_from_weight.clicked.connect(self._on_calc_volume_from_weight)
        self.btn_calc_volume_from_weight.setMaximumWidth(150)
        phys_row2.addWidget(self.btn_calc_volume_from_weight)

        phys_layout.addLayout(phys_row2)

        # Spacing before wall thickness
        phys_layout.addSpacing(15)

        # Wall Thickness with source indicator
        layout_label = QHBoxLayout()
        wall_label = QLabel("Wall Thickness (mm)")
        wall_font = QFont()
        wall_font.setBold(True)
        wall_label.setFont(wall_font)
        layout_label.addWidget(wall_label)
        layout_label.addStretch()
        phys_layout.addLayout(layout_label)

        phys_row3 = QHBoxLayout()

        # Estimated checkbox on left
        self.wall_thick_source_check = QCheckBox("Estimated")
        self.wall_thick_source_check.setMaximumWidth(120)
        phys_row3.addWidget(self.wall_thick_source_check)

        # Visual separator
        separator3 = QFrame()
        separator3.setFrameShape(QFrame.Shape.VLine)
        separator3.setLineWidth(2)
        separator3.setStyleSheet("color: #cccccc;")
        phys_row3.addWidget(separator3)

        self.wall_thick_input = QLineEdit()
        self.wall_thick_input.setPlaceholderText("e.g., 2.5")
        # Do NOT prefill - user must enter manually
        phys_row3.addWidget(self.wall_thick_input)

        # Wall thickness source dropdown
        self.wall_thick_source_combo = QComboBox()
        self.wall_thick_source_combo.addItem("Data", "data")
        self.wall_thick_source_combo.addItem("BOM", "bom")
        self.wall_thick_source_combo.addItem("Estimated", "estimated")
        if self.part and self.part.wall_thickness_source:
            index = self.wall_thick_source_combo.findData(self.part.wall_thickness_source)
            if index >= 0:
                self.wall_thick_source_combo.setCurrentIndex(index)
                self._wall_thickness_source = self.part.wall_thickness_source
                # Initialize checkbox to match source
                self.wall_thick_source_check.setChecked(self._wall_thickness_source == "estimated")
        self.wall_thick_source_combo.currentIndexChanged.connect(self._on_wall_thick_source_changed)
        # Link checkbox to combo
        self.wall_thick_source_check.toggled.connect(self._on_wall_thick_estimated_toggled)
        phys_row3.addWidget(self.wall_thick_source_combo)

        self.btn_estimate_wall = QPushButton("Estimate (2.5mm)")
        self.btn_estimate_wall.clicked.connect(self._on_estimate_wall_thickness)
        self.btn_estimate_wall.setMaximumWidth(130)
        phys_row3.addWidget(self.btn_estimate_wall)
        phys_row3.addStretch()
        phys_layout.addLayout(phys_row3)

        # Wall thickness needs improvement checkbox
        improve_row = QHBoxLayout()
        self.wall_thick_improve_check = QCheckBox("3D wall thickness needs improvement")
        self.wall_thick_improve_check.setChecked(self.part.wall_thickness_needs_improvement if self.part else False)
        improve_row.addWidget(self.wall_thick_improve_check)
        improve_row.addStretch()
        phys_layout.addLayout(improve_row)

        # Spacing after wall thickness
        phys_layout.addSpacing(10)

        phys_frame.setLayout(phys_layout)
        layout.addWidget(phys_frame)

        # Apply colors after all widgets are created
        self._update_wall_thickness_color()
        self._update_proj_area_color()

        layout.addStretch()
        return tab

    def _create_mfg_tab(self) -> QWidget:
        """Create manufacturing options tab with sub-BOM support."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Manufacturing options (at TOP now in V2.0)
        mfg_group = QGroupBox("Manufacturing Options")
        mfg_layout = QVBoxLayout()

        mfg_row1 = QHBoxLayout()
        self.assembly_check = QCheckBox("Assembly required")
        self.assembly_check.setChecked(self.part.assembly if self.part else False)
        self.assembly_check.toggled.connect(self._on_assembly_toggled)
        mfg_row1.addWidget(self.assembly_check)

        self.overmold_check = QCheckBox("Overmold")
        self.overmold_check.setChecked(self.part.overmold if self.part else False)
        self.overmold_check.toggled.connect(self._on_overmold_toggled)
        mfg_row1.addWidget(self.overmold_check)

        mfg_row1.addStretch()
        mfg_layout.addLayout(mfg_row1)

        mfg_group.setLayout(mfg_layout)
        layout.addWidget(mfg_group)

        layout.addSpacing(10)

        # Assembly sub-BOM (conditionally visible)
        self.assembly_bom_group, self.assembly_bom_table = self._create_bom_section(
            layout, "Assembly Sub-BOM (Components)", ["Item Name", "Qty", "Notes"],
            self._on_add_assembly_item, self._on_remove_assembly_item
        )

        # Overmold sub-BOM (conditionally visible)
        self.overmold_bom_group, self.overmold_bom_table = self._create_bom_section(
            layout, "Overmold Sub-BOM (Materials)", ["Material/Item", "Qty", "Notes"],
            self._on_add_overmold_item, self._on_remove_overmold_item
        )

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
        """Create revisions/audit log tab with collapsible tree view (grouped by day and user)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("<b>Change History</b>"))

        # Create tree widget with collapsible structure
        self.revisions_tree = QTreeWidget()
        self.revisions_tree.setHeaderLabels(["Date", "User", "Change"])
        self.revisions_tree.setColumnCount(3)
        self.revisions_tree.setUniformRowHeights(True)
        # Make tree read-only
        self.revisions_tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Load revisions grouped by date, then user
        revisions_exist = False
        if self.part and self.part_id:
            with session_scope() as session:
                revisions = session.query(PartRevision).filter(
                    PartRevision.part_id == self.part_id
                ).order_by(PartRevision.changed_at.desc()).all()

                if revisions:
                    revisions_exist = True

                    # Group by date, then by user
                    from collections import defaultdict
                    by_date = defaultdict(lambda: defaultdict(list))

                    for rev in revisions:
                        date_key = rev.changed_at.strftime("%Y-%m-%d") if rev.changed_at else "Unknown"
                        user = rev.changed_by or "system"
                        by_date[date_key][user].append(rev)

                    # Add items to tree in descending date order
                    for date_key in sorted(by_date.keys(), reverse=True):
                        # Create date item (collapsed by default)
                        date_item = QTreeWidgetItem([f"📅 {date_key}", "", ""])
                        date_item.setExpanded(False)  # Collapsed by default
                        self.revisions_tree.addTopLevelItem(date_item)

                        # Under each date, add users
                        for user in sorted(by_date[date_key].keys()):
                            user_item = QTreeWidgetItem(date_item)
                            user_item.setText(0, f"👤 {user}")
                            user_item.setExpanded(False)  # Collapsed by default

                            # Under each user, add detailed changes
                            for rev in by_date[date_key][user]:
                                time_str = rev.changed_at.strftime("%H:%M:%S") if rev.changed_at else "-"
                                field_display = rev.field_name

                                # Format change description
                                old_val = rev.old_value or "-"
                                new_val = rev.new_value or "-"

                                # Handle initial_creation specially
                                if rev.change_type == "initial_creation":
                                    change_desc = f"📝 {field_display}: {new_val}"
                                else:
                                    change_desc = f"📝 {field_display}: {old_val} → {new_val}"

                                change_item = QTreeWidgetItem(user_item)
                                change_item.setText(0, time_str)
                                change_item.setText(2, change_desc)

                            date_item.addChild(user_item)

        if not revisions_exist:
            # Show empty state message
            empty_item = QTreeWidgetItem(["📋 No changes yet", "", ""])
            empty_item.setDisabled(True)
            self.revisions_tree.addTopLevelItem(empty_item)

        # Set column widths
        self.revisions_tree.setColumnWidth(0, 150)
        self.revisions_tree.setColumnWidth(1, 100)
        self.revisions_tree.setColumnWidth(2, 500)

        layout.addWidget(self.revisions_tree)
        return tab

    def _create_dimension_input(self, layout: QVBoxLayout, label: str, min_val: float, max_val: float, initial_val=None) -> QLineEdit:
        """Create a dimension input textbox with label and add to layout."""
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        textbox = QLineEdit()
        textbox.setPlaceholderText(f"Enter value ({min_val}-{max_val})")
        # Do NOT prefill - user must enter manually
        row.addWidget(textbox)
        layout.addLayout(row)
        return textbox

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

    def _on_proj_surface_mode_changed(self):
        """Handle projected surface mode selection change - show/hide relevant frames."""
        is_box_mode = self.radio_proj_box.isChecked()

        # Show box frame, hide direct frame when box is selected
        self.proj_box_frame.setVisible(is_box_mode)
        self.proj_direct_frame.setVisible(not is_box_mode)

        # When switching to box mode, reset origin to "from_box"
        if is_box_mode:
            self._proj_area_origin = "from_box"  # Will show yellow (estimated)
        else:
            # When switching to direct mode, reset origin to manual
            self._proj_area_origin = "manual"
            # Clear the calculated value so it doesn't carry over
            self.proj_area_input.blockSignals(True)  # Don't trigger textChanged
            self.proj_area_input.clear()
            self.proj_area_input.blockSignals(False)

        self._update_validation_status()

    def _on_material_changed(self):
        """Handle material selection change."""
        # This could be used to update density for calculations in future
        pass

    def _on_material_estimated_toggled(self):
        """Handle material estimated checkbox toggle."""
        self._update_material_color()
        self._update_validation_status()  # Update properties panel immediately

    def _update_material_color(self):
        """Update material combo color based on estimated status."""
        from ui.color_coding import apply_source_color_to_widget
        if self.material_estimated_check.isChecked():
            apply_source_color_to_widget(self.material_combo, "estimated")
        else:
            apply_source_color_to_widget(self.material_combo, "data")

    def _on_surface_finish_estimated_toggled(self):
        """Handle surface finish estimated checkbox toggle."""
        self._update_surface_finish_colors()
        self._update_validation_status()  # Update properties panel immediately

    def _update_surface_finish_colors(self):
        """Update surface finish colors based on estimated status."""
        from ui.color_coding import apply_source_color_to_widget, COLOR_ESTIMATED_BG
        if self.surface_finish_estimated_check.isChecked():
            apply_source_color_to_widget(self.surface_finish_combo, "estimated")
            apply_source_color_to_widget(self.surface_finish_detail_input, "estimated")
        else:
            apply_source_color_to_widget(self.surface_finish_combo, "data")
            apply_source_color_to_widget(self.surface_finish_detail_input, "data")

    def _update_validation_status(self):
        """Update properties panel with current part data and highlight missing fields."""
        # Check if widgets exist (they might not during initialization)
        if not hasattr(self, 'demand_peak_spin'):
            return

        # Gather current values from textboxes and inputs
        name = self.name_input.text().strip() if hasattr(self, 'name_input') else ''
        material_id = self.material_combo.currentData() if hasattr(self, 'material_combo') else None
        material_name = self.material_combo.currentText() if hasattr(self, 'material_combo') else ''
        demand = self.demand_peak_spin.value() if self.demand_peak_spin.value() > 0 else None

        # Parse textbox values
        try:
            volume = float(self.volume_input.text().strip()) if hasattr(self, 'volume_input') and self.volume_input.text().strip() else None
        except ValueError:
            volume = None

        try:
            weight = float(self.weight_input.text().strip()) if hasattr(self, 'weight_input') and self.weight_input.text().strip() else None
        except ValueError:
            weight = None

        try:
            proj_area = float(self.proj_area_input.text().strip()) if hasattr(self, 'proj_area_input') and self.proj_area_input.text().strip() else None
        except ValueError:
            proj_area = None

        try:
            wall_thick = float(self.wall_thick_input.text().strip()) if hasattr(self, 'wall_thick_input') and self.wall_thick_input.text().strip() else None
        except ValueError:
            wall_thick = None

        surface_finish = self.surface_finish_combo.currentText() if hasattr(self, 'surface_finish_combo') else ''

        # Create temp part for validation
        temp_part = Part(
            name=name,
            volume_cm3=volume,
            material_id=material_id,
            parts_over_runtime=demand,
        )

        missing = get_missing_fields(temp_part)

        # Track which fields are missing
        missing_volume = volume is None
        missing_weight = weight is None
        missing_proj_area = proj_area is None
        missing_wall_thick = wall_thick is None

        # Track if name is missing
        missing_name = not name or name == ''

        # Update properties labels with missing field markers
        self.prop_labels['name'].setText(self._format_prop('Name', name if name else '-', missing_name))

        # Volume color logic: calculated from weight=grey, from box=yellow, manual with BOM=yellow, manual with CAD=none
        volume_text = f'{volume:.1f}' if volume else '-'
        if self._volume_origin == "from_weight":
            volume_source = "calculated"  # grey
        elif self._volume_origin == "from_box":
            volume_source = "estimated"  # yellow
        elif self._volume_origin == "manual" and hasattr(self, 'weight_volume_source_combo') and self.weight_volume_source_combo.currentData() == "bom":
            volume_source = "bom"  # yellow
        else:
            volume_source = "data"  # no color
        self.prop_labels['volume'].setText(self._format_prop_with_source('Volume (cm³)', volume_text, volume_source, missing_volume))

        # Material with estimated indicator
        material_missing = 'Material' in missing
        material_source = 'estimated' if (hasattr(self, 'material_estimated_check') and self.material_estimated_check.isChecked()) else 'data'
        self.prop_labels['material'].setText(self._format_prop_with_source('Material', material_name if material_id else '-', material_source, material_missing))
        self.prop_labels['demand'].setText(self._format_prop('Total Demand', str(int(demand)) if demand else '-', 'Total Demand' in missing))

        # Weight color logic: calculated from volume=grey, from box=yellow, manual with BOM=yellow, manual with CAD=none
        weight_text = f'{weight:.1f}' if weight else '-'
        if self._weight_origin == "from_volume":
            weight_source = "calculated"  # grey
        elif self._weight_origin == "from_box":
            weight_source = "estimated"  # yellow
        elif self._weight_origin == "manual" and hasattr(self, 'weight_volume_source_combo') and self.weight_volume_source_combo.currentData() == "bom":
            weight_source = "bom"  # yellow
        else:
            weight_source = "data"  # no color
        self.prop_labels['weight'].setText(self._format_prop_with_source('Weight (g)', weight_text, weight_source, missing_weight))

        # Projected area color logic: calculated from box=yellow, manual with BOM=yellow, manual with CAD=none
        proj_area_text = f'{proj_area:.1f}' if proj_area else '-'
        if self._proj_area_origin == "from_box":
            proj_area_source = "estimated"  # yellow (box estimate = estimated)
        elif self._proj_area_origin == "manual" and self._projected_area_source == "bom":
            proj_area_source = "bom"  # yellow
        else:
            proj_area_source = "data"  # no color
        self.prop_labels['proj_area'].setText(self._format_prop_with_source('Proj. Area (cm²)', proj_area_text, proj_area_source, missing_proj_area))

        # Wall thickness with source color and missing indicator
        wall_thick_text = f'{wall_thick:.2f}' if wall_thick else '-'
        wall_thick_source = self._wall_thickness_source if hasattr(self, '_wall_thickness_source') else 'data'
        self.prop_labels['wall_thick'].setText(self._format_prop_with_source('Wall Thick (mm)', wall_thick_text, wall_thick_source, missing_wall_thick))

        # Surface finish with estimated indicator and missing marker
        sf_text = surface_finish if surface_finish else '-'
        sf_detail = self.surface_finish_detail_input.text().strip() if hasattr(self, 'surface_finish_detail_input') else ''
        sf_detail_text = f"{sf_text} ({sf_detail})" if sf_detail else sf_text
        sf_source = 'estimated' if (hasattr(self, 'surface_finish_estimated_check') and self.surface_finish_estimated_check.isChecked()) else 'data'
        sf_missing = not surface_finish or surface_finish == ''
        self.prop_labels['surface_finish'].setText(self._format_prop_with_source('Surface Finish', sf_detail_text, sf_source, sf_missing))

        # Update missing fields indicator (all missing fields)
        all_missing = []
        if missing_name:
            all_missing.append('Name')
        if missing_volume:
            all_missing.append('Volume')
        if 'Material' in missing:
            all_missing.append('Material')
        if 'Total Demand' in missing:
            all_missing.append('Demand')
        if missing_weight:
            all_missing.append('Weight')
        if missing_proj_area:
            all_missing.append('Proj. Area')
        if missing_wall_thick:
            all_missing.append('Wall Thickness')
        if sf_missing:
            all_missing.append('Surface Finish')

        if all_missing:
            missing_text = ", ".join(all_missing)
            self.missing_label.setText(f"<font color='#FF5050'><b>Missing:</b> {missing_text}</font>")
        else:
            self.missing_label.setText("<font color='#70AD47'><b>✓ Complete</b></font>")

    def _format_prop(self, label: str, value: str, is_missing: bool) -> str:
        """Format a property label with optional red text for missing fields."""
        color = '#FF5050' if is_missing else '#ecf0f1'
        return f"<b style='color: #ecf0f1;'>{label}:</b> <font color='{color}'>{value}</font>"

    def _format_prop_with_source(self, label: str, value: str, source: str, is_missing: bool = False) -> str:
        """Format a property with source color indicator (yellow=estimated, blue=bom, grey=calculated, white=data, red=missing)."""
        if is_missing:
            # Missing field - show in red
            return f"<b style='color: #ecf0f1;'>{label}:</b> <font color='#FF5050'>{value}</font>"
        elif value == '-':
            color = '#ecf0f1'
            bg = ''
        elif source == 'estimated':
            color = '#000000'
            bg = "background-color: #FFD54F; padding: 2px 4px; border-radius: 2px;"
        elif source == 'bom':
            color = '#000000'
            bg = "background-color: #64B5F6; padding: 2px 4px; border-radius: 2px;"
        elif source == 'calculated':
            color = '#000000'
            bg = "background-color: #B0BEC5; padding: 2px 4px; border-radius: 2px;"
        else:
            color = '#ecf0f1'
            bg = ''

        if bg:
            return f"<b style='color: #ecf0f1;'>{label}:</b> <span style='{bg}'><font color='{color}'>{value}</font></span>"
        else:
            return f"<b style='color: #ecf0f1;'>{label}:</b> <font color='{color}'>{value}</font>"

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

            # Show preview in main image label
            pixmap = QPixmap(file_path)
            self.image_label.setPixmap(pixmap.scaledToHeight(150, Qt.TransformationMode.SmoothTransformation))
            self.image_label.setText("")
            self.btn_delete_image.setEnabled(True)

            # Update properties panel image
            self._update_properties_image()

            QMessageBox.information(self, "Image Loaded", f"Image '{self.image_filename}' loaded successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image: {str(e)}")

    def _on_image_clicked(self):
        """Handle image label click to show zoom preview."""
        if self.image_data and self.image_filename:
            show_image_preview(self, f"Part Image: {self.image_filename}", self.image_data)

    def _on_delete_image(self):
        """Delete the current image after confirmation."""
        reply = QMessageBox.question(
            self, "Delete Image",
            "Are you sure you want to delete this image?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.image_data = None
            self.image_filename = None
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("No image\nDrag-drop or click Upload")
            self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.btn_delete_image.setEnabled(False)

            # Update properties panel image
            self.props_image_label.setText("No image")
            self.props_image_label.setPixmap(QPixmap())

            QMessageBox.information(self, "Image Deleted", "Image has been removed")

    def _update_properties_image(self):
        """Update the properties panel image display."""
        if self.image_data:
            # Convert image data to pixmap
            pixmap = QPixmap()
            pixmap.loadFromData(self.image_data)
            if not pixmap.isNull():
                # Scale to fit in the properties panel
                scaled_pixmap = pixmap.scaledToHeight(80, Qt.TransformationMode.SmoothTransformation)
                self.props_image_label.setPixmap(scaled_pixmap)
                self.props_image_label.setText("")
            else:
                self.props_image_label.setText("Image error")
        else:
            self.props_image_label.setPixmap(QPixmap())
            self.props_image_label.setText("No image")

    def _on_calculate_box_area(self):
        """Calculate projected area from box dimensions and update the field."""
        try:
            length = float(self.box_length_input.text().strip()) if self.box_length_input.text().strip() else None
            width = float(self.box_width_input.text().strip()) if self.box_width_input.text().strip() else None
            effective_text = self.box_effective_input.text().strip()
            effective = float(effective_text) if effective_text else 100.0
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Length and width must be valid numbers")
            return

        if not length or not width or length <= 0 or width <= 0:
            QMessageBox.warning(self, "Invalid Input", "Length and width must be positive")
            return

        mode = BoxEstimateMode(length, width, effective)
        area = mode.calculate_projected_area()

        if area:
            self.proj_area_input.setText(f"{area:.2f}")
            self._proj_area_origin = "from_box"  # Mark as estimated from box
            self._update_validation_status()
            QMessageBox.information(self, "Calculated", f"Projected area: {area:.2f} cm² calculated from box dimensions")

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
        """Calculate volume from weight using material density and submit."""
        weight = self._get_float_value(self.weight_input)
        if not weight or weight <= 0:
            QMessageBox.warning(self, "Invalid Weight", "Weight must be positive")
            return

        density = self._get_material_density()
        if density is None:
            return

        volume = auto_calculate_volume(weight, density)
        if volume:
            self.volume_input.setText(f"{volume:.2f}")
            self._volume_origin = "from_weight"  # Mark as calculated from weight
            self._update_validation_status()
            QMessageBox.information(self, "Calculated & Applied", f"Volume: {volume:.2f} cm³ calculated from weight")

    def _on_calc_weight_from_volume(self):
        """Calculate weight from volume using material density and submit."""
        volume = self._get_float_value(self.volume_input)
        if not volume or volume <= 0:
            QMessageBox.warning(self, "Invalid Volume", "Volume must be positive")
            return

        density = self._get_material_density()
        if density is None:
            return

        weight = auto_calculate_weight(volume, density)
        if weight:
            self.weight_input.setText(f"{weight:.2f}")
            self._weight_origin = "from_volume"  # Mark as calculated from volume
            self._update_validation_status()
            QMessageBox.information(self, "Calculated & Applied", f"Weight: {weight:.2f} g calculated from volume")

    def _on_submit_proj_area(self):
        """Submit projected area value to properties."""
        try:
            value = float(self.proj_area_input.text().strip())
            if value <= 0:
                QMessageBox.warning(self, "Invalid Value", "Projected area must be positive")
                return
            # Only update source if in direct mode
            if self.radio_proj_direct.isChecked():
                self._projected_area_source = self.proj_area_source_combo.currentData()
                self._proj_area_origin = "manual"  # Reset to manual entry
            # If in box mode, origin stays as "from_box"
            self._update_validation_status()
            origin_label = "(Calculated from Box)" if self._proj_area_origin == "from_box" else "(Direct Entry)"
            QMessageBox.information(self, "Submitted", f"Projected area: {value:.2f} cm² submitted {origin_label}")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number")


    def _on_volume_input_changed(self):
        """Handle volume input change - reset origin to manual (no auto-update properties)."""
        self._volume_origin = "manual"

    def _on_weight_input_changed(self):
        """Handle weight input change - reset origin to manual (no auto-update properties)."""
        self._weight_origin = "manual"

    def _on_proj_area_input_changed(self):
        """Handle projected area input change - reset origin to manual (no auto-update properties)."""
        self._proj_area_origin = "manual"

    def _on_estimate_wall_thickness(self):
        """Estimate wall thickness with standard 2.5mm value."""
        self.wall_thick_input.setText("2.5")
        self._wall_thickness_source = "estimated"
        index = self.wall_thick_source_combo.findData("estimated")
        if index >= 0:
            self.wall_thick_source_combo.setCurrentIndex(index)
        self._on_wall_thick_source_changed()
        QMessageBox.information(self, "Estimated", "Wall thickness set to standard 2.5mm (marked as estimated)")

    def _on_wall_thick_source_changed(self):
        """Handle wall thickness source change."""
        self._wall_thickness_source = self.wall_thick_source_combo.currentData()
        # Update checkbox to reflect estimated status
        self.wall_thick_source_check.setChecked(self._wall_thickness_source == "estimated")
        self._update_wall_thickness_color()

    def _on_proj_area_source_changed(self):
        """Handle projected area source change."""
        self._projected_area_source = self.proj_area_source_combo.currentData()
        self._update_proj_area_color()

    def _on_wall_thick_estimated_toggled(self):
        """Handle wall thickness estimated checkbox toggle."""
        if self.wall_thick_source_check.isChecked():
            self.wall_thick_source_combo.setCurrentIndex(self.wall_thick_source_combo.findData("estimated"))
        else:
            self.wall_thick_source_combo.setCurrentIndex(self.wall_thick_source_combo.findData("data"))

    def _update_wall_thickness_color(self):
        """Update wall thickness display color based on source (handled in properties panel)."""
        # Color display now handled by properties panel via _format_prop_with_source()
        # This method kept for compatibility but no longer applies colors to widgets
        pass

    def _update_proj_area_color(self):
        """Update projected area display color based on source (handled in properties panel)."""
        # Color display now handled by properties panel via _format_prop_with_source()
        # This method kept for compatibility but no longer applies colors to widgets
        pass

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

    def _get_float_value(self, text_input: QLineEdit) -> float:
        """Safely parse float from textbox, return None if invalid/empty."""
        try:
            val = text_input.text().strip()
            return float(val) if val else None
        except (ValueError, AttributeError):
            return None

    def _on_save(self):
        """Save part."""
        name = self.name_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Validation", "Part name is required (database constraint)")
            return

        material_id = self.material_combo.currentData()
        geometry_mode = "box" if self.radio_box.isChecked() else "direct"

        # Parse textbox values
        weight = self._get_float_value(self.weight_input)
        volume = self._get_float_value(self.volume_input)
        proj_area = self._get_float_value(self.proj_area_input)
        wall_thick = self._get_float_value(self.wall_thick_input)

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
                    if part.weight_g != weight:
                        changes.append(("weight_g", str(part.weight_g), str(weight)))
                    if part.volume_cm3 != volume:
                        changes.append(("volume_cm3", str(part.volume_cm3), str(volume)))
                    if part.projected_area_cm2 != proj_area:
                        changes.append(("projected_area_cm2", str(part.projected_area_cm2), str(proj_area)))
                    if part.image_filename != self.image_filename:
                        changes.append(("image_filename", part.image_filename or "None", self.image_filename or "None"))

                    # Update all fields (excluding degate and eoat_type - moved to tool level in V2.0)
                    part.name = name
                    part.part_number = self.part_number_input.text().strip() or None
                    part.material_id = material_id
                    part.weight_g = weight
                    part.volume_cm3 = volume
                    part.projected_area_cm2 = proj_area
                    part.wall_thickness_mm = wall_thick
                    part.wall_thickness_source = self._wall_thickness_source
                    part.wall_thickness_needs_improvement = self.wall_thick_improve_check.isChecked()
                    # Projected area source (V2.0)
                    part.projected_area_source = self._projected_area_source
                    # Surface finish (V2.0)
                    part.surface_finish = self.surface_finish_combo.currentData() or None
                    part.surface_finish_detail = self.surface_finish_detail_input.text().strip() or None
                    part.surface_finish_estimated = self.surface_finish_estimated_check.isChecked()
                    # Note: demand_sop and demand_eaop are now at RFQ level (project-level)
                    # demand_peak_spin now holds total demand (saved to parts_over_runtime)
                    part.parts_over_runtime = self.demand_peak_spin.value() or None
                    part.assembly = self.assembly_check.isChecked()
                    part.overmold = self.overmold_check.isChecked()
                    # V2.0: degate and eoat_type are now at tool level
                    part.notes = self.notes_input.toPlainText().strip() or None
                    part.remarks = self.remarks_input.toPlainText().strip() or None
                    part.geometry_mode = geometry_mode
                    if geometry_mode == "box":
                        try:
                            part.box_length_mm = float(self.box_length_input.text().strip()) if self.box_length_input.text().strip() else None
                        except (ValueError, AttributeError):
                            part.box_length_mm = None
                        try:
                            part.box_width_mm = float(self.box_width_input.text().strip()) if self.box_width_input.text().strip() else None
                        except (ValueError, AttributeError):
                            part.box_width_mm = None
                        try:
                            part.box_effective_percent = float(self.box_effective_input.text().strip()) if self.box_effective_input.text().strip() else 100.0
                        except (ValueError, AttributeError):
                            part.box_effective_percent = 100.0

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
                        weight_g=weight,
                        volume_cm3=volume,
                        projected_area_cm2=proj_area,
                        wall_thickness_mm=wall_thick,
                        wall_thickness_source=self._wall_thickness_source,
                        wall_thickness_needs_improvement=self.wall_thick_improve_check.isChecked(),
                        # Projected area source (V2.0)
                        projected_area_source=self._projected_area_source,
                        # Surface finish (V2.0)
                        surface_finish=self.surface_finish_combo.currentData() or None,
                        surface_finish_detail=self.surface_finish_detail_input.text().strip() or None,
                        surface_finish_estimated=self.surface_finish_estimated_check.isChecked(),
                        # Note: demand_sop and demand_eaop are now at RFQ level (project-level)
                        # demand_peak_spin now holds total demand (saved to parts_over_runtime)
                        parts_over_runtime=self.demand_peak_spin.value() or None,
                        assembly=self.assembly_check.isChecked(),
                        overmold=self.overmold_check.isChecked(),
                        # V2.0: degate and eoat_type are now at tool level
                        notes=self.notes_input.toPlainText().strip() or None,
                        remarks=self.remarks_input.toPlainText().strip() or None,
                        geometry_mode=geometry_mode,
                        box_length_mm=(float(self.box_length_input.text().strip()) if self.box_length_input.text().strip() else None) if geometry_mode == "box" else None,
                        box_width_mm=(float(self.box_width_input.text().strip()) if self.box_width_input.text().strip() else None) if geometry_mode == "box" else None,
                        box_effective_percent=(float(self.box_effective_input.text().strip()) if self.box_effective_input.text().strip() else 100.0) if geometry_mode == "box" else 100.0,
                        image_binary=self.image_data,
                        image_filename=self.image_filename,
                        image_updated_date=datetime.now() if self.image_data else None,
                    )
                    session.add(part)
                    session.flush()
                    self._saved_part_id = part.id

                    # Log initial creation as revision
                    fields_created = []
                    if part.name:
                        fields_created.append(("name", "", part.name))
                    if part.volume_cm3:
                        fields_created.append(("volume_cm3", "", str(part.volume_cm3)))
                    if part.material_id:
                        fields_created.append(("material_id", "", str(part.material_id)))
                    if part.weight_g:
                        fields_created.append(("weight_g", "", str(part.weight_g)))
                    if part.projected_area_cm2:
                        fields_created.append(("projected_area_cm2", "", str(part.projected_area_cm2)))
                    if part.wall_thickness_mm:
                        fields_created.append(("wall_thickness_mm", "", str(part.wall_thickness_mm)))
                    if part.surface_finish:
                        fields_created.append(("surface_finish", "", part.surface_finish))
                    if part.surface_finish_detail:
                        fields_created.append(("surface_finish_detail", "", part.surface_finish_detail))
                    if part.parts_over_runtime:
                        fields_created.append(("parts_over_runtime", "", str(part.parts_over_runtime)))

                    for field_name, old_val, new_val in fields_created:
                        rev = PartRevision(
                            part_id=part.id,
                            field_name=field_name,
                            old_value=old_val or None,
                            new_value=str(new_val)[:500] if new_val else None,
                            changed_by="user",
                            change_type="initial_creation"
                        )
                        session.add(rev)

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
