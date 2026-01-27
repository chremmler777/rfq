#!/usr/bin/env python3
"""Test part saving to debug crash."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from database import init_db, seed_database, get_session
from database.models import RFQ, RFQStatus
from ui.dialogs.part_dialog import PartDialog

def test_save_part():
    """Test saving a new part."""
    print("\n=== Testing Part Save ===")

    app = QApplication.instance() or QApplication([])
    init_db()
    seed_database()

    try:
        # Create RFQ
        session = get_session()
        rfq = RFQ(name="Test Project", customer="Test Co", status=RFQStatus.DRAFT.value)
        session.add(rfq)
        session.commit()
        rfq_id = rfq.id
        session.close()

        print(f"✓ Created RFQ {rfq_id}")

        # Create and show dialog
        dialog = PartDialog(None, rfq_id=rfq_id)

        # Fill in part data
        dialog.name_input.setText("Test Housing")
        dialog.part_number_input.setText("PART-001")
        dialog.material_combo.setCurrentIndex(1)  # Select first material
        dialog.surface_finish_combo.setCurrentIndex(1)  # Select first surface finish
        dialog.weight_input.setText("100.0")
        dialog.volume_input.setText("110.0")
        dialog.proj_area_input.setText("150.0")
        dialog.wall_thick_input.setText("2.5")
        dialog.demand_peak_spin.setValue(5000)
        dialog.demand_peak_spin_year.setValue(10000)
        dialog.assembly_check.setChecked(True)

        print("✓ Filled in part data")

        # Simulate save
        dialog._on_save()

        print("✓ Save completed without crash!")

        # Get the saved part
        part = dialog.get_part()
        if part:
            print(f"✓ Retrieved saved part: {part.name} (ID: {part.id})")
            return True
        else:
            print("✗ Failed to retrieve saved part")
            return False

    except Exception as e:
        print(f"✗ Save failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_save_part()
    sys.exit(0 if success else 1)
