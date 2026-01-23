"""Shot volume calculation and barrel usage tracking."""

from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class ShotVolumeResult:
    """Result of shot volume calculation."""
    total_cm3: float
    parts_breakdown: Dict[str, float]  # {part_name: volume_cm3}
    runner_cm3: float
    runner_percent: float


@dataclass
class BarrelUsageResult:
    """Result of barrel usage percentage calculation."""
    percent: float
    is_warning: bool  # True if >= 70%
    is_critical: bool  # True if >= 85%
    message: str


def calculate_shot_volume(
    part_configurations: List,  # List of ToolPartConfiguration objects
    runner_percent: float = 15.0
) -> ShotVolumeResult:
    """Calculate total shot volume from part configurations and runner.

    Formula:
        shot_volume = sum(part.volume_cm3 × cavities) + runner
        runner = shot_volume_without_runner × (runner_percent / 100)

    Args:
        part_configurations: List of ToolPartConfiguration objects with parts
        runner_percent: Runner as percentage of parts volume (default 15%)

    Returns:
        ShotVolumeResult with total volume, parts breakdown, and runner volume
    """
    parts_volume_cm3 = 0.0
    parts_breakdown = {}

    for pc in part_configurations:
        if pc.part and pc.part.volume_cm3:
            part_vol = pc.part.volume_cm3 * pc.cavities
            parts_volume_cm3 += part_vol
            parts_breakdown[pc.part.name] = part_vol

    # Calculate runner volume
    runner_cm3 = parts_volume_cm3 * (runner_percent / 100)
    total_cm3 = parts_volume_cm3 + runner_cm3

    return ShotVolumeResult(
        total_cm3=round(total_cm3, 2),
        parts_breakdown=parts_breakdown,
        runner_cm3=round(runner_cm3, 2),
        runner_percent=runner_percent
    )


def calculate_barrel_usage(
    shot_volume_cm3: float,
    barrel_volume_cm3: Optional[float],
    warn_percent: float = 70.0,
    critical_percent: float = 85.0
) -> BarrelUsageResult:
    """Calculate barrel usage percentage with warnings.

    Args:
        shot_volume_cm3: Total shot volume in cm³
        barrel_volume_cm3: Machine barrel volume in cm³
        warn_percent: Warning threshold percentage (default 70%)
        critical_percent: Critical threshold percentage (default 85%)

    Returns:
        BarrelUsageResult with usage percent and status flags
    """
    if barrel_volume_cm3 is None or barrel_volume_cm3 <= 0:
        return BarrelUsageResult(
            percent=0.0,
            is_warning=False,
            is_critical=False,
            message="No barrel volume data available"
        )

    usage_percent = (shot_volume_cm3 / barrel_volume_cm3) * 100

    if usage_percent >= critical_percent:
        status = "CRITICAL"
        is_warning = True
        is_critical = True
    elif usage_percent >= warn_percent:
        status = "WARNING"
        is_warning = True
        is_critical = False
    else:
        status = "OK"
        is_warning = False
        is_critical = False

    message = f"{status}: {usage_percent:.1f}% barrel usage ({shot_volume_cm3:.1f}cm³ of {barrel_volume_cm3:.1f}cm³)"

    return BarrelUsageResult(
        percent=round(usage_percent, 1),
        is_warning=is_warning,
        is_critical=is_critical,
        message=message
    )
