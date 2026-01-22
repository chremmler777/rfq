# RFQ Tool - Injection Molding Quoting Software

Professional desktop application for managing Request for Quotation (RFQ) projects for injection molding manufacturing.

## Features

### 📋 Core Functionality
- **BOM Management**: Create and manage Bills of Material with part specifications
- **Multi-year Demand Planning**: Year-by-year volume forecasting with capacity flex % limits
- **Image Management**: Drag-drop image upload with binary storage and revision tracking
- **Flexible Geometry Input**: Direct area entry or box dimension estimation
- **Manufacturing Options**: Assembly, degating, overmolding, and EOAT configuration
- **Sub-BOM Support**: Add child components for assemblies and overmold materials
- **Revision Tracking**: Complete audit trail of all changes with timestamps
- **Weight↔Volume Auto-Calculation**: Material density-based conversions

### 🎯 Demand Planning
- **Project-Level**: SOP/EAOP volumes with start/end dates
- **Annual Breakdown**: Year-by-year volumes with flex % capacity limits
- **Example**: SOP April 2026 → EAOP 8/31/2028 auto-generates 2026, 2027, 2028 rows
- **Part-Level**: Peak annual demand and lifetime volume (part-specific)

### 🗄️ Data Management
- **SQLite Database**: Multi-user via WAL mode on shared network drives
- **Session Management**: Proper connection handling for concurrent access
- **Audit Trail**: Full revision history with field-level change tracking
- **Material Database**: Pre-populated materials with density/properties
- **Machine Database**: Machine specifications for tool sizing

## Installation

### Requirements
- Python 3.10+
- PyQt6 6.5+
- SQLAlchemy 2.0+
- openpyxl 3.1+

### Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run application
python3 main.py
```

### Configuration
Edit `config.py` to:
- Change database path (point to shared network drive for multi-user)
- Configure application settings

## Usage

### Creating an RFQ Project
1. Launch app → "RFQs" tab → "New RFQ"
2. Enter: Name, Customer, optional SOP/EAOP dates
3. Set annual demand volumes and flex % for each year
4. Save

### Adding Parts to BOM
1. Select RFQ → "Add Part"
2. **Basic Info Tab**: Name, part number, material, drag-drop image
3. **Geometry Tab**: Choose direct area or box estimation mode
4. **Manufacturing Tab**: Set assembly/overmold options, add sub-BOM items
5. **Demand Tab**: Peak year demand, lifetime volume
6. **Revisions Tab**: View change history
7. Save

### Key UI Elements

**Geometry Input**:
- Select mode → fields show/hide automatically
- Direct: Enter projected surface area (cm²)
- Box: Enter L×W (mm) + effective % → calculates area

**Wall Thickness**:
- Manual entry or "Estimate" button for standard 2.5mm
- Tracks source: "given" or "estimated" with audit trail

**Images**:
- Drag-drop or click "Upload Image"
- Shows preview, stores binary in database
- Updated date tracked with revisions

**Sub-BOM** (when assembly/overmold checked):
- Add child items with quantities
- Tracks item names, quantities, notes
- Examples: Bushings, core pins, rubber components

## Architecture

```
rfq/
├── main.py                 # Application entry point
├── config.py               # Settings and paths
├── requirements.txt        # Dependencies
│
├── database/
│   ├── models.py           # SQLAlchemy ORM models
│   ├── connection.py       # DB connection with WAL mode
│   ├── seed_data.py        # Pre-populate materials/machines
│   └── __init__.py         # Exports
│
├── calculations/
│   ├── geometry_calculator.py   # Area calculations (direct/box modes)
│   ├── weight_volume_helper.py  # Density-based conversions
│   └── __init__.py              # Exports
│
├── ui/
│   ├── main_window.py      # Main UI with tabs
│   ├── styles.py           # Qt stylesheets
│   └── dialogs/
│       ├── rfq_dialog.py        # RFQ creation/editing
│       └── part_dialog.py       # Part/BOM entry
│
└── data/
    └── seed/
        ├── materials.json  # Material properties
        └── machines.json   # Machine specifications
```

## Database Schema

### Core Tables

**rfqs** - RFQ Projects
- id, name, customer, status, created_date
- demand_sop, demand_sop_date (project SOP volume + start date)
- demand_eaop, demand_eaop_date (project EAOP volume + end date)
- notes

**parts** - BOM Items
- id, rfq_id, name, part_number, material_id
- weight_g, volume_cm3, projected_area_cm2
- wall_thickness_mm, wall_thickness_source ("given"/"estimated")
- geometry_mode ("direct"/"box"), box dimensions
- assembly, degate, overmold, eoat_type
- demand_peak, parts_over_runtime (part-specific)
- image_binary, image_filename, image_updated_date
- notes, remarks

**annual_demands** - Year-by-Year Volumes
- id, rfq_id, year, volume, flex_percent
- Stores: annual volume + max capacity % for each year

**sub_boms** - Child Components
- id, part_id, item_name, quantity
- item_type ("assembly"/"overmold"), notes

**part_revisions** - Audit Trail
- id, part_id, field_name, old_value, new_value
- changed_at, changed_by, change_type ("value"/"image"/"geometry")
- notes

**materials** - Material Database
- id, name, short_name, family (PP/ABS/PA/PC/POM)
- density_g_cm3, shrinkage_percent, melt_temp_c
- specific_pressure_bar, flow_length_ratio

## API Reference

### Geometry Calculation
```python
from calculations import BoxEstimateMode, DirectGeometryMode

