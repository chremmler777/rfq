"""Injection system validation checks."""

from typing import Optional
from dataclasses import dataclass


@dataclass
class ScrewDiameterCheckResult:
    """Result of screw diameter ratio check."""
    ratio: float
    is_optimal: bool  # True if 1.0 <= ratio <= 2.8
    is_acceptable: bool  # True if 0.5 <= ratio <= 3.5
    message: str


def check_screw_diameter_ratio(
    stroke_mm: float,
    diameter_mm: float,
    optimal_min: float = 1.0,
    optimal_max: float = 2.8,
    acceptable_min: float = 0.5,
    acceptable_max: float = 3.5
) -> ScrewDiameterCheckResult:
    """Check injection screw stroke/diameter ratio.

    The ratio affects material plastication and quality:
    - Optimal range: 1.0-2.8 (best mix of output and quality)
    - Acceptable range: 0.5-3.5 (usable but suboptimal)
    - Below 0.5: Poor material plastication
    - Above 3.5: Long residence time, material degradation risk

    Args:
        stroke_mm: Maximum injection stroke in mm
        diameter_mm: Screw diameter in mm
        optimal_min: Optimal ratio minimum (default 1.0)
        optimal_max: Optimal ratio maximum (default 2.8)
        acceptable_min: Acceptable ratio minimum (default 0.5)
        acceptable_max: Acceptable ratio maximum (default 3.5)

    Returns:
        ScrewDiameterCheckResult with ratio and status
    """
    if diameter_mm <= 0:
        return ScrewDiameterCheckResult(
            ratio=0.0,
            is_optimal=False,
            is_acceptable=False,
            message="Invalid screw diameter"
        )

    ratio = stroke_mm / diameter_mm

    if optimal_min <= ratio <= optimal_max:
        status = "OPTIMAL"
        is_optimal = True
        is_acceptable = True
    elif acceptable_min <= ratio <= acceptable_max:
        status = "ACCEPTABLE"
        is_optimal = False
        is_acceptable = True
    else:
        status = "OUT OF RANGE"
        is_optimal = False
        is_acceptable = False

    message = f"{status}: Screw ratio {ratio:.2f} (stroke {stroke_mm}mm / diameter {diameter_mm}mm)"

    return ScrewDiameterCheckResult(
        ratio=round(ratio, 2),
        is_optimal=is_optimal,
        is_acceptable=is_acceptable,
        message=message
    )
