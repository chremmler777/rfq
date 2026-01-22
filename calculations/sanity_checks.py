"""Sanity checks for demand feasibility and other validations."""

from dataclasses import dataclass
from typing import Optional, List
from config import DEFAULT_AVAILABLE_HOURS_PER_WEEK


@dataclass
class DemandCheckResult:
    """Result of demand feasibility check."""
    feasible: bool
    machine_hours_per_year: float
    machine_hours_per_week: float
    utilization_percent: float
    issues: List[str]
    warnings: List[str]

    def __str__(self) -> str:
        if self.feasible and not self.warnings:
            return f"Demand feasible: {self.machine_hours_per_week:.1f} hrs/week ({self.utilization_percent:.0f}% utilization)"
        elif self.feasible:
            return f"Demand feasible with warnings: {'; '.join(self.warnings)}"
        else:
            return f"Demand NOT feasible: {'; '.join(self.issues)}"


def check_demand_feasibility(
    annual_demand: int,
    cycle_time_s: float,
    cavities: int = 1,
    available_hours_per_week: float = DEFAULT_AVAILABLE_HOURS_PER_WEEK,
    weeks_per_year: int = 50,  # Allow 2 weeks for maintenance/holidays
    efficiency: float = 0.85
) -> DemandCheckResult:
    """Check if annual demand is feasible on one machine.

    Args:
        annual_demand: Total parts needed per year
        cycle_time_s: Cycle time in seconds
        cavities: Number of cavities
        available_hours_per_week: Machine availability per week
        weeks_per_year: Operating weeks per year
        efficiency: Overall equipment effectiveness (OEE)

    Returns:
        DemandCheckResult with feasibility status
    """
    issues = []
    warnings = []

    if cycle_time_s <= 0:
        return DemandCheckResult(
            feasible=False,
            machine_hours_per_year=0,
            machine_hours_per_week=0,
            utilization_percent=0,
            issues=["Cycle time must be greater than 0"],
            warnings=[]
        )

    if cavities <= 0:
        return DemandCheckResult(
            feasible=False,
            machine_hours_per_year=0,
            machine_hours_per_week=0,
            utilization_percent=0,
            issues=["Cavity count must be greater than 0"],
            warnings=[]
        )

    # Calculate production capacity
    parts_per_hour = (3600 / cycle_time_s) * cavities * efficiency
    hours_per_year_available = available_hours_per_week * weeks_per_year
    max_annual_capacity = parts_per_hour * hours_per_year_available

    # Calculate required hours
    hours_needed_per_year = annual_demand / parts_per_hour
    hours_needed_per_week = hours_needed_per_year / weeks_per_year

    utilization = (hours_needed_per_year / hours_per_year_available) * 100

    # Check feasibility
    if hours_needed_per_week > available_hours_per_week:
        issues.append(
            f"Need {hours_needed_per_week:.1f} hrs/week but only {available_hours_per_week:.0f} hrs available"
        )
    elif utilization > 95:
        issues.append(
            f"Utilization too high ({utilization:.0f}%) - no buffer for issues"
        )
    elif utilization > 85:
        warnings.append(
            f"High utilization ({utilization:.0f}%) - limited buffer"
        )
    elif utilization < 30:
        warnings.append(
            f"Low utilization ({utilization:.0f}%) - consider combining with other parts"
        )

    # Check for unrealistic values
    if cycle_time_s < 3:
        warnings.append(f"Very short cycle time ({cycle_time_s}s) - verify this is realistic")
    if cycle_time_s > 120:
        warnings.append(f"Long cycle time ({cycle_time_s}s) - consider process optimization")

    feasible = len(issues) == 0

    return DemandCheckResult(
        feasible=feasible,
        machine_hours_per_year=round(hours_needed_per_year, 1),
        machine_hours_per_week=round(hours_needed_per_week, 1),
        utilization_percent=round(utilization, 1),
        issues=issues,
        warnings=warnings
    )


def check_cavity_recommendation(
    annual_demand: int,
    cycle_time_s: float,
    target_utilization: float = 0.7,
    available_hours_per_week: float = DEFAULT_AVAILABLE_HOURS_PER_WEEK,
    weeks_per_year: int = 50,
    efficiency: float = 0.85,
    max_cavities: int = 16
) -> int:
    """Recommend number of cavities based on demand.

    Args:
        annual_demand: Total parts needed per year
        cycle_time_s: Cycle time in seconds
        target_utilization: Target machine utilization (0.0-1.0)
        available_hours_per_week: Machine availability per week
        weeks_per_year: Operating weeks per year
        efficiency: Overall equipment effectiveness
        max_cavities: Maximum cavities to consider

    Returns:
        Recommended number of cavities
    """
    if cycle_time_s <= 0:
        return 1

    hours_available_per_year = available_hours_per_week * weeks_per_year
    target_hours = hours_available_per_year * target_utilization

    # parts_needed = annual_demand
    # parts_per_hour = (3600 / cycle_time) * cavities * efficiency
    # hours_needed = parts_needed / parts_per_hour
    # We want: hours_needed ≈ target_hours
    # So: cavities ≈ annual_demand / (target_hours * (3600/cycle_time) * efficiency)

    shots_per_hour = 3600 / cycle_time_s
    parts_per_cavity_per_year = shots_per_hour * target_hours * efficiency

    if parts_per_cavity_per_year <= 0:
        return 1

    recommended = annual_demand / parts_per_cavity_per_year

    # Round up and constrain
    recommended = max(1, min(int(recommended + 0.5), max_cavities))

    return recommended


def validate_part_data(
    weight_g: Optional[float] = None,
    volume_cm3: Optional[float] = None,
    projected_area_cm2: Optional[float] = None,
    wall_thickness_mm: Optional[float] = None,
    density_g_cm3: Optional[float] = None
) -> List[str]:
    """Validate part data for consistency.

    Args:
        weight_g: Part weight in grams
        volume_cm3: Part volume in cm³
        projected_area_cm2: Projected area in cm²
        wall_thickness_mm: Wall thickness in mm
        density_g_cm3: Material density in g/cm³

    Returns:
        List of warning messages for inconsistent data
    """
    warnings = []

    # Check weight vs volume consistency
    if weight_g and volume_cm3 and density_g_cm3:
        calculated_weight = volume_cm3 * density_g_cm3
        deviation = abs(weight_g - calculated_weight) / calculated_weight
        if deviation > 0.2:  # >20% deviation
            warnings.append(
                f"Weight ({weight_g}g) doesn't match volume × density ({calculated_weight:.1f}g) - check values"
            )

    # Check reasonable ranges
    if wall_thickness_mm:
        if wall_thickness_mm < 0.5:
            warnings.append(f"Wall thickness ({wall_thickness_mm}mm) very thin - verify this is correct")
        elif wall_thickness_mm > 10:
            warnings.append(f"Wall thickness ({wall_thickness_mm}mm) unusually thick - consider sink marks")

    if projected_area_cm2 and volume_cm3:
        # Very rough check: projected area should be reasonable vs volume
        # For a cube: area ≈ volume^(2/3)
        expected_area = volume_cm3 ** 0.67 * 2  # Factor of 2 for flat parts
        if projected_area_cm2 > expected_area * 10:
            warnings.append(
                f"Projected area ({projected_area_cm2}cm²) seems large for volume ({volume_cm3}cm³)"
            )

    return warnings
