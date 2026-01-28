"""Dedicated window for RFQ detail editing (parts, tools, calculations)."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QMessageBox, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QScrollArea, QFrame, QSpinBox,
    QTreeWidget, QTreeWidgetItem, QCheckBox, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QMimeData, QByteArray, QPoint, QSize
from PyQt6.QtGui import QPixmap, QIcon, QColor, QDrag

from database.connection import session_scope
from database.models import RFQ, Part, Tool, Material, Machine, ToolPartConfiguration, AssemblyComponent, AssemblyProcessStep
from database import JoinMethod, ProcessStepType
from .dialogs.part_dialog import PartDialog
from .dialogs.tool_dialog import ToolDialog
from .widgets.image_preview import show_image_preview


class DraggableIMPartsTable(QTableWidget):
    """QTableWidget subclass that allows dragging IM parts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def startDrag(self, supportedActions):
        """Start drag operation when user drags from this table."""
        item = self.itemAt(self.mapFromGlobal(self.cursor().pos()))
        if not item:
            return

        # Only drag from name column (column 0)
        if item.column() != 0:
            return

        part_id = item.data(Qt.ItemDataRole.UserRole)
        if not part_id:
            return

        mime_data = QMimeData()
        mime_data.setText(str(part_id))
        mime_data.setData("application/x-part-id", str(part_id).encode())

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.CopyAction)


class DroppableAssemblyBOMTree(QTreeWidget):
    """QTreeWidget subclass for Master BOM."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rfq_window = None  # Reference to RFQDetailWindow for keyboard shortcuts

    def set_rfq_window(self, window):
        """Set reference to main window for keyboard shortcut handling."""
        self.rfq_window = window

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts: Ctrl+C (copy), Ctrl+X (cut), Ctrl+V (paste)."""
        if not self.rfq_window:
            super().keyPressEvent(event)
            return

        # Check if Ctrl is held (bitwise AND with ControlModifier flag)
        ctrl_held = event.modifiers() & Qt.KeyboardModifier.ControlModifier

        if not ctrl_held:
            super().keyPressEvent(event)
            return

        # Handle Ctrl+C (copy), Ctrl+X (cut), Ctrl+V (paste)
        key = event.key()

        if key == Qt.Key.Key_C:
            self._handle_copy_shortcut()
            event.accept()
            return
        elif key == Qt.Key.Key_X:
            self._handle_cut_shortcut()
            event.accept()
            return
        elif key == Qt.Key.Key_V:
            self._handle_paste_shortcut()
            event.accept()
            return

        # For any other key, use default behavior
        super().keyPressEvent(event)

    def _handle_copy_shortcut(self):
        """Handle Ctrl+C to copy component."""
        selected = self.selectedItems()
        if not selected:
            self.rfq_window.statusBar().showMessage("No component selected")
            return

        item = selected[0]
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)

        # Only allow copy for components
        if item_type and item_type.startswith("component_"):
            self.rfq_window._on_copy_component(item_id)
        else:
            self.rfq_window.statusBar().showMessage("Select a component to copy")

    def _handle_cut_shortcut(self):
        """Handle Ctrl+X to cut component."""
        selected = self.selectedItems()
        if not selected:
            self.rfq_window.statusBar().showMessage("No component selected")
            return

        item = selected[0]
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)

        # Only allow cut for components
        if item_type and item_type.startswith("component_"):
            self.rfq_window._on_cut_component(item_id)
        else:
            self.rfq_window.statusBar().showMessage("Select a component to cut")

    def _handle_paste_shortcut(self):
        """Handle Ctrl+V to paste component."""
        selected = self.selectedItems()
        if not selected:
            self.rfq_window.statusBar().showMessage("No IM component selected to paste under")
            return

        item = selected[0]
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)

        # Paste on IM component for cut/paste
        if item_type == "component_im":
            if hasattr(self.rfq_window, 'cut_component') and self.rfq_window.cut_component:
                self.rfq_window._on_paste_component_in_assembly(item_id)
            elif hasattr(self.rfq_window, 'copied_component') and self.rfq_window.copied_component:
                self.rfq_window._on_paste_copied_component_in_assembly(item_id)
            else:
                self.rfq_window.statusBar().showMessage("No component copied or cut")
        else:
            self.rfq_window.statusBar().showMessage("Select an IM component to paste under")


