"""Tool totals aggregation helpers."""

from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class ToolTotalsResult:
    """Aggregated totals for a tool."""
    total_cavities: int
    total_lifters: int
    total_sliders: int
    parts_breakdown: Dict[str, dict]  # {part_name: {cavities, lifters, sliders}}


def calculate_tool_totals(tool) -> ToolTotalsResult:
    """Calculate aggregated totals for a tool from part configurations.

    Sums cavities, lifters, and sliders across all parts in the tool.

    Args:
        tool: Tool model instance with part_configurations

    Returns:
        ToolTotalsResult with aggregated totals and per-part breakdown
    """
    total_cavities = 0
    total_lifters = 0
    total_sliders = 0
    parts_breakdown = {}

    if tool.part_configurations:
        for pc in tool.part_configurations:
            total_cavities += pc.cavities
            total_lifters += pc.lifters_count
            total_sliders += pc.sliders_count

            if pc.part:
                parts_breakdown[pc.part.name] = {
                    'cavities': pc.cavities,
                    'lifters': pc.lifters_count,
                    'sliders': pc.sliders_count
                }
    else:
        # Fallback to tool-level values for legacy tools
        total_cavities = tool.cavities
        total_lifters = tool.lifters_count
        total_sliders = tool.sliders_count

    return ToolTotalsResult(
        total_cavities=total_cavities,
        total_lifters=total_lifters,
        total_sliders=total_sliders,
        parts_breakdown=parts_breakdown
    )
