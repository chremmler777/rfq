#!/usr/bin/env python3
"""Comprehensive test suite for all functionality."""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db, seed_database, get_session, PartRevision
from database.models import RFQ, Part, Material, RFQStatus
from calculations import BoxEstimateMode, auto_calculate_volume, auto_calculate_weight

def test_database_init():
    """Test database initialization."""
    print("\n=== Testing Database Initialization ===")
    try:
        init_db()
        print("✓ Database created")

        materials_added, machines_added = seed_database()
        print(f"✓ Seeded {materials_added} materials and {machines_added} machines")
        return True
    except Exception as e:
        print(f"✗ Database init failed: {e}")
        return False


def test_rfq_creation():
    """Test RFQ creation and retrieval."""
    print("\n=== Testing RFQ Creation ===")
    try:
        session = get_session()

        # Create RFQ
        rfq = RFQ(
            name="Test Project Alpha",
            customer="ACME Corporation",
            status=RFQStatus.DRAFT.value,
            notes="Initial test project"
        )
        session.add(rfq)
        session.commit()
        rfq_id = rfq.id

        print(f"✓ Created RFQ: {rfq.name} (ID: {rfq_id})")

        # Retrieve RFQ
        retrieved = session.query(RFQ).filter(RFQ.id == rfq_id).first()
        assert retrieved is not None, "RFQ not found after creation"
        assert retrieved.name == "Test Project Alpha", "RFQ name mismatch"
        print(f"✓ Retrieved RFQ: {retrieved.name}")

        session.close()
        return rfq_id
    except Exception as e:
        print(f"✗ RFQ creation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_part_creation(rfq_id: int):
    """Test part creation with all new fields."""
    print("\n=== Testing Part Creation ===")
    try:
        session = get_session()

        # Get a material
        material = session.query(Material).filter(Material.short_name == "PP-H").first()
        assert material is not None, "Material not found"

        # Create part with all fields
        part = Part(
            rfq_id=rfq_id,
            name="Housing Assembly",
            part_number="PART-001",
            material_id=material.id,
            weight_g=125.5,
            volume_cm3=138.0,
            projected_area_cm2=250.0,
            wall_thickness_mm=2.5,
            demand_sop=5000,
            demand_eaop=7500,
            demand_peak=10000,
            parts_over_runtime=50000,
            assembly=True,
            degate="yes",
            overmold=False,
            eoat_type="complex",
            notes="Complex assembly with tight tolerances",
            remarks="Customer requested quick turnaround",
            geometry_mode="direct",
            image_filename="housing_v1.png",
            image_updated_date=datetime.now()
        )
        session.add(part)
        session.commit()
        part_id = part.id

        print(f"✓ Created Part: {part.name} (ID: {part_id})")
        print(f"  - Material: {material.short_name}")
        print(f"  - Weight: {part.weight_g}g, Volume: {part.volume_cm3}cm³")
        print(f"  - Assembly: {part.assembly}, EOAT: {part.eoat_type}")
        print(f"  - Demand SOP: {part.demand_sop} pcs/year")

        session.close()
        return part_id
    except Exception as e:
        print(f"✗ Part creation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_geometry_calculator():
    """Test geometry calculation modes."""
    print("\n=== Testing Geometry Calculator ===")
    try:
        # Test direct mode
        from calculations.geometry_calculator import DirectGeometryMode
        direct = DirectGeometryMode(projected_area_cm2=150.0)
        area = direct.calculate_projected_area()
        assert area == 150.0, f"Direct mode failed: expected 150, got {area}"
        print(f"✓ Direct Mode: 150 cm² → {area} cm²")

        # Test box mode
        box = BoxEstimateMode(length_mm=200, width_mm=75, effective_percent=100)
        area = box.calculate_projected_area()
        expected = (200 * 75) / 100  # = 150 cm²
        assert area == expected, f"Box mode failed: expected {expected}, got {area}"
        print(f"✓ Box Mode: 200×75mm @ 100% → {area} cm²")

        # Test with effective percentage
        box2 = BoxEstimateMode(length_mm=200, width_mm=75, effective_percent=50)
        area2 = box2.calculate_projected_area()
        expected2 = (200 * 75 * 0.5) / 100  # = 75 cm²
        assert area2 == expected2, f"Box mode with % failed: expected {expected2}, got {area2}"
        print(f"✓ Box Mode: 200×75mm @ 50% → {area2} cm²")

        return True
    except Exception as e:
        print(f"✗ Geometry calculation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_weight_volume_calculation():
    """Test weight/volume auto-calculation."""
    print("\n=== Testing Weight ↔ Volume Calculation ===")
    try:
        session = get_session()

        # Get material with density
        material = session.query(Material).filter(Material.short_name == "PP-H").first()
        assert material is not None, "Material not found"
        assert material.density_g_cm3 is not None, "Material has no density"

        density = material.density_g_cm3
        print(f"  Material: {material.short_name} (density: {density} g/cm³)")

        # Test weight → volume
        weight = 100.0
        volume = auto_calculate_volume(weight, density)
        assert volume is not None, "Volume calculation returned None"
        print(f"✓ Weight→Volume: {weight}g → {volume}cm³")

        # Test volume → weight
        volume2 = 110.0
        weight2 = auto_calculate_weight(volume2, density)
        assert weight2 is not None, "Weight calculation returned None"
        print(f"✓ Volume→Weight: {volume2}cm³ → {weight2}g")

        # Test round-trip
        original_weight = 50.0
        calc_volume = auto_calculate_volume(original_weight, density)
        calc_weight = auto_calculate_weight(calc_volume, density)
        assert abs(calc_weight - original_weight) < 0.1, f"Round-trip failed: {original_weight} → {calc_volume} → {calc_weight}"
        print(f"✓ Round-trip: {original_weight}g → {calc_volume}cm³ → {calc_weight}g")

        session.close()
        return True
    except Exception as e:
        print(f"✗ Weight/Volume calculation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_revision_tracking(part_id: int):
    """Test revision/audit log creation and retrieval."""
    print("\n=== Testing Revision Tracking ===")
    try:
        session = get_session()

        # Create revisions
        rev1 = PartRevision(
            part_id=part_id,
            field_name="weight_g",
            old_value="100.0",
            new_value="125.5",
            changed_by="test_user",
            change_type="value",
            notes="Updated based on CAD review"
        )
        rev2 = PartRevision(
            part_id=part_id,
            field_name="projected_area_cm2",
            old_value="200.0",
            new_value="250.0",
            changed_by="test_user",
            change_type="value",
            notes="Recalculated from new dimensions"
        )
        rev3 = PartRevision(
            part_id=part_id,
            field_name="image_filename",
            old_value="housing_old.png",
            new_value="housing_v1.png",
            changed_by="test_user",
            change_type="image",
            notes="Updated to v1 image"
        )

        session.add_all([rev1, rev2, rev3])
        session.commit()

        print(f"✓ Created 3 revision records")

        # Retrieve revisions
        revisions = session.query(PartRevision).filter(PartRevision.part_id == part_id).order_by(PartRevision.changed_at.desc()).all()
        assert len(revisions) >= 3, f"Expected 3+ revisions, got {len(revisions)}"

        print(f"✓ Retrieved {len(revisions)} revisions:")
        for rev in revisions[:3]:
            print(f"  - {rev.field_name}: {rev.old_value} → {rev.new_value} ({rev.changed_by})")

        session.close()
        return True
    except Exception as e:
        print(f"✗ Revision tracking failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_part_update(part_id: int):
    """Test part update and change tracking."""
    print("\n=== Testing Part Update ===")
    try:
        session = get_session()

        # Retrieve part
        part = session.query(Part).filter(Part.id == part_id).first()
        assert part is not None, "Part not found for update"

        old_weight = part.weight_g

        # Update part
        part.weight_g = 200.0
        part.volume_cm3 = 220.0
        part.remarks = "Updated remarks after review"
        session.commit()

        print(f"✓ Updated Part {part_id}:")
        print(f"  - Weight: {old_weight}g → {part.weight_g}g")
        print(f"  - Remarks updated")

        # Create revision
        rev = PartRevision(
            part_id=part.id,
            field_name="weight_g",
            old_value=str(old_weight),
            new_value=str(part.weight_g),
            changed_by="test_user",
            change_type="value"
        )
        session.add(rev)
        session.commit()

        print(f"✓ Revision logged")

        session.close()
        return True
    except Exception as e:
        print(f"✗ Part update failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_part_deletion(rfq_id: int):
    """Test part deletion."""
    print("\n=== Testing Part Deletion ===")
    try:
        session = get_session()

        # Create a part to delete
        material = session.query(Material).filter(Material.short_name == "ABS").first()
        part = Part(
            rfq_id=rfq_id,
            name="Temp Part to Delete",
            material_id=material.id,
            weight_g=50.0,
            assembly=False,
            degate="no",
            eoat_type="standard"
        )
        session.add(part)
        session.commit()
        part_id = part.id

        print(f"✓ Created temporary part (ID: {part_id})")

        # Delete it
        session.delete(part)
        session.commit()

        print(f"✓ Deleted part {part_id}")

        # Verify deletion
        deleted = session.query(Part).filter(Part.id == part_id).first()
        assert deleted is None, "Part still exists after deletion"

        print(f"✓ Verified deletion")

        session.close()
        return True
    except Exception as e:
        print(f"✗ Part deletion failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rfq_retrieval():
    """Test RFQ with parts retrieval."""
    print("\n=== Testing RFQ with Parts Retrieval ===")
    try:
        session = get_session()

        # Get first RFQ with parts
        rfq = session.query(RFQ).first()
        assert rfq is not None, "No RFQs found"

        print(f"✓ Retrieved RFQ: {rfq.name}")
        print(f"  - Customer: {rfq.customer}")
        print(f"  - Status: {rfq.status}")
        print(f"  - Parts: {len(rfq.parts)}")

        for i, part in enumerate(rfq.parts):
            print(f"    Part {i+1}: {part.name} ({part.part_number})")
            print(f"      - Material: {part.material.short_name if part.material else 'None'}")
            print(f"      - Weight: {part.weight_g}g")
            print(f"      - Assembly: {part.assembly}, EOAT: {part.eoat_type}")

        session.close()
        return True
    except Exception as e:
        print(f"✗ RFQ retrieval failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("COMPREHENSIVE TEST SUITE")
    print("="*60)

    results = []

    # Test 1: Database
    results.append(("Database Init", test_database_init()))

    # Test 2: Geometry
    results.append(("Geometry Calculator", test_geometry_calculator()))

    # Test 3: Weight/Volume
    results.append(("Weight↔Volume", test_weight_volume_calculation()))

    # Test 4: RFQ Creation
    rfq_id = test_rfq_creation()
    results.append(("RFQ Creation", rfq_id is not None))

    if rfq_id:
        # Test 5: Part Creation
        part_id = test_part_creation(rfq_id)
        results.append(("Part Creation", part_id is not None))

        if part_id:
            # Test 6: Revision Tracking
            results.append(("Revision Tracking", test_revision_tracking(part_id)))

            # Test 7: Part Update
            results.append(("Part Update", test_part_update(part_id)))

        # Test 8: Part Deletion
        results.append(("Part Deletion", test_part_deletion(rfq_id)))

        # Test 9: RFQ Retrieval
        results.append(("RFQ Retrieval", test_rfq_retrieval()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All tests passed! Application is ready.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. See details above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
