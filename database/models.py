"""SQLAlchemy ORM models for RFQ Tool Quoting Software."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Table, Enum
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
import enum


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class RFQStatus(enum.Enum):
    """Status options for RFQs."""
    DRAFT = "draft"
    QUOTED = "quoted"
    ORDERED = "ordered"
    CLOSED = "closed"


class InjectionSystem(enum.Enum):
    """Injection system types."""
    COLD_RUNNER = "cold_runner"
    HOT_RUNNER = "hot_runner"
    VALVE_GATE = "valve_gate"


class SurfaceFinish(enum.Enum):
    """Surface finish types."""
    DRAW_POLISH = "draw_polish"
    POLISH = "polish"
    HIGH_POLISH = "high_polish"
    GRAIN = "grain"
    TECHNICAL_POLISH = "technical_polish"
    EDM = "edm"


class ToolType(enum.Enum):
    """Tool types."""
    SINGLE = "single"
    FAMILY = "family"


class DegateOption(enum.Enum):
    """Degate options."""
    YES = "yes"
    NO = "no"
    MAYBE = "maybe"


class EOATType(enum.Enum):
    """EOAT complexity type."""
    STANDARD = "standard"
    COMPLEX = "complex"


class NozzleType(enum.Enum):
    """Injection nozzle types for tools."""
    HEATED_SPRUE = "heated_sprue"
    HOT_RUNNER = "hot_runner"
    NEEDLE_VALVE = "needle_valve"
    DIRECT_INJECTION = "direct_injection"
    SUBGATED = "subgated"
    COLD_RUNNER = "cold_runner"


# Legacy junction table for family tools (kept for backwards compatibility)
# New code should use ToolPartConfiguration for more detailed tool-part relationships
tool_parts = Table(
    'tool_parts',
    Base.metadata,
    Column('tool_id', Integer, ForeignKey('tools.id'), primary_key=True),
    Column('part_id', Integer, ForeignKey('parts.id'), primary_key=True)
)


class ToolPartConfiguration(Base):
    """Detailed tool-part configuration for family tools and multi-cavity setups.

    This model provides:
    - Per-part cavity count within a tool
    - Per-part lifters/sliders (summed for tool totals)
    - Configuration groups for alternative setups (OR logic)
    - Position tracking for layout

    Alternative Tool Configurations (Future Feature):
    -----------------------------------------------
    The config_group_id field is intended to support OR logic for alternative
    tool configurations. Example use case:

    Tool 1 can run EITHER:
    - Option A: 4 cavities of Part1 + 2 cavities of Part2 (config_group_id=1)
    - Option B: 2 cavities of Part3 (config_group_id=2)

    Parts with the same config_group_id run together (AND logic).
    Parts with different config_group_id values are alternatives (OR logic).
    Parts with NULL config_group_id are always included (base configuration).

    UI Implementation TODO:
    - Add UI to create/edit alternative configurations
    - Add visual indicator (🔀 badge) when tool has alternatives
    - Add dialog to select which configuration to view/calculate
    - Update calculations to handle alternative config scenarios
    - Export to Excel should show all alternatives with separate rows
    """
    __tablename__ = 'tool_part_configurations'

    id: Mapped[int] = mapped_column(primary_key=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey('tools.id'), nullable=False)
    part_id: Mapped[int] = mapped_column(ForeignKey('parts.id'), nullable=False)

    # Cavities for THIS part within the tool
    cavities: Mapped[int] = mapped_column(Integer, default=1)

    # Per-part mechanical features (aggregated for tool totals)
    lifters_count: Mapped[int] = mapped_column(Integer, default=0)
    sliders_count: Mapped[int] = mapped_column(Integer, default=0)

    # Configuration groups for alternative setups:
    # - Parts with same config_group_id = OR (alternatives, only one group runs at a time)
    # - Parts with different/null config_group_id = AND (run together)
    config_group_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Layout position within the tool (for visualization)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Additional notes for this part configuration
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    tool: Mapped["Tool"] = relationship("Tool", back_populates="part_configurations")
    part: Mapped["Part"] = relationship("Part", back_populates="tool_configurations")

    def __repr__(self):
        return f"<ToolPartConfig(tool_id={self.tool_id}, part_id={self.part_id}, cav={self.cavities})>"


class RFQ(Base):
    """RFQ (Request for Quote) project."""
    __tablename__ = 'rfqs'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer: Mapped[Optional[str]] = mapped_column(String(200))
    created_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    modified_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    status: Mapped[str] = mapped_column(String(20), default=RFQStatus.DRAFT.value)

    # Demand planning (project-level)
    demand_sop: Mapped[Optional[int]] = mapped_column(Integer)  # Start of production annual volume
    demand_sop_date: Mapped[Optional[datetime]] = mapped_column(DateTime)  # SOP start date
    demand_eaop: Mapped[Optional[int]] = mapped_column(Integer)  # End adjusted operating annual volume
    demand_eaop_date: Mapped[Optional[datetime]] = mapped_column(DateTime)  # EAOP end date
    flex_percent: Mapped[Optional[float]] = mapped_column(Float, default=100.0)  # Global flex % capacity

    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    parts: Mapped[List["Part"]] = relationship("Part", back_populates="rfq", cascade="all, delete-orphan")
    annual_demands: Mapped[List["AnnualDemand"]] = relationship("AnnualDemand", back_populates="rfq", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<RFQ(id={self.id}, name='{self.name}', customer='{self.customer}')>"


class AnnualDemand(Base):
    """Annual demand forecast for RFQ project (year-by-year breakdown)."""
    __tablename__ = 'annual_demands'

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey('rfqs.id'), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)  # Calendar year (e.g., 2026)
    volume: Mapped[Optional[int]] = mapped_column(Integer)  # Annual volume for this year
    flex_percent: Mapped[Optional[float]] = mapped_column(Float)  # Max capacity as % (e.g., 100, 80, 110)

    # Relationships
    rfq: Mapped["RFQ"] = relationship("RFQ", back_populates="annual_demands")

    def __repr__(self):
        return f"<AnnualDemand(year={self.year}, volume={self.volume}, flex={self.flex_percent}%)>"


class Part(Base):
    """Part within an RFQ."""
    __tablename__ = 'parts'

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey('rfqs.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    part_number: Mapped[Optional[str]] = mapped_column(String(100))

    # Image (binary data stored in DB)
    image_binary: Mapped[Optional[bytes]] = mapped_column(None)  # Binary image data
    image_filename: Mapped[Optional[str]] = mapped_column(String(255))  # Original filename
    image_updated_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # CAD file reference
    cad_path: Mapped[Optional[str]] = mapped_column(String(500))

    # Physical properties
    weight_g: Mapped[Optional[float]] = mapped_column(Float)
    volume_cm3: Mapped[Optional[float]] = mapped_column(Float)
    projected_area_cm2: Mapped[Optional[float]] = mapped_column(Float)
    wall_thickness_mm: Mapped[Optional[float]] = mapped_column(Float)
    wall_thickness_source: Mapped[str] = mapped_column(String(20), default="data")  # "data", "bom", or "estimated"

    # Geometry input mode
    geometry_mode: Mapped[str] = mapped_column(String(20), default="direct")  # "direct" or "box"
    # For box mode: length × width × effective %
    box_length_mm: Mapped[Optional[float]] = mapped_column(Float)
    box_width_mm: Mapped[Optional[float]] = mapped_column(Float)
    box_effective_percent: Mapped[Optional[float]] = mapped_column(Float, default=100.0)

    # Material
    material_id: Mapped[Optional[int]] = mapped_column(ForeignKey('materials.id'))

    # Demand planning (part-level; SOP/EAOP moved to RFQ level for consistency)
    # DEPRECATED: demand_sop and demand_eaop are now at RFQ level - these are kept for backward compatibility only
    demand_sop: Mapped[Optional[int]] = mapped_column(Integer)  # DEPRECATED: use RFQ.demand_sop
    demand_eaop: Mapped[Optional[int]] = mapped_column(Integer)  # DEPRECATED: use RFQ.demand_eaop
    demand_peak: Mapped[Optional[int]] = mapped_column(Integer)  # Peak annual demand (part-specific)
    parts_over_runtime: Mapped[Optional[int]] = mapped_column(Integer)  # Total lifetime volume (part-specific)

    # Manufacturing options
    assembly: Mapped[bool] = mapped_column(Boolean, default=False)
    degate: Mapped[str] = mapped_column(String(10), default=DegateOption.NO.value)
    overmold: Mapped[bool] = mapped_column(Boolean, default=False)
    eoat_type: Mapped[str] = mapped_column(String(20), default=EOATType.STANDARD.value)

    notes: Mapped[Optional[str]] = mapped_column(Text)
    remarks: Mapped[Optional[str]] = mapped_column(Text)  # Sales remarks

    # Surface finish (V2.0)
    surface_finish: Mapped[Optional[str]] = mapped_column(String(30))
    surface_finish_detail: Mapped[Optional[str]] = mapped_column(String(200))
    surface_finish_estimated: Mapped[bool] = mapped_column(Boolean, default=False)

    # Geometry source tracking (V2.0)
    projected_area_source: Mapped[str] = mapped_column(String(20), default="data")  # "data", "bom", "estimated"
    wall_thickness_needs_improvement: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    rfq: Mapped["RFQ"] = relationship("RFQ", back_populates="parts")
    material: Mapped[Optional["Material"]] = relationship("Material")
    tools: Mapped[List["Tool"]] = relationship("Tool", secondary=tool_parts, back_populates="parts")
    tool_configurations: Mapped[List["ToolPartConfiguration"]] = relationship(
        "ToolPartConfiguration", back_populates="part", cascade="all, delete-orphan"
    )
    revisions: Mapped[List["PartRevision"]] = relationship("PartRevision", back_populates="part", cascade="all, delete-orphan")
    sub_boms: Mapped[List["SubBOM"]] = relationship("SubBOM", back_populates="part", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Part(id={self.id}, name='{self.name}', part_number='{self.part_number}')>"


class SubBOM(Base):
    """Sub-BOM item for assemblies and overmolds (child parts with quantities)."""
    __tablename__ = 'sub_boms'

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey('parts.id'), nullable=False)  # Parent part

    # Sub-BOM item details
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g., "Bushing LL5934"
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    item_type: Mapped[str] = mapped_column(String(20), default="assembly")  # "assembly" or "overmold"
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    part: Mapped["Part"] = relationship("Part", back_populates="sub_boms")

    def __repr__(self):
        return f"<SubBOM(part_id={self.part_id}, item_name='{self.item_name}', qty={self.quantity})>"


class PartRevision(Base):
    """Audit log for part changes."""
    __tablename__ = 'part_revisions'

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey('parts.id'), nullable=False)

    # Change tracking
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    changed_by: Mapped[Optional[str]] = mapped_column(String(100))  # Username or "system"

    # Field that changed
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "weight_g", "image_filename"
    old_value: Mapped[Optional[str]] = mapped_column(Text)  # Serialized old value
    new_value: Mapped[Optional[str]] = mapped_column(Text)  # Serialized new value

    # For image changes, store what changed
    change_type: Mapped[str] = mapped_column(String(50), default="value")  # "value", "image", "geometry"
    notes: Mapped[Optional[str]] = mapped_column(Text)  # e.g., "Updated image from v2 to v3"

    # Relationships
    part: Mapped["Part"] = relationship("Part", back_populates="revisions")

    def __repr__(self):
        return f"<PartRevision(part_id={self.part_id}, field={self.field_name}, changed_at={self.changed_at})>"


class Tool(Base):
    """Injection molding tool."""
    __tablename__ = 'tools'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Tool configuration
    tool_type: Mapped[str] = mapped_column(String(20), default=ToolType.SINGLE.value)
    cavities: Mapped[int] = mapped_column(Integer, default=1)  # Total cavities (legacy, sum from configs)

    # Injection system
    injection_system: Mapped[str] = mapped_column(String(30), default=InjectionSystem.COLD_RUNNER.value)
    injection_points: Mapped[Optional[int]] = mapped_column(Integer)
    runner_type: Mapped[Optional[str]] = mapped_column(String(100))  # Specific hot runner type

    # V2.0: Enhanced injection configuration
    nozzle_type: Mapped[str] = mapped_column(String(30), default=NozzleType.COLD_RUNNER.value)
    hot_runner_nozzle_count: Mapped[int] = mapped_column(Integer, default=0)  # Number of hot runner nozzles

    # V2.0: Manufacturing options moved from Part level
    degate: Mapped[str] = mapped_column(String(10), default=DegateOption.NO.value)
    eoat_type: Mapped[str] = mapped_column(String(20), default=EOATType.STANDARD.value)

    # Surface
    surface_finish: Mapped[str] = mapped_column(String(30), default=SurfaceFinish.EDM.value)
    surface_notes: Mapped[Optional[str]] = mapped_column(String(500))

    # Mechanical features (legacy - totals; detailed per-part in ToolPartConfiguration)
    sliders_count: Mapped[int] = mapped_column(Integer, default=0)
    lifters_count: Mapped[int] = mapped_column(Integer, default=0)

    # Dimensions (mm)
    tool_length_mm: Mapped[Optional[float]] = mapped_column(Float)
    tool_width_mm: Mapped[Optional[float]] = mapped_column(Float)
    tool_height_mm: Mapped[Optional[float]] = mapped_column(Float)

    # Calculated values
    estimated_clamping_force_kn: Mapped[Optional[float]] = mapped_column(Float)
    clamping_force_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_injection_pressure_bar: Mapped[Optional[float]] = mapped_column(Float)
    injection_pressure_manual: Mapped[bool] = mapped_column(Boolean, default=False)

    # V2.0: Manual pressure override for clamping calculation (e.g., 750 bar instead of material's 500-700)
    manual_pressure_bar: Mapped[Optional[float]] = mapped_column(Float)

    # V2.0: Shot volume tracking
    total_shot_volume_cm3: Mapped[Optional[float]] = mapped_column(Float)  # Sum of (part.vol × cav) + runner

    # Machine assignment
    machine_id: Mapped[Optional[int]] = mapped_column(ForeignKey('machines.id'))
    fits_machine: Mapped[Optional[bool]] = mapped_column(Boolean)
    fit_issues: Mapped[Optional[str]] = mapped_column(Text)  # Description of fit problems

    # Pricing
    price_enquiry: Mapped[Optional[float]] = mapped_column(Float)  # Price from supplier quote
    price_estimated: Mapped[Optional[float]] = mapped_column(Float)  # Our estimate
    price_final: Mapped[Optional[float]] = mapped_column(Float)  # Final agreed price

    # Supplier info
    supplier_country: Mapped[Optional[str]] = mapped_column(String(100))
    supplier_name: Mapped[Optional[str]] = mapped_column(String(200))

    # Complexity
    complexity_rating: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5 scale

    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    machine: Mapped[Optional["Machine"]] = relationship("Machine")
    parts: Mapped[List["Part"]] = relationship("Part", secondary=tool_parts, back_populates="tools")
    part_configurations: Mapped[List["ToolPartConfiguration"]] = relationship(
        "ToolPartConfiguration", back_populates="tool", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Tool(id={self.id}, name='{self.name}', type='{self.tool_type}')>"

    def get_total_cavities(self) -> int:
        """Calculate total cavities from part configurations."""
        if self.part_configurations:
            return sum(pc.cavities for pc in self.part_configurations)
        return self.cavities

    def get_total_lifters(self) -> int:
        """Calculate total lifters from part configurations."""
        if self.part_configurations:
            return sum(pc.lifters_count for pc in self.part_configurations)
        return self.lifters_count

    def get_total_sliders(self) -> int:
        """Calculate total sliders from part configurations."""
        if self.part_configurations:
            return sum(pc.sliders_count for pc in self.part_configurations)
        return self.sliders_count

    def has_alternative_configs(self) -> bool:
        """Check if tool has alternative configuration groups."""
        if not self.part_configurations:
            return False
        groups = set(pc.config_group_id for pc in self.part_configurations if pc.config_group_id is not None)
        return len(groups) > 1

    def is_defined(self) -> bool:
        """Check if tool has parts assigned (is defined)."""
        return bool(self.part_configurations and len(self.part_configurations) > 0)

    def get_parts_count(self) -> int:
        """Get number of parts assigned to this tool."""
        return len(self.part_configurations) if self.part_configurations else 0


class Material(Base):
    """Injection molding material."""
    __tablename__ = 'materials'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str] = mapped_column(String(20), nullable=False)
    family: Mapped[str] = mapped_column(String(50))  # PP, ABS, PA, PC, POM, etc.

    # Physical properties
    density_g_cm3: Mapped[Optional[float]] = mapped_column(Float)
    shrinkage_min_percent: Mapped[Optional[float]] = mapped_column(Float)
    shrinkage_max_percent: Mapped[Optional[float]] = mapped_column(Float)

    # Processing parameters
    melt_temp_min_c: Mapped[Optional[float]] = mapped_column(Float)
    melt_temp_max_c: Mapped[Optional[float]] = mapped_column(Float)
    mold_temp_min_c: Mapped[Optional[float]] = mapped_column(Float)
    mold_temp_max_c: Mapped[Optional[float]] = mapped_column(Float)

    # For calculations
    specific_pressure_min_bar: Mapped[Optional[float]] = mapped_column(Float)
    specific_pressure_max_bar: Mapped[Optional[float]] = mapped_column(Float)
    flow_length_ratio: Mapped[Optional[float]] = mapped_column(Float)  # Flow length / wall thickness

    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False)  # True for seed data

    def __repr__(self):
        return f"<Material(id={self.id}, short_name='{self.short_name}', family='{self.family}')>"

    @property
    def specific_pressure_avg_bar(self) -> Optional[float]:
        """Average specific pressure for calculations."""
        if self.specific_pressure_min_bar and self.specific_pressure_max_bar:
            return (self.specific_pressure_min_bar + self.specific_pressure_max_bar) / 2
        return self.specific_pressure_min_bar or self.specific_pressure_max_bar


class Machine(Base):
    """Injection molding machine."""
    __tablename__ = 'machines'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))

    # Clamping
    clamping_force_kn: Mapped[Optional[float]] = mapped_column(Float)

    # Injection
    shot_weight_g: Mapped[Optional[float]] = mapped_column(Float)
    injection_pressure_bar: Mapped[Optional[float]] = mapped_column(Float)

    # V2.0: Barrel and screw specs for shot volume and ratio calculations
    barrel_volume_cm3: Mapped[Optional[float]] = mapped_column(Float)  # For barrel usage % calculation
    screw_diameter_mm: Mapped[Optional[float]] = mapped_column(Float)  # For stroke/diameter ratio
    max_injection_stroke_mm: Mapped[Optional[float]] = mapped_column(Float)  # For stroke/diameter ratio

    # Platen dimensions (mm)
    platen_width_mm: Mapped[Optional[float]] = mapped_column(Float)
    platen_height_mm: Mapped[Optional[float]] = mapped_column(Float)

    # Tie bar spacing (mm)
    tie_bar_spacing_h_mm: Mapped[Optional[float]] = mapped_column(Float)
    tie_bar_spacing_v_mm: Mapped[Optional[float]] = mapped_column(Float)

    # Mold height (mm)
    max_mold_height_mm: Mapped[Optional[float]] = mapped_column(Float)
    min_mold_height_mm: Mapped[Optional[float]] = mapped_column(Float)

    # Opening stroke
    max_opening_stroke_mm: Mapped[Optional[float]] = mapped_column(Float)

    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self):
        return f"<Machine(id={self.id}, name='{self.name}', clamping={self.clamping_force_kn}kN)>"

    def get_screw_ratio(self) -> Optional[float]:
        """Calculate stroke/diameter ratio (optimal range: 1.0-2.8)."""
        if self.max_injection_stroke_mm and self.screw_diameter_mm and self.screw_diameter_mm > 0:
            return self.max_injection_stroke_mm / self.screw_diameter_mm
        return None


class ExistingTool(Base):
    """Reference database for existing tools (not linked to RFQ)."""
    __tablename__ = 'existing_tools'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Part characteristics
    part_type: Mapped[Optional[str]] = mapped_column(String(100))
    part_weight_g: Mapped[Optional[float]] = mapped_column(Float)
    part_volume_cm3: Mapped[Optional[float]] = mapped_column(Float)
    projected_area_cm2: Mapped[Optional[float]] = mapped_column(Float)

    # Tool characteristics
    complexity_rating: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    cavities: Mapped[int] = mapped_column(Integer, default=1)
    sliders_count: Mapped[int] = mapped_column(Integer, default=0)
    lifters_count: Mapped[int] = mapped_column(Integer, default=0)

    # Surface & tech
    surface_finish: Mapped[Optional[str]] = mapped_column(String(30))
    injection_system: Mapped[Optional[str]] = mapped_column(String(30))
    technology_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Tool dimensions
    tool_length_mm: Mapped[Optional[float]] = mapped_column(Float)
    tool_width_mm: Mapped[Optional[float]] = mapped_column(Float)
    tool_height_mm: Mapped[Optional[float]] = mapped_column(Float)
    steel_weight_kg: Mapped[Optional[float]] = mapped_column(Float)

    # Supplier & pricing
    supplier_country: Mapped[Optional[str]] = mapped_column(String(100))
    supplier_name: Mapped[Optional[str]] = mapped_column(String(200))
    actual_price: Mapped[Optional[float]] = mapped_column(Float)
    price_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    currency: Mapped[str] = mapped_column(String(10), default='EUR')

    # Experience
    issues: Mapped[Optional[str]] = mapped_column(Text)
    lessons_learned: Mapped[Optional[str]] = mapped_column(Text)

    # Files
    image_path: Mapped[Optional[str]] = mapped_column(String(500))

    # Filtering
    tags: Mapped[Optional[str]] = mapped_column(String(500))  # Comma-separated tags

    created_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<ExistingTool(id={self.id}, name='{self.name}', price={self.actual_price})>"

    def get_tags_list(self) -> List[str]:
        """Return tags as a list."""
        if self.tags:
            return [t.strip() for t in self.tags.split(',') if t.strip()]
        return []

    def set_tags_list(self, tags: List[str]):
        """Set tags from a list."""
        self.tags = ', '.join(tags) if tags else None


# Alias for junction table
ToolPart = tool_parts
