"""Seed database with pre-populated materials and machines."""

import json
from pathlib import Path

from .models import Material, Machine
from .connection import session_scope


SEED_DATA_PATH = Path(__file__).parent.parent / 'data' / 'seed'


def load_materials():
    """Load materials from JSON seed file."""
    materials_file = SEED_DATA_PATH / 'materials.json'
    if materials_file.exists():
        with open(materials_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def load_machines():
    """Load machines from JSON seed file."""
    machines_file = SEED_DATA_PATH / 'machines.json'
    if machines_file.exists():
        with open(machines_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def seed_materials(session):
    """Seed materials table if empty."""
    existing_count = session.query(Material).filter(Material.is_preset == True).count()
    if existing_count > 0:
        return 0  # Already seeded

    materials_data = load_materials()
    count = 0
    for mat_data in materials_data:
        material = Material(
            name=mat_data['name'],
            short_name=mat_data['short_name'],
            family=mat_data['family'],
            density_g_cm3=mat_data.get('density_g_cm3'),
            shrinkage_min_percent=mat_data.get('shrinkage_min_percent'),
            shrinkage_max_percent=mat_data.get('shrinkage_max_percent'),
            melt_temp_min_c=mat_data.get('melt_temp_min_c'),
            melt_temp_max_c=mat_data.get('melt_temp_max_c'),
            mold_temp_min_c=mat_data.get('mold_temp_min_c'),
            mold_temp_max_c=mat_data.get('mold_temp_max_c'),
            specific_pressure_min_bar=mat_data.get('specific_pressure_min_bar'),
            specific_pressure_max_bar=mat_data.get('specific_pressure_max_bar'),
            flow_length_ratio=mat_data.get('flow_length_ratio'),
            notes=mat_data.get('notes'),
            is_preset=True
        )
        session.add(material)
        count += 1

    return count


def seed_machines(session):
    """Seed machines table if empty."""
    existing_count = session.query(Machine).filter(Machine.is_preset == True).count()
    if existing_count > 0:
        return 0  # Already seeded

    machines_data = load_machines()
    count = 0
    for mach_data in machines_data:
        machine = Machine(
            name=mach_data['name'],
            manufacturer=mach_data.get('manufacturer'),
            clamping_force_kn=mach_data.get('clamping_force_kn'),
            shot_weight_g=mach_data.get('shot_weight_g'),
            injection_pressure_bar=mach_data.get('injection_pressure_bar'),
            platen_width_mm=mach_data.get('platen_width_mm'),
            platen_height_mm=mach_data.get('platen_height_mm'),
            tie_bar_spacing_h_mm=mach_data.get('tie_bar_spacing_h_mm'),
            tie_bar_spacing_v_mm=mach_data.get('tie_bar_spacing_v_mm'),
            max_mold_height_mm=mach_data.get('max_mold_height_mm'),
            min_mold_height_mm=mach_data.get('min_mold_height_mm'),
            max_opening_stroke_mm=mach_data.get('max_opening_stroke_mm'),
            notes=mach_data.get('notes'),
            is_preset=True
        )
        session.add(machine)
        count += 1

    return count


def seed_database():
    """Seed all preset data into the database.

    Returns:
        Tuple of (materials_added, machines_added)
    """
    with session_scope() as session:
        materials_added = seed_materials(session)
        machines_added = seed_machines(session)
        return materials_added, machines_added


if __name__ == '__main__':
    # Can be run directly to seed the database
    from .connection import init_db
    init_db()
    materials, machines = seed_database()
    print(f"Seeded {materials} materials and {machines} machines")