# Direct mode: area directly entered
direct = DirectGeometryMode(projected_area_cm2=150.0)
area = direct.calculate_projected_area()  # Returns 150.0

# Box mode: L × W × effective %
box = BoxEstimateMode(length_mm=200, width_mm=75, effective_percent=100)
area = box.calculate_projected_area()  # Returns 150.0
```

### Weight/Volume Conversion
```python
from calculations import auto_calculate_volume, auto_calculate_weight

# Weight → Volume (using material density)
volume = auto_calculate_volume(weight_g=100, density_g_cm3=0.91)

# Volume → Weight
weight = auto_calculate_weight(volume_cm3=110, density_g_cm3=0.91)
```

### Database Access
```python
from database.connection import session_scope
from database.models import RFQ, Part, AnnualDemand

# Query with automatic session management
with session_scope() as session:
    rfq = session.query(RFQ).filter(RFQ.id == 1).first()
    # Objects auto-commit on exit, expunge on exception
```

## Key Design Patterns

### Session Management
- **session_scope()** context manager handles create/commit/close
- Objects are expunged from session after context exit
- Prevents DetachedInstanceError in GUI operations

### Geometry Modes
- **Strategy Pattern**: Different calculation modes for different inputs
- **Dynamic UI**: Fields show/hide based on selected mode
- **Factory**: GeometryFactory creates appropriate calculator

### Audit Trail
- **PartRevision Table**: Tracks all changes with full context
- **Field Tracking**: Monitors specific field changes
- **Timestamp + User**: All changes attributed with date/time

### Image Storage
- **Binary in DB**: Images stored as binary in database
- **Portability**: No external file dependencies
- **Versioning**: Image changes tracked in audit trail

## Multi-User Setup

### Network Configuration
1. Place database file on shared network drive
2. Update `config.py`: `DATABASE_PATH = "/mnt/shared_drive/rfq.db"`
3. SQLite WAL mode handles concurrent reads/writes
4. 30-second busy timeout for lock contention

### Best Practices
- One database per project
- Use descriptive RFQ names for easy filtering
- Document material changes in notes
- Review revision history regularly

## Troubleshooting

**App won't start**: Check Python 3.10+, PyQt6 installation
**Database locked**: Wait 30s, close other instances, check shared drive access
**Detached object error**: Use session_scope() for all database operations
**Image not loading**: Check file format (PNG/JPG/BMP/GIF), file size < 50MB

## Performance Optimization

- **Query optimization**: Batch loads related objects
- **Index creation**: Database auto-indexes foreign keys
- **Image compression**: Consider resizing large images before upload
- **Annual demands**: Generates rows on-demand based on date range

## Version 1.0.0 Changes (Latest)

### New Features
- **Global Capacity Flex %**: Single flex percentage at RFQ level applies to all years
  - Range: 10% to 500% for flexibility control
  - Formula: `volume * (100 + flex) / 100`
  - Real-time calculation updates in "w/Flex" column

- **Annual Demand Table**: Clean table widget replacing scroll area
  - Year-by-year volume input with thousands separator formatting
  - Real-time flex calculation display
  - Lifetime summary showing total with and without flex capacity

- **Demand Visual Chart**: Bar chart of annual demand by year
  - Professional blue color scheme matching UI
  - Value labels on bars with comma formatting
  - Updates in real-time as volumes change
  - Clean white background

- **Part Image Thumbnails in Table**:
  - 75px row height for clear image visibility
  - 65px scaled thumbnail preview inline
  - Click thumbnail to view full-size image in dialog
  - Drag-drop or upload image in part dialog

- **Total Demand Field**:
  - Renamed from "Peak Demand" for clarity
  - Single field for lifetime volume per part
  - Stores as `parts_over_runtime` in database

### Bug Fixes
- Fixed DetachedInstanceError in RFQ/Part dialogs
- Fixed layout widget deletion null-pointer crashes
- Improved error messages with specific attribute names
- Removed deprecated demand_sop/eaop references from part save

## Future Enhancements

- Tool costing engine
- Export to Excel
- Supplier management
- Tooling design integration
- 3D model preview (STEP/IGES)
- Quote template generation

## License

Internal use only - [Your Company]

## Support

For issues or feature requests, contact the development team.
