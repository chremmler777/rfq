"""Cycle time estimation helpers."""

from typing import Optional


def estimate_cycle_time(
    wall_thickness_mm: float,
    material_family: str = 'PP',
    part_volume_cm3: Optional[float] = None,
    has_hot_runner: bool = False
) -> float:
    """Estimate cycle time based on part characteristics.

    This provides a rough estimate. Actual cycle times depend on many factors
    including cooling channel design, mold temperature, part geometry, etc.

    Args:
        wall_thickness_mm: Nominal wall thickness
        material_family: Material family (PP, ABS, PA, PC, POM, etc.)
        part_volume_cm3: Part volume (optional, for adjustment)
        has_hot_runner: True if using hot runner (faster cycles)

    Returns:
        Estimated cycle time in seconds
    """
    # Base cooling time depends heavily on wall thickness
    # Cooling time ≈ thickness² × material factor
    # Rule of thumb: 1mm wall ≈ 1-2 sec cooling

    # Material-specific factors (higher = longer cooling)
    material_factors = {
        'PP': 1.2,   # Crystalline, moderate cooling
        'PE': 1.3,   # Crystalline, needs good cooling
        'PA': 1.4,   # Crystalline, longer cooling
        'POM': 1.3,  # Crystalline
        'ABS': 1.0,  # Amorphous, base reference
        'PS': 0.9,   # Amorphous, fast cooling
        'PC': 1.1,   # Amorphous but high temp
        'PMMA': 1.0, # Amorphous
        'PBT': 1.2,  # Crystalline
        'TPU': 1.3,  # Slower demold
    }

    # Get material factor (default to ABS-like)
    mat_factor = material_factors.get(material_family.upper().split('-')[0], 1.0)

    # Cooling time estimation (seconds)
    cooling_time = (wall_thickness_mm ** 1.8) * mat_factor * 2

    # Injection time (rough estimate based on volume)
    if part_volume_cm3:
        injection_time = max(0.5, part_volume_cm3 / 20)  # ~20 cm³/s injection rate
    else:
        injection_time = 1.5  # Default

    # Fixed times
    mold_open_close = 2.0  # seconds
    ejection = 0.5  # seconds
    packing_time = cooling_time * 0.3  # Packing is part of cooling

    # Hot runner saves sprue removal time
    runner_time = 0 if has_hot_runner else 0.5

    total = injection_time + packing_time + cooling_time + mold_open_close + ejection + runner_time

    return round(total, 1)


def calculate_shots_per_hour(cycle_time_s: float) -> float:
    """Calculate number of shots per hour.

    Args:
        cycle_time_s: Cycle time in seconds

    Returns:
        Shots per hour
    """
    if cycle_time_s <= 0:
        return 0
    return 3600 / cycle_time_s


def calculate_parts_per_hour(cycle_time_s: float, cavities: int = 1) -> float:
    """Calculate number of parts per hour.

    Args:
        cycle_time_s: Cycle time in seconds
        cavities: Number of cavities

    Returns:
        Parts per hour
    """
    shots = calculate_shots_per_hour(cycle_time_s)
    return shots * cavities


def estimate_annual_machine_hours(
    annual_demand: int,
    cycle_time_s: float,
    cavities: int = 1,
    efficiency: float = 0.85
) -> float:
    """Estimate required machine hours per year.

    Args:
        annual_demand: Annual part demand
        cycle_time_s: Cycle time in seconds
        cavities: Number of cavities
        efficiency: Machine efficiency (default 85%)

    Returns:
        Required machine hours per year
    """
    if cycle_time_s <= 0 or cavities <= 0:
        return 0

    parts_per_hour = calculate_parts_per_hour(cycle_time_s, cavities)
    if parts_per_hour <= 0:
        return 0

    # Adjust for efficiency (scrap, downtime, changeovers)
    effective_parts_per_hour = parts_per_hour * efficiency

    hours_needed = annual_demand / effective_parts_per_hour
    return round(hours_needed, 1)
