"""Main application window."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QToolBar,
    QStatusBar, QMessageBox, QHeaderView, QAbstractItemView,
    QSplitter, QFrame, QLabel, QComboBox, QLineEdit, QDialog, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon, QPixmap

from config import APP_NAME, APP_VERSION
from database import get_session, init_db, seed_database, RFQ, Part, Tool, ExistingTool
from database.connection import session_scope
from .dialogs.rfq_dialog import RFQDialog
from .dialogs.part_dialog import PartDialog


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1200, 800)

        # Initialize database
        self._init_database()

        # Setup UI
        self._setup_ui()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_statusbar()

        # Load initial data
        self._refresh_data()

    def _init_database(self):
        """Initialize database and seed data."""
        init_db()
        materials_added, machines_added = seed_database()
        if materials_added > 0 or machines_added > 0:
            print(f"Seeded {materials_added} materials and {machines_added} machines")

    def _setup_ui(self):
        """Setup the main UI layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Tab widget for main sections
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # RFQ tab
        self.rfq_tab = self._create_rfq_tab()
        self.tab_widget.addTab(self.rfq_tab, "RFQs")

        # Existing Tools tab
        self.existing_tools_tab = self._create_existing_tools_tab()
        self.tab_widget.addTab(self.existing_tools_tab, "Existing Tools")

        # Materials tab
        self.materials_tab = self._create_materials_tab()
        self.tab_widget.addTab(self.materials_tab, "Materials")

        # Machines tab
        self.machines_tab = self._create_machines_tab()
        self.tab_widget.addTab(self.machines_tab, "Machines")

    def _create_rfq_tab(self) -> QWidget:
        """Create the RFQ management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Toolbar for RFQ actions
        toolbar = QHBoxLayout()

        self.btn_new_rfq = QPushButton("New RFQ")
        self.btn_new_rfq.clicked.connect(self._on_new_rfq)
        toolbar.addWidget(self.btn_new_rfq)

        self.btn_edit_rfq = QPushButton("Edit RFQ")
        self.btn_edit_rfq.clicked.connect(self._on_edit_rfq)
        toolbar.addWidget(self.btn_edit_rfq)

        self.btn_delete_rfq = QPushButton("Delete RFQ")
        self.btn_delete_rfq.clicked.connect(self._on_delete_rfq)
        toolbar.addWidget(self.btn_delete_rfq)

        toolbar.addStretch()

        self.btn_export_rfq = QPushButton("Export to Excel")
        self.btn_export_rfq.clicked.connect(self._on_export_rfq)
        toolbar.addWidget(self.btn_export_rfq)

        layout.addLayout(toolbar)

        # Splitter for RFQ list and details
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # RFQ list
        self.rfq_table = QTableWidget()
        self.rfq_table.setColumnCount(5)
        self.rfq_table.setHorizontalHeaderLabels(["ID", "Name", "Customer", "Status", "Created"])
        self.rfq_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.rfq_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rfq_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.rfq_table.itemSelectionChanged.connect(self._on_rfq_selected)
        self.rfq_table.doubleClicked.connect(self._on_edit_rfq)
        splitter.addWidget(self.rfq_table)

        # Details panel
        details_frame = QFrame()
        details_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        details_layout = QVBoxLayout(details_frame)

        # RFQ Demand Info
        details_layout.addWidget(QLabel("<b>RFQ Demand Planning</b>"))
        self.rfq_demand_label = QLabel()
        self.rfq_demand_label.setWordWrap(True)
        details_layout.addWidget(self.rfq_demand_label)

        details_layout.addSpacing(10)
        details_layout.addWidget(QLabel("<b>Parts & Tools</b>"))

        # Parts table
        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(11)
        self.parts_table.setHorizontalHeaderLabels([
            "Part Name", "Image", "Material", "Weight (g)", "Proj. Surface", "Total Demand",
            "Assy", "Degate", "Overmold", "EOAT", "Notes"
        ])
        self.parts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.parts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.parts_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # Increase row height by 50% for image preview
        self.parts_table.verticalHeader().setDefaultSectionSize(75)
        self.parts_table.setColumnWidth(1, 100)  # Image column width
        details_layout.addWidget(self.parts_table)

        # Part actions
        part_toolbar = QHBoxLayout()
        self.btn_add_part = QPushButton("Add Part")
        self.btn_add_part.clicked.connect(self._on_add_part)
        part_toolbar.addWidget(self.btn_add_part)

        self.btn_edit_part = QPushButton("Edit Part")
        self.btn_edit_part.clicked.connect(self._on_edit_part)
        part_toolbar.addWidget(self.btn_edit_part)

        self.btn_delete_part = QPushButton("Delete Part")
        self.btn_delete_part.clicked.connect(self._on_delete_part)
        part_toolbar.addWidget(self.btn_delete_part)

        part_toolbar.addStretch()

        self.btn_add_tool = QPushButton("Add Tool")
        self.btn_add_tool.clicked.connect(self._on_add_tool)
        part_toolbar.addWidget(self.btn_add_tool)

        part_toolbar.addStretch()
        details_layout.addLayout(part_toolbar)

        # Tools table
        details_layout.addWidget(QLabel("<b>Tools</b>"))
        self.tools_table = QTableWidget()
        self.tools_table.setColumnCount(7)
        self.tools_table.setHorizontalHeaderLabels([
            "Tool Name", "Type", "Cavities", "Clamping (kN)", "Machine", "Fits?", "Price"
        ])
        self.tools_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        details_layout.addWidget(self.tools_table)

        splitter.addWidget(details_frame)
        splitter.setSizes([400, 800])

        layout.addWidget(splitter)
        return tab

    def _create_existing_tools_tab(self) -> QWidget:
        """Create the existing tools reference tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Toolbar
        toolbar = QHBoxLayout()

        self.btn_new_existing = QPushButton("Add Tool")
        self.btn_new_existing.clicked.connect(self._on_new_existing_tool)
        toolbar.addWidget(self.btn_new_existing)

        self.btn_edit_existing = QPushButton("Edit Tool")
        self.btn_edit_existing.clicked.connect(self._on_edit_existing_tool)
        toolbar.addWidget(self.btn_edit_existing)

        toolbar.addWidget(QLabel("Filter:"))
        self.existing_filter = QLineEdit()
        self.existing_filter.setPlaceholderText("Search by name, supplier, tags...")
        self.existing_filter.textChanged.connect(self._filter_existing_tools)
        self.existing_filter.setMaximumWidth(300)
        toolbar.addWidget(self.existing_filter)

        toolbar.addStretch()

        self.btn_export_existing = QPushButton("Export to Excel")
        self.btn_export_existing.clicked.connect(self._on_export_existing)
        toolbar.addWidget(self.btn_export_existing)

        layout.addLayout(toolbar)

        # Table
        self.existing_table = QTableWidget()
        self.existing_table.setColumnCount(10)
        self.existing_table.setHorizontalHeaderLabels([
            "Name", "Part Type", "Complexity", "Cavities", "Sliders", "Lifters",
            "Supplier", "Country", "Price", "Date"
        ])
        self.existing_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.existing_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.existing_table.doubleClicked.connect(self._on_edit_existing_tool)
        layout.addWidget(self.existing_table)

        return tab

    def _create_materials_tab(self) -> QWidget:
        """Create the materials reference tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Table
        self.materials_table = QTableWidget()
        self.materials_table.setColumnCount(8)
        self.materials_table.setHorizontalHeaderLabels([
            "Short Name", "Full Name", "Family", "Density",
            "Shrinkage %", "Melt Temp", "Mold Temp", "Spec. Pressure"
        ])
        self.materials_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.materials_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.materials_table)

        return tab

    def _create_machines_tab(self) -> QWidget:
        """Create the machines reference tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Table
        self.machines_table = QTableWidget()
        self.machines_table.setColumnCount(8)
        self.machines_table.setHorizontalHeaderLabels([
            "Name", "Manufacturer", "Clamping (kN)", "Shot (g)",
            "Platen WxH", "Tie-bar Spacing", "Mold Height", "Notes"
        ])
        self.machines_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.machines_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.machines_table)

        return tab

    def _setup_menubar(self):
        """Setup the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_rfq_action = QAction("&New RFQ", self)
        new_rfq_action.setShortcut("Ctrl+N")
        new_rfq_action.triggered.connect(self._on_new_rfq)
        file_menu.addAction(new_rfq_action)

        file_menu.addSeparator()

        export_action = QAction("&Export to Excel", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._on_export_rfq)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_data)
        edit_menu.addAction(refresh_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        """Setup the toolbar."""
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        toolbar.addAction("New RFQ", self._on_new_rfq)
        toolbar.addAction("Refresh", self._refresh_data)
        toolbar.addSeparator()
        toolbar.addAction("Export", self._on_export_rfq)

    def _setup_statusbar(self):
        """Setup the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready")

    def _refresh_data(self):
        """Refresh all data from database."""
        self._load_rfqs()
        self._load_existing_tools()
        self._load_materials()
        self._load_machines()
        self.statusbar.showMessage("Data refreshed", 3000)

    def _load_rfqs(self):
        """Load RFQs into table."""
        with session_scope() as session:
            rfqs = session.query(RFQ).order_by(RFQ.created_date.desc()).all()

            self.rfq_table.setRowCount(len(rfqs))
            for row, rfq in enumerate(rfqs):
                self.rfq_table.setItem(row, 0, QTableWidgetItem(str(rfq.id)))
                self.rfq_table.setItem(row, 1, QTableWidgetItem(rfq.name))
                self.rfq_table.setItem(row, 2, QTableWidgetItem(rfq.customer or "-"))
                self.rfq_table.setItem(row, 3, QTableWidgetItem(rfq.status))
                date_str = rfq.created_date.strftime('%Y-%m-%d') if rfq.created_date else "-"
                self.rfq_table.setItem(row, 4, QTableWidgetItem(date_str))

    def _load_existing_tools(self):
        """Load existing tools into table."""
        with session_scope() as session:
            tools = session.query(ExistingTool).order_by(ExistingTool.created_date.desc()).all()

            self.existing_table.setRowCount(len(tools))
            for row, tool in enumerate(tools):
                self.existing_table.setItem(row, 0, QTableWidgetItem(tool.name))
                self.existing_table.setItem(row, 1, QTableWidgetItem(tool.part_type or "-"))
                self.existing_table.setItem(row, 2, QTableWidgetItem(str(tool.complexity_rating or "-")))
                self.existing_table.setItem(row, 3, QTableWidgetItem(str(tool.cavities)))
                self.existing_table.setItem(row, 4, QTableWidgetItem(str(tool.sliders_count)))
                self.existing_table.setItem(row, 5, QTableWidgetItem(str(tool.lifters_count)))
                self.existing_table.setItem(row, 6, QTableWidgetItem(tool.supplier_name or "-"))
                self.existing_table.setItem(row, 7, QTableWidgetItem(tool.supplier_country or "-"))
                price_str = f"{tool.currency} {tool.actual_price:,.2f}" if tool.actual_price else "-"
                self.existing_table.setItem(row, 8, QTableWidgetItem(price_str))
                date_str = tool.price_date.strftime('%Y-%m-%d') if tool.price_date else "-"
                self.existing_table.setItem(row, 9, QTableWidgetItem(date_str))

    def _load_materials(self):
        """Load materials into table."""
        from database.models import Material

        with session_scope() as session:
            materials = session.query(Material).order_by(Material.family, Material.short_name).all()

            self.materials_table.setRowCount(len(materials))
            for row, mat in enumerate(materials):
                self.materials_table.setItem(row, 0, QTableWidgetItem(mat.short_name))
                self.materials_table.setItem(row, 1, QTableWidgetItem(mat.name))
                self.materials_table.setItem(row, 2, QTableWidgetItem(mat.family))
                self.materials_table.setItem(row, 3, QTableWidgetItem(f"{mat.density_g_cm3:.2f}" if mat.density_g_cm3 else "-"))

                shrink = f"{mat.shrinkage_min_percent}-{mat.shrinkage_max_percent}" if mat.shrinkage_min_percent else "-"
                self.materials_table.setItem(row, 4, QTableWidgetItem(shrink))

                melt = f"{mat.melt_temp_min_c:.0f}-{mat.melt_temp_max_c:.0f}°C" if mat.melt_temp_min_c else "-"
                self.materials_table.setItem(row, 5, QTableWidgetItem(melt))

                mold = f"{mat.mold_temp_min_c:.0f}-{mat.mold_temp_max_c:.0f}°C" if mat.mold_temp_min_c else "-"
                self.materials_table.setItem(row, 6, QTableWidgetItem(mold))

                pressure = f"{mat.specific_pressure_min_bar:.0f}-{mat.specific_pressure_max_bar:.0f} bar" if mat.specific_pressure_min_bar else "-"
                self.materials_table.setItem(row, 7, QTableWidgetItem(pressure))

    def _load_machines(self):
        """Load machines into table."""
        from database.models import Machine

        with session_scope() as session:
            machines = session.query(Machine).order_by(Machine.clamping_force_kn).all()

            self.machines_table.setRowCount(len(machines))
            for row, mach in enumerate(machines):
                self.machines_table.setItem(row, 0, QTableWidgetItem(mach.name))
                self.machines_table.setItem(row, 1, QTableWidgetItem(mach.manufacturer or "-"))
                self.machines_table.setItem(row, 2, QTableWidgetItem(f"{mach.clamping_force_kn:.0f}" if mach.clamping_force_kn else "-"))
                self.machines_table.setItem(row, 3, QTableWidgetItem(f"{mach.shot_weight_g:.0f}" if mach.shot_weight_g else "-"))

                platen = f"{mach.platen_width_mm:.0f}x{mach.platen_height_mm:.0f}" if mach.platen_width_mm else "-"
                self.machines_table.setItem(row, 4, QTableWidgetItem(platen))

                tiebar = f"{mach.tie_bar_spacing_h_mm:.0f}x{mach.tie_bar_spacing_v_mm:.0f}" if mach.tie_bar_spacing_h_mm else "-"
                self.machines_table.setItem(row, 5, QTableWidgetItem(tiebar))

                height = f"{mach.min_mold_height_mm:.0f}-{mach.max_mold_height_mm:.0f}" if mach.min_mold_height_mm else "-"
                self.machines_table.setItem(row, 6, QTableWidgetItem(height))

                self.machines_table.setItem(row, 7, QTableWidgetItem(mach.notes or "-"))

    def _get_selected_id_from_table(self, table: QTableWidget, column: int = 0) -> int:
        """Get ID from first column of selected row. Returns None if no selection."""
        selected = table.selectedItems()
        if not selected:
            return None
        try:
            return int(table.item(selected[0].row(), column).text())
        except (ValueError, AttributeError):
            return None

    def _on_rfq_selected(self):
        """Handle RFQ selection change."""
        rfq_id = self._get_selected_id_from_table(self.rfq_table)
        if rfq_id is None:
            self.parts_table.setRowCount(0)
            self.tools_table.setRowCount(0)
            return

        self._load_rfq_details(rfq_id)

    def _load_rfq_details(self, rfq_id: int):
        """Load parts and tools for selected RFQ."""
        with session_scope() as session:
            rfq = session.query(RFQ).get(rfq_id)
            if not rfq:
                return

            # Display RFQ demand info
            sop_text = f"{rfq.demand_sop:,} pcs/year" if rfq.demand_sop else "Not set"
            eaop_text = f"{rfq.demand_eaop:,} pcs/year" if rfq.demand_eaop else "Not set"
            demand_info = f"SOP: {sop_text}  |  EAOP: {eaop_text}"
            self.rfq_demand_label.setText(demand_info)

            # Load parts
            self.parts_table.setRowCount(len(rfq.parts))
            for row, part in enumerate(rfq.parts):
                self.parts_table.setItem(row, 0, QTableWidgetItem(part.name))

                # Image column (clickable thumbnail preview)
                if part.image_binary:
                    img_label = QLabel()
                    pixmap = QPixmap()
                    pixmap.loadFromData(part.image_binary)
                    # Scale to fit cell (75px height with some padding)
                    scaled_pixmap = pixmap.scaledToHeight(65, Qt.TransformationMode.SmoothTransformation)
                    img_label.setPixmap(scaled_pixmap)
                    img_label.setStyleSheet("text-align: center; cursor: pointer; padding: 3px; border: 1px solid #ddd; border-radius: 3px;")
                    img_label.setCursor(Qt.CursorShape.PointingHandCursor)
                    img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    img_label.part_id = part.id
                    img_label.image_data = part.image_binary
                    img_label.mousePressEvent = lambda e, pid=part.id, img=part.image_binary: self._on_image_clicked(pid, img)
                    self.parts_table.setCellWidget(row, 1, img_label)
                else:
                    self.parts_table.setItem(row, 1, QTableWidgetItem("-"))

                mat_name = part.material.short_name if part.material else "-"
                self.parts_table.setItem(row, 2, QTableWidgetItem(mat_name))
                self.parts_table.setItem(row, 3, QTableWidgetItem(f"{part.weight_g:.1f}" if part.weight_g else "-"))
                self.parts_table.setItem(row, 4, QTableWidgetItem(f"{part.projected_area_cm2:.1f}" if part.projected_area_cm2 else "-"))
                # Changed from demand_peak to parts_over_runtime (total demand)
                self.parts_table.setItem(row, 5, QTableWidgetItem(str(part.parts_over_runtime or "-")))
                self.parts_table.setItem(row, 6, QTableWidgetItem("✓" if part.assembly else ""))
                self.parts_table.setItem(row, 7, QTableWidgetItem(part.degate))
                self.parts_table.setItem(row, 8, QTableWidgetItem("✓" if part.overmold else ""))
                self.parts_table.setItem(row, 9, QTableWidgetItem(part.eoat_type))
                remarks = (part.remarks or "")[:20] + ("..." if part.remarks and len(part.remarks) > 20 else "")
                self.parts_table.setItem(row, 10, QTableWidgetItem(remarks))

            # Load tools (get all tools associated with this RFQ's parts)
            tool_ids = set()
            tools = []
            for part in rfq.parts:
                for tool in part.tools:
                    if tool.id not in tool_ids:
                        tool_ids.add(tool.id)
                        tools.append(tool)

            self.tools_table.setRowCount(len(tools))
            for row, tool in enumerate(tools):
                self.tools_table.setItem(row, 0, QTableWidgetItem(tool.name))
                self.tools_table.setItem(row, 1, QTableWidgetItem(tool.tool_type))
                self.tools_table.setItem(row, 2, QTableWidgetItem(str(tool.cavities)))
                self.tools_table.setItem(row, 3, QTableWidgetItem(f"{tool.estimated_clamping_force_kn:.0f}" if tool.estimated_clamping_force_kn else "-"))
                self.tools_table.setItem(row, 4, QTableWidgetItem(tool.machine.name if tool.machine else "-"))

                fits_text = "?" if tool.fits_machine is None else ("Yes" if tool.fits_machine else "NO")
                self.tools_table.setItem(row, 5, QTableWidgetItem(fits_text))

                price = tool.price_enquiry or tool.price_estimated
                price_text = f"€ {price:,.0f}" if price else "-"
                self.tools_table.setItem(row, 6, QTableWidgetItem(price_text))

    def _filter_existing_tools(self, text: str):
        """Filter existing tools table by search text."""
        text = text.lower()
        for row in range(self.existing_table.rowCount()):
            show = False
            for col in range(self.existing_table.columnCount()):
                item = self.existing_table.item(row, col)
                if item and text in item.text().lower():
                    show = True
                    break
            self.existing_table.setRowHidden(row, not show)

    # Action handlers
    def _on_new_rfq(self):
        """Create new RFQ."""
        dialog = RFQDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_rfqs()
            self.statusbar.showMessage("RFQ created successfully", 3000)

    def _on_edit_rfq(self):
        """Edit selected RFQ."""
        rfq_id = self._get_selected_id_from_table(self.rfq_table)
        if rfq_id is None:
            QMessageBox.warning(self, "No Selection", "Please select an RFQ to edit")
            return

        dialog = RFQDialog(self, rfq_id=rfq_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_rfqs()
            self.statusbar.showMessage("RFQ updated successfully", 3000)

    def _get_selected_row_values(self, table: QTableWidget, columns: list) -> list:
        """Get values from specific columns of selected row."""
        selected = table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        return [table.item(row, col).text() for col in columns]

    def _on_delete_rfq(self):
        """Delete selected RFQ."""
        values = self._get_selected_row_values(self.rfq_table, [0, 1])
        if values is None:
            QMessageBox.warning(self, "No Selection", "Please select an RFQ to delete")
            return

        rfq_id, rfq_name = int(values[0]), values[1]
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete RFQ '{rfq_name}'?\nThis will also delete all associated parts and tools.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with session_scope() as session:
                rfq = session.query(RFQ).get(rfq_id)
                if rfq:
                    session.delete(rfq)
            self._load_rfqs()
            self.parts_table.setRowCount(0)
            self.tools_table.setRowCount(0)
            self.statusbar.showMessage(f"Deleted RFQ: {rfq_name}", 3000)

    def _on_export_rfq(self):
        """Export selected RFQ to Excel."""
        # TODO: Implement export with file dialog
        QMessageBox.information(self, "Not Implemented", "Excel export will be implemented in Phase 5")

    def _on_add_part(self):
        """Add part to selected RFQ."""
        rfq_id = self._get_selected_id_from_table(self.rfq_table)
        if rfq_id is None:
            QMessageBox.warning(self, "No Selection", "Please select an RFQ first")
            return

        dialog = PartDialog(self, rfq_id=rfq_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_rfq_details(rfq_id)
            self.statusbar.showMessage("Part added successfully", 3000)

    def _on_edit_part(self):
        """Edit selected part."""
        rfq_id = self._get_selected_id_from_table(self.rfq_table)
        if rfq_id is None:
            QMessageBox.warning(self, "No RFQ", "Please select an RFQ first")
            return

        part_name = self._get_selected_row_values(self.parts_table, [0])
        if part_name is None:
            QMessageBox.warning(self, "No Selection", "Please select a part to edit")
            return

        # Find part ID by name in current RFQ
        part_id = self._get_part_id_by_name(rfq_id, part_name[0])
        if part_id is None:
            return

        dialog = PartDialog(self, rfq_id=rfq_id, part_id=part_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_rfq_details(rfq_id)
            self.statusbar.showMessage("Part updated successfully", 3000)

    def _get_part_id_by_name(self, rfq_id: int, part_name: str) -> int:
        """Get part ID by name within RFQ. Returns None if not found."""
        with session_scope() as session:
            part = session.query(Part).filter(
                Part.rfq_id == rfq_id,
                Part.name == part_name
            ).first()
            if not part:
                QMessageBox.warning(self, "Error", "Part not found")
                return None
            return part.id

    def _on_delete_part(self):
        """Delete selected part."""
        rfq_id = self._get_selected_id_from_table(self.rfq_table)
        if rfq_id is None:
            QMessageBox.warning(self, "No RFQ", "Please select an RFQ first")
            return

        part_name = self._get_selected_row_values(self.parts_table, [0])
        if part_name is None:
            QMessageBox.warning(self, "No Selection", "Please select a part to delete")
            return

        part_name = part_name[0]
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete part '{part_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with session_scope() as session:
                part = session.query(Part).filter(
                    Part.rfq_id == rfq_id,
                    Part.name == part_name
                ).first()
                if part:
                    session.delete(part)
            self._load_rfq_details(rfq_id)
            self.statusbar.showMessage(f"Deleted part: {part_name}", 3000)

    def _on_image_clicked(self, part_id: int, image_data: bytes):
        """Open image viewer dialog when image is clicked."""
        if not image_data:
            return

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Part Image #{part_id}")
        dialog.setMinimumSize(600, 600)

        # Create layout with scrollable image
        layout = QVBoxLayout(dialog)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        # Display image
        img_label = QLabel()
        pixmap = QPixmap()
        pixmap.loadFromData(image_data)
        # Scale if too large
        if pixmap.width() > 1000 or pixmap.height() > 1000:
            pixmap = pixmap.scaledToWidth(1000, Qt.TransformationMode.SmoothTransformation)
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        scroll.setWidget(img_label)
        layout.addWidget(scroll)

        # Close button
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)

        dialog.exec()

    def _on_add_tool(self):
        """Add tool to selected RFQ."""
        selected = self.rfq_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select an RFQ first")
            return
        # TODO: Implement Tool dialog in Phase 3
        QMessageBox.information(self, "Not Implemented", "Tool dialog will be implemented in Phase 3")

    def _on_new_existing_tool(self):
        """Add new existing tool reference."""
        # TODO: Implement ExistingTool dialog
        QMessageBox.information(self, "Not Implemented", "Existing tool dialog will be implemented in Phase 4")

    def _on_edit_existing_tool(self):
        """Edit selected existing tool."""
        # TODO: Implement ExistingTool dialog
        QMessageBox.information(self, "Not Implemented", "Existing tool dialog will be implemented in Phase 4")

    def _on_export_existing(self):
        """Export existing tools to Excel."""
        # TODO: Implement export with file dialog
        QMessageBox.information(self, "Not Implemented", "Excel export will be implemented in Phase 5")

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h3>{APP_NAME}</h3>"
            f"<p>Version {APP_VERSION}</p>"
            "<p>RFQ Tool Quoting Software for Injection Molding</p>"
            "<p>Features:</p>"
            "<ul>"
            "<li>Manage RFQs with parts and tools</li>"
            "<li>Automatic clamping force calculation</li>"
            "<li>Machine fit validation</li>"
            "<li>Demand feasibility checks</li>"
            "<li>Historical tool price database</li>"
            "<li>Excel export</li>"
            "</ul>"
        )
