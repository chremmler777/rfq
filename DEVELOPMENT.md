# RFQ Tool - Development Guide

## Project Overview

RFQ Tool is a PyQt6 desktop application for managing injection molding quotes with multi-user SQLite support. This document covers development practices, architecture, and contributing guidelines.

## Getting Started for Developers

### Setup
```bash
git clone <repo>
cd rfq
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running
```bash
python3 main.py
```

### Code Style
- Follow PEP 8
- Use type hints for function signatures
- Document public methods with docstrings
- Max 100 characters per line

## Architecture

### Layer Pattern
```
UI Layer (PyQt6)
    ↓
Business Logic (Dialogs, Calculations)
    ↓
Database Layer (SQLAlchemy ORM)
    ↓
SQLite Database
```

### File Organization

**ui/** - User Interface
- `main_window.py` - Main application window with RFQ/Parts/Tools tabs
- `dialogs/rfq_dialog.py` - RFQ creation/editing with demand planning
- `dialogs/part_dialog.py` - Part details with 5 tabs (Basic, Geometry, Manufacturing, Demand, Revisions)

**database/** - Data Access
- `models.py` - SQLAlchemy ORM definitions
- `connection.py` - Session management with locking for multi-user
- `__init__.py` - Database initialization and seeding

**calculations/** - Business Logic (Future)
- Geometry calculations
- Weight/volume conversions
- Clamping force calculations

## Key Components

### RFQ Dialog (ui/dialogs/rfq_dialog.py)

**Purpose**: Create/edit RFQ projects with annual demand planning

**Key Fields**:
- `name`: Project name
- `customer`: Customer name
- `status`: Draft/Quoted/Ordered/Closed
- `demand_sop_date`, `demand_eaop_date`: Production window
- `flex_percent`: Global capacity flex % (10-500)
- `annual_demands`: List of AnnualDemand records

**Key Methods**:
- `_setup_ui()`: Build dialog layout
- `_regenerate_annual_demands()`: Generate year rows based on SOP/EAOP dates
- `_update_flex_display()`: Recalculate flex volumes and update chart
- `_update_demand_chart()`: Render bar chart of annual demand
- `_on_save()`: Persist RFQ to database
- `_save_annual_demands()`: Save year-by-year volumes

**Important**: Annual demands read directly from table cells, not from dict tracking

### Part Dialog (ui/dialogs/part_dialog.py)

**Purpose**: Create/edit parts with comprehensive manufacturing details

**Tabs**:
1. **Basic Info**: Name, part number, material, image upload
2. **Geometry**: Direct area OR box estimate mode
3. **Manufacturing**: Assembly/Overmold sub-BOMs, degate, EOAT
4. **Demand**: Total lifetime demand, notes
5. **Revisions**: Audit trail of changes

**Key Fields**:
- Geometry mode: "direct" or "box"
- Image: Binary storage in `image_binary`, filename in `image_filename`
- Sub-BOMs: List of SubBOM records (assembly/overmold items)
- Wall thickness source tracking: "given" or "estimated"

**Important**: `demand_peak_spin` now holds total lifetime demand (saved to `parts_over_runtime`)

### Main Window (ui/main_window.py)

**Purpose**: Application entry point with RFQ/Parts/Tools management

**Key Components**:
- `rfq_table`: List of RFQs (sortable, selectable)
- `parts_table`: Parts for selected RFQ with image thumbnails
- `tools_table`: Tools associated with RFQ parts

**Table Configuration**:
- Parts table: 11 columns (Part Name, Image, Material, Weight, Area, Demand, Assy, Degate, Overmold, EOAT, Notes)
- Row height: 75px (50% taller for image preview)
- Image column width: 100px
- Image preview: 65px scaled thumbnail with 3px padding

**Key Methods**:
- `_on_rfq_selected()`: Load parts/tools for selected RFQ
- `_load_rfq_details()`: Populate tables with RFQ data
- `_on_add_part()`: Open part dialog for new part
- `_on_image_clicked()`: Open full-size image viewer
- `_load_rfq_list()`: Refresh RFQ table from database

### Database Models (database/models.py)

**RFQ Model**:
```python
class RFQ(Base):
    id: int (primary key)
    name: str (required)
    customer: str
    status: str (enum)
    demand_sop: int (volume at SOP)
    demand_sop_date: datetime
    demand_eaop: int (volume at EAOP)
    demand_eaop_date: datetime
    flex_percent: float (default 100.0)
    created_date: datetime
    notes: str
    parts: List[Part] (relationship)
    annual_demands: List[AnnualDemand] (relationship)
