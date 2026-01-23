"""Tool configuration dialog with 5 tabs for comprehensive tool management."""

from typing import Optional, List, Dict
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTextEdit, QPushButton, QMessageBox, QSpinBox, QDoubleSpinBox,
    QScrollArea, QFrame, QTabWidget, QWidget, QCheckBox
)
from PyQt6.QtCore import Qt

from database import NozzleType, DegateOption, EOATType, ToolPartConfiguration
from database.connection import session_scope
from database.models import Tool, Material, Machine, RFQ, ToolType, InjectionSystem, SurfaceFinish
from calculations import (
    calculate_shot_volume, calculate_barrel_usage,
    check_screw_diameter_ratio, calculate_tool_totals
)
from ..widgets.part_assignment_widget import PartAssignmentWidget


class ToolDialog(QDialog):
    """Dialog for creating/editing tools with part assignments and calculations."""

    def __init__(self, parent=None, rfq_id: int = None, tool_id: int = None):
        super().__init__(parent)
        self.rfq_id = rfq_id
        self.tool_id = tool_id
        self.tool = None
        self._saved_tool_id = None

        self.setWindowTitle("Add Tool" if not tool_id else "Edit Tool")
        self.setMinimumWidth(1000)
        self.setMinimumHeight(800)
        self.setModal(True)

        if tool_id:
            self._load_tool()

        self._setup_ui()

    def _load_tool(self):
        """Load existing tool if editing."""
        if self.tool_id:
            with session_scope() as session:
                # Eagerly load part_configurations before detaching
                from sqlalchemy.orm import joinedload
                self.tool = session.query(Tool).options(
                    joinedload(Tool.part_configurations)
                ).filter(Tool.id == self.tool_id).first()

                if self.tool:
                    # Deep copy the part configurations to avoid detached instance errors
                    if self.tool.part_configurations:
                        self.tool._loaded_configs = [
                            {
                                'id': pc.id,
                                'part_id': pc.part_id,
                                'part_name': pc.part.name if pc.part else "Unknown",
                                'cavities': pc.cavities,
                                'lifters_count': pc.lifters_count,
                                'sliders_count': pc.sliders_count,
                                'config_group_id': pc.config_group_id
                            }
                            for pc in self.tool.part_configurations
                        ]
                    session.expunge(self.tool)

    def _setup_ui(self):
        """Setup the dialog UI."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        main_widget = QFrame()
        layout = QVBoxLayout(main_widget)

        # Tab widget for organized sections
        self.tabs = QTabWidget()

        # ===== TAB 1: Basic Info =====
        basic_widget = self._create_basic_tab()
        self.tabs.addTab(basic_widget, "Basic Info")

        # ===== TAB 2: Part Assignments =====
        assign_widget = self._create_assignment_tab()
        self.tabs.addTab(assign_widget, "Part Assignments")

        # ===== TAB 3: Injection System =====
        inject_widget = self._create_injection_tab()
        self.tabs.addTab(inject_widget, "Injection System")

        # ===== TAB 4: Manufacturing =====
        mfg_widget = self._create_mfg_tab()
        self.tabs.addTab(mfg_widget, "Manufacturing")

        # ===== TAB 5: Calculations =====
        calc_widget = self._create_calculations_tab()
        self.tabs.addTab(calc_widget, "Calculations")

        layout.addWidget(self.tabs)
        scroll.setWidget(main_widget)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        # Buttons
        button_layout = QHBoxLayout()

        self.btn_save = QPushButton("Save Tool")
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

        layout.addWidget(QLabel("Tool Name (auto-generated from parts)"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Auto-generated from assigned parts")
        if self.tool:
            self.name_input.setText(self.tool.name)
        layout.addWidget(self.name_input)

        # Button to auto-generate name
        btn_auto_gen = QPushButton("Auto-Generate Name from Parts")
        btn_auto_gen.clicked.connect(self._on_auto_generate_name)
        layout.addWidget(btn_auto_gen)

        layout.addSpacing(10)

        layout.addWidget(QLabel("Tool Type"))
        self.tool_type_combo = QComboBox()
        self.tool_type_combo.addItem("Single Part", ToolType.SINGLE.value)
        self.tool_type_combo.addItem("Family Tool", ToolType.FAMILY.value)
        if self.tool:
            index = self.tool_type_combo.findData(self.tool.tool_type)
            if index >= 0:
                self.tool_type_combo.setCurrentIndex(index)
        layout.addWidget(self.tool_type_combo)

        # Machine assignment
        layout.addWidget(QLabel("Machine Assignment"))
        self.machine_combo = QComboBox()
        self.machine_combo.addItem("- No machine assigned -", None)
        with session_scope() as session:
            machines = session.query(Machine).order_by(Machine.clamping_force_kn).all()
            for machine in machines:
                self.machine_combo.addItem(
                    f"{machine.name} ({machine.clamping_force_kn}kN)",
                    machine.id
                )
        if self.tool and self.tool.machine_id:
            index = self.machine_combo.findData(self.tool.machine_id)
            if index >= 0:
                self.machine_combo.setCurrentIndex(index)
        layout.addWidget(self.machine_combo)

        # Tool dimensions
        dim_layout = QHBoxLayout()
        dim_layout.addWidget(QLabel("Length (mm):"))
        self.length_spin = QDoubleSpinBox()
        self.length_spin.setRange(0, 10000)
        if self.tool and self.tool.tool_length_mm:
            self.length_spin.setValue(self.tool.tool_length_mm)
        dim_layout.addWidget(self.length_spin)

        dim_layout.addWidget(QLabel("Width (mm):"))
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0, 10000)
        if self.tool and self.tool.tool_width_mm:
            self.width_spin.setValue(self.tool.tool_width_mm)
        dim_layout.addWidget(self.width_spin)

        dim_layout.addWidget(QLabel("Height (mm):"))
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(0, 10000)
        if self.tool and self.tool.tool_height_mm:
            self.height_spin.setValue(self.tool.tool_height_mm)
        dim_layout.addWidget(self.height_spin)

        layout.addLayout(dim_layout)

        # Surface finish
        layout.addWidget(QLabel("Surface Finish"))
        self.surface_combo = QComboBox()
        for sf in SurfaceFinish:
            self.surface_combo.addItem(sf.value.replace("_", " ").title(), sf.value)
        if self.tool:
            index = self.surface_combo.findData(self.tool.surface_finish)
            if index >= 0:
                self.surface_combo.setCurrentIndex(index)
        layout.addWidget(self.surface_combo)

        layout.addWidget(QLabel("Notes"))
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(100)
        if self.tool and self.tool.notes:
            self.notes_input.setPlainText(self.tool.notes)
        layout.addWidget(self.notes_input)

        layout.addStretch()
        return tab

    def _create_assignment_tab(self) -> QWidget:
        """Create part assignment tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        if not self.rfq_id:
            layout.addWidget(QLabel("No RFQ selected"))
            layout.addStretch()
            return tab

        # Use the part assignment widget with callback for auto-naming
        self.part_assignment = PartAssignmentWidget(
            self.rfq_id,
            self,
            on_config_changed=self._auto_update_tool_name
        )

        # Load existing assignments if editing
        if self.tool and hasattr(self.tool, '_loaded_configs') and self.tool._loaded_configs:
            configs = [
                {
                    'part_id': pc['part_id'],
                    'part_name': pc['part_name'],
                    'cavities': pc['cavities'],
                    'lifters_count': pc['lifters_count'],
                    'sliders_count': pc['sliders_count'],
                    'config_group_id': pc['config_group_id']
                }
                for pc in self.tool._loaded_configs
            ]
            self.part_assignment.set_part_configurations(configs)

        layout.addWidget(self.part_assignment)
        return tab

    def _auto_update_tool_name(self):
        """Auto-update tool name when parts change (callback from part_assignment)."""
        if not hasattr(self, 'part_assignment'):
            return

        part_configs = self.part_assignment.get_part_configurations()
        if not part_configs:
            return

        # Generate name from parts and cavity count
        part_names = [c['part_name'] for c in part_configs]
        total_cavities = sum(c.get('cavities', 1) for c in part_configs)

        # Format: "Part1 + Part2 4-cav" or just "Part1 4-cav"
        if len(part_names) > 1:
            name = f"{' + '.join(part_names)} {total_cavities}-cav"
        else:
            name = f"{part_names[0]} {total_cavities}-cav"

        # Limit length
        if len(name) > 100:
            name = name[:97] + "..."

        self.name_input.setText(name)

    def _create_injection_tab(self) -> QWidget:
        """Create injection system configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("Injection System Type"))
        self.inj_system_combo = QComboBox()
        for inj_sys in InjectionSystem:
            self.inj_system_combo.addItem(inj_sys.value.replace("_", " ").title(), inj_sys.value)
        if self.tool:
            index = self.inj_system_combo.findData(self.tool.injection_system)
            if index >= 0:
                self.inj_system_combo.setCurrentIndex(index)
        layout.addWidget(self.inj_system_combo)

        layout.addWidget(QLabel("Nozzle Type (V2.0)"))
        self.nozzle_combo = QComboBox()
        for nozzle in NozzleType:
            self.nozzle_combo.addItem(nozzle.value.replace("_", " ").title(), nozzle.value)
        if self.tool:
            index = self.nozzle_combo.findData(self.tool.nozzle_type)
            if index >= 0:
                self.nozzle_combo.setCurrentIndex(index)
        layout.addWidget(self.nozzle_combo)

        # Hot runner nozzle count
        hr_layout = QHBoxLayout()
        hr_layout.addWidget(QLabel("Hot Runner Nozzle Count:"))
        self.nozzle_count_spin = QSpinBox()
        self.nozzle_count_spin.setRange(0, 100)
        if self.tool:
            self.nozzle_count_spin.setValue(self.tool.hot_runner_nozzle_count)
        hr_layout.addWidget(self.nozzle_count_spin)
        hr_layout.addStretch()
        layout.addLayout(hr_layout)

        # Injection points
        inj_layout = QHBoxLayout()
        inj_layout.addWidget(QLabel("Injection Points:"))
        self.injection_points_spin = QSpinBox()
        self.injection_points_spin.setRange(0, 100)
        if self.tool and self.tool.injection_points:
            self.injection_points_spin.setValue(self.tool.injection_points)
        inj_layout.addWidget(self.injection_points_spin)
        inj_layout.addStretch()
        layout.addLayout(inj_layout)

        layout.addWidget(QLabel("Runner Type / Notes"))
        self.runner_input = QTextEdit()
        self.runner_input.setMaximumHeight(80)
        if self.tool and self.tool.runner_type:
            self.runner_input.setPlainText(self.tool.runner_type)
        layout.addWidget(self.runner_input)

        layout.addStretch()
        return tab

    def _create_mfg_tab(self) -> QWidget:
        """Create manufacturing options tab (moved from Part level)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("<b>Manufacturing Options (V2.0 - Moved from Part level)</b>"))
        layout.addSpacing(10)

        # Degate
        layout.addWidget(QLabel("Degate"))
        self.degate_combo = QComboBox()
        for degate in DegateOption:
            self.degate_combo.addItem(degate.value.capitalize(), degate.value)
        if self.tool:
            index = self.degate_combo.findData(self.tool.degate)
            if index >= 0:
                self.degate_combo.setCurrentIndex(index)
        layout.addWidget(self.degate_combo)

        # EOAT Type
        layout.addWidget(QLabel("EOAT Type"))
        self.eoat_combo = QComboBox()
        for eoat in EOATType:
            self.eoat_combo.addItem(eoat.value.capitalize(), eoat.value)
        if self.tool:
            index = self.eoat_combo.findData(self.tool.eoat_type)
            if index >= 0:
                self.eoat_combo.setCurrentIndex(index)
        layout.addWidget(self.eoat_combo)

        layout.addSpacing(20)
        layout.addWidget(QLabel("<b>Pressure Override (V2.0)</b>"))

        # Manual pressure override
        pressure_layout = QHBoxLayout()
        pressure_layout.addWidget(QLabel("Manual Pressure Override (bar):"))
        self.manual_pressure_spin = QDoubleSpinBox()
        self.manual_pressure_spin.setRange(0, 3000)
        self.manual_pressure_spin.setDecimals(0)
        if self.tool and self.tool.manual_pressure_bar:
            self.manual_pressure_spin.setValue(self.tool.manual_pressure_bar)
        pressure_layout.addWidget(self.manual_pressure_spin)
        pressure_layout.addWidget(QLabel("(0 = use material default)"))
        pressure_layout.addStretch()
        layout.addLayout(pressure_layout)

        layout.addStretch()
        return tab

    def _create_calculations_tab(self) -> QWidget:
        """Create calculations preview tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("<b>Calculation Previews</b>"))

        self.calc_display = QTextEdit()
        self.calc_display.setReadOnly(True)
        self.calc_display.setStyleSheet("background-color: #f5f5f5; font-family: monospace;")
        layout.addWidget(self.calc_display)

        # Button to refresh calculations
        btn_update_calc = QPushButton("Update Calculations")
        btn_update_calc.clicked.connect(self._update_calculations)
        layout.addWidget(btn_update_calc)

        self._update_calculations()

        return tab

    def _on_auto_generate_name(self):
        """Auto-generate tool name from assigned parts."""
        if not hasattr(self, 'part_assignment'):
            QMessageBox.warning(self, "No Parts", "Add parts in the Part Assignments tab first")
            return

        part_configs = self.part_assignment.get_part_configurations()
        if not part_configs:
            QMessageBox.warning(self, "No Parts", "No parts assigned to this tool")
            return

        # Generate name from parts and cavity count
        part_names = [c['part_name'] for c in part_configs]
        total_cavities = sum(c.get('cavities', 1) for c in part_configs)

        # Format: "Part1 + Part2 4-cav" or just "Part1 4-cav"
        if len(part_names) > 1:
            name = f"{' + '.join(part_names)} {total_cavities}-cav"
        else:
            name = f"{part_names[0]} {total_cavities}-cav"

        # Limit length
        if len(name) > 100:
            name = name[:97] + "..."

        self.name_input.setText(name)
        QMessageBox.information(self, "Name Generated", f"Tool name: {name}")

    def _update_calculations(self):
        """Update calculation previews."""
        if not hasattr(self, 'part_assignment'):
            self.calc_display.setText("No part assignments yet")
            return

        part_configs = self.part_assignment.get_part_configurations()
        if not part_configs:
            self.calc_display.setText("Status: ⚠️ UNDEFINED - No parts assigned to this tool\n\nAdd parts in the 'Part Assignments' tab to define this tool.")
            return

        calc_text = ""
        calc_text += "Status: ✓ DEFINED - Tool has " + str(len(part_configs)) + " part(s) assigned\n\n"
        calc_text += "=== SHOT VOLUME CALCULATION ===\n"

        # Create temporary config objects for calculation
        class TempConfig:
            def __init__(self, config_dict):
                self.cavities = config_dict.get('cavities', 1)
                self.lifters_count = config_dict.get('lifters_count', 0)
                self.sliders_count = config_dict.get('sliders_count', 0)
                self.part = None
                # Load part from DB
                with session_scope() as session:
                    from database.models import Part
                    part = session.query(Part).get(config_dict.get('part_id'))
                    if part:
                        self.part = type('Part', (), {
                            'name': part.name,
                            'volume_cm3': part.volume_cm3
                        })()

        temp_configs = [TempConfig(c) for c in part_configs]
        shot_result = calculate_shot_volume(temp_configs, runner_percent=15.0)

        calc_text += f"Parts volume: {sum(c.part.volume_cm3 * c.cavities if c.part else 0 for c in temp_configs):.1f} cm³\n"
        calc_text += f"Runner (15%): {shot_result.runner_cm3:.1f} cm³\n"
        calc_text += f"Total shot: {shot_result.total_cm3:.1f} cm³\n\n"

        # Barrel usage
        machine_id = self.machine_combo.currentData()
        if machine_id:
            with session_scope() as session:
                machine = session.query(Machine).get(machine_id)
                if machine and machine.barrel_volume_cm3:
                    barrel_result = calculate_barrel_usage(
                        shot_result.total_cm3,
                        machine.barrel_volume_cm3
                    )
                    calc_text += "=== BARREL USAGE ===\n"
                    calc_text += barrel_result.message + "\n\n"

                    # Screw ratio check
                    if machine.max_injection_stroke_mm and machine.screw_diameter_mm:
                        screw_result = check_screw_diameter_ratio(
                            machine.max_injection_stroke_mm,
                            machine.screw_diameter_mm
                        )
                        calc_text += "=== SCREW DIAMETER RATIO ===\n"
                        calc_text += screw_result.message + "\n\n"

        # Tool totals
        calc_text += "=== TOOL TOTALS ===\n"
        total_cav = sum(c.get('cavities', 1) for c in part_configs)
        total_lift = sum(c.get('lifters_count', 0) for c in part_configs)
        total_slid = sum(c.get('sliders_count', 0) for c in part_configs)
        calc_text += f"Total cavities: {total_cav}\n"
        calc_text += f"Total lifters: {total_lift}\n"
        calc_text += f"Total sliders: {total_slid}\n"

        self.calc_display.setText(calc_text)

    def _on_save(self):
        """Save tool."""
        name = self.name_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Validation", "Tool name is required")
            return

        tool_type = self.tool_type_combo.currentData()
        machine_id = self.machine_combo.currentData()

        try:
            with session_scope() as session:
                if self.tool:
                    # Update existing
                    tool = session.query(Tool).get(self.tool.id)

                    tool.name = name
                    tool.tool_type = tool_type
                    tool.machine_id = machine_id
                    tool.tool_length_mm = self.length_spin.value() or None
                    tool.tool_width_mm = self.width_spin.value() or None
                    tool.tool_height_mm = self.height_spin.value() or None
                    tool.surface_finish = self.surface_combo.currentData()
                    tool.injection_system = self.inj_system_combo.currentData()
                    tool.nozzle_type = self.nozzle_combo.currentData()
                    tool.hot_runner_nozzle_count = self.nozzle_count_spin.value()
                    tool.injection_points = self.injection_points_spin.value() or None
                    tool.runner_type = self.runner_input.toPlainText().strip() or None
                    tool.degate = self.degate_combo.currentData()
                    tool.eoat_type = self.eoat_combo.currentData()
                    tool.manual_pressure_bar = self.manual_pressure_spin.value() or None
                    tool.notes = self.notes_input.toPlainText().strip() or None

                    # Clear and update part configurations
                    session.query(ToolPartConfiguration).filter(
                        ToolPartConfiguration.tool_id == tool.id
                    ).delete()

                    self._saved_tool_id = tool.id
                else:
                    # Create new
                    tool = Tool(
                        name=name,
                        tool_type=tool_type,
                        machine_id=machine_id,
                        tool_length_mm=self.length_spin.value() or None,
                        tool_width_mm=self.width_spin.value() or None,
                        tool_height_mm=self.height_spin.value() or None,
                        surface_finish=self.surface_combo.currentData(),
                        injection_system=self.inj_system_combo.currentData(),
                        nozzle_type=self.nozzle_combo.currentData(),
                        hot_runner_nozzle_count=self.nozzle_count_spin.value(),
                        injection_points=self.injection_points_spin.value() or None,
                        runner_type=self.runner_input.toPlainText().strip() or None,
                        degate=self.degate_combo.currentData(),
                        eoat_type=self.eoat_combo.currentData(),
                        manual_pressure_bar=self.manual_pressure_spin.value() or None,
                        notes=self.notes_input.toPlainText().strip() or None
                    )
                    session.add(tool)
                    session.flush()
                    self._saved_tool_id = tool.id

                # Save part configurations
                part_configs = self.part_assignment.get_part_configurations()
                for i, config in enumerate(part_configs):
                    pc = ToolPartConfiguration(
                        tool_id=self._saved_tool_id,
                        part_id=config['part_id'],
                        cavities=config.get('cavities', 1),
                        lifters_count=config.get('lifters_count', 0),
                        sliders_count=config.get('sliders_count', 0),
                        config_group_id=config.get('config_group_id'),
                        position=i
                    )
                    session.add(pc)

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save tool: {str(e)}")
