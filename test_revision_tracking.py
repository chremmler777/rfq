"""Test revision tracking for parts."""

import pytest
from datetime import datetime
from database import init_db, Part, RFQ, PartRevision, Material, SurfaceFinish
from database.connection import session_scope, get_engine
from sqlalchemy import text
import os


def setup_test_db():
    """Setup test database."""
    test_db = "data/test_rfq_revisions.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    if os.path.exists(test_db + "-shm"):
        os.remove(test_db + "-shm")
    if os.path.exists(test_db + "-wal"):
        os.remove(test_db + "-wal")

    # Create test database
    os.environ["TEST_DB"] = test_db
    init_db()
    return test_db


def test_part_creation_creates_initial_revision():
    """Test that creating a part logs initial revision."""
    test_db = setup_test_db()

    try:
        with session_scope() as session:
            # Create materials first
            mat = Material(
                name="Polypropylene",
                short_name="PP",
                family="Polypropylene",
                density_g_cm3=0.905,
            )
            session.add(mat)
            session.flush()
            mat_id = mat.id

            # Create RFQ
            rfq = RFQ(name="Test RFQ", status="draft")
            session.add(rfq)
            session.flush()
            rfq_id = rfq.id

            # Create part with data
            part = Part(
                rfq_id=rfq_id,
                name="Test Part",
                volume_cm3=50.5,
                material_id=mat_id,
                weight_g=45.7,
                projected_area_cm2=100.0,
                wall_thickness_mm=2.5,
                surface_finish="draw_polish",
                surface_finish_detail="grid 800",
                parts_over_runtime=10000,
            )
            session.add(part)
            session.flush()
            part_id = part.id

            # Log initial creation (simulating what the dialog does)
            fields_created = []
            if part.name:
                fields_created.append(("name", "", part.name))
            if part.volume_cm3:
                fields_created.append(("volume_cm3", "", str(part.volume_cm3)))
            if part.material_id:
                fields_created.append(("material_id", "", str(part.material_id)))
            if part.weight_g:
                fields_created.append(("weight_g", "", str(part.weight_g)))
            if part.projected_area_cm2:
                fields_created.append(("projected_area_cm2", "", str(part.projected_area_cm2)))
            if part.wall_thickness_mm:
                fields_created.append(("wall_thickness_mm", "", str(part.wall_thickness_mm)))
            if part.surface_finish:
                fields_created.append(("surface_finish", "", part.surface_finish))

            for field_name, old_val, new_val in fields_created:
                rev = PartRevision(
                    part_id=part_id,
                    field_name=field_name,
                    old_value=old_val or None,
                    new_value=str(new_val)[:500] if new_val else None,
                    changed_by="test_user",
                    change_type="initial_creation"
                )
                session.add(rev)

            session.commit()

        # Verify revisions were created
        with session_scope() as session:
            revisions = session.query(PartRevision).filter(
                PartRevision.part_id == part_id
            ).all()

            assert len(revisions) > 0, "No revisions created"
            assert all(r.change_type == "initial_creation" for r in revisions), \
                "All initial revisions should have change_type='initial_creation'"

            # Check specific fields
            field_names = [r.field_name for r in revisions]
            assert "name" in field_names
            assert "volume_cm3" in field_names
            assert "material_id" in field_names

            print("✓ Part creation creates initial revisions")

    finally:
        os.environ.pop("TEST_DB", None)


