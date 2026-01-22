"""Clamping force and injection pressure calculations."""

from typing import Optional
from config import DEFAULT_SAFETY_FACTOR


def calculate_clamping_force(
    projected_area_cm2: float,
    specific_pressure_bar: float,
    cavities: int = 1,
    safety_factor: float = DEFAULT_SAFETY_FACTOR
) -> float:
    """Calculate required clamping force.

    Formula: F = A × p × n × safety
    Where:
        F = Clamping force (kN)
        A = Projected area per cavity (cm²)
        p = Specific injection pressure (bar)
        n = Number of cavities
        safety = Safety factor (typically 1.1-1.3)

    Args:
        projected_area_cm2: Projected area of single part in cm²
        specific_pressure_bar: Material-specific pressure in bar
        cavities: Number of cavities
        safety_factor: Safety factor (default 1.2)

    Returns:
        Required clamping force in kN
    """
    # Convert: 1 bar × 1 cm² = 0.01 kN
    # So: F(kN) = A(cm²) × p(bar) × 0.01
    force_kn = projected_area_cm2 * specific_pressure_bar * cavities * 0.01 * safety_factor
    return round(force_kn, 1)


def calculate_clamping_force_from_material(
    projected_area_cm2: float,
    material,  # Material model instance
    cavities: int = 1,
    safety_factor: float = DEFAULT_SAFETY_FACTOR,
    use_max_pressure: bool = False
) -> Optional[float]:
    """Calculate clamping force using material data.

    Args:
        projected_area_cm2: Projected area of single part in cm²
        material: Material model instance with specific_pressure fields
        cavities: Number of cavities
        safety_factor: Safety factor
        use_max_pressure: If True, use max pressure; else use average

    Returns:
        Required clamping force in kN, or None if material has no pressure data
    """
    if use_max_pressure:
        pressure = material.specific_pressure_max_bar
    else:
        pressure = material.specific_pressure_avg_bar

    if pressure is None:
        return None

    return calculate_clamping_force(
        projected_area_cm2, pressure, cavities, safety_factor
    )


def calculate_injection_pressure(
    wall_thickness_mm: float,
    flow_length_mm: float,
    base_pressure_bar: float = 500
) -> float:
    """Estimate required injection pressure based on flow path.

    This is a simplified estimation. Real values depend on many factors.

    Args:
        wall_thickness_mm: Nominal wall thickness
        flow_length_mm: Maximum flow length from gate
        base_pressure_bar: Base pressure for the material

    Returns:
        Estimated injection pressure in bar
    """
    # Flow length ratio affects pressure significantly
    if wall_thickness_mm > 0:
        flow_ratio = flow_length_mm / wall_thickness_mm
        # Rough estimation: pressure increases with flow ratio
        # Thin walls need more pressure
        thickness_factor = 2.0 / wall_thickness_mm if wall_thickness_mm < 2.0 else 1.0
        pressure = base_pressure_bar * (1 + flow_ratio / 100) * thickness_factor
        return round(min(pressure, 2500), 0)  # Cap at typical machine max
    return base_pressure_bar


def recommend_machine_size(clamping_force_kn: float) -> str:
    """Recommend machine size based on clamping force.

    Args:
        clamping_force_kn: Required clamping force

    Returns:
        Machine size recommendation string
    """
    # Standard machine sizes (in tonnes, which ≈ 10 kN)
    sizes = [50, 80, 100, 130, 160, 200, 250, 320, 400, 500, 650, 800, 1000, 1300, 1600, 2000]

    force_tonnes = clamping_force_kn / 10

    for size in sizes:
        if force_tonnes <= size * 0.8:  # 80% utilization is ideal
            return f"{size}t"

    return f">{sizes[-1]}t (special machine required)"
