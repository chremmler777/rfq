# RFQ Tool v1.0.1 - Implementation Documentation

## Overview

This document describes the major enhancements to the RFQ Tool, focusing on the Part Dialog improvements and UI/UX redesign implemented in this version.

---

## Major Features Added

### Phase 1: Database & Foundation
**Files Modified:**
- `database/models.py` - Updated SurfaceFinish enum and added 5 new Part fields
- `database/connection.py` - Added schema migration with `upgrade_schema()` function
- `database/__init__.py` - Exports updated enum

**Changes:**
- **SurfaceFinish Enum** (6 options): DRAW_POLISH, POLISH, HIGH_POLISH, GRAIN, TECHNICAL_POLISH, EDM
- **New Part Fields:**
  - `surface_finish: str` - Surface finish type
  - `surface_finish_detail: str` - Specification (e.g., "grid 800")
  - `surface_finish_estimated: bool` - Whether surface finish is estimated
  - `projected_area_source: str` - Source of projected area ("data", "bom", "estimated")
  - `wall_thickness_needs_improvement: bool` - Flag for 3D improvement needed

- **Wall Thickness Source** changed default from "given" to "data" (supports: "data", "bom", "estimated")
- **Schema Migration** automatically adds new columns to existing databases without data loss

---

### Phase 2: Color Coding Module
**New File:**
- `ui/color_coding.py` - Reusable color coding system

**Features:**
- `COLOR_ESTIMATED_BG = #FFD54F` (Vibrant Yellow)
- `COLOR_BOM_BG = #64B5F6` (Vibrant Blue)
- `COLOR_MISSING_TEXT = #FF5050` (Red)
- `COLOR_COMPLETE_BG = #E6F4E6` (Light Green)

**Functions:**
- `get_source_color(source)` - Returns QColor for source type
- `apply_source_color_to_widget(widget, source)` - Applies color + dark text to widgets
- `apply_source_color_to_table_item(item, source)` - Applies color to table cells
- `get_missing_fields(part)` - Returns list of missing required fields
- `is_part_complete(part)` - Boolean check for completeness

**Required Fields:** Name, Volume, Material, Total Demand

---

### Phase 3: Image Preview & Management
**Files Modified:**
- `ui/dialogs/part_dialog.py` - Enhanced image handling
- `ui/widgets/image_preview.py` (NEW) - Shared zoom preview
- `ui/rfq_detail_window.py` - Refactored to use shared preview

**Features:**
- **Image Preview Window** - Click thumbnail to zoom with:
  - Zoom in/out buttons (×1.2 scaling)
  - Fit window to reset zoom
  - Scroll area for panned viewing

- **Delete Image** button with confirmation dialog
- **Single image support** - Compact 120px preview area
- **Drag-drop or upload** support
- **Persistent across edits** - Image data maintained in session

---

### Phase 4: Surface Finish (Basic Info Tab)
**Features:**
- Dropdown with 6 surface finish options
- Detail text input for specifications (e.g., "Ra 1.6 μm", "grid 800")
- "Estimated" checkbox to mark as estimated
- **Auto-colors when estimated:** Yellow background + black text
- **Required field** marked with asterisk
- **Material field also required**

---

### Phase 5: Geometry Tab Source Tracking
**Features:**

**Projected Area Source:**
- Dropdown: "Part Data" (default) or "BOM"
- Blue background when BOM selected
- Auto-yellow when box mode selected (estimated)

**Wall Thickness Source:**
- Dropdown: "Data" | "BOM" | "Estimated"
- Color changes based on selection:
  - Data → normal
  - BOM → blue background
  - Estimated → yellow background
- "Estimated (2.5mm)" button sets both value and source
- "3D wall thickness needs improvement" checkbox

