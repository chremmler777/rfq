"""Modular geometry calculator for flexible part dimension input."""

from typing import Optional, Tuple


class GeometryMode:
    """Base class for geometry input modes."""

    def calculate_projected_area(self) -> Optional[float]:
        """Calculate projected area in cm².

        Returns:
            Projected area or None if insufficient data
        """
        raise NotImplementedError

    def validate(self) -> Tuple[bool, str]:
        """Validate input data.

        Returns:
            Tuple of (is_valid, error_message)
        """
        raise NotImplementedError

    def to_dict(self) -> dict:
        """Serialize to dict for storage."""
        raise NotImplementedError


class DirectGeometryMode(GeometryMode):
    """Direct projected area input."""

    def __init__(self, projected_area_cm2: Optional[float] = None):
        """Initialize with direct area.

        Args:
            projected_area_cm2: Projected area in cm²
        """
        self.projected_area_cm2 = projected_area_cm2

    def calculate_projected_area(self) -> Optional[float]:
        """Return the directly entered area."""
        return self.projected_area_cm2

    def validate(self) -> Tuple[bool, str]:
        """Validate that area is positive."""
        if self.projected_area_cm2 is None:
            return False, "Projected area not entered"
        if self.projected_area_cm2 <= 0:
            return False, "Projected area must be positive"
        return True, ""

    def to_dict(self) -> dict:
        return {
            "mode": "direct",
            "projected_area_cm2": self.projected_area_cm2
        }

    def __repr__(self):
        return f"DirectMode(area={self.projected_area_cm2}cm²)"


class BoxEstimateMode(GeometryMode):
    """Box dimension estimation: length × width × effective %."""

    def __init__(
        self,
        length_mm: Optional[float] = None,
        width_mm: Optional[float] = None,
        effective_percent: float = 100.0
    ):
        """Initialize with box dimensions.

        Args:
            length_mm: Box length in mm (X dimension - plane surface)
            width_mm: Box width in mm (Y dimension - plane surface)
            effective_percent: Effective surface area % (0-100)
        """
        self.length_mm = length_mm
        self.width_mm = width_mm
        self.effective_percent = max(0, min(100, effective_percent))  # Clamp 0-100

    def calculate_projected_area(self) -> Optional[float]:
        """Calculate area from box dimensions.

        Formula: (length × width) × (effective% / 100) = area in mm²
        Then convert to cm²: area_cm² = area_mm² / 100
        """
        if self.length_mm is None or self.width_mm is None:
            return None

        area_mm2 = self.length_mm * self.width_mm
        effective_area_mm2 = area_mm2 * (self.effective_percent / 100.0)
        area_cm2 = effective_area_mm2 / 100.0  # Convert mm² to cm²

        return round(area_cm2, 2)

    def validate(self) -> Tuple[bool, str]:
        """Validate box dimensions."""
        if self.length_mm is None:
            return False, "Length not entered"
        if self.width_mm is None:
            return False, "Width not entered"
        if self.length_mm <= 0:
            return False, "Length must be positive"
        if self.width_mm <= 0:
            return False, "Width must be positive"
        if not (0 < self.effective_percent <= 100):
            return False, "Effective % must be 0-100"
        return True, ""

    def to_dict(self) -> dict:
        return {
            "mode": "box",
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "effective_percent": self.effective_percent
        }

    def __repr__(self):
        area = self.calculate_projected_area()
        return f"BoxMode({self.length_mm}×{self.width_mm}mm @ {self.effective_percent}% = {area}cm²)"


class GeometryFactory:
    """Factory to create geometry modes from data."""

    @staticmethod
    def from_dict(data: dict) -> Optional[GeometryMode]:
        """Create geometry mode from dict.

        Args:
            data: Dict with 'mode' key and mode-specific parameters

        Returns:
            GeometryMode instance or None if invalid
        """
        mode = data.get("mode", "direct")

        if mode == "direct":
            return DirectGeometryMode(
                projected_area_cm2=data.get("projected_area_cm2")
            )
        elif mode == "box":
            return BoxEstimateMode(
                length_mm=data.get("length_mm"),
                width_mm=data.get("width_mm"),
                effective_percent=data.get("effective_percent", 100.0)
            )
        return None

    @staticmethod
    def create_direct(area_cm2: float) -> DirectGeometryMode:
        """Convenience: create direct mode."""
        return DirectGeometryMode(area_cm2)

    @staticmethod
    def create_box(
        length_mm: float,
        width_mm: float,
        effective_percent: float = 100.0
    ) -> BoxEstimateMode:
        """Convenience: create box mode."""
        return BoxEstimateMode(length_mm, width_mm, effective_percent)


# Helper function for the dialog
def estimate_from_box(
    length_mm: float,
    width_mm: float,
    effective_percent: float = 100.0
) -> float:
    """Quick calculation for box estimate.

    Args:
        length_mm: Box length (X dimension)
        width_mm: Box width (Y dimension)
        effective_percent: Surface coverage percentage

    Returns:
        Projected area in cm²
    """
    mode = BoxEstimateMode(length_mm, width_mm, effective_percent)
    area = mode.calculate_projected_area()
    return area or 0.0
