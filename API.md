# RFQ Tool - API Documentation

## Database Models

### RFQ
```python
from database.models import RFQ
from database import RFQStatus

rfq = RFQ(
    name="Customer Project Q1 2026",
    customer="ACME Corp",
    status=RFQStatus.DRAFT.value,
    demand_sop=5000,
    demand_sop_date=datetime(2026, 4, 1),
    demand_eaop=10000,
    demand_eaop_date=datetime(2028, 8, 31),
    notes="High-volume injection project"
)
```

**Fields:**
- `id`: Primary key
- `name`: Project name
- `customer`: Customer name
- `status`: DRAFT/QUOTED/ORDERED/CLOSED
- `demand_sop`: Start of production annual volume (pcs)
- `demand_sop_date`: SOP start date
- `demand_eaop`: End adjusted operating annual volume (pcs)
- `demand_eaop_date`: EAOP end date
- `created_date`: Auto-set timestamp
- `modified_date`: Auto-updated timestamp
- `notes`: Optional notes
- **Relationships:**
  - `parts`: List of Part objects
  - `annual_demands`: List of AnnualDemand objects

### Part
```python
from database.models import Part
from database import DegateOption, EOATType

part = Part(
    rfq_id=1,
    name="Housing Assembly",
    part_number="PART-001",
    material_id=5,
    weight_g=125.5,
    volume_cm3=138.0,
    projected_area_cm2=250.0,
    wall_thickness_mm=2.5,
    wall_thickness_source="given",
    geometry_mode="direct",
    assembly=True,
    degate=DegateOption.YES.value,
    overmold=False,
    eoat_type=EOATType.COMPLEX.value,
    demand_peak=10000,
    parts_over_runtime=50000,
    image_binary=b'...',
    image_filename="housing_v1.png",
    notes="Tight tolerances",
    remarks="Quick turnaround"
)
```

**Fields:**
- Physical: `weight_g`, `volume_cm3`, `projected_area_cm2`, `wall_thickness_mm`
- Geometry: `geometry_mode` ("direct"/"box"), `box_length_mm`, `box_width_mm`, `box_effective_percent`
- Manufacturing: `assembly`, `degate`, `overmold`, `eoat_type`
- Demand: `demand_peak` (pcs/year), `parts_over_runtime` (lifetime pcs)
- Images: `image_binary` (bytes), `image_filename` (str), `image_updated_date` (datetime)
- Wall thickness source: `wall_thickness_source` ("given"/"estimated")
- **Relationships:**
  - `rfq`: Parent RFQ
  - `material`: Material reference
  - `sub_boms`: List of SubBOM items
  - `revisions`: List of PartRevision (audit trail)

### AnnualDemand
```python
from database.models import AnnualDemand

ad = AnnualDemand(
    rfq_id=1,
    year=2026,
    volume=5000,      # pcs for this year
    flex_percent=100.0 # max capacity as %
)
```

**Fields:**
- `id`: Primary key
- `rfq_id`: Foreign key to RFQ
- `year`: Calendar year (e.g., 2026)
- `volume`: Annual volume in pieces (nullable)
- `flex_percent`: Max capacity % (e.g., 80, 100, 110)
- **Relationships:**
  - `rfq`: Parent RFQ

### SubBOM
```python
from database.models import SubBOM

sub = SubBOM(
    part_id=1,
    item_name="Bushing LL5934",
    quantity=4,
    item_type="assembly",  # "assembly" or "overmold"
    notes="Core pin retention"
)
```

**Fields:**
- `id`: Primary key
- `part_id`: Foreign key to Part
- `item_name`: Component name
- `quantity`: Quantity required
- `item_type`: "assembly" or "overmold"
- `notes`: Optional notes
- **Relationships:**
  - `part`: Parent Part

### PartRevision (Audit Trail)
```python
from database.models import PartRevision

rev = PartRevision(
    part_id=1,
    field_name="weight_g",
    old_value="100.0",
    new_value="125.5",
    changed_by="john_doe",
    change_type="value",
    notes="Updated based on CAD review"
)
```

**Fields:**
- `id`: Primary key
- `part_id`: Foreign key to Part
- `field_name`: Name of changed field
- `old_value`: Previous value (string)
- `new_value`: New value (string)
- `changed_at`: Timestamp (auto-set)
- `changed_by`: Username making change
- `change_type`: "value"/"image"/"geometry"
- `notes`: Optional notes

### Material
```python
from database.models import Material

# Pre-populated, but accessible for reference
material = Material(
    name="Polypropylene",
    short_name="PP-H",
    family="PP",
    density_g_cm3=0.91,
    shrinkage_percent=2.0,
    melt_temp_c=220,
    specific_pressure_bar=400,
    flow_length_ratio=100
)
```

## Calculation Functions

### Geometry Calculations

#### DirectGeometryMode
```python
from calculations import DirectGeometryMode

mode = DirectGeometryMode(projected_area_cm2=150.0)
area = mode.calculate_projected_area()  # 150.0
```

#### BoxEstimateMode
```python
from calculations import BoxEstimateMode

# Formula: (length_mm × width_mm × effective%) / 100 / 100 = area_cm²
mode = BoxEstimateMode(
    length_mm=200,
    width_mm=75,
    effective_percent=100
)
area = mode.calculate_projected_area()  # 150.0

# With effective %
mode2 = BoxEstimateMode(
    length_mm=200,
    width_mm=75,
    effective_percent=50
)
area2 = mode2.calculate_projected_area()  # 75.0
```

### Weight/Volume Conversion

