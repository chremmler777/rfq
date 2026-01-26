# Part Revision Tracking System

## Overview

The RFQ Tool now includes comprehensive revision tracking for all parts. Every change is logged with timestamps and user attribution, allowing you to see exactly what changed, when it changed, and who changed it.

---

## Features

### 1. Automatic Change Logging

**Initial Creation**
- When a part is first created, all non-empty fields are logged as "initial creation"
- Each field value is recorded with no "old value" (shows just the new value)
- Example: `Name: "Widget Base"` (created)

**Field Updates**
- Every time you edit a part field, the change is logged
- Both old and new values are recorded
- Timestamp and user attribution captured
- Example: `Volume: 45.5 cm³ → 50.0 cm³` (updated)

**Tracked Fields**
- Part name
- Volume
- Weight
- Projected area
- Wall thickness
- Surface finish
- Material selection
- Total demand
- Manufacturing options (assembly, overmold)
- All geometry and source fields

---

## Properties Panel (Real-Time Updates)

### Always Visible on the Right
- Displays 8 key metrics in real-time
- Updates instantly as you type/select values
- Shows what you're currently entering

### Display Modes

**Complete Status**
```
✓ Complete (green)
```
All 4 required fields filled:
- Part Name
- Volume (cm³)
- Material
- Total Demand

**Missing Fields**
```
Missing: Volume, Material (red)
```
Shows exactly which required fields are empty

