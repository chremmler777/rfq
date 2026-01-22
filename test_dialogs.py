#!/usr/bin/env python3
"""Test dialogs can be instantiated without crashing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from database import init_db, seed_database, get_session
from database.models import RFQ, RFQStatus
from ui.dialogs.rfq_dialog import RFQDialog
from ui.dialogs.part_dialog import PartDialog

def test_dialogs():
    """Test dialog instantiation and basic functionality."""
    print("\n=== Testing Dialog Instantiation ===")

    # Initialize app
    app = QApplication.instance() or QApplication([])

    # Initialize database
    init_db()
    seed_database()

    try:
        # Test RFQ Dialog - New
        print("Testing RFQ Dialog (new)...")
        dialog = RFQDialog(None)
        assert dialog is not None
        print("✓ RFQ Dialog instantiated")

        # Test RFQ Dialog - Edit
        session = get_session()
        rfq = RFQ(name="Test", customer="Test Co", status=RFQStatus.DRAFT.value)
        session.add(rfq)
        session.commit()
        rfq_id = rfq.id
        session.close()

        print("Testing RFQ Dialog (edit)...")
        dialog = RFQDialog(None, rfq_id=rfq_id)
        assert dialog is not None
        assert dialog.name_input.text() == "Test"
        print("✓ RFQ Dialog edit instantiated and loaded correctly")

        # Test Part Dialog - New
        print("Testing Part Dialog (new)...")
        dialog = PartDialog(None, rfq_id=rfq_id)
        assert dialog is not None
        print("✓ Part Dialog (new) instantiated")

        # Create a part for testing edit
        session = get_session()
        from database.models import Part
        part = Part(
            rfq_id=rfq_id,
            name="Test Part",
            assembly=False,
            degate="no",
            eoat_type="standard"
        )
        session.add(part)
        session.commit()
        part_id = part.id
        session.close()

        # Test Part Dialog - Edit
        print("Testing Part Dialog (edit)...")
        dialog = PartDialog(None, rfq_id=rfq_id, part_id=part_id)
        assert dialog is not None
        assert dialog.name_input.text() == "Test Part"
        print("✓ Part Dialog (edit) instantiated and loaded correctly")

        print("\n✓ All dialog tests passed!")
        return True

    except Exception as e:
        print(f"\n✗ Dialog test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_dialogs()
    sys.exit(0 if success else 1)
