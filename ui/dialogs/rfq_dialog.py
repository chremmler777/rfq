"""RFQ creation and editing dialog."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTextEdit, QPushButton, QMessageBox, QSpinBox, QDateEdit, QDoubleSpinBox,
    QScrollArea, QFrame, QWidget, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtCore import Qt, QDate
from datetime import datetime
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
# Ensure white background style
import matplotlib as mpl
mpl.rcParams['figure.facecolor'] = 'white'
mpl.rcParams['axes.facecolor'] = 'white'
mpl.rcParams['figure.edgecolor'] = 'white'

from database import RFQStatus, AnnualDemand
from database.connection import session_scope
from database.models import RFQ


class RFQDialog(QDialog):
    """Dialog for creating/editing RFQs."""

    def __init__(self, parent=None, rfq_id: int = None):
        super().__init__(parent)
        self.rfq_id = rfq_id  # ID for loading existing RFQ
        self.rfq = None
        self._saved_rfq_id = None  # Track saved RFQ ID to avoid detached instance errors
        self.annual_demand_widgets = {}  # Store year inputs: {year: (volume_spin, flex_spin)}

        self.setWindowTitle("RFQ" if not rfq_id else "Edit RFQ")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self.setModal(True)

        self._load_rfq()
        self._setup_ui()

    def _load_rfq(self):
        """Load existing RFQ if editing."""
        if self.rfq_id:
            with session_scope() as session:
                self.rfq = session.query(RFQ).get(self.rfq_id)
                # Detach from session and load relationships
                if self.rfq:
                    session.expunge(self.rfq)

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Name
        layout.addWidget(QLabel("RFQ Name *"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Customer Project A - 2025")
        if self.rfq:
            self.name_input.setText(self.rfq.name)
        layout.addWidget(self.name_input)

        # Customer
        layout.addWidget(QLabel("Customer *"))
        self.customer_input = QLineEdit()
        self.customer_input.setPlaceholderText("Customer name")
        if self.rfq:
            self.customer_input.setText(self.rfq.customer or "")
        layout.addWidget(self.customer_input)

        # Status
        layout.addWidget(QLabel("Status"))
        self.status_combo = QComboBox()
        self.status_combo.addItems([s.value for s in RFQStatus])
        if self.rfq:
            self.status_combo.setCurrentText(self.rfq.status)
        layout.addWidget(self.status_combo)

        # Demand planning (project-level)
        layout.addWidget(QLabel("<b>Demand Planning (Project-Level)</b>"))

        # SOP Row (just dates for defining the range)
        sop_row = QHBoxLayout()
        sop_row.addWidget(QLabel("SOP Start Date"))
        self.sop_date = QDateEdit()
        self.sop_date.setCalendarPopup(True)
        self.sop_date.setDate(QDate.currentDate())
        if self.rfq and self.rfq.demand_sop_date:
            self.sop_date.setDate(QDate(self.rfq.demand_sop_date.year, self.rfq.demand_sop_date.month, self.rfq.demand_sop_date.day))
        sop_row.addWidget(self.sop_date)
        sop_row.addStretch()
        layout.addLayout(sop_row)

        # EAOP Row (just dates for defining the range)
        eaop_row = QHBoxLayout()
        eaop_row.addWidget(QLabel("EAOP End Date"))
        self.eaop_date = QDateEdit()
        self.eaop_date.setCalendarPopup(True)
        self.eaop_date.setDate(QDate.currentDate())
        if self.rfq and self.rfq.demand_eaop_date:
            self.eaop_date.setDate(QDate(self.rfq.demand_eaop_date.year, self.rfq.demand_eaop_date.month, self.rfq.demand_eaop_date.day))
        eaop_row.addWidget(self.eaop_date)
        eaop_row.addStretch()
        layout.addLayout(eaop_row)

        # Connect date changes to regenerate annual demands
        self.sop_date.dateChanged.connect(self._regenerate_annual_demands)
        self.eaop_date.dateChanged.connect(self._regenerate_annual_demands)

        # Global Flex % capacity
        flex_row = QHBoxLayout()
        flex_row.addWidget(QLabel("Capacity Flex %"))
        self.flex_spin = QDoubleSpinBox()
        self.flex_spin.setRange(10, 500)
        self.flex_spin.setValue(100)
        self.flex_spin.setDecimals(0)
        self.flex_spin.setMaximumWidth(100)
        if self.rfq and self.rfq.flex_percent:
            self.flex_spin.setValue(self.rfq.flex_percent)
        flex_row.addWidget(self.flex_spin)
        flex_row.addWidget(QLabel("(applies to all years)"))
        flex_row.addStretch()
        layout.addLayout(flex_row)

        # Annual demand breakdown section (using table instead of scroll)
        layout.addWidget(QLabel("<b>Annual Demand Breakdown</b>"))

        # Horizontal layout: table on left, chart on right
        demand_layout = QHBoxLayout()

        # Table on left
        self.annual_demand_table = QTableWidget()
        self.annual_demand_table.setColumnCount(3)
        self.annual_demand_table.setHorizontalHeaderLabels(["Year", "Volume (pcs)", "w/ Flex"])
        self.annual_demand_table.setMaximumHeight(250)
        self.annual_demand_table.setMinimumWidth(400)
        self.annual_demand_table.horizontalHeader().setStretchLastSection(True)
        demand_layout.addWidget(self.annual_demand_table, stretch=1)

        # Chart on right
        self.demand_figure = Figure(figsize=(3, 2.5), dpi=100)
        self.demand_canvas = FigureCanvas(self.demand_figure)
        self.demand_canvas.setMaximumWidth(350)
        demand_layout.addWidget(self.demand_canvas, stretch=0)

        layout.addLayout(demand_layout)

        # Lifetime summary
        self.lifetime_summary_label = QLabel()
        self.lifetime_summary_label.setStyleSheet("background-color: #e8f4f8; color: #004a6d; font-weight: bold; font-size: 12px; padding: 10px; border-radius: 4px; border-left: 4px solid #0088cc;")
        layout.addWidget(self.lifetime_summary_label)

        # Generate initial annual demand rows
        self._regenerate_annual_demands()

        # Notes
        layout.addWidget(QLabel("Notes"))
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Additional notes...")
        self.notes_input.setMaximumHeight(100)
        if self.rfq:
            self.notes_input.setPlainText(self.rfq.notes or "")
        layout.addWidget(self.notes_input)

        # Buttons
        button_layout = QHBoxLayout()

        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self._on_save)
        button_layout.addWidget(self.btn_save)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)

        layout.addStretch()
        layout.addLayout(button_layout)

    def _on_save(self):
        """Save RFQ."""
        name = self.name_input.text().strip()
        customer = self.customer_input.text().strip()
        status = self.status_combo.currentText()
        notes = self.notes_input.toPlainText().strip()

        # Get SOP/EAOP from table (first and last year volumes)
        demand_sop = None
        demand_eaop = None
        if self.annual_demand_table.rowCount() > 0:
            # Get first year volume
            first_widget = self.annual_demand_table.cellWidget(0, 1)
            if first_widget:
                demand_sop = first_widget.value() or None
            # Get last year volume
            last_row = self.annual_demand_table.rowCount() - 1
            last_widget = self.annual_demand_table.cellWidget(last_row, 1)
            if last_widget:
                demand_eaop = last_widget.value() or None

        demand_sop_date = datetime(self.sop_date.date().year(), self.sop_date.date().month(), self.sop_date.date().day())
        demand_eaop_date = datetime(self.eaop_date.date().year(), self.eaop_date.date().month(), self.eaop_date.date().day())
        flex_percent = self.flex_spin.value()

        if not name:
            QMessageBox.warning(self, "Validation", "RFQ name is required")
            return

        if not customer:
            QMessageBox.warning(self, "Validation", "Customer name is required")
            return

        try:
            rfq_id = None
            with session_scope() as session:
                if self.rfq:
                    # Update existing - need to get fresh instance from DB
                    rfq = session.query(RFQ).get(self.rfq.id)
                    rfq.name = name
                    rfq.customer = customer
                    rfq.status = status
                    rfq.notes = notes or None
                    rfq.demand_sop = demand_sop
                    rfq.demand_sop_date = demand_sop_date
                    rfq.demand_eaop = demand_eaop
                    rfq.demand_eaop_date = demand_eaop_date
                    rfq.flex_percent = flex_percent
                    rfq_id = rfq.id  # Capture ID while in session
                    self.rfq = rfq
                else:
                    # Create new
                    self.rfq = RFQ(
                        name=name,
                        customer=customer,
                        status=status,
                        notes=notes or None,
                        demand_sop=demand_sop,
                        demand_sop_date=demand_sop_date,
                        demand_eaop=demand_eaop,
                        demand_eaop_date=demand_eaop_date,
                        flex_percent=flex_percent
                    )
                    session.add(self.rfq)
                    session.flush()
                    rfq_id = self.rfq.id  # Capture ID while in session

            # Save annual demands after RFQ is created/updated
            if rfq_id:
                self._saved_rfq_id = rfq_id  # Store for later use
                self._save_annual_demands(rfq_id)

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save RFQ: {str(e)}")
            import traceback
            traceback.print_exc()

    def _regenerate_annual_demands(self):
        """Generate annual demand table based on SOP/EAOP dates."""
        # Clear existing data
        self.annual_demand_widgets.clear()
        self.annual_demand_table.setRowCount(0)

        sop_date = self.sop_date.date()
        eaop_date = self.eaop_date.date()

        sop_year = sop_date.year()
        eaop_year = eaop_date.year()

        if sop_year > eaop_year:
            self.lifetime_summary_label.setText("(SOP date must be before EAOP date)")
            return

        # Load existing annual demands if editing
        existing_demands = {}
        load_rfq_id = self._saved_rfq_id or self.rfq_id
        if load_rfq_id:
            with session_scope() as session:
                rfq = session.query(RFQ).get(load_rfq_id)
                if rfq:
                    for ad in rfq.annual_demands:
                        existing_demands[ad.year] = ad.volume or 0

        # Generate table rows for each year
        lifetime_total = 0
        for year in range(sop_year, eaop_year + 1):
            row = self.annual_demand_table.rowCount()
            self.annual_demand_table.insertRow(row)

            # Year cell (read-only)
            year_cell = QTableWidgetItem(str(year))
            year_cell.setFlags(year_cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.annual_demand_table.setItem(row, 0, year_cell)

            # Volume input
            volume_spin = QSpinBox()
            volume_spin.setRange(0, 10000000)
            volume_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
            volume_spin.setGroupSeparatorShown(True)
            if year in existing_demands:
                volume_spin.setValue(existing_demands[year])
            # Connect volume changes to update flex display
            volume_spin.valueChanged.connect(self._update_flex_display)

            self.annual_demand_table.setCellWidget(row, 1, volume_spin)

            # Flex calculation (updated dynamically)
            flex_cell = QTableWidgetItem()
            flex_cell.setFlags(flex_cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            flex_cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.annual_demand_table.setItem(row, 2, flex_cell)

            # Store reference for later saving
            self.annual_demand_widgets[year] = volume_spin

            # Add to lifetime total
            lifetime_total += existing_demands.get(year, 0)

        # Update flex display for all rows
        self._update_flex_display()

        # Connect flex % changes to update display (only once)
        try:
            self.flex_spin.valueChanged.disconnect()
        except TypeError:
            pass
        self.flex_spin.valueChanged.connect(self._update_flex_display)

    def _update_flex_display(self):
        """Update the flex calculation in table and summary."""
        flex_percent = int(self.flex_spin.value())
        lifetime_total = 0
        lifetime_with_flex = 0

        for row in range(self.annual_demand_table.rowCount()):
            # Get volume from spinbox
            volume_widget = self.annual_demand_table.cellWidget(row, 1)
            if volume_widget:
                volume = volume_widget.value()
                lifetime_total += volume

                # Calculate with flex: volume * (100 + flex) / 100
                # 100% flex = 2x capacity, 50% flex = 1.5x, 0% = exactly demand
                flex_volume = int(volume * (100 + flex_percent) / 100)
                flex_cell = self.annual_demand_table.item(row, 2)
                if flex_cell is not None:
                    flex_cell.setText(f"{flex_volume:,}")
                    flex_cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                lifetime_with_flex += flex_volume

        # Update summary
        summary = f"Lifetime: {lifetime_total:,} pcs | With Flex (+{flex_percent}%): {lifetime_with_flex:,} pcs"
        self.lifetime_summary_label.setText(summary)

        # Update chart
        self._update_demand_chart()

    def _update_demand_chart(self):
        """Update the lifetime demand barchart."""
        self.demand_figure.clear()

        # Set figure and axes colors to white explicitly
        self.demand_figure.patch.set_facecolor('white')
        self.demand_figure.patch.set_edgecolor('white')

        # Collect data from table
        years = []
        volumes = []

        for row in range(self.annual_demand_table.rowCount()):
            year_item = self.annual_demand_table.item(row, 0)
            volume_widget = self.annual_demand_table.cellWidget(row, 1)

            if year_item and volume_widget:
                years.append(year_item.text())
                volumes.append(volume_widget.value())

        # Only draw if there's data
        if not years:
            self.demand_canvas.draw()
            return

        # Create bar chart
        ax = self.demand_figure.add_subplot(111)
        ax.patch.set_facecolor('white')
        ax.patch.set_edgecolor('white')
        bars = ax.bar(years, volumes, color='#0088cc', edgecolor='#004a6d', linewidth=1.5, alpha=0.8)

        # Format
        ax.set_ylabel('Volume (pcs)', fontsize=9, color='#333')
        ax.set_xlabel('Year', fontsize=9, color='#333')
        ax.set_title('Annual Demand', fontsize=10, fontweight='bold', color='#004a6d')
        ax.tick_params(labelsize=8, colors='#333')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#999')
        ax.spines['bottom'].set_color('#999')
        ax.grid(axis='y', alpha=0.3, linestyle='--', color='#ddd')

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height):,}',
                       ha='center', va='bottom', fontsize=8, color='#004a6d')

        # Layout adjustments
        self.demand_figure.tight_layout(pad=0.5)
        self.demand_canvas.draw()

    def _save_annual_demands(self, rfq_id: int):
        """Save annual demand entries to database."""
        with session_scope() as session:
            # Delete existing annual demands
            session.query(AnnualDemand).filter(AnnualDemand.rfq_id == rfq_id).delete()

            # Create new annual demand entries from table rows
            saved_count = 0
            for row in range(self.annual_demand_table.rowCount()):
                # Get volume from spinbox widget
                volume_widget = self.annual_demand_table.cellWidget(row, 1)
                if not volume_widget:
                    continue

                volume = volume_widget.value()
                if volume > 0:  # Only save if volume is > 0
                    year_text = self.annual_demand_table.item(row, 0).text()
                    try:
                        year = int(year_text)
                        ad = AnnualDemand(
                            rfq_id=rfq_id,
                            year=year,
                            volume=volume
                        )
                        session.add(ad)
                        saved_count += 1
                    except (ValueError, TypeError):
                        pass

            # Debug: Print how many were saved
            if saved_count == 0:
                print(f"Warning: No annual demands saved for RFQ {rfq_id}")

    def get_rfq(self) -> RFQ:
        """Return the created/edited RFQ."""
        return self.rfq