```python
from calculations import auto_calculate_volume, auto_calculate_weight

# Weight → Volume
volume = auto_calculate_volume(
    weight_g=100.0,
    density_g_cm3=0.91
)  # Returns volume_cm3

# Volume → Weight
weight = auto_calculate_weight(
    volume_cm3=110.0,
    density_g_cm3=0.91
)  # Returns weight_g

# Round-trip accuracy
weight_orig = 50.0
volume = auto_calculate_volume(weight_orig, density)
weight_calc = auto_calculate_weight(volume, density)
assert abs(weight_calc - weight_orig) < 0.1  # Within tolerance
```

## Database Access

### Session Management
```python
from database.connection import session_scope
from database.models import RFQ, Part

# Basic query with auto-commit
with session_scope() as session:
    rfq = session.query(RFQ).filter(RFQ.id == 1).first()
    rfq.status = "quoted"
    # Auto-commits on success, rolls back on exception

# Multiple queries
with session_scope() as session:
    rfqs = session.query(RFQ).filter(RFQ.customer == "ACME").all()
    for rfq in rfqs:
        print(rfq.name, len(rfq.parts))
```

### Common Queries

```python
from database.connection import session_scope
from database.models import RFQ, Part, AnnualDemand, PartRevision

# Get RFQ with all parts
with session_scope() as session:
    rfq = session.query(RFQ).get(rfq_id)
    for part in rfq.parts:
        print(part.name, part.weight_g)

# Get annual demands for RFQ
with session_scope() as session:
    rfq = session.query(RFQ).get(rfq_id)
    for ad in rfq.annual_demands:
        print(f"{ad.year}: {ad.volume} pcs ({ad.flex_percent}%)")

# Get part revision history
with session_scope() as session:
    revisions = session.query(PartRevision)\
        .filter(PartRevision.part_id == part_id)\
        .order_by(PartRevision.changed_at.desc())\
        .all()
    for rev in revisions:
        print(f"{rev.changed_at}: {rev.field_name} {rev.old_value} → {rev.new_value}")

# Get sub-BOM items
with session_scope() as session:
    part = session.query(Part).get(part_id)
    for sub in part.sub_boms:
        print(f"{sub.item_name} (qty: {sub.quantity})")
```

### Creating & Updating

```python
from database.connection import session_scope
from database.models import RFQ, Part, AnnualDemand

# Create new RFQ with annual demands
with session_scope() as session:
    rfq = RFQ(
        name="Q1 2026 Project",
        customer="Customer",
        demand_sop=5000,
        demand_sop_date=datetime(2026, 4, 1),
        demand_eaop=10000,
        demand_eaop_date=datetime(2028, 8, 31)
    )
    session.add(rfq)
    session.flush()  # Get ID before commit

    # Add annual demands
    for year in range(2026, 2029):
        ad = AnnualDemand(
            rfq_id=rfq.id,
            year=year,
            volume=5000 + (year - 2026) * 2500,
            flex_percent=100.0
        )
        session.add(ad)

# Update part with audit trail
with session_scope() as session:
    part = session.query(Part).get(part_id)
    old_weight = part.weight_g
    part.weight_g = 150.0

    rev = PartRevision(
        part_id=part.id,
        field_name="weight_g",
        old_value=str(old_weight),
        new_value="150.0",
        changed_by="user",
        change_type="value"
    )
    session.add(rev)
```

## UI Dialogs

### RFQDialog
```python
from ui.dialogs.rfq_dialog import RFQDialog

# Create new RFQ
dialog = RFQDialog(parent_window)
if dialog.exec() == QDialog.DialogCode.Accepted:
    rfq = dialog.get_rfq()
    print(f"Created RFQ: {rfq.name}")

# Edit existing RFQ
dialog = RFQDialog(parent_window, rfq_id=1)
if dialog.exec() == QDialog.DialogCode.Accepted:
    rfq = dialog.get_rfq()
    print(f"Updated RFQ: {rfq.name}")
```

### PartDialog
```python
from ui.dialogs.part_dialog import PartDialog

# Create new part for RFQ
dialog = PartDialog(parent_window, rfq_id=1)
if dialog.exec() == QDialog.DialogCode.Accepted:
    part = dialog.get_part()
    print(f"Created part: {part.name}")

# Edit existing part
dialog = PartDialog(parent_window, rfq_id=1, part_id=5)
if dialog.exec() == QDialog.DialogCode.Accepted:
    part = dialog.get_part()
    print(f"Updated part: {part.name}")
```

## Configuration

### config.py
```python
from pathlib import Path

# Database location (can point to network share for multi-user)
DATABASE_PATH = Path(__file__).parent / "data" / "rfq_tools.db"

# Application info
APP_NAME = "RFQ Tool"
APP_VERSION = "1.0"

# Ensure data directories exist
def ensure_directories():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    (DATABASE_PATH.parent / "projects").mkdir(exist_ok=True)
    (DATABASE_PATH.parent / "seed").mkdir(exist_ok=True)
```

## Error Handling

```python
from database.connection import session_scope
from sqlalchemy.orm.exc import DetachedInstanceError

# Proper error handling
try:
    with session_scope() as session:
        part = session.query(Part).get(1)
        # Operate on part
except Exception as e:
    print(f"Database error: {e}")
    # Session auto-rolls back

# Avoid accessing objects outside session context
with session_scope() as session:
    part = session.query(Part).get(1)
# Don't access part.name here - will raise DetachedInstanceError

# Instead, extract needed data inside session:
with session_scope() as session:
    part = session.query(Part).get(1)
    part_name = part.name
print(part_name)  # Safe to use
```