```

**Part Model**:
```python
class Part(Base):
    id: int (primary key)
    rfq_id: int (foreign key)
    name: str (required)
    part_number: str
    material_id: int
    weight_g: float
    volume_cm3: float
    projected_area_cm2: float
    wall_thickness_mm: float
    wall_thickness_source: str ("given"/"estimated")
    geometry_mode: str ("direct"/"box")
    box_length_mm, box_width_mm: float
    box_effective_percent: float
    assembly: bool
    degate: str
    overmold: bool
    eoat_type: str
    parts_over_runtime: int (total lifetime demand)
    demand_peak: int (DEPRECATED - use parts_over_runtime)
    demand_sop, demand_eaop: int (DEPRECATED - now at RFQ level)
    image_binary: bytes
    image_filename: str
    image_updated_date: datetime
    notes: str
    remarks: str
    tools: List[Tool] (relationship)
    sub_boms: List[SubBOM] (relationship)
    revisions: List[PartRevision] (relationship)
```

**AnnualDemand Model**:
```python
class AnnualDemand(Base):
    id: int
    rfq_id: int (foreign key)
    year: int
    volume: int
    rfq: RFQ (relationship)
```

**SubBOM Model**:
```python
class SubBOM(Base):
    id: int
    part_id: int (foreign key)
    item_name: str
    quantity: int
    item_type: str ("assembly"/"overmold")
    notes: str
    part: Part (relationship)
```

## Session Management Pattern

All database operations use `session_scope()` context manager:

```python
from database.connection import session_scope
from database.models import RFQ

# Query and persist
with session_scope() as session:
    rfq = session.query(RFQ).get(1)
    rfq.name = "Updated Name"
    # Auto-commits on exit, expunges on exception
```

**Important**: Don't access detached object attributes outside session
```python
# WRONG - rfq is detached after session closes
with session_scope() as session:
    rfq = session.query(RFQ).get(1)
rfq.name  # ERROR: DetachedInstanceError

# CORRECT - capture ID while in session
with session_scope() as session:
    rfq = session.query(RFQ).get(1)
    rfq_id = rfq.id
# Use rfq_id outside session
```

## Common Issues & Solutions

### Issue: DetachedInstanceError
**Cause**: Accessing object attributes after session closes
**Solution**: Capture needed data (IDs, values) while in session

### Issue: NoneType has no attribute 'deleteLater'
**Cause**: Layout item widget() returns None (could be nested layout)
**Solution**: Check if widget is not None before calling deleteLater()

### Issue: Chart background appears dark
**Cause**: Matplotlib using system theme colors
**Solution**: Set matplotlib rcParams and explicit patch colors:
```python
import matplotlib as mpl
mpl.rcParams['figure.facecolor'] = 'white'
mpl.rcParams['axes.facecolor'] = 'white'
self.demand_figure.patch.set_facecolor('white')
ax.patch.set_facecolor('white')
```

### Issue: Part save missing attribute error
**Cause**: UI widget doesn't exist but save code tries to access
**Solution**: Remove deprecated field references, add comments explaining why

## Testing

### Manual Testing Checklist
- [ ] Create new RFQ with SOP/EAOP dates
- [ ] Verify annual demand rows generate correctly
- [ ] Change volumes and verify flex calculations update
- [ ] Change flex % and verify w/Flex column updates
- [ ] Create part with image
- [ ] Verify image thumbnail appears in table
- [ ] Click image thumbnail and view full-size
- [ ] Save part and verify it persists
- [ ] Edit part and verify changes save
- [ ] Add sub-BOM items (assembly/overmold)
- [ ] Delete part and verify removal

### Multi-User Testing
- [ ] Open same RFQ in two instances
- [ ] Modify in one, refresh in other
- [ ] Verify no data corruption
- [ ] Check timeout handling under lock contention

## Contributing Guidelines

### Before Committing
1. Test your changes manually
2. Run syntax check: `python3 -m py_compile <file>`
3. Verify no debug prints left in
4. Update documentation for new features
5. Add comment for non-obvious logic

### Commit Message Format
```
<type>: <summary>

<body (optional)>

Fixes: #<issue-number> (if applicable)
```

**Types**: feature, fix, refactor, docs, test, style

### Code Review Checklist
- [ ] No hardcoded paths or credentials
- [ ] Proper error handling
- [ ] Session management correct (session_scope usage)
- [ ] No detached object access
- [ ] UI responsive (no blocking operations)
- [ ] Comments explain "why", not "what"

## Performance Notes

- **Image Scaling**: Thumbnails pre-scaled to 65px to minimize memory
- **Lazy Loading**: Annual demand rows generated on-demand
- **Batch Queries**: Parts loaded with related materials in single query
- **Index Usage**: Foreign keys auto-indexed by SQLAlchemy

## Future Work

### Phase 3: Tool Configuration
- Tool dialog for machine fit validation
- Clamping force calculation engine
- Machine database and selection

### Phase 4: Existing Tools
- Reference tool database
- Historical pricing trends
- Supplier management

### Phase 5: Export
- Excel export with formatting
- PDF quote generation
- Supplier communication templates

## Debugging Tips

### Enable Debug Output
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Database Inspection
```bash
sqlite3 data/rfq_tools.db
> .schema  # View all tables
> SELECT * FROM rfqs;  # Query data
```

### PyQt Debug
```python
# Enable paint event logging
QtCore.pyqtRemoveInputHook()  # For IDE debugging
```

---

**Last Updated**: 2026-01-21
**Maintainer**: Development Team