class DroppableAssemblyLinesTree(QTreeWidget):
    """QTreeWidget subclass for Assembly Lines that accepts dropped IM parts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDropIndicatorShown(True)
        self.setAcceptDrops(True)
        self.rfq_window = None  # Reference to RFQDetailWindow for keyboard shortcuts

    def set_rfq_window(self, window):
        """Set reference to main window for keyboard shortcut handling."""
        self.rfq_window = window

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts: Ctrl+C (copy), Ctrl+X (cut), Ctrl+V (paste)."""
        if not self.rfq_window:
            super().keyPressEvent(event)
            return

        # Check if Ctrl is held (bitwise AND with ControlModifier flag)
        ctrl_held = event.modifiers() & Qt.KeyboardModifier.ControlModifier

        if not ctrl_held:
            super().keyPressEvent(event)
            return

        # Handle Ctrl+C (copy), Ctrl+X (cut), Ctrl+V (paste)
        key = event.key()

        if key == Qt.Key.Key_C:
            self._handle_copy_shortcut()
            event.accept()
            return
        elif key == Qt.Key.Key_X:
            self._handle_cut_shortcut()
            event.accept()
            return
        elif key == Qt.Key.Key_V:
            self._handle_paste_shortcut()
            event.accept()
            return

        # For any other key, use default behavior
        super().keyPressEvent(event)

    def _handle_copy_shortcut(self):
        """Handle Ctrl+C to copy component."""
        selected = self.selectedItems()
        if not selected:
            self.rfq_window.statusBar().showMessage("No component selected")
            return

        item = selected[0]
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)

        # Only allow copy for components
        if item_type and item_type.startswith("component_"):
            self.rfq_window._on_copy_component(item_id)
        else:
            self.rfq_window.statusBar().showMessage("Select a component to copy")

    def _handle_cut_shortcut(self):
        """Handle Ctrl+X to cut component."""
        selected = self.selectedItems()
        if not selected:
            self.rfq_window.statusBar().showMessage("No component selected")
            return

        item = selected[0]
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)

        # Only allow cut for components
        if item_type and item_type.startswith("component_"):
            self.rfq_window._on_cut_component(item_id)
        else:
            self.rfq_window.statusBar().showMessage("Select a component to cut")

    def _handle_paste_shortcut(self):
        """Handle Ctrl+V to paste component."""
        selected = self.selectedItems()
        if not selected:
            self.rfq_window.statusBar().showMessage("No IM component selected to paste under")
            return

        item = selected[0]
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)

        # Paste on IM component for cut/paste
        if item_type == "component_im":
            if hasattr(self.rfq_window, 'cut_component') and self.rfq_window.cut_component:
                self.rfq_window._on_paste_component_in_assembly(item_id)
            elif hasattr(self.rfq_window, 'copied_component') and self.rfq_window.copied_component:
                self.rfq_window._on_paste_copied_component_in_assembly(item_id)
            else:
                self.rfq_window.statusBar().showMessage("No component copied or cut")
        else:
            self.rfq_window.statusBar().showMessage("Select an IM component to paste under")

    def dragEnterEvent(self, event):
        """Accept drag if MIME data contains part ID."""
        if event.mimeData().hasFormat("application/x-part-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Show drop indicator only on assembly items."""
        pos = event.position().toPoint()
        item = self.itemAt(pos)
        if item and item.data(0, Qt.ItemDataRole.UserRole + 1) == "assembly":
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle drop of IM part onto assembly."""
        if not event.mimeData().hasFormat("application/x-part-id"):
            event.ignore()
            return

        pos = event.position().toPoint()
        item = self.itemAt(pos)
        if not item:
            event.ignore()
            return

        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if item_type != "assembly":
            event.ignore()
            return

        assembly_id = item.data(0, Qt.ItemDataRole.UserRole)
        part_id_str = event.mimeData().data("application/x-part-id").decode()
        try:
            part_id = int(part_id_str)
        except (ValueError, AttributeError):
            event.ignore()
            return

        event.acceptProposedAction()

        # Call handler to add component
        parent_window = self
        while parent_window and not hasattr(parent_window, '_on_drop_part_on_assembly'):
            parent_window = parent_window.parent()

        if parent_window and hasattr(parent_window, '_on_drop_part_on_assembly'):
            parent_window._on_drop_part_on_assembly(assembly_id, part_id)


class RFQDetailWindow(QMainWindow):
    """Dedicated window for editing a single RFQ with parts and tools."""

    def __init__(self, rfq_id: int, parent=None):
        super().__init__(parent)
        self.rfq_id = rfq_id
        self.rfq = None
        self.copied_component = None  # For copy/paste functionality
        self.cut_component = None  # For cut/paste functionality (components can be moved)

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

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        button_layout.addWidget(btn_close)

        layout.addLayout(button_layout)

    def _create_bom_tab(self) -> QWidget:
        """Create the BOM (Parts) tab with three sub-views."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Toolbar (shared across all sub-tabs)
        toolbar = QHBoxLayout()

        btn_add = QPushButton("Add Part")
        btn_add.clicked.connect(self._on_add_part)
        toolbar.addWidget(btn_add)

        toolbar.addSpacing(10)

        # Toggle expand/collapse all button
        self.btn_expand_toggle = QPushButton("Collapse All")
        self.btn_expand_toggle.clicked.connect(self._on_toggle_expand_all)
        self.btn_expand_toggle.setMaximumWidth(100)
        toolbar.addWidget(self.btn_expand_toggle)

        # Track auto-expand state: True = all expanded, False = manually set
        self.tree_auto_expanded = True
        # Flag to prevent signal handlers from interfering with programmatic changes
        self.programmatically_changing = False

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Sub-tabs for three views
        self.bom_sub_tabs = QTabWidget()

        # Tab 1: Master BOM
        master_tab = QWidget()
        master_layout = QVBoxLayout(master_tab)
        self.parts_tree = DroppableAssemblyBOMTree()
        self.parts_tree.set_rfq_window(self)
        self.parts_tree.setColumnCount(8)
        self.parts_tree.setHeaderLabels([
            "Name", "Image", "Part#", "Type", "Material", "Qty", "Join Method", "Status"
        ])
        self.parts_tree.setColumnWidth(0, 250)
        self.parts_tree.setColumnWidth(1, 50)
        self.parts_tree.setColumnWidth(2, 80)
        self.parts_tree.setColumnWidth(3, 100)
        self.parts_tree.setColumnWidth(4, 100)
        self.parts_tree.setColumnWidth(5, 60)
        self.parts_tree.setColumnWidth(6, 120)
        self.parts_tree.setColumnWidth(7, 80)
        self.parts_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.parts_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.parts_tree.setUniformRowHeights(False)  # Allow variable row heights for process steps
        # Increase row height for better image visibility via stylesheet
        self.parts_tree.setStyleSheet("QTreeWidget::item { height: 50px; }")
        self.parts_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.parts_tree.customContextMenuRequested.connect(self._on_parts_context_menu)
        self.parts_tree.doubleClicked.connect(self._on_tree_item_double_clicked)
        self.parts_tree.clicked.connect(self._on_tree_item_clicked)
        self.parts_tree.expanded.connect(self._on_item_manually_expanded)
        self.parts_tree.collapsed.connect(self._on_item_manually_collapsed)
        master_layout.addWidget(self.parts_tree)
        self.bom_sub_tabs.addTab(master_tab, "Master BOM")

        # Tab 2: IM Parts (flat table for tooling engineer)
        im_tab = QWidget()
        im_layout = QVBoxLayout(im_tab)
        self.im_parts_table = DraggableIMPartsTable()
        self.im_parts_table.setColumnCount(10)
        self.im_parts_table.setHorizontalHeaderLabels([
            "Name", "Part#", "Material", "Weight (g)", "Volume (cm\u00b3)",
            "Proj.Area (cm\u00b2)", "Wall (mm)", "Peak Demand", "Total Usage", "Status"
        ])
        self.im_parts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.im_parts_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.im_parts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.im_parts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.im_parts_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.im_parts_table.customContextMenuRequested.connect(self._on_im_parts_context_menu)
        self.im_parts_table.doubleClicked.connect(self._on_im_parts_double_clicked)
        im_layout.addWidget(self.im_parts_table)
        self.bom_sub_tabs.addTab(im_tab, "IM Parts")

        # Tab 3: Assembly Lines (assembly-only tree for manufacturing engineer)
        asm_tab = QWidget()
        asm_layout = QVBoxLayout(asm_tab)

        self.assembly_tree = DroppableAssemblyLinesTree()
        self.assembly_tree.set_rfq_window(self)
        self.assembly_tree.setColumnCount(8)
        self.assembly_tree.setHeaderLabels([
            "Name", "Image", "Part#", "Type", "Material", "Qty", "Join Method", "Status"
        ])
        self.assembly_tree.setColumnWidth(0, 250)
        self.assembly_tree.setColumnWidth(1, 50)
        self.assembly_tree.setColumnWidth(2, 80)
        self.assembly_tree.setColumnWidth(3, 100)
        self.assembly_tree.setColumnWidth(4, 100)
        self.assembly_tree.setColumnWidth(5, 60)
        self.assembly_tree.setColumnWidth(6, 120)
        self.assembly_tree.setColumnWidth(7, 80)
        self.assembly_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.assembly_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # Increase row height for image visibility via stylesheet
        self.assembly_tree.setStyleSheet("QTreeWidget::item { height: 50px; }")
        self.assembly_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.assembly_tree.customContextMenuRequested.connect(self._on_assembly_tree_context_menu)
        self.assembly_tree.doubleClicked.connect(self._on_assembly_tree_double_clicked)
        self.assembly_tree.clicked.connect(self._on_assembly_tree_clicked)
        self.assembly_tree.expanded.connect(self._on_item_manually_expanded)
        self.assembly_tree.collapsed.connect(self._on_item_manually_collapsed)
        self.asm_no_data_label = QLabel("No assemblies defined. Create assemblies in the Master BOM tab.")
        self.asm_no_data_label.setStyleSheet("font-size: 11pt; color: #888; padding: 20px;")
        self.asm_no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.asm_no_data_label.setVisible(False)
        asm_layout.addWidget(self.asm_no_data_label)
        asm_layout.addWidget(self.assembly_tree)
        self.bom_sub_tabs.addTab(asm_tab, "Assembly Lines")

        # Tab 4: Parts Summary (total quantities across assemblies)
        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        self.parts_summary_table = QTableWidget()
        self.parts_summary_table.setColumnCount(4)
        self.parts_summary_table.setHorizontalHeaderLabels([
            "Name", "Part#", "Type", "Total Quantity"
        ])
        self.parts_summary_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.parts_summary_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.parts_summary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.parts_summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.parts_summary_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.parts_summary_table.customContextMenuRequested.connect(self._on_im_parts_context_menu)
        self.parts_summary_table.doubleClicked.connect(self._on_im_parts_double_clicked)
        summary_layout.addWidget(self.parts_summary_table)
        self.bom_sub_tabs.addTab(summary_tab, "Parts Summary")

        layout.addWidget(self.bom_sub_tabs)
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
        # Save expanded state before refreshing (only in manual mode)
        expanded_state = None
        if not self.tree_auto_expanded:
            expanded_state = self._save_tree_expanded_state(self.parts_tree)

        self._load_parts_tree()

        # Restore or auto-expand based on mode
        if self.tree_auto_expanded:
            self._expand_all_items(self.parts_tree)
        elif expanded_state:
            self._restore_tree_expanded_state(self.parts_tree, expanded_state)

        self._load_im_parts_table()
        self._load_parts_summary_table()

        # Save and restore Assembly Lines tree state (also respects auto-expand mode)
        expanded_state_asm = None
        if not self.tree_auto_expanded:
            expanded_state_asm = self._save_tree_expanded_state(self.assembly_tree)

        self._load_assembly_tree()

        if self.tree_auto_expanded:
            self._expand_all_items(self.assembly_tree)
        elif expanded_state_asm:
            self._restore_tree_expanded_state(self.assembly_tree, expanded_state_asm)

        self._load_tools_table()
        self._update_calculations()

    def _save_tree_expanded_state(self, tree):
        """Save which items are expanded in the tree."""
        expanded = set()
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            self._collect_expanded_items(item, expanded)
        return expanded

    def _collect_expanded_items(self, item, expanded_set):
        """Recursively collect IDs of expanded items."""
        if item.isExpanded():
            item_id = item.data(0, Qt.ItemDataRole.UserRole)
            item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if item_id:
                expanded_set.add((item_id, item_type))
        for i in range(item.childCount()):
            self._collect_expanded_items(item.child(i), expanded_set)

    def _restore_tree_expanded_state(self, tree, expanded_set):
        """Restore expanded state of items in tree."""
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            self._restore_expanded_items(item, expanded_set)

    def _restore_expanded_items(self, item, expanded_set):
        """Recursively restore expanded state."""
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if item_id and (item_id, item_type) in expanded_set:
            item.setExpanded(True)
        for i in range(item.childCount()):
            self._restore_expanded_items(item.child(i), expanded_set)

    def _expand_all_items(self, tree):
        """Recursively expand all items in tree."""
        self.programmatically_changing = True
        try:
            for i in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(i)
                self._expand_item_recursive(item)
        finally:
            self.programmatically_changing = False

    def _expand_item_recursive(self, item):
        """Recursively expand an item and all children."""
        item.setExpanded(True)
        for i in range(item.childCount()):
            self._expand_item_recursive(item.child(i))

    def _collapse_all_items(self, tree):
        """Recursively collapse all items in tree."""
        self.programmatically_changing = True
        try:
            for i in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(i)
                self._collapse_item_recursive(item)
        finally:
            self.programmatically_changing = False

    def _collapse_item_recursive(self, item):
        """Recursively collapse an item and all children."""
        item.setExpanded(False)
        for i in range(item.childCount()):
            self._collapse_item_recursive(item.child(i))

    def _on_item_manually_expanded(self):
        """Handle manual expansion of an item."""
        # Ignore if this is a programmatic change
        if self.programmatically_changing:
            return

        if self.tree_auto_expanded:
            # Switch to manual mode
            self.tree_auto_expanded = False
            self.btn_expand_toggle.setText("Expand All")

    def _on_item_manually_collapsed(self):
        """Handle manual collapse of an item."""
        # Ignore if this is a programmatic change
        if self.programmatically_changing:
            return

        if self.tree_auto_expanded:
            # Switch to manual mode
            self.tree_auto_expanded = False
            self.btn_expand_toggle.setText("Expand All")

    def _on_toggle_expand_all(self):
        """Toggle between expand all and collapse all."""
        self.tree_auto_expanded = not self.tree_auto_expanded

        if self.tree_auto_expanded:
            # Expand all
            self._expand_all_items(self.parts_tree)
            self._expand_all_items(self.assembly_tree)
            self.btn_expand_toggle.setText("Collapse All")
            self.statusBar().showMessage("Expanded all items - auto-expand enabled")
        else:
            # Collapse all
            self._collapse_all_items(self.parts_tree)
            self._collapse_all_items(self.assembly_tree)
            self.btn_expand_toggle.setText("Expand All")
            self.statusBar().showMessage("Collapsed all items - manual expand/collapse mode enabled")

    def _normalize_component_positions(self, assembly_id: int, session):
        """Fix only NULL/invalid positions. Preserve existing decimal position assignments.

        IM parts must have integer positions (1, 2, 3...).
        Components with positions like 1.1, 2.1 are preserved (assigned to those IM parts).
        Only NULL or clearly invalid (0, 0.5) positions are reassigned.
        """
        all_comps = session.query(AssemblyComponent).filter(
            AssemblyComponent.assembly_id == assembly_id
        ).all()

        # Separate: IM components and others
        im_comps = [c for c in all_comps if c.component_type == "injection_molded"]
        other_comps = [c for c in all_comps if c.component_type != "injection_molded"]

        # Step 1: Fix IM component positions (must be integers)
        im_with_pos = [c for c in im_comps if c.position and c.position > 0]
        im_without_pos = [c for c in im_comps if not c.position or c.position == 0]

        # If we have some positioned IM components, use them as a base
        if im_with_pos:
            # Find used integer positions
            used_positions = set(int(c.position) for c in im_with_pos)
            # Assign missing ones
            next_pos = 1
            for comp in im_without_pos:
                while next_pos in used_positions:
                    next_pos += 1
                comp.position = float(next_pos)
                used_positions.add(next_pos)
        else:
            # No positioned IM components, assign 1, 2, 3...
            for i, comp in enumerate(im_comps, start=1):
                comp.position = float(i)

        # Step 2: For other components, check if they have valid decimal positions
        # Valid decimal = (parent_int).1 to (parent_int).9
        for comp in other_comps:
            if comp.position and comp.position > 0.1:
                # Has a decimal position - check if parent IM exists
                parent_int = int(comp.position)
                parent_exists = any(c.position == float(parent_int) for c in all_comps if c.component_type == "injection_molded")
                if not parent_exists:
                    # Parent IM doesn't exist - reassign under last IM
                    comp.position = None

        # Step 3: Fix remaining NULL positions for other components
        other_without_pos = [c for c in other_comps if not c.position or c.position <= 0.1]
        if other_without_pos:
            if im_comps:
                # Assign under the last IM component
                last_im_pos = max(int(c.position) for c in im_comps if c.position)
                existing_decimals = [c.position for c in all_comps if c.position and int(c.position) == last_im_pos]
                next_decimal = max(existing_decimals) + 0.01 if existing_decimals else float(last_im_pos) + 0.1

                for comp in other_without_pos:
                    comp.position = next_decimal
                    next_decimal += 0.01
            else:
                # No IM components, assign to 0.1, 0.2, etc.
                for j, comp in enumerate(other_without_pos, start=1):
                    comp.position = 0.0 + (0.1 * j)

    def _load_parts_tree(self):
        """Load parts into BOM tree with assemblies and components."""
        from ui.color_coding import get_missing_fields

        self.parts_tree.clear()

        with session_scope() as session:
            rfq = session.query(RFQ).get(self.rfq_id)
            if not rfq:
                return

            parts = rfq.parts

            # Normalize positions for all assemblies (in case they have NULL or bad values)
            for part in parts:
                if part.part_type == "assembly":
                    self._normalize_component_positions(part.id, session)

            # Get IDs of all IM parts that are used as assembly components
            assembly_ids = [p.id for p in parts if p.part_type == "assembly"]
            assembly_part_ids = set()
            if assembly_ids:
                assembly_part_ids = set(
                    comp.component_part_id
                    for comp in session.query(AssemblyComponent)
                        .filter(AssemblyComponent.component_part_id.isnot(None))
                        .filter(AssemblyComponent.assembly_id.in_(assembly_ids))
                        .all()
                )

            for part in parts:
                if part.part_type == "assembly":
                    # Create assembly item (top-level, no background color, bold, no indent)
                    asm_item = QTreeWidgetItem()
                    asm_item.setText(0, f"🗂 {part.name}")  # Assembly icon

                    # Add image if available (column 1) - scale to match row height
                    if part.image_binary:
                        pixmap = QPixmap()
                        pixmap.loadFromData(part.image_binary)
                        scaled = pixmap.scaledToHeight(45, Qt.TransformationMode.SmoothTransformation)
                        asm_item.setIcon(1, QIcon(scaled))

                    asm_item.setText(2, part.part_number or "-")
                    asm_item.setText(3, "Assembly")
                    asm_item.setText(4, "-")
                    # Quantity field for assembly
                    asm_item.setText(5, str(part.demand_peak or 1))  # Use demand_peak as assembly quantity
                    asm_item.setText(6, "-")
                    asm_item.setText(7, "")

                    # Set user data for identification
                    asm_item.setData(0, Qt.ItemDataRole.UserRole, part.id)
                    asm_item.setData(0, Qt.ItemDataRole.UserRole + 1, "assembly")

                    # Apply styling: bold only, no background color
                    font = asm_item.font(0)
                    font.setBold(True)
                    for col in range(8):
                        asm_item.setFont(col, font)

                    # Add component children (indented), grouped under IM parts
                    if part.assembly_components:
                        # Sort by position to maintain order
                        sorted_comps = sorted(part.assembly_components, key=lambda c: c.position if c.position else 0)

                        # Build a mapping of integer positions to IM component tree items
                        im_position_to_item = {}

                        # First pass: add all IM components
                        for comp in sorted_comps:
                            if comp.component_type == "injection_molded":
                                child_item = QTreeWidgetItem(asm_item)
                                self._style_component_item(child_item, comp, session, apply_colors=False)
                                # Store the item by its integer position
                                if comp.position is not None:
                                    im_pos = int(comp.position)
                                    im_position_to_item[im_pos] = child_item

                        # Second pass: add purchased/takeover components under correct IM part
                        for comp in sorted_comps:
                            if comp.component_type != "injection_molded":
                                # Find which IM part this should be grouped under
                                # Components with position between X.0 and X.99... belong under IM part at position X
                                parent_item = None
                                if comp.position is not None:
                                    comp_pos = comp.position
                                    target_im_pos = int(comp_pos)
                                    parent_item = im_position_to_item.get(target_im_pos)

                                # Add as child of the correct IM part, or to assembly as fallback
                                if parent_item:
                                    child_item = QTreeWidgetItem(parent_item)
                                else:
                                    child_item = QTreeWidgetItem(asm_item)
                                self._style_component_item(child_item, comp, session, apply_colors=False)

                    self.parts_tree.addTopLevelItem(asm_item)
                    # Process steps MUST be added after asm_item is in the tree
                    self._add_process_steps_to_tree(self.parts_tree, asm_item, part, session)

                elif part.id not in assembly_part_ids:
                    # Only show as standalone if NOT used in any assembly
                    part_item = QTreeWidgetItem()
                    part_item.setText(0, f"📦 {part.name}")  # IM part icon, NO indentation - top level like assembly

                    # Add image if available (column 1) - scale to match row height
                    if part.image_binary:
                        pixmap = QPixmap()
                        pixmap.loadFromData(part.image_binary)
                        scaled = pixmap.scaledToHeight(45, Qt.TransformationMode.SmoothTransformation)
                        part_item.setIcon(1, QIcon(scaled))

                    part_item.setText(2, part.part_number or "-")
                    part_item.setText(3, "Standalone IM")  # Clearly mark as standalone
                    mat_name = part.material.short_name if part.material else "-"
                    part_item.setText(4, mat_name)
                    # Quantity for standalone part (use demand_peak)
                    part_item.setText(5, str(part.demand_peak or 1))
                    part_item.setText(6, "-")

                    # Check completeness for status
                    missing = get_missing_fields(part)
                    if len(missing) == 0:
                        part_item.setText(7, "✓ Complete")
                        part_item.setForeground(7, QColor("#70AD47"))
                    else:
                        part_item.setText(7, "⚠ Incomplete")
                        part_item.setForeground(7, QColor("#FF5050"))

                    # Set user data for identification
                    part_item.setData(0, Qt.ItemDataRole.UserRole, part.id)
                    part_item.setData(0, Qt.ItemDataRole.UserRole + 1, "im_part")

                    # Apply red text if incomplete
                    if len(missing) > 0:
                        part_item.setForeground(0, QColor("#FF5050"))

                    self.parts_tree.addTopLevelItem(part_item)

    def _style_component_item(self, item: QTreeWidgetItem, component: AssemblyComponent, session, apply_colors=False):
        """Style a component tree item based on type (IM, purchased, takeover).

        Args:
            apply_colors: If True, applies background colors. Set to False for Master BOM, True for Assembly tree.
        """
        from ui.color_coding import get_missing_fields

        if component.component_type == "injection_molded" and component.component_part:
            # IM part component - yellow, indented under assembly
            item.setText(0, f"    └─ {component.component_part.name}")

            # Add image if available - scale to match row height
            if component.component_part.image_binary:
                pixmap = QPixmap()
                pixmap.loadFromData(component.component_part.image_binary)
                scaled = pixmap.scaledToHeight(45, Qt.TransformationMode.SmoothTransformation)
                item.setIcon(1, QIcon(scaled))

            item.setText(2, component.component_part.part_number or "-")
            item.setText(3, "IM")
            mat_name = component.component_part.material.short_name if component.component_part.material else "-"
            item.setText(4, mat_name)
            item.setText(5, str(component.quantity))
            join_method_label = component.join_method.replace("_", " ").title() if component.join_method != "none" else "-"
            if component.join_quantity > 0:
                join_method_label += f" x{component.join_quantity}"
            item.setText(6, join_method_label)

            # Check completeness of IM part
            missing = get_missing_fields(component.component_part)
            if len(missing) == 0:
                item.setText(7, "✓")
                item.setForeground(7, QColor("#70AD47"))
            else:
                item.setText(7, "⚠")
                item.setForeground(7, QColor("#FF5050"))
                item.setForeground(0, QColor("#FF5050"))

            if apply_colors:
                for col in range(8):
                    item.setBackground(col, QColor("#F0B840"))
            item.setData(0, Qt.ItemDataRole.UserRole, component.id)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "component_im")

        elif component.component_type == "purchased":
            # Purchased component - red, more indented
            item.setText(0, f"        └─ {component.component_name}")

            item.setText(2, "-")
            item.setText(3, "Purchased")
            item.setText(4, component.component_material or "-")
            item.setText(5, str(component.quantity))
            join_method_label = component.join_method.replace("_", " ").title() if component.join_method != "none" else "-"
            if component.join_quantity > 0:
                join_method_label += f" x{component.join_quantity}"
            item.setText(6, join_method_label)
            item.setText(7, "✓")

            if apply_colors:
                for col in range(8):
                    item.setBackground(col, QColor("#E04040"))
            item.setData(0, Qt.ItemDataRole.UserRole, component.id)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "component_purchased")

        elif component.component_type == "takeover":
            # Takeover component - grey, more indented
            item.setText(0, f"        └─ {component.component_name} (Takeover)")

            item.setText(2, "-")
            item.setText(3, "Takeover")
            item.setText(4, component.component_material or "-")
            item.setText(5, str(component.quantity))
            join_method_label = component.join_method.replace("_", " ").title() if component.join_method != "none" else "-"
            if component.join_quantity > 0:
                join_method_label += f" x{component.join_quantity}"
            item.setText(6, join_method_label)
            item.setText(7, "✓")

            if apply_colors:
                for col in range(8):
                    item.setBackground(col, QColor("#B0B0B0"))
            item.setData(0, Qt.ItemDataRole.UserRole, component.id)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "component_takeover")

    def _format_component_name_short(self, comp: AssemblyComponent) -> str:
        """Format component name briefly for display."""
        if comp.component_type == "injection_molded":
            return comp.component_part.name if comp.component_part else "IM"
        else:
            return comp.component_name or "Component"

    def _load_im_parts_table(self):
        """Load flat list of all IM parts for tooling engineer view."""
        from ui.color_coding import get_missing_fields, apply_source_color_to_table_item

        self.im_parts_table.setRowCount(0)

        with session_scope() as session:
            im_parts = session.query(Part).filter(
                Part.rfq_id == self.rfq_id,
                Part.part_type == "injection_molded"
            ).all()

            for row_idx, part in enumerate(im_parts):
                self.im_parts_table.insertRow(row_idx)

                # Calculate total usage across all assemblies
                total_usage = 0
                components = session.query(AssemblyComponent).filter(
                    AssemblyComponent.component_part_id == part.id
                ).all()
                for comp in components:
                    assembly = session.query(Part).get(comp.assembly_id)
                    if assembly:
                        asm_qty = assembly.demand_peak or 1
                        total_usage += asm_qty * comp.quantity

                # If not used in any assembly, it's standalone
                if total_usage == 0:
                    total_usage = part.demand_peak or 0

                # Name
                name_item = QTableWidgetItem(part.name)
                name_item.setData(Qt.ItemDataRole.UserRole, part.id)
                self.im_parts_table.setItem(row_idx, 0, name_item)

                # Part#
                self.im_parts_table.setItem(row_idx, 1, QTableWidgetItem(part.part_number or "-"))

                # Material
                mat_name = part.material.short_name if part.material else "-"
                self.im_parts_table.setItem(row_idx, 2, QTableWidgetItem(mat_name))

                # Weight (g)
                self.im_parts_table.setItem(row_idx, 3, QTableWidgetItem(
                    f"{part.weight_g:.2f}" if part.weight_g else "-"
                ))

                # Volume (cm³)
                self.im_parts_table.setItem(row_idx, 4, QTableWidgetItem(
                    f"{part.volume_cm3:.2f}" if part.volume_cm3 else "-"
                ))

                # Proj.Area (cm²) - with color coding for source
                proj_item = QTableWidgetItem(
                    f"{part.projected_area_cm2:.2f}" if part.projected_area_cm2 else "-"
                )
                apply_source_color_to_table_item(proj_item, part.projected_area_source)
                self.im_parts_table.setItem(row_idx, 5, proj_item)

                # Wall Thickness (mm) - with color coding for source
                wall_item = QTableWidgetItem(
                    f"{part.wall_thickness_mm:.2f}" if part.wall_thickness_mm else "-"
                )
                apply_source_color_to_table_item(wall_item, part.wall_thickness_source)
                self.im_parts_table.setItem(row_idx, 6, wall_item)

                # Peak Demand
                self.im_parts_table.setItem(row_idx, 7, QTableWidgetItem(
                    str(part.demand_peak) if part.demand_peak else "-"
                ))

                # Total Usage
                self.im_parts_table.setItem(row_idx, 8, QTableWidgetItem(str(total_usage)))

                # Status
                missing = get_missing_fields(part)
                if len(missing) == 0:
                    status_item = QTableWidgetItem("\u2713 Complete")
                    status_item.setForeground(QColor("#70AD47"))
                else:
                    status_item = QTableWidgetItem("\u26a0 Incomplete")
                    status_item.setForeground(QColor("#FF5050"))
                self.im_parts_table.setItem(row_idx, 9, status_item)

    def _load_parts_summary_table(self):
        """Load summary of all parts (excluding assemblies) with total quantities."""
        self.parts_summary_table.setRowCount(0)

        with session_scope() as session:
            rfq = session.query(RFQ).get(self.rfq_id)
            if not rfq:
                return

            # Get all IM parts
            im_parts = [p for p in rfq.parts if p.part_type == "injection_molded"]

            # Collect purchased and takeover components (group by name)
            purchased_components = {}  # {component_name: total_qty}
            all_components = session.query(AssemblyComponent).filter(
                AssemblyComponent.component_type.in_(["purchased", "takeover"])
            ).all()
            for comp in all_components:
                assembly = session.query(Part).get(comp.assembly_id)
                if assembly:
                    asm_qty = assembly.demand_peak or 1
                    comp_name = comp.component_name or f"{comp.component_type}_{comp.id}"
                    if comp_name not in purchased_components:
                        purchased_components[comp_name] = 0
                    purchased_components[comp_name] += asm_qty * comp.quantity

            row_idx = 0

            # Add IM parts
            for part in im_parts:
                self.parts_summary_table.insertRow(row_idx)

                # Calculate total quantity across all assemblies
                total_qty = 0
                components = session.query(AssemblyComponent).filter(
                    AssemblyComponent.component_part_id == part.id
                ).all()
                for comp in components:
                    assembly = session.query(Part).get(comp.assembly_id)
                    if assembly:
                        asm_qty = assembly.demand_peak or 1
                        total_qty += asm_qty * comp.quantity

                # If not used in assemblies, show the part's own demand
                if total_qty == 0:
                    total_qty = part.demand_peak or 0

                # Name
                name_item = QTableWidgetItem(part.name)
                name_item.setData(Qt.ItemDataRole.UserRole, part.id)
                self.parts_summary_table.setItem(row_idx, 0, name_item)

                # Part#
                self.parts_summary_table.setItem(row_idx, 1, QTableWidgetItem(part.part_number or "-"))

                # Type
                self.parts_summary_table.setItem(row_idx, 2, QTableWidgetItem("IM"))

                # Total Quantity
                self.parts_summary_table.setItem(row_idx, 3, QTableWidgetItem(str(total_qty)))

                row_idx += 1

            # Add purchased/takeover components
            for comp_name, total_qty in sorted(purchased_components.items()):
                self.parts_summary_table.insertRow(row_idx)

                # Name
                self.parts_summary_table.setItem(row_idx, 0, QTableWidgetItem(comp_name))

                # Part# (not applicable for purchased)
                self.parts_summary_table.setItem(row_idx, 1, QTableWidgetItem("-"))

                # Type (Purchased or Takeover)
                type_item = QTableWidgetItem("Purchased")
                self.parts_summary_table.setItem(row_idx, 2, type_item)

                # Total Quantity
                self.parts_summary_table.setItem(row_idx, 3, QTableWidgetItem(str(total_qty)))

                row_idx += 1

    def _load_assembly_tree(self):
        """Load assembly-only tree view for manufacturing engineer."""
        self.assembly_tree.clear()

        with session_scope() as session:
            rfq = session.query(RFQ).get(self.rfq_id)
            if not rfq:
                return

            assemblies = [p for p in rfq.parts if p.part_type == "assembly"]

            if not assemblies:
                self.asm_no_data_label.setVisible(True)
                self.assembly_tree.setVisible(False)
                return

            self.asm_no_data_label.setVisible(False)
            self.assembly_tree.setVisible(True)

            for part in assemblies:
                asm_item = QTreeWidgetItem()
                asm_item.setText(0, f"\U0001f5c2 {part.name}")

                if part.image_binary:
                    pixmap = QPixmap()
                    pixmap.loadFromData(part.image_binary)
                    scaled = pixmap.scaledToHeight(30, Qt.TransformationMode.SmoothTransformation)
                    asm_item.setIcon(1, QIcon(scaled))

                asm_item.setText(2, part.part_number or "-")
                asm_item.setText(3, "Assembly")
                asm_item.setText(4, "-")
                asm_item.setText(5, str(part.demand_peak or 1))
                asm_item.setText(6, "-")
                asm_item.setText(7, "")

                asm_item.setData(0, Qt.ItemDataRole.UserRole, part.id)
                asm_item.setData(0, Qt.ItemDataRole.UserRole + 1, "assembly")

                font = asm_item.font(0)
                font.setBold(True)
                for col in range(8):
                    asm_item.setFont(col, font)

                if part.assembly_components:
                    # Sort by position to maintain order
                    sorted_comps = sorted(part.assembly_components, key=lambda c: c.position if c.position else 0)

                    # Build a mapping of integer positions to IM component tree items
                    im_position_to_item = {}

                    # First pass: add all IM components
                    for comp in sorted_comps:
                        if comp.component_type == "injection_molded":
                            child_item = QTreeWidgetItem(asm_item)
                            self._style_component_item(child_item, comp, session, apply_colors=True)
                            # Store the item by its integer position
                            if comp.position is not None:
                                im_pos = int(comp.position)
                                im_position_to_item[im_pos] = child_item

                    # Second pass: add purchased/takeover components under correct IM part
                    for comp in sorted_comps:
                        if comp.component_type != "injection_molded":
                            # Find which IM part this should be grouped under
                            # Components with position between X.0 and X.99... belong under IM part at position X
                            parent_item = None
                            if comp.position is not None:
                                comp_pos = comp.position
                                target_im_pos = int(comp_pos)
                                parent_item = im_position_to_item.get(target_im_pos)

                            # Add as child of the correct IM part, or to assembly as fallback
                            if parent_item:
                                child_item = QTreeWidgetItem(parent_item)
                            else:
                                child_item = QTreeWidgetItem(asm_item)
                            self._style_component_item(child_item, comp, session, apply_colors=True)

                self.assembly_tree.addTopLevelItem(asm_item)
                # Process steps MUST be added after asm_item is in the tree
                self._add_process_steps_to_tree(self.assembly_tree, asm_item, part, session)

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
        """Show choice dialog: Create Assembly or Add Standalone IM Part."""
        from ui.dialogs.assembly_dialog import AssemblyDialog

        # Show choice dialog with custom buttons - larger size
        msg = QMessageBox(self)
        msg.setWindowTitle("Add to BOM")
        msg.setText("What would you like to add to this RFQ?\n\n")
        msg.setInformativeText("Choose 'Create Assembly' to add a new assembly container,\nor 'Add Standalone Part' to add a shoot-and-ship IM part.")

        btn_assembly = msg.addButton("Create Assembly", QMessageBox.ButtonRole.AcceptRole)
        btn_part = msg.addButton("Add Standalone Part", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton(QMessageBox.StandardButton.Cancel)

        # Make buttons larger
        for button in msg.findChildren(QPushButton):
            button.setMinimumHeight(40)
            button.setMinimumWidth(140)

        msg.setMinimumWidth(550)
        msg.setMinimumHeight(280)

        msg.exec()

        if msg.clickedButton() == btn_assembly:
            # Create Assembly
            dialog = AssemblyDialog(self, rfq_id=self.rfq_id)
            if dialog.exec():
                self._refresh_data()
                self.statusBar().showMessage("Assembly created successfully")
        elif msg.clickedButton() == btn_part:
            # Add Standalone IM Part (shoot and ship)
            dialog = PartDialog(self, rfq_id=self.rfq_id)
            if dialog.exec():
                self._refresh_data()
                self.statusBar().showMessage("Standalone part added successfully")

    def _on_edit_part(self, part_id: int = None):
        """Edit selected part."""
        if part_id is None:
            selected = self.parts_tree.selectedItems()
            if not selected:
                QMessageBox.warning(self, "No Selection", "Please select a part to edit")
                return
            item = selected[0]
            part_id = item.data(0, Qt.ItemDataRole.UserRole)

        dialog = PartDialog(self, rfq_id=self.rfq_id, part_id=part_id)
        if dialog.exec():
            self._refresh_data()
            self.statusBar().showMessage("Part updated successfully")

    def _on_parts_context_menu(self, position):
        """Show context menu for parts tree."""
        from PyQt6.QtWidgets import QMenu

        item = self.parts_tree.itemAt(position)
        if not item:
            return

        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        item_id = item.data(0, Qt.ItemDataRole.UserRole)

        menu = QMenu()

        if item_type == "assembly":
            # Assembly context menu
            add_im_action = menu.addAction("Add New IM Part")
            add_existing_action = menu.addAction("Add Existing IM Part")
            add_purchased_action = menu.addAction("Add Purchased Component")
            add_takeover_action = menu.addAction("Add Takeover Part")

            # Show paste option if component is copied
            paste_action = None
            if self.copied_component:
                menu.addSeparator()
                paste_action = menu.addAction("Paste Component")

            menu.addSeparator()
            add_step_action = menu.addAction("Add Process Step")

            menu.addSeparator()
            edit_action = menu.addAction("Edit Assembly")
            delete_action = menu.addAction("Delete Assembly")

            action = menu.exec(self.parts_tree.mapToGlobal(position))

            if action == add_im_action:
                self._on_add_new_im_to_assembly(item_id)
            elif action == add_existing_action:
                self._on_add_existing_im_to_assembly(item_id)
            elif action == add_purchased_action:
                self._on_add_purchased_to_assembly(item_id)
            elif action == add_takeover_action:
                self._on_add_takeover_to_assembly(item_id)
            elif paste_action and action == paste_action:
                self._on_paste_component_to_assembly(item_id)
            elif action == add_step_action:
                self._on_add_process_step(item_id)
            elif action == edit_action:
                self._on_edit_assembly(item_id)
            elif action == delete_action:
                self._on_delete_assembly(item_id)

        elif item_type == "process_step":
            # Process step context menu
            edit_step_action = menu.addAction("Edit Step")
            menu.addSeparator()
            move_up_action = menu.addAction("Move Up")
            move_down_action = menu.addAction("Move Down")
            menu.addSeparator()
            delete_step_action = menu.addAction("Delete Step")

            action = menu.exec(self.parts_tree.mapToGlobal(position))

            if action == edit_step_action:
                self._on_edit_process_step(item_id)
            elif action == move_up_action:
                self._on_move_process_step(item_id, "up")
            elif action == move_down_action:
                self._on_move_process_step(item_id, "down")
            elif action == delete_step_action:
                self._on_delete_process_step(item_id)

        elif item_type == "im_part":
            # Standalone IM part context menu
            edit_action = menu.addAction("Edit Part")
            delete_action = menu.addAction("Delete Part")

            action = menu.exec(self.parts_tree.mapToGlobal(position))

            if action == edit_action:
                self._on_edit_part(item_id)
            elif action == delete_action:
                self._on_delete_part(item_id)

        elif item_type.startswith("component_"):
            # Component context menu
            edit_action = menu.addAction("Edit Component Details")
            if item_type == "component_im":
                edit_part_action = menu.addAction("Edit Part")
            menu.addSeparator()
            cut_action = menu.addAction("Cut")
            copy_action = menu.addAction("Copy")

            # Show paste option if there's a cut or copied component AND this is an IM component
            paste_action = None
            if item_type == "component_im":
                if (hasattr(self, 'cut_component') and self.cut_component) or \
                   (hasattr(self, 'copied_component') and self.copied_component):
                    paste_action = menu.addAction("Paste")

            menu.addSeparator()
            delete_action = menu.addAction("Delete")

            action = menu.exec(self.parts_tree.mapToGlobal(position))

            if action == edit_action:
                self._on_edit_component(item_id)
            elif item_type == "component_im" and action == edit_part_action:
                # Get the component to find the part_id
                with session_scope() as session:
                    comp = session.query(AssemblyComponent).get(item_id)
                    if comp and comp.component_part_id:
                        self._on_edit_part(comp.component_part_id)
            elif action == cut_action:
                self._on_cut_component(item_id)
            elif action == copy_action:
                self._on_copy_component(item_id)
            elif paste_action and action == paste_action:
                # Paste can be cut (move) or copy (duplicate)
                if hasattr(self, 'cut_component') and self.cut_component:
                    self._on_paste_component_in_assembly(item_id)
                elif hasattr(self, 'copied_component') and self.copied_component:
                    self._on_paste_copied_component_in_assembly(item_id)
            elif action == delete_action:
                self._on_remove_component(item_id)

    def _on_delete_part(self, part_id: int = None):
        """Delete selected part."""
        if part_id is None:
            selected = self.parts_tree.selectedItems()
            if not selected:
                QMessageBox.warning(self, "No Selection", "Please select a part to delete")
                return
            item = selected[0]
            part_id = item.data(0, Qt.ItemDataRole.UserRole)

        with session_scope() as session:
            part = session.query(Part).get(part_id)
            if not part:
                QMessageBox.warning(self, "Error", "Part not found")
                return

            part_name = part.name

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete part '{part_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with session_scope() as session:
                part = session.query(Part).get(part_id)
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

    def _on_tree_item_clicked(self, index):
        """Handle click on tree items (for image preview in column 1)."""
        if index.column() != 1:  # Only handle column 1 (image column)
            return

        item = self.parts_tree.itemFromIndex(index)
        if not item or not item.icon(1) or item.icon(1).isNull():
            return  # No image in this item

        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        item_id = item.data(0, Qt.ItemDataRole.UserRole)

        # Get the part/component and show image preview
        with session_scope() as session:
            if item_type == "assembly":
                part = session.query(Part).get(item_id)
                if part and part.image_binary:
                    from ui.widgets.image_preview import show_image_preview
                    show_image_preview(self, f"Assembly: {part.name}", part.image_binary)

            elif item_type == "im_part":
                part = session.query(Part).get(item_id)
                if part and part.image_binary:
                    from ui.widgets.image_preview import show_image_preview
                    show_image_preview(self, f"Part: {part.name}", part.image_binary)

            elif item_type == "component_im":
                component = session.query(AssemblyComponent).get(item_id)
                if component and component.component_part and component.component_part.image_binary:
                    from ui.widgets.image_preview import show_image_preview
                    show_image_preview(self, f"Part: {component.component_part.name}", component.component_part.image_binary)

    def _on_tree_item_double_clicked(self, index):
        """Handle double-click on tree items."""
        item = self.parts_tree.itemFromIndex(index)
        if not item:
            return

        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        item_id = item.data(0, Qt.ItemDataRole.UserRole)

        if item_type == "assembly":
            self._on_edit_assembly(item_id)
        elif item_type == "im_part":
            self._on_edit_part(item_id)
        elif item_type == "component_im":
            # Edit component details for IM components
            self._on_edit_component(item_id)
        elif item_type in ("component_purchased", "component_takeover"):
            self._on_edit_component(item_id)
        elif item_type == "process_step":
            self._on_edit_process_step(item_id)

    def _on_add_new_im_to_assembly(self, assembly_id: int):
        """Add a new IM part to assembly."""
        from ui.dialogs.component_dialog import ComponentDetailDialog

        # Verify assembly exists and get its name for confirmation
        with session_scope() as session:
            assembly = session.query(Part).get(assembly_id)
            if not assembly or assembly.part_type != "assembly":
                QMessageBox.warning(self, "Error", "Invalid assembly selected")
                return
            assembly_name = assembly.name

        # Open PartDialog to create new part
        dialog = PartDialog(self, rfq_id=self.rfq_id)
        if dialog.exec():
            # Get the created part ID
            with session_scope() as session:
                # Get the most recently created part (hacky but works)
                parts = session.query(Part).filter(Part.rfq_id == self.rfq_id).order_by(Part.id.desc()).first()
                if parts:
                    new_part_id = parts.id

                    # Now open ComponentDetailDialog
                    comp_dialog = ComponentDetailDialog(
                        self, assembly_id=assembly_id,
                        component_type="injection_molded",
                        part_id=new_part_id
                    )
                    comp_dialog.setWindowTitle(f"Add IM Part to '{assembly_name}'")
                    if comp_dialog.exec():
                        self._refresh_data()
                        self.statusBar().showMessage(f"Component added to '{assembly_name}'")

    def _on_add_existing_im_to_assembly(self, assembly_id: int):
        """Add existing IM part to assembly."""
        from ui.dialogs.component_dialog import ComponentDetailDialog
        from PyQt6.QtWidgets import QInputDialog

        # Verify assembly exists and get its name for confirmation
        with session_scope() as session:
            assembly = session.query(Part).get(assembly_id)
            if not assembly or assembly.part_type != "assembly":
                QMessageBox.warning(self, "Error", "Invalid assembly selected")
                return
            assembly_name = assembly.name

        # Get list of available IM parts in RFQ (excluding assemblies)
        with session_scope() as session:
            parts = session.query(Part).filter(
                Part.rfq_id == self.rfq_id,
                Part.part_type == "injection_molded"
            ).all()

            if not parts:
                QMessageBox.warning(self, "No Parts", "No injection molded parts available in this RFQ")
                return

            # Create list of part names with IDs
            part_map = {p.name: p.id for p in parts}
            part_names = [p.name for p in parts]

            # Show selection dialog
            part_name, ok = QInputDialog.getItem(
                self, "Select IM Part", f"Choose a part to add to '{assembly_name}':",
                part_names, 0, False
            )

            if ok and part_name:
                part_id = part_map[part_name]

                # Open ComponentDetailDialog
                comp_dialog = ComponentDetailDialog(
                    self, assembly_id=assembly_id,
                    component_type="injection_molded",
                    part_id=part_id
                )
                comp_dialog.setWindowTitle(f"Add IM Part to '{assembly_name}'")
                if comp_dialog.exec():
                    self._refresh_data()
                    self.statusBar().showMessage(f"Component added to '{assembly_name}'")

    def _on_add_purchased_to_assembly(self, assembly_id: int):
        """Add purchased component to assembly."""
        from ui.dialogs.component_dialog import ComponentDetailDialog

        # Verify assembly exists and get its name for confirmation
        with session_scope() as session:
            assembly = session.query(Part).get(assembly_id)
            if not assembly or assembly.part_type != "assembly":
                QMessageBox.warning(self, "Error", "Invalid assembly selected")
                return
            assembly_name = assembly.name

        # Open dialog with assembly info in title for clarity
        comp_dialog = ComponentDetailDialog(
            self, assembly_id=assembly_id,
            component_type="purchased"
        )
        comp_dialog.setWindowTitle(f"Add Purchased Component to '{assembly_name}'")
        if comp_dialog.exec():
            self._refresh_data()
            self.statusBar().showMessage(f"Purchased component added to '{assembly_name}'")

    def _on_add_takeover_to_assembly(self, assembly_id: int):
        """Add takeover component to assembly."""
        from ui.dialogs.component_dialog import ComponentDetailDialog

        # Verify assembly exists and get its name for confirmation
        with session_scope() as session:
            assembly = session.query(Part).get(assembly_id)
            if not assembly or assembly.part_type != "assembly":
                QMessageBox.warning(self, "Error", "Invalid assembly selected")
                return
            assembly_name = assembly.name

        comp_dialog = ComponentDetailDialog(
            self, assembly_id=assembly_id,
            component_type="takeover"
        )
        comp_dialog.setWindowTitle(f"Add Takeover Component to '{assembly_name}'")
        if comp_dialog.exec():
            self._refresh_data()
            self.statusBar().showMessage(f"Takeover component added to '{assembly_name}'")

    def _on_edit_assembly(self, assembly_id: int):
        """Edit assembly details."""
        from ui.dialogs.assembly_dialog import AssemblyDialog

        dialog = AssemblyDialog(self, rfq_id=self.rfq_id, assembly_id=assembly_id)
        if dialog.exec():
            self._refresh_data()
            self.statusBar().showMessage("Assembly updated successfully")

    def _on_delete_assembly(self, assembly_id: int):
        """Delete assembly and its components."""
        with session_scope() as session:
            assembly = session.query(Part).get(assembly_id)
            if not assembly:
                QMessageBox.warning(self, "Error", "Assembly not found")
                return

            assembly_name = assembly.name

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete assembly '{assembly_name}' and all its components?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with session_scope() as session:
                assembly = session.query(Part).get(assembly_id)
                if assembly:
                    session.delete(assembly)
            self._refresh_data()
            self.statusBar().showMessage(f"Deleted assembly: {assembly_name}")

    def _on_edit_component(self, component_id: int):
        """Edit component details."""
        from ui.dialogs.component_dialog import ComponentDetailDialog

        dialog = ComponentDetailDialog(self, component_id=component_id)
        if dialog.exec():
            self._refresh_data()
            self.statusBar().showMessage("Component updated successfully")

    def _on_remove_component(self, component_id: int):
        """Remove component from assembly."""
        with session_scope() as session:
            component = session.query(AssemblyComponent).get(component_id)
            if not component:
                QMessageBox.warning(self, "Error", "Component not found")
                return

            comp_name = component.component_name or (
                component.component_part.name if component.component_part else "Component"
            )

        reply = QMessageBox.question(
            self, "Confirm Remove",
            f"Remove '{comp_name}' from assembly?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with session_scope() as session:
                component = session.query(AssemblyComponent).get(component_id)
                if component:
                    session.delete(component)
            self._refresh_data()
            self.statusBar().showMessage(f"Removed component from assembly")

    def _on_cut_component(self, component_id: int):
        """Cut a component for moving within assembly (change which IM part it's grouped under)."""
        with session_scope() as session:
            component = session.query(AssemblyComponent).get(component_id)
            if not component:
                QMessageBox.warning(self, "Error", "Component not found")
                return

            comp_name = component.component_name or (
                component.component_part.name if component.component_part else "Component"
            )

            # Store component ID and assembly for cutting (moving within assembly)
            self.cut_component = {
                "id": component_id,
                "assembly_id": component.assembly_id,
                "name": comp_name
            }
            # Clear copied component when cutting
            self.copied_component = None

            self.statusBar().showMessage(f"Cut '{comp_name}' - right-click an IM part and select 'Paste' to move it")

    def _on_copy_component(self, component_id: int):
        """Copy a component for pasting."""
        with session_scope() as session:
            component = session.query(AssemblyComponent).get(component_id)
            if not component:
                QMessageBox.warning(self, "Error", "Component not found")
                return

            comp_name = component.component_name or (
                component.component_part.name if component.component_part else "Component"
            )

            # Store component data for pasting (copy relevant fields)
            self.copied_component = {
                "component_type": component.component_type,
                "component_name": component.component_name,
                "component_material": component.component_material,
                "component_part_id": component.component_part_id,
                "quantity": component.quantity,
                "join_method": component.join_method,
                "join_quantity": component.join_quantity,
                "join_detail": component.join_detail,
                "notes": component.notes,
            }

            self.statusBar().showMessage(f"Copied '{comp_name}' - right-click assembly and select 'Paste Component'")

    def _on_paste_component_to_assembly(self, assembly_id: int):
        """Paste a previously copied component to an assembly."""
        if not self.copied_component:
            QMessageBox.warning(self, "Error", "No component to paste")
            return

        with session_scope() as session:
            # Get the last IM component in the assembly to attach to
            last_im_component = session.query(AssemblyComponent).filter(
                AssemblyComponent.assembly_id == assembly_id,
                AssemblyComponent.component_type == "injection_molded"
            ).order_by(AssemblyComponent.position.desc()).first()

            # Determine position for new component
            if last_im_component and last_im_component.position is not None:
                # Attach under the last IM component
                new_position = last_im_component.position + 0.1
            else:
                # Fallback: if no IM components, use position 0.1
                new_position = 0.1

            # Create new component with copied data
            new_component = AssemblyComponent(
                assembly_id=assembly_id,
                component_type=self.copied_component["component_type"],
                component_name=self.copied_component["component_name"],
                component_material=self.copied_component["component_material"],
                component_part_id=self.copied_component["component_part_id"],
                quantity=self.copied_component["quantity"],
                join_method=self.copied_component["join_method"],
                join_quantity=self.copied_component["join_quantity"],
                join_detail=self.copied_component["join_detail"],
                notes=self.copied_component["notes"],
                position=new_position
            )
            session.add(new_component)

        self._refresh_data()
        comp_name = self.copied_component["component_name"] or "Component"
        self.statusBar().showMessage(f"Pasted '{comp_name}' to assembly")

    def _on_paste_component_in_assembly(self, target_im_component_id: int):
        """Paste a cut component to be grouped under a different IM part within the same assembly."""
        if not self.cut_component:
            QMessageBox.warning(self, "Error", "No component to paste")
            return

        component_id = self.cut_component["id"]
        source_assembly_id = self.cut_component["assembly_id"]

        with session_scope() as session:
            # Get the target IM component (the IM part we're pasting after)
            target_component = session.query(AssemblyComponent).get(target_im_component_id)
            if not target_component or target_component.component_type != "injection_molded":
                QMessageBox.warning(self, "Error", "Can only paste after IM parts")
                return

            # Get the component being moved
            component = session.query(AssemblyComponent).get(component_id)
            if not component:
                QMessageBox.warning(self, "Error", "Component to move not found")
                return

            # Verify they're in the same assembly
            if component.assembly_id != target_component.assembly_id:
                QMessageBox.warning(self, "Error", "Components must be in the same assembly")
                return

            target_part_name = target_component.component_part.name if target_component.component_part else "part"
            comp_name = component.component_name or (component.component_part.name if component.component_part else "Component")

            # Ensure target component has a proper position
            if target_component.position is None:
                # Find the highest position in this assembly and use next integer
                highest = session.query(AssemblyComponent).filter(
                    AssemblyComponent.assembly_id == target_component.assembly_id
                ).order_by(AssemblyComponent.position.desc()).first()
                target_component.position = (highest.position or 0) + 1 if highest else 1

            target_position = int(target_component.position)  # Force to integer

            # Get highest decimal position under this IM part (to avoid conflicts)
            existing_under_target = session.query(AssemblyComponent).filter(
                AssemblyComponent.assembly_id == component.assembly_id,
                AssemblyComponent.position > target_position,
                AssemblyComponent.position < (target_position + 1)
            ).order_by(AssemblyComponent.position.desc()).first()

            if existing_under_target and existing_under_target.position:
                new_position = existing_under_target.position + 0.01
            else:
                new_position = float(target_position) + 0.1

            # Set the moved component's position
            component.position = new_position

        self._refresh_data()
        self.cut_component = None
        self.statusBar().showMessage(f"Moved '{comp_name}' to be grouped with '{target_part_name}'")

    def _on_paste_copied_component_in_assembly(self, target_im_component_id: int):
        """Paste a copied component (creating a duplicate) under a different IM part within the same assembly."""
        if not self.copied_component:
            QMessageBox.warning(self, "Error", "No component to paste")
            return

        # Ask for quantity
        from PyQt6.QtWidgets import QInputDialog
        qty, ok = QInputDialog.getInt(
            self,
            "Paste Component",
            "Quantity:",
            value=self.copied_component.get("quantity", 1),
            min=1,
            max=10000
        )

        if not ok:
            return

        with session_scope() as session:
            # Get the target IM component (the IM part we're pasting after)
            target_component = session.query(AssemblyComponent).get(target_im_component_id)
            if not target_component or target_component.component_type != "injection_molded":
                QMessageBox.warning(self, "Error", "Can only paste after IM parts")
                return

            target_part_name = target_component.component_part.name if target_component.component_part else "part"
            comp_name = self.copied_component.get("component_name") or "Component"

            # Check for duplicates: can't have same purchased part twice under one IM component
            assembly_id = target_component.assembly_id
            target_position_int = int(target_component.position) if target_component.position else 0

            # For purchased components, check if same name/type already exists under this IM part
            if self.copied_component["component_type"] in ["purchased", "takeover"]:
                existing_under_target = session.query(AssemblyComponent).filter(
                    AssemblyComponent.assembly_id == assembly_id,
                    AssemblyComponent.component_type == self.copied_component["component_type"],
                    AssemblyComponent.component_name == self.copied_component["component_name"]
                ).all()

                # Filter to only those under the target IM part
                existing_under_target = [
                    c for c in existing_under_target
                    if c.position and int(c.position) == target_position_int
                ]

                if existing_under_target:
                    QMessageBox.warning(
                        self,
                        "Duplicate Component",
                        f"'{comp_name}' already exists under '{target_part_name}'.\n\n"
                        f"To add more, edit the existing component and increase its quantity."
                    )
                    return

            # Ensure target component has a proper position
            if target_component.position is None:
                # Find the highest position in this assembly and use next integer
                highest = session.query(AssemblyComponent).filter(
                    AssemblyComponent.assembly_id == target_component.assembly_id
                ).order_by(AssemblyComponent.position.desc()).first()
                target_component.position = (highest.position or 0) + 1 if highest else 1

            target_position = int(target_component.position)  # Force to integer

            # Get highest decimal position under this IM part
            existing_under_target = session.query(AssemblyComponent).filter(
                AssemblyComponent.assembly_id == target_component.assembly_id,
                AssemblyComponent.position > target_position,
                AssemblyComponent.position < (target_position + 1)
            ).order_by(AssemblyComponent.position.desc()).first()

            if existing_under_target and existing_under_target.position:
                new_position = existing_under_target.position + 0.01
            else:
                new_position = float(target_position) + 0.1

            # Create new component with copied data
            new_component = AssemblyComponent(
                assembly_id=target_component.assembly_id,
                component_type=self.copied_component["component_type"],
                component_name=self.copied_component["component_name"],
                component_material=self.copied_component["component_material"],
                component_part_id=self.copied_component["component_part_id"],
                quantity=qty,  # Use the entered quantity
                join_method=self.copied_component["join_method"],
                join_quantity=self.copied_component["join_quantity"],
                join_detail=self.copied_component["join_detail"],
                notes=self.copied_component["notes"],
                position=new_position
            )
            session.add(new_component)

        self._refresh_data()
        self.statusBar().showMessage(f"Pasted '{comp_name}' (qty: {qty}) under '{target_part_name}'")

    # --- IM Parts Table Handlers ---

    def _on_im_parts_context_menu(self, position):
        """Show context menu for IM parts table."""
        from PyQt6.QtWidgets import QMenu

        item = self.im_parts_table.itemAt(position)
        if not item:
            return

        row = self.im_parts_table.row(item)
        name_item = self.im_parts_table.item(row, 0)
        if not name_item:
            return

        part_id = name_item.data(Qt.ItemDataRole.UserRole)
        if not part_id:
            return

        menu = QMenu()
        edit_action = menu.addAction("Edit Part")
        view_master_action = menu.addAction("View in Master BOM")

        action = menu.exec(self.im_parts_table.mapToGlobal(position))

        if action == edit_action:
            self._on_edit_part(part_id)
        elif action == view_master_action:
            self._switch_to_master_bom_and_highlight(part_id)

    def _on_im_parts_double_clicked(self, index):
        """Handle double-click on IM parts table — open part editor."""
        row = index.row()
        name_item = self.im_parts_table.item(row, 0)
        if name_item:
            part_id = name_item.data(Qt.ItemDataRole.UserRole)
            if part_id:
                self._on_edit_part(part_id)

    def _switch_to_master_bom_and_highlight(self, part_id: int):
        """Switch to Master BOM tab and highlight the given part."""
        self.bom_sub_tabs.setCurrentIndex(0)
        # Search for the part in the tree and select it
        for i in range(self.parts_tree.topLevelItemCount()):
            top_item = self.parts_tree.topLevelItem(i)
            item_id = top_item.data(0, Qt.ItemDataRole.UserRole)
            item_type = top_item.data(0, Qt.ItemDataRole.UserRole + 1)
            if item_type == "im_part" and item_id == part_id:
                self.parts_tree.setCurrentItem(top_item)
                self.parts_tree.scrollToItem(top_item)
                return
            # Also check children (IM parts inside assemblies)
            for j in range(top_item.childCount()):
                child = top_item.child(j)
                child_type = child.data(0, Qt.ItemDataRole.UserRole + 1)
                if child_type == "component_im":
                    child_id = child.data(0, Qt.ItemDataRole.UserRole)
                    # component_id is stored, need to check component_part_id
                    with session_scope() as session:
                        comp = session.query(AssemblyComponent).get(child_id)
                        if comp and comp.component_part_id == part_id:
                            self.parts_tree.expandItem(top_item)
                            self.parts_tree.setCurrentItem(child)
                            self.parts_tree.scrollToItem(child)
                            return

    # --- Assembly Lines Tree Handlers ---

    def _on_assembly_tree_context_menu(self, position):
        """Show context menu for assembly lines tree."""
        from PyQt6.QtWidgets import QMenu

        item = self.assembly_tree.itemAt(position)
        if not item:
            return

        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        item_id = item.data(0, Qt.ItemDataRole.UserRole)

        menu = QMenu()

        if item_type == "assembly":
            add_im_action = menu.addAction("Add New IM Part")
            add_existing_action = menu.addAction("Add Existing IM Part")
            add_purchased_action = menu.addAction("Add Purchased Component")
            add_takeover_action = menu.addAction("Add Takeover Part")

            paste_action = None
            if self.copied_component:
                menu.addSeparator()
                paste_action = menu.addAction("Paste Component")

            menu.addSeparator()
            add_step_action = menu.addAction("Add Process Step")

            menu.addSeparator()
            edit_action = menu.addAction("Edit Assembly")
            delete_action = menu.addAction("Delete Assembly")

            action = menu.exec(self.assembly_tree.mapToGlobal(position))

            if action == add_im_action:
                self._on_add_new_im_to_assembly(item_id)
            elif action == add_existing_action:
                self._on_add_existing_im_to_assembly(item_id)
            elif action == add_purchased_action:
                self._on_add_purchased_to_assembly(item_id)
            elif action == add_takeover_action:
                self._on_add_takeover_to_assembly(item_id)
            elif paste_action and action == paste_action:
                self._on_paste_component_to_assembly(item_id)
            elif action == add_step_action:
                self._on_add_process_step(item_id)
            elif action == edit_action:
                self._on_edit_assembly(item_id)
            elif action == delete_action:
                self._on_delete_assembly(item_id)

        elif item_type == "process_step":
            # Process step context menu
            edit_step_action = menu.addAction("Edit Step")
            menu.addSeparator()
            move_up_action = menu.addAction("Move Up")
            move_down_action = menu.addAction("Move Down")
            menu.addSeparator()
            delete_step_action = menu.addAction("Delete Step")

            action = menu.exec(self.assembly_tree.mapToGlobal(position))

            if action == edit_step_action:
                self._on_edit_process_step(item_id)
            elif action == move_up_action:
                self._on_move_process_step(item_id, "up")
            elif action == move_down_action:
                self._on_move_process_step(item_id, "down")
            elif action == delete_step_action:
                self._on_delete_process_step(item_id)

        elif item_type and item_type.startswith("component_"):
            edit_action = menu.addAction("Edit Component Details")
            if item_type == "component_im":
                edit_part_action = menu.addAction("Edit Part")
            menu.addSeparator()
            copy_action = menu.addAction("Copy Component")
            remove_action = menu.addAction("Remove from Assembly")

            action = menu.exec(self.assembly_tree.mapToGlobal(position))

            if action == edit_action:
                self._on_edit_component(item_id)
            elif item_type == "component_im" and action == edit_part_action:
                with session_scope() as session:
                    comp = session.query(AssemblyComponent).get(item_id)
                    if comp and comp.component_part_id:
                        self._on_edit_part(comp.component_part_id)
            elif action == copy_action:
                self._on_copy_component(item_id)
            elif action == remove_action:
                self._on_remove_component(item_id)

    def _on_assembly_tree_double_clicked(self, index):
        """Handle double-click on assembly lines tree items."""
        item = self.assembly_tree.itemFromIndex(index)
        if not item:
            return

        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        item_id = item.data(0, Qt.ItemDataRole.UserRole)

        if item_type == "assembly":
            self._on_edit_assembly(item_id)
        elif item_type == "component_im":
            self._on_edit_component(item_id)
        elif item_type in ("component_purchased", "component_takeover"):
            self._on_edit_component(item_id)
        elif item_type == "process_step":
            self._on_edit_process_step(item_id)

    def _on_assembly_tree_clicked(self, index):
        """Handle click on assembly lines tree items (for image preview in column 1 and process steps display)."""
        item = self.assembly_tree.itemFromIndex(index)
        if not item:
            return

        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        item_id = item.data(0, Qt.ItemDataRole.UserRole)

        # Show process steps for selected assembly
        if item_type == "assembly":
            self._update_process_steps_display(item_id)

        # Handle image preview on column 1 click
        if index.column() != 1:
            return

        if not item.icon(1) or item.icon(1).isNull():
            return

        with session_scope() as session:
            if item_type == "assembly":
                part = session.query(Part).get(item_id)
                if part and part.image_binary:
                    from ui.widgets.image_preview import show_image_preview
                    show_image_preview(self, f"Assembly: {part.name}", part.image_binary)
            elif item_type == "component_im":
                component = session.query(AssemblyComponent).get(item_id)
                if component and component.component_part and component.component_part.image_binary:
                    from ui.widgets.image_preview import show_image_preview
                    show_image_preview(self, f"Part: {component.component_part.name}", component.component_part.image_binary)

    def _update_process_steps_display(self, assembly_id: int):
        """Update process steps display for selected assembly."""
        with session_scope() as session:
            steps = session.query(AssemblyProcessStep).filter(
                AssemblyProcessStep.assembly_id == assembly_id
            ).order_by(AssemblyProcessStep.step_number).all()

            if not steps:
                self.process_steps_display.setPlainText("")
                return

            # Build text display
            lines = []
            for step in steps:
                process_label = step.process_type.replace("_", " ").title()
                comp_parts = []
                components_dict = step.get_components()
                if components_dict:
                    for comp_id_str, qty in components_dict.items():
                        try:
                            comp_id = int(comp_id_str)
                            comp = session.query(AssemblyComponent).get(comp_id)
                            if comp:
                                comp_name = self._format_component_name_short(comp)
                                comp_parts.append(f"{comp_name} x{qty}")
                        except:
                            pass

                comp_text = ", ".join(comp_parts) if comp_parts else ""
                step_header = f"{step.step_number}. {process_label}:"

                if comp_text:
                    lines.append(f"{step_header} {comp_text}")
                else:
                    lines.append(step_header)

                if step.notes:
                    lines.append(f"   Notes: {step.notes}")

            self.process_steps_display.setPlainText("\n".join(lines))

    def _on_assembly_tree_selection_changed(self, selected, deselected):
        """Update process steps display when selection changes in assembly tree."""
        if not selected.indexes():
            self.process_steps_display.setPlainText("")
            return

        index = selected.indexes()[0]
        item = self.assembly_tree.itemFromIndex(index)
        if not item:
            return

        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        item_id = item.data(0, Qt.ItemDataRole.UserRole)

        if item_type == "assembly":
            self._update_process_steps_display(item_id)
        else:
            self.process_steps_display.setPlainText("")

    def _on_assembly_tree_selection_changed_direct(self):
        """Update process steps display when selection changes (no parameters)."""
        selected_items = self.assembly_tree.selectedItems()
        if not selected_items:
            self.process_steps_display.setPlainText("")
            return

        item = selected_items[0]
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        item_id = item.data(0, Qt.ItemDataRole.UserRole)

        if item_type == "assembly":
            self._update_process_steps_display(item_id)
        else:
            self.process_steps_display.setPlainText("")

    def _add_process_steps_to_tree(self, tree, asm_item: QTreeWidgetItem, part, session):
        """Add process steps as children of assembly (so they collapse/expand together)."""
        steps = session.query(AssemblyProcessStep).filter(
            AssemblyProcessStep.assembly_id == part.id
        ).order_by(AssemblyProcessStep.step_number).all()

        if not steps:
            return

        # Separator row
        sep_item = QTreeWidgetItem()
        sep_item.setText(0, "── Process Steps ──")
        font = sep_item.font(0)
        font.setItalic(True)
        sep_item.setFont(0, font)
        sep_item.setForeground(0, QColor("#808080"))
        for col in range(tree.columnCount()):
            sep_item.setBackground(col, QColor("#4a4a4a"))
        sep_item.setFlags(sep_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        asm_item.addChild(sep_item)
        # Must be called AFTER item is in the tree
        sep_item.setFirstColumnSpanned(True)

        # Each step — use native tree text + background (spans full width)
        for step in steps:
            step_item = QTreeWidgetItem()

            # Format: "1. Assemble: Part1 x1, Part2 x2"
            process_label = step.process_type.replace("_", " ").title()
            comp_parts = []
            components_dict = step.get_components()
            if components_dict:
                for comp_id_str, qty in components_dict.items():
                    try:
                        comp_id = int(comp_id_str)
                        comp = session.query(AssemblyComponent).get(comp_id)
                        if comp:
                            comp_name = self._format_component_name_short(comp)
                            comp_parts.append(f"{comp_name} x{qty}")
                    except:
                        pass

            comp_text = ", ".join(comp_parts) if comp_parts else ""
            if comp_text:
                step_text = f"  {step.step_number}. {process_label}: {comp_text}"
            else:
                step_text = f"  {step.step_number}. {process_label}"

            step_item.setText(0, step_text)

            # Green background across ALL columns so full row is green
            green = QColor("#90C890")
            for col in range(tree.columnCount()):
                step_item.setBackground(col, green)

            step_item.setForeground(0, QColor("#1a1a1a"))

            if step.notes:
                step_item.setToolTip(0, step.notes)

            step_item.setData(0, Qt.ItemDataRole.UserRole, step.id)
            step_item.setData(0, Qt.ItemDataRole.UserRole + 1, "process_step")

            asm_item.addChild(step_item)
            # Must be called AFTER item is in the tree
            step_item.setFirstColumnSpanned(True)

    def _on_move_component(self, component_id: int):
        """Show dialog to move component to another assembly."""
        from PyQt6.QtWidgets import QInputDialog

        # Get current component and assembly info
        with session_scope() as session:
            component = session.query(AssemblyComponent).get(component_id)
            if not component:
                QMessageBox.warning(self, "Error", "Component not found")
                return

            current_assembly = session.query(Part).get(component.assembly_id)
            if not current_assembly:
                QMessageBox.warning(self, "Error", "Assembly not found")
                return

            # Get list of all other assemblies (not current)
            assemblies = session.query(Part).filter(
                Part.rfq_id == self.rfq_id,
                Part.part_type == "assembly",
                Part.id != component.assembly_id
            ).all()

            if not assemblies:
                QMessageBox.information(
                    self,
                    "No Other Assemblies",
                    f"There are no other assemblies to move '{component.component_name or 'component'}' to."
                )
                return

            # Show selection dialog
            assembly_map = {asm.name: asm.id for asm in assemblies}
            assembly_names = [asm.name for asm in assemblies]

            target_name, ok = QInputDialog.getItem(
                self,
                "Move Component",
                f"Move component from '{current_assembly.name}' to:",
                assembly_names,
                0,
                False
            )

            if ok and target_name:
                target_assembly_id = assembly_map[target_name]
                self._on_move_component_to_assembly(component_id, target_assembly_id)

    def _on_move_component_to_assembly(self, component_id: int, target_assembly_id: int):
        """Handle moving a component from one assembly to another."""
        with session_scope() as session:
            component = session.query(AssemblyComponent).get(component_id)
            if not component:
                QMessageBox.warning(self, "Error", "Component not found")
                return

            source_assembly = session.query(Part).get(component.assembly_id)
            target_assembly = session.query(Part).get(target_assembly_id)

            if not source_assembly or not target_assembly:
                QMessageBox.warning(self, "Error", "Assembly not found")
                return

            source_name = source_assembly.name
            target_name = target_assembly.name
            comp_name = component.component_name or (
                component.component_part.name if component.component_part else "Component"
            )

        reply = QMessageBox.question(
            self,
            "Move Component",
            f"Move '{comp_name}' from '{source_name}' to '{target_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with session_scope() as session:
                component = session.query(AssemblyComponent).get(component_id)
                if component:
                    component.assembly_id = target_assembly_id
            self._refresh_data()
            self.statusBar().showMessage(f"Moved '{comp_name}' to '{target_name}'")

    def _on_drop_part_on_assembly(self, assembly_id: int, part_id: int):
        """Handle drop of IM part onto assembly — add as component with dialog."""
        from ui.dialogs.component_dialog import ComponentDetailDialog

        # Verify both assembly and part exist
        with session_scope() as session:
            assembly = session.query(Part).get(assembly_id)
            part = session.query(Part).get(part_id)

            if not assembly or assembly.part_type != "assembly":
                QMessageBox.warning(self, "Error", "Invalid assembly selected")
                return

            if not part or part.part_type != "injection_molded":
                QMessageBox.warning(self, "Error", "Invalid IM part selected")
                return

            assembly_name = assembly.name
            part_name = part.name

        # Check if this part is already used as a component in this assembly
        with session_scope() as session:
            existing = session.query(AssemblyComponent).filter(
                AssemblyComponent.assembly_id == assembly_id,
                AssemblyComponent.component_part_id == part_id
            ).first()

            if existing:
                reply = QMessageBox.question(
                    self,
                    "Part Already in Assembly",
                    f"'{part_name}' is already a component in '{assembly_name}'.\n\n"
                    "Would you like to edit the existing component or add another instance?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )

                if reply == QMessageBox.StandardButton.Yes:
                    # Edit existing component
                    comp_dialog = ComponentDetailDialog(
                        self, component_id=existing.id
                    )
                    if comp_dialog.exec():
                        self._refresh_data()
                        self.statusBar().showMessage(f"Component updated in '{assembly_name}'")
                    return
                elif reply == QMessageBox.StandardButton.Cancel:
                    return
                # If No, continue to add another instance

        # Open dialog to set component details (join method, quantity, notes)
        comp_dialog = ComponentDetailDialog(
            self, assembly_id=assembly_id,
            component_type="injection_molded",
            part_id=part_id
        )
        comp_dialog.setWindowTitle(f"Add '{part_name}' to '{assembly_name}'")
        if comp_dialog.exec():
            self._refresh_data()
            self.statusBar().showMessage(f"'{part_name}' added to '{assembly_name}'")

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts: Ctrl+C (copy), Ctrl+X (cut), Ctrl+V (paste)."""
        # Get the currently focused tree widget
        current_tab = self.bom_sub_tabs.currentIndex()
        tree = None

        if current_tab == 0:  # Master BOM
            tree = self.parts_tree
        elif current_tab == 2:  # Assembly Lines
            tree = self.assembly_tree

        if not tree:
            super().keyPressEvent(event)
            return

        # Check if Ctrl is held
        ctrl_held = event.modifiers() & Qt.KeyboardModifier.ControlModifier

        if not ctrl_held:
            super().keyPressEvent(event)
            return

        key = event.key()

        # Delegate to tree's keyboard shortcut handlers
        if key == Qt.Key.Key_C:
            if hasattr(tree, '_handle_copy_shortcut'):
                tree._handle_copy_shortcut()
                event.accept()
                return
        elif key == Qt.Key.Key_X:
            if hasattr(tree, '_handle_cut_shortcut'):
                tree._handle_cut_shortcut()
                event.accept()
                return
        elif key == Qt.Key.Key_V:
            if hasattr(tree, '_handle_paste_shortcut'):
                tree._handle_paste_shortcut()
                event.accept()
                return

        super().keyPressEvent(event)

    # --- Process Step Handlers ---

    def _on_add_process_step(self, assembly_id: int):
        """Add a process step to an assembly."""
        from ui.dialogs.process_step_dialog import ProcessStepDialog

        dialog = ProcessStepDialog(self, assembly_id=assembly_id)
        if dialog.exec():
            self._refresh_data()
            self.statusBar().showMessage("Process step added")

    def _on_edit_process_step(self, step_id: int):
        """Edit an existing process step."""
        from ui.dialogs.process_step_dialog import ProcessStepDialog

        dialog = ProcessStepDialog(self, step_id=step_id)
        if dialog.exec():
            self._refresh_data()
            self.statusBar().showMessage("Process step updated")

    def _on_delete_process_step(self, step_id: int):
        """Delete a process step and renumber remaining steps."""
        with session_scope() as session:
            step = session.query(AssemblyProcessStep).get(step_id)
            if not step:
                return
            desc = step.description
            assembly_id = step.assembly_id

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete step: '{desc}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        with session_scope() as session:
            step = session.query(AssemblyProcessStep).get(step_id)
            if not step:
                return
            assembly_id = step.assembly_id
            session.delete(step)
            session.flush()

            # Renumber remaining steps
            remaining = session.query(AssemblyProcessStep).filter(
                AssemblyProcessStep.assembly_id == assembly_id
            ).order_by(AssemblyProcessStep.step_number).all()
            for i, s in enumerate(remaining, start=1):
                s.step_number = i

        self._refresh_data()
        self.statusBar().showMessage("Process step deleted")

    def _on_move_process_step(self, step_id: int, direction: str):
        """Move a process step up or down by swapping step_number with neighbor."""
        with session_scope() as session:
            step = session.query(AssemblyProcessStep).get(step_id)
            if not step:
                return

            all_steps = session.query(AssemblyProcessStep).filter(
                AssemblyProcessStep.assembly_id == step.assembly_id
            ).order_by(AssemblyProcessStep.step_number).all()

            idx = next((i for i, s in enumerate(all_steps) if s.id == step_id), None)
            if idx is None:
                return

            if direction == "up" and idx > 0:
                neighbor = all_steps[idx - 1]
            elif direction == "down" and idx < len(all_steps) - 1:
                neighbor = all_steps[idx + 1]
            else:
                return

            # Swap step numbers
            step.step_number, neighbor.step_number = neighbor.step_number, step.step_number

        self._refresh_data()

    def closeEvent(self, event):
        """Handle window close event."""
        # RFQDetailWindow is a QMainWindow, just close normally
        event.accept()
