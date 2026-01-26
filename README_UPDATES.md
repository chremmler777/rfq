# RFQ Tool v1.0.1 - Release Notes

## What's New in This Release

### ✨ Major UI/UX Overhaul

#### Part Dialog Redesign
- **Two-column layout:** Editing area (left) + persistent properties panel (right)
- **Properties panel never changes context:** Shows all key data while switching tabs
- **Real-time feedback:** All values update as you type/select
- **Professional dark theme:** Dark sidebar with light text for easy reading

#### Color Coding System
- **Comprehensive color system** applied throughout the application
- **Yellow (#FFD54F):** Estimated values
- **Blue (#64B5F6):** BOM sourced values
- **Red (#FF5050):** Missing required fields
- **Green (#70AD47):** Complete/valid status
- **Built-in legend** in properties panel with tooltips

#### Image Management
- **Bigger preview:** 120px height for better visibility
- **Click to zoom:** Click thumbnail to open full preview with zoom controls
- **Delete button:** Remove image with confirmation
- **Drag-drop support:** Drag images onto the preview area
- **Single image:** Compact, efficient storage

#### Form Improvements
- **No autofill for new parts:** User must explicitly enter all values
- **Auto-fill for existing parts:** Editing restores previous selections
- **Section headers:** Bold, larger font with clear spacing
- **Clean checkboxes:** Removed visual clutter, clear text labels
- **Gray separators:** Visual distinction between estimated checkbox and data fields
- **Required field indicators:** Asterisks on Material and Surface Finish

#### Properties Panel (New)
- **8 key properties displayed:** Name, Volume, Material, Total Demand, Weight, Proj Area, Wall Thick, Surface Finish
- **Missing field highlighting:** RED text shows what's not filled
- **Source colors:** Yellow/blue backgrounds show data origin
- **Color legend:** Always visible reference for what colors mean
- **Tooltips everywhere:** Hover for explanations

---

## Database Enhancements

### New Fields (Automatic Migration)
- `surface_finish` - Type of surface finish
- `surface_finish_detail` - Specification text
- `surface_finish_estimated` - Is it estimated?
- `projected_area_source` - Where did this come from?
- `wall_thickness_needs_improvement` - Flag for review

### Updated Enum
**SurfaceFinish:** 6 options
- Draw Polish
- Polish
- High Polish
- Grain
- Technical Polish
- EDM

### Smart Migration
- Automatic schema upgrade on startup
- No data loss - existing records preserved
- Backward compatible with v1.0.0 databases

---

## Geometry Tracking

### Projected Area Source
- **Part Data** (default) - From CAD/measurements
- **BOM** - From Bill of Materials
- Shows blue background when BOM selected
- Auto-yellows in box estimate mode

### Wall Thickness Source
- **Data** - From design specs
- **BOM** - From bill of materials
- **Estimated** - Conservative guess (2.5mm standard)
- "Estimate" button auto-sets to 2.5mm + estimated source
- Color updates in real-time

### Improvement Tracking
- Check "3D wall thickness needs improvement" for QA flag
- Persists across edit sessions

---

## Manufacturing Tab Reorganization

### New Structure (Top to Bottom)
1. **Manufacturing Options** (top)
   - Assembly required? ☐
   - Overmold? ☐

2. **Assembly Sub-BOM** (conditionally visible)
   - Name, Qty, Notes

3. **Overmold Sub-BOM** (conditionally visible)
   - Material/Item, Qty, Notes

*(Removed deprecated degate/EOAT note)*

---

## Overview Table Enhancements (BOM Tab)

### New Columns
- **Surface Finish** - Shows specification
- **Status** - Complete ✓ or Missing: [fields]

### Cell Color Coding
- Yellow cells = Estimated data
- Blue cells = BOM sourced data
- Red row text = Incomplete part
- Green status = All required fields filled

---

## Tooltips & Help

### Everywhere
- Hover over color legend items for explanations
- Hover over property labels for descriptions
- Estimated checkboxes explain their purpose
- Source dropdowns show what each option means

### Color Legend
```
■ Estimated        → Value is estimated (yellow)
■ BOM Sourced      → Value from Bill of Materials (blue)
■ Missing Required → Field not filled (red)
```

---

## Installation & Migration

### For New Users
1. Run normally
2. First launch auto-creates database
3. Start creating parts
4. No special steps needed

### For Existing Users (v1.0.0)
1. Update the code
2. Run normally
3. Auto-migration adds new columns
4. **No data loss**
5. All existing parts still available
6. New features available immediately

---

## Breaking Changes
**None.** This release is 100% backward compatible.

---

## Performance
- No performance impact
- Real-time updates in properties panel are instant
- Database queries unchanged
- File size minimal

---

## Accessibility
- High contrast colors for visibility
- Tooltips explain every feature
- Keyboard navigation works as before
- Drag-drop is optional (file dialog always available)

---

## Known Limitations
- Single image per part (by design - keeps it simple)
- Properties panel width is fixed (prevents text wrapping)
- Color legend takes ~40px height (always visible)
- Surface Finish is now required (was optional)

---

## Files Changed

### New Files
- `ui/color_coding.py` - Color system
- `ui/widgets/image_preview.py` - Zoom preview

### Modified Files
- `database/models.py` - 5 new fields, enum update
- `database/connection.py` - Auto-migration
- `database/__init__.py` - Export updates
- `ui/styles.py` - New color constants
- `ui/dialogs/part_dialog.py` - Major redesign
- `ui/rfq_detail_window.py` - Table enhancements
- `IMPLEMENTATION.md` - Complete documentation

### Unchanged
- All other functionality works as v1.0.0
- All existing data preserved
- All existing workflows supported

---

## Testing Checklist

✅ Database migration works
✅ New parts start empty
✅ Existing parts autofill
✅ Properties panel updates in real-time
✅ Missing fields show in RED
✅ Color indicators work correctly
✅ Image preview zooms properly
✅ Delete image with confirmation works
✅ Tooltips appear on hover
✅ Color legend is visible
✅ All tabs switch without context loss
✅ BOM table shows new columns
✅ Source colors appear in table
✅ Status column shows correctly
✅ Manufacturing tab reordered

---

## Feedback Welcome

This release focuses on:
- **Clarity:** Clear visual indicators of data quality
- **Usability:** Properties always visible, no searching
- **Aesthetics:** Professional dark theme with vibrant accents
- **Efficiency:** No wasted space, all info at a glance

Please report any issues or suggestions for improvement.

---

**Version 1.0.1** | Released 2026-01-26