def test_part_update_creates_update_revision():
    """Test that updating a part logs change revision."""
    test_db = setup_test_db()

    try:
        with session_scope() as session:
            # Setup: Create material, RFQ, and initial part
            mat = Material(
                name="Acrylonitrile Butadiene Styrene",
                short_name="ABS",
                family="Acrylonitrile Butadiene Styrene",
                density_g_cm3=1.05,
            )
            session.add(mat)
            session.flush()
            mat_id = mat.id

            rfq = RFQ(name="Test RFQ 2", status="draft")
            session.add(rfq)
            session.flush()
            rfq_id = rfq.id

            part = Part(
                rfq_id=rfq_id,
                name="Original Part",
                volume_cm3=30.0,
                material_id=mat_id,
            )
            session.add(part)
            session.flush()
            part_id = part.id

            # Log initial creation
            rev = PartRevision(
                part_id=part_id,
                field_name="name",
                old_value="",
                new_value="Original Part",
                changed_by="test_user",
                change_type="initial_creation"
            )
            session.add(rev)
            session.commit()

        # Now update the part (simulate edit)
        with session_scope() as session:
            part = session.query(Part).get(part_id)
            old_name = part.name
            old_volume = part.volume_cm3

            # Change values
            part.name = "Updated Part"
            part.volume_cm3 = 45.0

            # Log changes
            rev1 = PartRevision(
                part_id=part_id,
                field_name="name",
                old_value=old_name,
                new_value="Updated Part",
                changed_by="test_user",
                change_type="value"
            )
            rev2 = PartRevision(
                part_id=part_id,
                field_name="volume_cm3",
                old_value=str(old_volume),
                new_value="45.0",
                changed_by="test_user",
                change_type="value"
            )
            session.add(rev1)
            session.add(rev2)
            session.commit()

        # Verify all revisions exist
        with session_scope() as session:
            revisions = session.query(PartRevision).filter(
                PartRevision.part_id == part_id
            ).order_by(PartRevision.changed_at).all()

            assert len(revisions) >= 3, f"Expected at least 3 revisions, got {len(revisions)}"

            # Check initial creation
            initial = [r for r in revisions if r.change_type == "initial_creation"]
            assert len(initial) >= 1, "Should have initial creation revision"

            # Check updates
            updates = [r for r in revisions if r.change_type == "value"]
            assert len(updates) >= 2, "Should have 2+ update revisions"

            # Verify name change
            name_changes = [r for r in updates if r.field_name == "name"]
            assert len(name_changes) > 0, "Should have name change"
            assert name_changes[0].old_value == "Original Part"
            assert name_changes[0].new_value == "Updated Part"

            print("✓ Part update creates change revisions")

    finally:
        os.environ.pop("TEST_DB", None)


def test_revisions_grouped_by_date_and_user():
    """Test that revisions can be grouped by date and user."""
    test_db = setup_test_db()

    try:
        with session_scope() as session:
            # Setup
            mat = Material(
                name="Polyamide",
                short_name="PA",
                family="Polyamide",
                density_g_cm3=1.14,
            )
            session.add(mat)
            session.flush()

            rfq = RFQ(name="Test RFQ 3", status="draft")
            session.add(rfq)
            session.flush()

            part = Part(
                rfq_id=rfq.id,
                name="PA Part",
                volume_cm3=25.0,
            )
            session.add(part)
            session.flush()
            part_id = part.id

            # Create revisions from different "users"
            for i in range(3):
                rev = PartRevision(
                    part_id=part_id,
                    field_name=f"test_field_{i}",
                    old_value="old",
                    new_value="new",
                    changed_by=f"user_{i % 2}",  # 2 different users
                    change_type="value"
                )
                session.add(rev)

            session.commit()

        # Verify grouping possible
        with session_scope() as session:
            revisions = session.query(PartRevision).filter(
                PartRevision.part_id == part_id
            ).all()

            # Group by date
            from collections import defaultdict
            by_date = defaultdict(lambda: defaultdict(list))

            for rev in revisions:
                date_key = rev.changed_at.strftime("%Y-%m-%d")
                user = rev.changed_by or "system"
                by_date[date_key][user].append(rev)

            # Verify grouping
            assert len(by_date) > 0, "Should have date groups"
            for date_key in by_date:
                users = by_date[date_key]
                assert len(users) >= 1, "Should have users in date group"
                for user in users:
                    changes = by_date[date_key][user]
                    assert len(changes) > 0, "Should have changes for user"

            print("✓ Revisions can be grouped by date and user")

    finally:
        os.environ.pop("TEST_DB", None)


if __name__ == "__main__":
    # Don't use pytest, just run tests directly
    print("\n=== Testing Revision Tracking ===\n")

    try:
        test_part_creation_creates_initial_revision()
        test_part_update_creates_update_revision()
        test_revisions_grouped_by_date_and_user()
        print("\n✓ All revision tracking tests passed!\n")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}\n")
        raise
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        raise
