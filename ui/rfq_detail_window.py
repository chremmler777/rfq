"""Dedicated window for RFQ detail editing (parts, tools, calculations)."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QMessageBox, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QScrollArea, QFrame, QSpinBox,
    QTreeWidget, QTreeWidgetItem, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QIcon, QColor

from database.connection import session_scope
from database.models import RFQ, Part, Tool, Material, Machine, ToolPartConfiguration
from .dialogs.part_dialog import PartDialog
from .dialogs.tool_dialog import ToolDialog
from .widgets.image_preview import show_image_preview


class RFQDetailWindow(QMainWindow):
    """Dedicated window for editing a single RFQ with parts and tools."""

    def __init__(self, rfq_id: int, parent=None):
        super().__init__(parent)
        self.rfq_id = rfq_id
        self.rfq = None

        self.setMinimumSize(1200, 800)
        self._load_rfq()
        self._setup_ui()
        self._refresh_data()

    def _load_rfq(self):
        """Load RFQ from database."""
        with session_scope() as session:
            self.rfq = session.query(RFQ).get(self.rfq_id)
            if self.rfq:
                session.expunge(self.rfq)

    def _setup_ui(self):
        """Setup the window UI."""
        if not self.rfq:
            QMessageBox.critical(self, "Error", "RFQ not found")
            self.close()
            return

        self.setWindowTitle(f"RFQ: {self.rfq.name} (ID: {self.rfq.id})")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # RFQ info header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(f"<b>Customer:</b> {self.rfq.customer or 'N/A'}"))
        header_layout.addWidget(QLabel(f"<b>Status:</b> {self.rfq.status}"))
        header_layout.addWidget(QLabel(f"<b>Created:</b> {self.rfq.created_date.strftime('%Y-%m-%d') if self.rfq.created_date else 'N/A'}"))
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Tab widget
        self.tabs = QTabWidget()

        # BOM tab (Parts)
        self.bom_tab = self._create_bom_tab()
        self.tabs.addTab(self.bom_tab, "BOM (Parts)")

        # Tools tab
        self.tools_tab = self._create_tools_tab()
        self.tabs.addTab(self.tools_tab, "Tools")

        # Calculations tab
        self.calc_tab = self._create_calculations_tab()
        self.tabs.addTab(self.calc_tab, "Calculations")

        layout.addWidget(self.tabs)

        # Button bar
        button_layout = QHBoxLayout()

        btn_save = QPushButton("Save & Close")
        btn_save.clicked.connect(self.accept)
        button_layout.addWidget(btn_save)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        button_layout.addWidget(btn_close)

        layout.addLayout(button_layout)

    def _create_bom_tab(self) -> QWidget:
        """Create the BOM (Parts) tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Toolbar
        toolbar = QHBoxLayout()

        btn_add = QPushButton("Add Part")
        btn_add.clicked.connect(self._on_add_part)
        toolbar.addWidget(btn_add)

        # Edit Part button removed - use right-click context menu instead
        # btn_edit = QPushButton("Edit Part")
        # btn_edit.clicked.connect(self._on_edit_part)
        # toolbar.addWidget(btn_edit)

        btn_delete = QPushButton("Delete Part")
        btn_delete.clicked.connect(self._on_delete_part)
        toolbar.addWidget(btn_delete)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Parts table (V2.0: added Surface Finish and Status columns)
        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(16)
        self.parts_table.setHorizontalHeaderLabels([
            "Name", "Part#", "Image", "Material", "Weight (g)", "Volume (cm³)",
            "Proj. Area\n(cm²)", "Wall-\nthickness\n(mm)", "Surface\nFinish", "Total\nDemand", "Tool\nDefined",
            "Assembly\nDefined", "Over-\nmolding", "Status", "Notes"
        ])
        self.parts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.parts_table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        self.parts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.parts_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # Enable context menu for right-click
        self.parts_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.parts_table.customContextMenuRequested.connect(self._on_parts_context_menu)
        layout.addWidget(self.parts_table)

        return tab

    def _create_tools_tab(self) -> QWidget:
        """Create the Tools tab with father-child tree view."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Toolbar
        toolbar = QHBoxLayout()

        btn_add = QPushButton("Add Tool")
        btn_add.clicked.connect(self._on_add_tool)
        toolbar.addWidget(btn_add)

        btn_edit = QPushButton("Edit Tool")
        btn_edit.clicked.connect(self._on_edit_tool)
        toolbar.addWidget(btn_edit)

        btn_delete = QPushButton("Delete Tool")
        btn_delete.clicked.connect(self._on_delete_tool)
        toolbar.addWidget(btn_delete)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Info label
        info_label = QLabel("Father-Child View: Tools with assigned parts")
        info_label.setStyleSheet("font-size: 10pt; color: #666;")
        layout.addWidget(info_label)

        # Tools tree view (father-child)
        self.tools_tree = QTreeWidget()
        self.tools_tree.setColumnCount(9)
        self.tools_tree.setHeaderLabels([
            "Tool / Part", "Qty\n(Cav)", "Lifters", "Sliders", "Injection\nPoints",
            "Clamping\n(kN)", "Machine", "Notes"
        ])
        self.tools_tree.setColumnWidth(0, 250)
        self.tools_tree.setColumnWidth(1, 60)
        self.tools_tree.setColumnWidth(2, 70)
        self.tools_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tools_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tools_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tools_tree.itemSelectionChanged.connect(self._on_tool_selected)
        self.tools_tree.clicked.connect(self._on_tree_item_clicked)  # Click handler for images
        layout.addWidget(self.tools_tree)

        return tab

    def _create_calculations_tab(self) -> QWidget:
        """Create the Calculations summary tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Summary info
        self.calc_info = QLabel()
        self.calc_info.setWordWrap(True)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.calc_info)
        layout.addWidget(scroll)

        return tab

    def _refresh_data(self):
        """Refresh all data displays."""
        self._load_parts_table()
        self._load_tools_table()
        self._update_calculations()

    def _load_parts_table(self):
        """Load parts into BOM table with tool assignment status and color coding (V2.0)."""
        from ui.color_coding import get_missing_fields, get_source_color, apply_source_color_to_table_item

        with session_scope() as session:
            rfq = session.query(RFQ).get(self.rfq_id)
            if not rfq:
                return

            parts = rfq.parts
            self.parts_table.setRowCount(len(parts))

            for row, part in enumerate(parts):
                # Check completeness for row coloring
                missing = get_missing_fields(part)
                is_complete = len(missing) == 0

                # Name
                name_item = QTableWidgetItem(part.name)
                if not is_complete:
                    name_item.setForeground(QColor("#FF5050"))  # Red text for incomplete
                self.parts_table.setItem(row, 0, name_item)

                # Part#
                part_num_item = QTableWidgetItem(part.part_number or "-")
                if not is_complete:
                    part_num_item.setForeground(QColor("#FF5050"))
                self.parts_table.setItem(row, 1, part_num_item)

                # Image (placeholder)
                if part.image_binary:
                    img_label = QLabel()
                    pixmap = QPixmap()
                    pixmap.loadFromData(part.image_binary)
                    scaled = pixmap.scaledToHeight(40, Qt.TransformationMode.SmoothTransformation)
                    img_label.setPixmap(scaled)
                    self.parts_table.setCellWidget(row, 2, img_label)
                else:
                    img_item = QTableWidgetItem("-")
                    if not is_complete:
                        img_item.setForeground(QColor("#FF5050"))
                    self.parts_table.setItem(row, 2, img_item)

                # Material
                mat_name = part.material.short_name if part.material else "-"
                mat_item = QTableWidgetItem(mat_name)
                if not is_complete:
                    mat_item.setForeground(QColor("#FF5050"))
                self.parts_table.setItem(row, 3, mat_item)

                # Weight
                weight_item = QTableWidgetItem(f"{part.weight_g:.1f}" if part.weight_g else "-")
                if not is_complete:
                    weight_item.setForeground(QColor("#FF5050"))
                self.parts_table.setItem(row, 4, weight_item)

                # Volume
                volume_item = QTableWidgetItem(f"{part.volume_cm3:.1f}" if part.volume_cm3 else "-")
                if not is_complete:
                    volume_item.setForeground(QColor("#FF5050"))
                self.parts_table.setItem(row, 5, volume_item)

                # Projected Area (with source color coding)
                proj_area_item = QTableWidgetItem(f"{part.projected_area_cm2:.1f}" if part.projected_area_cm2 else "-")
                if not is_complete:
                    proj_area_item.setForeground(QColor("#FF5050"))
                # Apply source color
                if part.projected_area_cm2 and hasattr(part, 'projected_area_source') and part.projected_area_source:
                    apply_source_color_to_table_item(proj_area_item, part.projected_area_source)
                self.parts_table.setItem(row, 6, proj_area_item)

                # Wall Thickness (with source color coding)
                wall_thick_item = QTableWidgetItem(f"{part.wall_thickness_mm:.2f}" if part.wall_thickness_mm else "-")
                if not is_complete:
                    wall_thick_item.setForeground(QColor("#FF5050"))
                # Apply source color
                if part.wall_thickness_mm and hasattr(part, 'wall_thickness_source') and part.wall_thickness_source:
                    apply_source_color_to_table_item(wall_thick_item, part.wall_thickness_source)
                self.parts_table.setItem(row, 7, wall_thick_item)

                # Surface Finish (V2.0)
                surface_finish_text = "-"
                if part.surface_finish:
                    surface_finish_text = part.surface_finish.replace("_", " ").title()
                    if hasattr(part, 'surface_finish_detail') and part.surface_finish_detail:
                        surface_finish_text += f" ({part.surface_finish_detail})"
                sf_item = QTableWidgetItem(surface_finish_text)
                if not is_complete:
                    sf_item.setForeground(QColor("#FF5050"))
                # Apply yellow if estimated
                if hasattr(part, 'surface_finish_estimated') and part.surface_finish_estimated:
                    apply_source_color_to_table_item(sf_item, "estimated")
                self.parts_table.setItem(row, 8, sf_item)

                # Total Demand
                demand_item = QTableWidgetItem(str(part.parts_over_runtime or "-"))
                if not is_complete:
                    demand_item.setForeground(QColor("#FF5050"))
                self.parts_table.setItem(row, 9, demand_item)

                # Tool assignment info
                tool_configs = session.query(ToolPartConfiguration).filter(
                    ToolPartConfiguration.part_id == part.id
                ).all()

                if tool_configs:
                    # Get tool names for this part
                    tools_assigned = set()
                    for pc in tool_configs:
                        tool = session.query(Tool).get(pc.tool_id)
                        if tool:
                            tools_assigned.add(tool.name)

                    tool_names = ", ".join(sorted(tools_assigned))
                    tool_item = QTableWidgetItem(tool_names[:50])  # Tool name(s)
                    if not is_complete:
                        tool_item.setForeground(QColor("#FF5050"))
                    self.parts_table.setItem(row, 10, tool_item)
                else:
                    tool_item = QTableWidgetItem("-")  # No tool assigned
                    if not is_complete:
                        tool_item.setForeground(QColor("#FF5050"))
                    self.parts_table.setItem(row, 10, tool_item)

                # Assembly Defined (grey out if assembly not required)
                if part.assembly:
                    asm_item = QTableWidgetItem("✓ Assembly")
                    self.parts_table.setItem(row, 11, asm_item)
                else:
                    asm_item = QTableWidgetItem("-")
                    asm_item.setForeground(QColor("#999999"))  # Grey out
                    self.parts_table.setItem(row, 11, asm_item)

                # Overmolding (grey out if not required)
                if part.overmold:
                    over_item = QTableWidgetItem("✓ Overmold")
                    self.parts_table.setItem(row, 12, over_item)
                else:
                    over_item = QTableWidgetItem("-")
                    over_item.setForeground(QColor("#999999"))  # Grey out
                    self.parts_table.setItem(row, 12, over_item)

                # Status (V2.0)
                if is_complete:
                    status_item = QTableWidgetItem("✓ Complete")
                    status_item.setForeground(QColor("#70AD47"))  # Green
                else:
                    missing_text = ", ".join(missing)
                    status_item = QTableWidgetItem(f"Missing: {missing_text}")
                    status_item.setForeground(QColor("#FF5050"))  # Red
                self.parts_table.setItem(row, 13, status_item)

                # Notes
                notes = (part.notes or "")[:30] + ("..." if part.notes and len(part.notes) > 30 else "")
                notes_item = QTableWidgetItem(notes)
                if not is_complete:
                    notes_item.setForeground(QColor("#FF5050"))
                self.parts_table.setItem(row, 14, notes_item)

    def _format_cavities_display(self, tool: Tool) -> str:
        """Format cavities display as 'cav1/cav2/...' and check for imbalance."""
        if not tool.part_configurations:
            return "-"

        cavities_list = [str(pc.cavities) for pc in tool.part_configurations]
        cav_display = "/".join(cavities_list)

        # Check for cavity imbalance (sanity check)
        imbalance_warning = self._check_cavity_imbalance(tool)
        if imbalance_warning:
            cav_display += " ⚠️"  # Add warning icon

        return cav_display

    def _check_cavity_imbalance(self, tool: Tool) -> bool:
        """Check if cavity distribution creates >1% imbalance in production.

        Returns True if tool needs cavity shutoff capability.
        """
        if not tool.part_configurations or len(tool.part_configurations) < 2:
            return False

        # Get part demand data
        with session_scope() as session:
            demands = []
            for pc in tool.part_configurations:
                part = session.query(Part).get(pc.part_id)
                if part and part.parts_over_runtime:
                    annual_demand = part.parts_over_runtime
                    cavities = pc.cavities
                    # Shots per cavity per year
                    shots_per_cavity = annual_demand / cavities
                    demands.append(shots_per_cavity)

            if len(demands) < 2:
                return False

            # Calculate imbalance: difference between min and max as percentage
            min_demand = min(demands)
            max_demand = max(demands)

            if min_demand == 0:
                return False

            imbalance_percent = ((max_demand - min_demand) / min_demand) * 100

            return imbalance_percent > 1.0

    def _get_imbalance_message(self, tool: Tool) -> str:
        """Get tooltip message with imbalance details."""
        if not tool.part_configurations or len(tool.part_configurations) < 2:
            return ""

        with session_scope() as session:
            demands = {}  # part_name: shots_per_cavity
            for pc in tool.part_configurations:
                part = session.query(Part).get(pc.part_id)
                if part and part.parts_over_runtime:
                    annual_demand = part.parts_over_runtime
                    cavities = pc.cavities
                    shots_per_cavity = annual_demand / cavities
                    demands[part.name] = shots_per_cavity

            if len(demands) < 2:
                return ""

            min_demand = min(demands.values())
            max_demand = max(demands.values())

            if min_demand == 0:
                return ""

            imbalance_percent = ((max_demand - min_demand) / min_demand) * 100

            if imbalance_percent > 1.0:
                msg = f"⚠️ CAVITY IMBALANCE DETECTED ({imbalance_percent:.1f}%)\n"
                msg += "This tool needs cavity shutoff capability\n\n"
                msg += "Shots per cavity per year:\n"
                for part_name in sorted(demands.keys()):
                    msg += f"  {part_name}: {demands[part_name]:.0f}\n"
                return msg

            return ""

    def _load_tools_table(self):
        """Load tools into tree view with father-child structure."""
        self.tools_tree.clear()

        with session_scope() as session:
            tools = session.query(Tool).all()  # Get all tools for this RFQ

            for tool in tools:
                # Create parent item for tool (father)
                parts_count = len(tool.part_configurations) if tool.part_configurations else 0
                total_cav = tool.get_total_cavities()

                # Format cavities as "cav1/cav2/..." for parts
                cav_display = self._format_cavities_display(tool)

                tool_item = QTreeWidgetItem()
                tool_item.setText(0, f"🔧 {tool.name}")
                tool_item.setText(1, cav_display)  # Cavities display format
                tool_item.setText(2, str(tool.get_total_lifters()))  # Total lifters
                tool_item.setText(3, str(tool.get_total_sliders()))  # Total sliders
                tool_item.setText(4, str(tool.injection_points) if tool.injection_points else "-")  # Injection points
                tool_item.setText(5, f"{tool.estimated_clamping_force_kn:.0f}" if tool.estimated_clamping_force_kn else "-")
                tool_item.setText(6, tool.machine.name if tool.machine else "-")
                tool_item.setText(7, (tool.notes or "")[:40])

                # Set tool ID as user data for selection handling
                tool_item.setData(0, Qt.ItemDataRole.UserRole, tool.id)

                # Add tooltip with cavity imbalance info if needed
                imbalance_msg = self._get_imbalance_message(tool)
                if imbalance_msg:
                    tool_item.setToolTip(0, imbalance_msg)

                # Bold font for tool (parent) items
                font = tool_item.font(0)
                font.setBold(True)
                tool_item.setFont(0, font)

                # Add child items (parts assigned to this tool)
                if tool.part_configurations:
                    for pc in tool.part_configurations:
                        if pc.part:
                            part_item = QTreeWidgetItem(tool_item)
                            part_name = f"├─ {pc.part.name}"
                            part_item.setText(0, part_name)
                            part_item.setText(1, str(pc.cavities))  # Cavities for this part (Qty)
                            part_item.setText(2, str(pc.lifters_count))  # Lifters for this part
                            part_item.setText(3, str(pc.sliders_count))  # Sliders for this part
                            part_item.setText(4, "-")  # Injection points (per tool, not per part)

                            # Add part image as icon if available
                            if pc.part.image_binary:
                                pixmap = QPixmap()
                                pixmap.loadFromData(pc.part.image_binary)
                                scaled_pixmap = pixmap.scaledToHeight(30, Qt.TransformationMode.SmoothTransformation)
                                part_item.setIcon(0, QIcon(scaled_pixmap))

                            # Set part ID and config ID as user data
                            part_item.setData(0, Qt.ItemDataRole.UserRole, pc.id)
                            part_item.setData(0, Qt.ItemDataRole.UserRole + 1, "part_config")

                self.tools_tree.addTopLevelItem(tool_item)

    def _update_calculations(self):
        """Update calculations summary."""
        summary = "<b>Calculation Summary</b><br>"
        summary += f"RFQ: {self.rfq.name}<br>"

        with session_scope() as session:
            rfq = session.query(RFQ).get(self.rfq_id)
            if rfq:
                summary += f"Parts: {len(rfq.parts)}<br>"
                summary += f"SOP Demand: {rfq.demand_sop or 'Not set'} pcs/year<br>"
                summary += f"EAOP Demand: {rfq.demand_eaop or 'Not set'} pcs/year<br>"

        self.calc_info.setText(summary)

    def _on_add_part(self):
        """Add part to RFQ."""
        dialog = PartDialog(self, rfq_id=self.rfq_id)
        if dialog.exec():
            self._refresh_data()
            self.statusBar().showMessage("Part added successfully")

    def _on_edit_part(self):
        """Edit selected part."""
        selected = self.parts_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a part to edit")
            return

        part_name = self.parts_table.item(selected[0].row(), 0).text()
        with session_scope() as session:
            part = session.query(Part).filter(
                Part.rfq_id == self.rfq_id,
                Part.name == part_name
            ).first()
            if part:
                part_id = part.id

        dialog = PartDialog(self, rfq_id=self.rfq_id, part_id=part_id)
        if dialog.exec():
            self._refresh_data()
            self.statusBar().showMessage("Part updated successfully")

    def _on_parts_context_menu(self, position):
        """Show context menu for parts table."""
        from PyQt6.QtWidgets import QMenu

        item = self.parts_table.itemAt(position)
        if not item:
            return

        menu = QMenu()
        edit_action = menu.addAction("Edit Part")
        menu.addSeparator()
        delete_action = menu.addAction("Delete Part")

        action = menu.exec(self.parts_table.mapToGlobal(position))

        if action == edit_action:
            # Select the row and call edit
            self.parts_table.selectRow(item.row())
            self._on_edit_part()
        elif action == delete_action:
            # Select the row and call delete
            self.parts_table.selectRow(item.row())
            self._on_delete_part()

    def _on_delete_part(self):
        """Delete selected part."""
        selected = self.parts_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a part to delete")
            return

        part_name = self.parts_table.item(selected[0].row(), 0).text()
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete part '{part_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with session_scope() as session:
                part = session.query(Part).filter(
                    Part.rfq_id == self.rfq_id,
                    Part.name == part_name
                ).first()
                if part:
                    session.delete(part)
            self._refresh_data()

    def _on_add_tool(self):
        """Add tool to RFQ."""
        dialog = ToolDialog(self, rfq_id=self.rfq_id)
        if dialog.exec():
            self._refresh_data()
            self.statusBar().showMessage("Tool added successfully")

    def _on_tool_selected(self):
        """Handle tool/part selection in tree."""
        selected = self.tools_tree.selectedItems()
        if selected:
            self._selected_tool_item = selected[0]

    def _on_tree_item_clicked(self, index):
        """Handle click on tree items (to show image zoom for parts when clicking image icon)."""
        item = self.tools_tree.itemFromIndex(index)
        if not item or not item.parent():  # Only handle child items (parts)
            return

        # Only trigger image zoom if clicking on column 0 (image icon)
        if index.column() != 0:
            return

        # Check if item has part configuration data
        part_config_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not part_config_id:
            return

        # Get the part image data
        with session_scope() as session:
            part_config = session.query(ToolPartConfiguration).get(part_config_id)
            if part_config and part_config.part and part_config.part.image_binary:
                show_image_preview(
                    self,
                    f"Part Image: {part_config.part.name}",
                    part_config.part.image_binary
                )

    def _get_selected_tool_id(self) -> int:
        """Get ID of selected tool (parent item)."""
        selected = self.tools_tree.selectedItems()
        if not selected:
            return None

        item = selected[0]

        # If it's a child item (part), get parent
        if item.parent():
            item = item.parent()

        return item.data(0, Qt.ItemDataRole.UserRole)

    def _on_edit_tool(self):
        """Edit selected tool."""
        tool_id = self._get_selected_tool_id()
        if tool_id is None:
            QMessageBox.warning(self, "No Selection", "Please select a tool to edit")
            return

        dialog = ToolDialog(self, rfq_id=self.rfq_id, tool_id=tool_id)
        if dialog.exec():
            self._refresh_data()
            self.statusBar().showMessage("Tool updated successfully")

    def _on_delete_tool(self):
        """Delete selected tool."""
        tool_id = self._get_selected_tool_id()
        if tool_id is None:
            QMessageBox.warning(self, "No Selection", "Please select a tool to delete")
            return

        with session_scope() as session:
            tool = session.query(Tool).get(tool_id)
            if not tool:
                QMessageBox.warning(self, "Error", "Tool not found")
                return

            tool_name = tool.name

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete tool '{tool_name}'? This will also delete all part configurations.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with session_scope() as session:
                tool = session.query(Tool).get(tool_id)
                if tool:
                    session.delete(tool)
            self._refresh_data()
            self.statusBar().showMessage(f"Deleted tool: {tool_name}")

    def accept(self):
        """Save and close."""
        # Save any changes
        super().accept()

    def reject(self):
        """Close without saving."""
        super().reject()