**Color Coding:**
- Estimated values: Yellow (#FFD54F)
- BOM values: Blue (#64B5F6)
- Normal/Data: White (default)

---

### Phase 6: Manufacturing Tab Reorder
**Changes:**
- **Manufacturing Options moved to TOP** (checkboxes for Assembly/Overmold)
- **Sub-BOM tables below** (conditionally visible based on checkboxes)
- **Removed deprecated note** about degate/EOAT (now tool-level)

---

### Phase 7: Properties Panel (Right Sidebar - NEW)
**Layout:** Two-column design
- Left: Scrollable tabs with editing fields
- Right: Persistent properties panel (never changes context)

**Properties Panel Features:**
- **Dark theme:** #2c3e50 background, #ecf0f1 text
- **Displays 8 key properties:**
  - Name (required)
  - Volume (required)
  - Material (required)
  - Total Demand (required)
  - Weight
  - Projected Area (with source color)
  - Wall Thickness (with source color)
  - Surface Finish (with estimated indicator)

- **Missing fields in RED text**
- **Complete status in GREEN**
- **Real-time updates** as user edits any field
- **Source color indicators:** Yellow/blue backgrounds for estimated/BOM values
- **Built-in color legend** with tooltips:
  - ■ Estimated (yellow)
  - ■ BOM Sourced (blue)
  - ■ Missing Required (red)

---

### Phase 8: Overview Table Color Coding (RFQ Detail Window)
**Files Modified:**
- `ui/rfq_detail_window.py` - Enhanced BOM table visualization

**New Columns:**
- Column 8: Surface Finish (after Material)
- Column 13: Status (showing "Complete" or "Missing: [fields]")

**Color Coding per Cell:**
- **Projected Area:** Yellow if estimated/box-mode, Blue if BOM
- **Wall Thickness:** Yellow if estimated, Blue if BOM
- **Surface Finish:** Yellow if estimated
- **Incomplete parts:** Red text across entire row

**Status Column:**
- Green: "✓ Complete"
- Red: "Missing: [field names]"

---

## UI/UX Improvements

### Section Headers
- **Bold, 10pt font** for emphasis
- **15px spacing** between sections
- Clear visual hierarchy

### Checkboxes
- Removed `☐` square symbols
- Clean text: "Estimated", "3D wall thickness needs improvement"
- **Gray vertical separator lines** between checkbox and fields
- Visual clarity on what is "estimated"

### Dropdowns
- **No empty "Select..." placeholders**
- New parts start empty (user must choose)
- Existing parts autofill with previous values
- Clear, human-readable options

### Image Upload
- **120px preview area** (bigger for visibility)
- Compact buttons: "Upload" and "Delete"
- Drag-drop and file dialog support
- Click thumbnail to zoom preview
- Single image per part

### Form Validation
- **Properties panel replaces separate validation panel**
- Missing required fields highlighted in RED
- Validation status always visible
- No separate "validation panel" cluttering UI

---

## Color System (Constant Throughout App)

### Source Indicators
```
Yellow (#FFD54F) = Estimated value
Blue   (#64B5F6) = BOM sourced value
White  (default)  = Part data / manual entry
Red    (#FF5050)  = Missing required field
Green  (#70AD47)  = Complete/valid
```

### Visual Implementation
- **Widgets (spinboxes, combos, inputs):** Colored background + black text
- **Table cells:** Colored background + black text
- **Text:** Dark text on light backgrounds; light text on dark backgrounds
- **Properties panel:** Light text (#ecf0f1) on dark background (#2c3e50)

### Tooltips
- All color legend items have mouseover tooltips
- All properties have explanatory tooltips
- "Estimated" checkboxes explain their purpose
- Source dropdowns explain what each option means

---

## File Structure

```
rfq/
├── database/
│   ├── __init__.py          (exports updated)
│   ├── models.py            (5 new fields, updated enum)
│   ├── connection.py        (upgrade_schema() added)
│   └── ...
├── ui/
│   ├── color_coding.py      (NEW - color constants & functions)
│   ├── styles.py            (updated with new colors)
│   ├── rfq_detail_window.py (table columns & coloring)
│   ├── dialogs/
│   │   └── part_dialog.py   (major overhaul)
│   └── widgets/
│       ├── image_preview.py (NEW - shared zoom window)
│       └── ...
├── main.py
├── config.py
└── ...
```

---

## Database Migration

**Automatic on startup:**
1. Run `init_db()` in `database/connection.py`
2. `upgrade_schema()` checks for missing columns
3. Adds new columns via `ALTER TABLE` if needed
4. Migrates `wall_thickness_source="given"` → `"data"`
5. No data loss - existing records preserved

---

## How to Use

### Creating a New Part

1. **Basic Info Tab:**
   - Enter Part Name (required)
   - Enter Part Number (optional)
   - Select Material (required) - starts empty
   - Select Surface Finish (required) - starts empty
   - Mark "Estimated" if values are guesses
   - Upload image (optional, 120px preview)

2. **Geometry Tab:**
   - Choose geometry mode: Direct or Box estimate
   - Set Projected Area (with source: Data/BOM)
   - Set Wall Thickness (with source: Data/BOM/Estimated)
   - Check "needs improvement" if 3D review needed

3. **Manufacturing Tab:**
   - Check "Assembly required" if part needs sub-components
   - Add assembly BOM items (name, qty, notes)
   - Check "Overmold" if overmold process needed
   - Add overmold BOM items

4. **Demand & Notes Tab:**
   - Enter Total Demand (pcs) - required
   - Add Engineering Notes (optional)
   - Add Sales Remarks (optional)

5. **Properties Panel (Always Visible):**
   - Monitor all values in real-time
   - See missing required fields in RED
   - Understand data source (yellow/blue backgrounds)
   - Reference color legend

6. **Save:**
   - All required fields filled? Panel shows ✓ Complete
   - Click Save Part
   - Returns to RFQ overview

### Editing a Part

- Same as above, but dropdowns and fields are pre-filled
- Can change any value at any time
- Properties panel updates in real-time
- Image carries forward (can delete or replace)

### Viewing Completeness

- **Properties Panel:** Shows missing required fields in RED
- **BOM Table:**
  - Complete parts show green "Complete" status
  - Incomplete parts show red text + "Missing: [field names]"

---

## Keyboard & Mouse Features

### Tooltips
- Hover over any property label → see what it is
- Hover over color legend items → explanation of color
- Hover over estimated checkboxes → see why they exist

### Drag & Drop
- Drag image from file explorer onto image box
- Click image thumbnail to zoom/preview
- Click Delete to remove image (with confirmation)

### Source Indicators
- When setting wall thickness to "Estimated" source
  - Spinbox background turns yellow
  - Properties panel shows yellow background
- When setting projected area to "BOM" source
  - Spinbox background turns blue
  - Properties panel shows blue background

---

## Verification Checklist

- [x] Database migration runs without errors
- [x] New part creation starts with empty dropdowns
- [x] Existing part editing autofills previous values
- [x] Properties panel updates in real-time
- [x] Missing fields show in RED
- [x] Color indicators (yellow/blue) appear correctly
- [x] Image preview works (click thumbnail to zoom)
- [x] Delete image button works with confirmation
- [x] Image size is 120px (visible but compact)
- [x] Section headers are bold and spaced
- [x] Checkboxes have no `☐` symbols
- [x] Separators between checkbox and fields
- [x] Tooltips work on legend items
- [x] BOM table shows source colors
- [x] Status column shows Complete/Missing
- [x] Manufacturing tab reordered (options on top)
- [x] All syntax passes Python compilation
- [x] All imports work correctly

---

## Version Info

- **Version:** 1.0.1
- **Date:** 2026-01-26
- **Changes:** Part Dialog Redesign & Color Coding System
- **Compatibility:** Backward compatible (auto-migrates existing DB)

---

## Technical Details

### Color Coding System
- Uses Material Design color palette
- High contrast for accessibility
- Works on both light and dark backgrounds
- Applied consistently across all UI elements

### Properties Panel
- Updates via signal-slot connections
- 8 signals connected to `_update_validation_status()`
- Persistent across tab switches (QFrame with fixed width)
- Separated from scrollable content area

### Source Indicators
- Applied to both widgets (in-place coloring) and table cells
- Checkbox changes trigger color updates immediately
- Dropdown changes trigger color updates immediately
- Real-time feedback to user

### Tooltips
- Set on all interactive elements
- Explain purpose and source of data
- Color legend items have contextual help
- Improve discoverability of features

---

## Future Enhancements

Potential improvements for next version:
- Part templates for common configurations
- Bulk import from CSV/Excel
- Part history/revision tracking UI
- Advanced search and filtering
- Export to BOM report
- 3D model preview integration
- Material database synchronization
- Supplier integration

---

## Support & Issues

For issues or questions:
1. Check the color legend in properties panel
2. Verify all required fields are filled (red indicator)
3. Hover over tooltips for explanations
4. Check database migration completed (no errors at startup)
5. Review implementation details in this document

---

**End of Documentation**
