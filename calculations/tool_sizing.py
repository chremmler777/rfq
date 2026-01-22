"""Tool sizing and machine fit checks."""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class MachineCheckResult:
    """Result of machine fit check."""
    fits: bool
    issues: List[str]
    warnings: List[str]

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def __str__(self) -> str:
        if self.fits and not self.has_warnings:
            return "Tool fits machine"
        elif self.fits:
            return f"Tool fits with warnings: {'; '.join(self.warnings)}"
        else:
            return f"Tool does NOT fit: {'; '.join(self.issues)}"


def check_machine_fit(
    tool_width_mm: Optional[float],
    tool_height_mm: Optional[float],
    tool_length_mm: Optional[float],  # Mold height / stack height
    required_clamping_kn: Optional[float],
    machine,  # Machine model instance
    required_shot_weight_g: Optional[float] = None
) -> MachineCheckResult:
    """Check if a tool fits on a given machine.

    Checks:
    - Tool dimensions vs platen size
    - Tool dimensions vs tie-bar spacing
    - Mold height vs machine mold height range
    - Clamping force requirement
    - Shot weight requirement

    Args:
        tool_width_mm: Tool width (across platen)
        tool_height_mm: Tool height (across platen)
        tool_length_mm: Tool length / stack height (between platens)
        required_clamping_kn: Required clamping force
        machine: Machine model instance
        required_shot_weight_g: Required shot weight (optional)

    Returns:
        MachineCheckResult with fit status and any issues/warnings
    """
    issues = []
    warnings = []

    # Check platen size (tool must fit on platen)
    if tool_width_mm and machine.platen_width_mm:
        if tool_width_mm > machine.platen_width_mm:
            issues.append(
                f"Tool width ({tool_width_mm}mm) exceeds platen width ({machine.platen_width_mm}mm)"
            )
        elif tool_width_mm > machine.platen_width_mm * 0.95:
            warnings.append(
                f"Tool width ({tool_width_mm}mm) very close to platen width ({machine.platen_width_mm}mm)"
            )

    if tool_height_mm and machine.platen_height_mm:
        if tool_height_mm > machine.platen_height_mm:
            issues.append(
                f"Tool height ({tool_height_mm}mm) exceeds platen height ({machine.platen_height_mm}mm)"
            )
        elif tool_height_mm > machine.platen_height_mm * 0.95:
            warnings.append(
                f"Tool height ({tool_height_mm}mm) very close to platen height ({machine.platen_height_mm}mm)"
            )

    # Check tie-bar spacing (tool must pass through tie-bars)
    if tool_width_mm and machine.tie_bar_spacing_h_mm:
        if tool_width_mm > machine.tie_bar_spacing_h_mm:
            issues.append(
                f"Tool width ({tool_width_mm}mm) exceeds tie-bar spacing ({machine.tie_bar_spacing_h_mm}mm)"
            )

    if tool_height_mm and machine.tie_bar_spacing_v_mm:
        if tool_height_mm > machine.tie_bar_spacing_v_mm:
            issues.append(
                f"Tool height ({tool_height_mm}mm) exceeds vertical tie-bar spacing ({machine.tie_bar_spacing_v_mm}mm)"
            )

    # Check mold height (stack height)
    if tool_length_mm:
        if machine.max_mold_height_mm and tool_length_mm > machine.max_mold_height_mm:
            issues.append(
                f"Mold height ({tool_length_mm}mm) exceeds machine max ({machine.max_mold_height_mm}mm)"
            )
        if machine.min_mold_height_mm and tool_length_mm < machine.min_mold_height_mm:
            issues.append(
                f"Mold height ({tool_length_mm}mm) below machine min ({machine.min_mold_height_mm}mm)"
            )

    # Check clamping force
    if required_clamping_kn and machine.clamping_force_kn:
        utilization = required_clamping_kn / machine.clamping_force_kn
        if utilization > 1.0:
            issues.append(
                f"Required clamping ({required_clamping_kn}kN) exceeds machine capacity ({machine.clamping_force_kn}kN)"
            )
        elif utilization > 0.9:
            warnings.append(
                f"High clamping utilization ({utilization*100:.0f}%) - consider larger machine"
            )
        elif utilization < 0.3:
            warnings.append(
                f"Low clamping utilization ({utilization*100:.0f}%) - machine may be oversized"
            )

    # Check shot weight
    if required_shot_weight_g and machine.shot_weight_g:
        shot_utilization = required_shot_weight_g / machine.shot_weight_g
        if shot_utilization > 0.8:
            issues.append(
                f"Required shot ({required_shot_weight_g}g) exceeds 80% of machine capacity ({machine.shot_weight_g}g)"
            )
        elif shot_utilization > 0.7:
            warnings.append(
                f"High shot weight utilization ({shot_utilization*100:.0f}%)"
            )

    fits = len(issues) == 0
    return MachineCheckResult(fits=fits, issues=issues, warnings=warnings)


def estimate_tool_dimensions(
    part_length_mm: float,
    part_width_mm: float,
    part_height_mm: float,
    cavities: int = 1,
    cavity_layout: str = 'linear'  # 'linear', 'square', '2x2', etc.
) -> tuple[float, float, float]:
    """Estimate tool dimensions based on part size.

    This is a rough estimation. Actual tool size depends on:
    - Runner system
    - Cooling channels
    - Ejection system
    - Sliders/lifters

    Args:
        part_length_mm: Part length
        part_width_mm: Part width
        part_height_mm: Part height (depth)
        cavities: Number of cavities
        cavity_layout: How cavities are arranged

    Returns:
        Tuple of (tool_width, tool_height, tool_length) in mm
    """
    # Add margins for mold structure
    # Rule of thumb: ~100mm on each side for small tools, more for larger
    margin = max(80, min(part_length_mm, part_width_mm) * 0.3)

    if cavities == 1:
        tool_width = part_width_mm + margin * 2
        tool_height = part_length_mm + margin * 2
    elif cavity_layout == 'linear' or cavities == 2:
        tool_width = part_width_mm * cavities + margin * (cavities + 1)
        tool_height = part_length_mm + margin * 2
    elif cavity_layout == 'square' or cavities == 4:
        cols = 2
        rows = (cavities + 1) // 2
        tool_width = part_width_mm * cols + margin * (cols + 1)
        tool_height = part_length_mm * rows + margin * (rows + 1)
    else:
        # Generic multi-cavity estimate
        cols = int(cavities ** 0.5) + 1
        rows = (cavities + cols - 1) // cols
        tool_width = part_width_mm * cols + margin * (cols + 1)
        tool_height = part_length_mm * rows + margin * (rows + 1)

    # Tool length (stack height) = part depth + clamping plates + ejection
    # Rule of thumb: 2.5-3x part depth for simple parts
    tool_length = part_height_mm * 3 + 200  # 200mm for plates

    return (round(tool_width, 0), round(tool_height, 0), round(tool_length, 0))