### Color Coding
- **Yellow (#FFD54F):** Estimated values
- **Blue (#64B5F6):** BOM sourced values
- **Red (#FF5050):** Missing required fields
- **White:** Normal data (part-defined)

---

## New Parts Start Completely Blank

### All Input Fields Empty
- Part Name: (blank)
- Volume: (no value)
- Weight: (no value)
- Material: (empty dropdown, "Select...")
- Surface Finish: (empty dropdown, "Select...")
- Wall Thickness: (no value)
- And all other fields...

### Properties Panel Shows All Blanks
```
Name: -
Volume: -
Material: -
Total Demand: -
Weight: -
Proj. Area: -
Wall Thick: -
Surface Finish: -
```

### No Autofill for New Parts
- You must explicitly enter every value
- Ensures intentional, not accidental, data entry
- Every value you enter is logged as initial creation

### Autofill for Existing Parts
- When editing an existing part, dropdowns restore previous selections
- Spinboxes show previous values
- Faster editing workflow

---

## Revisions Tab (History View)

### Location
- 6th tab in the Part Dialog
- Always available (shows "No changes yet" for new parts)

### Organization Structure

```
📅 2026-01-26 (Date - collapsed by default)
   👤 user1 (User - collapsed by default)
      08:15:30 📝 name: "" → "Widget Base"
      08:15:31 📝 volume_cm3: "" → "50.5"
      08:15:32 📝 material_id: "" → "3"
   👤 user2
      08:30:45 📝 wall_thickness_mm: "2.5" → "3.0"

📅 2026-01-25
   👤 user1
      14:22:10 📝 weight_g: "45.0" → "47.5"
```

### Interaction Pattern

1. **Dates are collapsed by default**
   - Click to expand and see users for that day
   - Shows icon: `📅 2026-01-26`

2. **Users are collapsed by default**
   - Click to expand and see detailed changes for that user
   - Shows icon: `👤 user1`

3. **Changes are always visible**
   - Time, field name, old value → new value
   - Shows icon: `📝 field_name: old → new`
   - Initial creation shows just the new value

### Empty State
- When no revisions exist: "📋 No changes yet" (grayed out)
- After saving first time: Revisions populate automatically

---

## Typical Workflow

### Creating a New Part

1. **Open Part Dialog**
   - Click "Add Part"
   - Properties panel shows all blanks

2. **Fill In Values**
   - Type "Widget Base" in Name field
   - Select Material from dropdown
   - Enter Volume value
   - etc.
   - Properties panel updates in real-time

3. **Save Part**
   - Click "Save Part"
   - All entered values logged as initial creation

4. **View Revisions**
   - Click "Revisions" tab
   - Expand date → expand user
   - See all values that were created

### Editing an Existing Part

1. **Open Part Dialog**
   - Click "Edit" on part
   - Properties panel shows current values (some may be blank)
   - Dropdowns show previous selections

2. **Make Changes**
   - Modify any field
   - Properties panel updates in real-time
   - Save button ready

3. **Save Changes**
   - Click "Save Part"
   - Only changed fields logged
   - Old → new values recorded

4. **View History**
   - Click "Revisions" tab
   - See all changes since creation
   - Grouped by date and user

---

## Database Storage

### PartRevision Table

| Field | Content |
|-------|---------|
| `id` | Unique revision ID |
| `part_id` | Which part this change belongs to |
| `changed_at` | Timestamp (YYYY-MM-DD HH:MM:SS) |
| `changed_by` | Username (currently "user") |
| `field_name` | Which field changed (e.g., "name", "volume_cm3") |
| `old_value` | Previous value (or empty for creation) |
| `new_value` | New value |
| `change_type` | "initial_creation" or "value" |
| `notes` | Optional notes about the change |

### Storage Details
- Stored in SQLite database
- Safe for concurrent users (WAL mode)
- Automatic timestamp on each change
- Unlimited revision history (no archival)
- Can be exported for audits

---

## Example Scenarios

### Scenario 1: Create a Simple Part

**Initial creation:**
```
2026-01-26 08:15:00 user1
  📝 name: "" → "Handle Assembly"
  📝 volume_cm3: "" → "75.5"
  📝 material_id: "" → "2"  (ABS)
  📝 parts_over_runtime: "" → "50000"
```

**First edit (next day):**
```
2026-01-27 10:30:00 user2
  📝 weight_g: "" → "125.0"
  📝 surface_finish: "" → "polish"
```

**Latest edit (same user, same day):**
```
2026-01-27 11:15:00 user2
  📝 wall_thickness_mm: "" → "2.5"
```

### Scenario 2: Track Multiple Edits

User1 creates part, User2 updates material, User3 updates wall thickness:
```
📅 2026-01-26
  👤 user1
    08:15:00 📝 name: "" → "Button"
    08:15:01 📝 volume_cm3: "" → "10.0"
  👤 user2
    09:30:00 📝 material_id: "1" → "3"
  👤 user3
    14:45:00 📝 wall_thickness_mm: "2.0" → "2.5"
```

---

## Advantages

### Quality Assurance
- See who made which changes
- Identify incomplete edits
- Track estimation changes to actual data

### Compliance & Auditing
- Full audit trail of all changes
- Timestamps prove when changes occurred
- User attribution (useful for multi-user environments)

### Debugging
- Trace why a value is what it is
- See progression from initial to final
- Identify who to ask about specific decisions

### Documentation
- Automatic documentation of data sources
- Shows evolution of part specification
- No manual record-keeping needed

---

## Technical Details

### Implementation

**Database:** PartRevision model in models.py
```python
class PartRevision(Base):
    id: PK
    part_id: FK to Part
    changed_at: DateTime (auto-timestamp)
    changed_by: String (username)
    field_name: String (what changed)
    old_value: Text (previous state)
    new_value: Text (new state)
    change_type: "initial_creation" | "value"
```

**UI:** Revisions Tab with QTreeWidget
```python
Tree Structure:
├── Date (collapsed)
│   ├── User (collapsed)
│   │   ├── Change 1
│   │   ├── Change 2
│   │   └── Change N
│   └── User N
└── Date N
```

**Grouping:** Collections.defaultdict for efficient grouping

```python
by_date = defaultdict(lambda: defaultdict(list))
# Group revisions by date, then by user within each date
# Allows fast hierarchical rendering
```

---

## Configuration & Future Enhancements

### Current Configuration
- User attribution: Set to "user" (future: OS username)
- Timestamp format: YYYY-MM-DD HH:MM:SS
- All revisions permanent (no deletion/archival)

### Potential Future Features
- Revision comparison (side-by-side view of two revisions)
- Undo/rollback (restore to previous state)
- Export revision history to PDF
- Advanced search/filtering by date, user, field
- Revision notes/comments field
- Automatic archival of old revisions
- Integration with engineering change order (ECO) system

---

## Usage Tips

### Effective Revision Tracking

1. **Save Frequently**
   - Each save creates a milestone
   - Makes revision history cleaner
   - Easier to track specific decisions

2. **Use Meaningful Names**
   - "Widget Base v2" instead of "Part1"
   - Helps in revision history readability

3. **Update All Fields**
   - Complete the part spec at once
   - Avoids fragmented history
   - Creates cleaner revision timeline

4. **Review Before Saving**
   - Check Properties panel
   - Ensure all required fields filled (green ✓)
   - Reduces error corrections in history

### Reading Revision History

1. **Understand the Flow**
   - Top date is most recent
   - Expand dates to see timeline
   - Revisions within date are time-ordered

2. **Identify Data Source**
   - Look at who created vs. who updated
   - Check if estimated (checkbox) or measured
   - Track evolution from estimate to actual data

3. **Investigate Changes**
   - If value seems wrong, check history
   - See who changed it and when
   - Might reveal data entry error

---

## Support & Troubleshooting

### Revisions Tab Shows "No changes yet"
- **Reason:** Part is brand new and hasn't been saved
- **Solution:** Fill in values and save first

### Missing revisions in history
- **Reason:** Revisions only logged on explicit save
- **Solution:** Changes aren't saved until you click "Save Part"

### Revisions for fields I didn't change
- **Reason:** Fields have default values that change on save
- **Solution:** This is normal - all non-zero values are logged on initial creation

### Date grouping not showing
- **Reason:** All revisions on same day
- **Solution:** All changes grouped under one date node - expand to see users and details

---

## Version Info

- **Feature Added:** v1.0.2 (Revision Tracking)
- **Backward Compatible:** Yes (new feature, doesn't affect existing parts)
- **Database Migration:** Automatic (PartRevision table created on first use)
- **User Attribution:** Currently "user" (OS username in future versions)

---

**End of Revision Tracking Documentation**
