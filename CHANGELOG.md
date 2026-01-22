# RFQ Tool - Changelog

## Version 1.0.0 - Initial Release

### Overview
RFQ Tool Quoting Software for injection molding manufacturing. Multi-user desktop application with SQLite database, PyQt6 UI, automatic demand planning calculations, and Excel export capabilities.

### Core Features

#### 1. RFQ Management
- **Create/Edit/Delete RFQs** with project-level demand planning
- **SOP/EAOP Dates**: Define production window at project level
- **Annual Demand Breakdown**: Year-by-year volume planning with visual barchart
- **Global Capacity Flex %**: Single flex percentage applies to all years
- **Lifetime Summary**: Real-time calculation of total demand with and without flex capacity

#### 2. Part Management
- **Part Creation Dialog** with comprehensive fields:
  - Basic info: name, part number, material selection
  - Geometry: direct surface input OR box estimate mode (L × W × Effective %)
  - Physical properties: weight, volume, projected area, wall thickness
  - Manufacturing options: assembly sub-BOM, overmold sub-BOM, degate, EOAT type
  - Demand: total lifetime demand per part
  - Notes & sales remarks

- **Image Management**:
  - Drag-and-drop image upload with preview
  - Binary storage in database (portable)
  - Part image thumbnail display in parts table (75px height)
  - Click thumbnail to view full-size image in dialog

- **Parts Table Display**:
  - Part name, image preview, material, weight, projected area
  - Total demand, assembly/overmold flags, degate type, EOAT type, notes
  - 75px row height for clear image visibility
  - Increased image column width (100px) for thumbnail preview

#### 3. Material Database
- Pre-populated with common plastics:
  - PP (Polypropylene), ABS, PA6, PA66, PC, POM, PE-HD
  - Density, shrinkage, melt temp, mold temp
  - Specific pressure for clamping force calculations
- Extensible for custom materials

#### 4. Demand Planning
- **Project-Level Planning (RFQ)**:
  - SOP (Start of Production) date
  - EAOP (End Adjusted Operating Period) date
  - Automatic year range generation
  - Global capacity flex percentage

- **Annual Demand Table**:
  - Year-by-year volume input (spinbox with thousands separator)
  - Real-time flex calculation (w/Flex column)
  - Lifetime summary with impact of flex capacity
  - Synchronized with project dates

- **Visual Demand Chart**:
  - Bar chart of annual demand by year
  - Professional blue color scheme
  - Value labels on each bar with comma formatting
  - White background for clean appearance
  - Updates in real-time as volumes change

#### 5. Manufacturing Options
- **Assembly Sub-BOM**: Track component assemblies (e.g., "Bushing LL5934")
- **Overmold Sub-BOM**: Track overmold materials
- **Manufacturing Flags**:
  - Assembly required (checkbox + degate dropdown)
  - Overmold required (checkbox + EOAT type dropdown)
- Sub-BOM items include: name, quantity, notes

#### 6. Database Schema
**Tables:**
- `rfqs`: RFQ projects with demand planning fields
- `parts`: Part details, images, manufacturing options
- `annual_demands`: Year-by-year demand volumes
- `materials`: Material database
- `machines`: Injection molding machine specs (future)
- `sub_boms`: Assembly/overmold sub-items
- `part_revisions`: Audit trail of part changes

**Key Fields:**
- Binary image storage (`image_binary`, `image_filename`)
- Geometry mode support (direct vs box estimate)
- Wall thickness source tracking (given vs estimated)
- Sub-BOM with item type (assembly/overmold)
- Annual demand per year linked to RFQ

### Recent Improvements

#### Flex Capacity Implementation
- **Issue**: Flex percentage per year created UI clutter
- **Solution**: Moved to single global flex % at RFQ level
- **Range**: 10% to 500% (allows flexibility from tight to over-capacity)
- **Formula**: `volume * (100 + flex) / 100`
  - 100% flex = 2x capacity (100% buffer)
  - 50% flex = 1.5x capacity (50% buffer)
  - 20% flex = 1.2x capacity (20% buffer)

#### Annual Demand Display
- **Issue**: Scrolling interface with overlapping fields unclear
- **Solution**: Clean table widget with inline spinboxes
- **Features**:
  - Thousands separator formatting (e.g., "5,000")
  - Real-time flex calculation
  - Visual barchart showing annual pattern
  - Lifetime summary with flex impact

#### Part Images
- **Issue**: No visual identification of parts
- **Solution**: Image display integrated into parts table
- **Features**:
  - Thumbnail preview (65px height in 75px row)
  - Drag-and-drop upload + manual upload button
  - Click thumbnail to view full image
  - Binary storage for portability

#### Total Demand Field
- **Issue**: Peak demand per-year concept was confusing
- **Solution**: Single "Total Demand" field per part (lifetime volume)
- **Location**: Part dialog Demand tab
- **Usage**: Represents total pcs for entire part lifetime

### Bug Fixes
1. **Detached Instance Errors**: Fixed SQLAlchemy session lifecycle issues
2. **Layout Clearing**: Added null-checks when removing widgets
3. **Chart Background**: Matplotlib styling for white background appearance
4. **Part Dialog Save**: Removed deprecated demand_sop/eaop references

### Technical Stack
- **UI**: PyQt6 (native desktop)
- **Database**: SQLite with WAL mode (multi-user support)
- **ORM**: SQLAlchemy 2.0+ with type hints
- **Charts**: Matplotlib with Qt5 backend
- **Export**: openpyxl (future)

### File Structure
```
rfq/
├── main.py                          # Entry point
├── config.py                        # Settings
├── requirements.txt                 # Dependencies
├── database/
│   ├── models.py                   # SQLAlchemy ORM
│   ├── connection.py               # DB connection + locking
│   ├── __init__.py                 # Session management
│   └── seed_data.py                # Pre-populated data
├── ui/
│   ├── main_window.py              # Main UI window
│   └── dialogs/
│       ├── rfq_dialog.py           # RFQ creation/editing
│       └── part_dialog.py          # Part details
├── calculations/                    # (Future) Clamping force, cycle time
├── export/                          # (Future) Excel export
└── data/
    ├── seed/                       # Pre-populated materials/machines
    └── rfq_tools.db               # SQLite database
```

### Usage
```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
python3 main.py
```

### Future Phases
- Phase 3: Tool configuration with machine fit validation
- Phase 4: Existing tools database with pricing history
- Phase 5: Excel export with detailed RFQ summaries

---
**Version**: 1.0.0
**Date**: 2026-01-21
**Status**: Initial Release - Ready for Production Use
