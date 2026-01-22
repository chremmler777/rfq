"""Weight ↔ Volume conversion helper using material density."""

from typing import Optional, Tuple


class WeightVolumeHelper:
    """Helper for converting between weight and volume using density."""

    def __init__(self, density_g_cm3: Optional[float] = None):
        """Initialize with material density.

        Args:
            density_g_cm3: Material density in g/cm³
        """
        self.density_g_cm3 = density_g_cm3

    def has_density(self) -> bool:
        """Check if density is available."""
        return self.density_g_cm3 is not None and self.density_g_cm3 > 0

    def calculate_volume_from_weight(self, weight_g: float) -> Optional[float]:
        """Calculate volume from weight.

        Formula: volume_cm³ = weight_g / density_g_cm³

        Args:
            weight_g: Weight in grams

        Returns:
            Volume in cm³ or None if density not available
        """
        if not self.has_density() or weight_g <= 0:
            return None

        volume = weight_g / self.density_g_cm3
        return round(volume, 2)

    def calculate_weight_from_volume(self, volume_cm3: float) -> Optional[float]:
        """Calculate weight from volume.

        Formula: weight_g = volume_cm³ × density_g_cm³

        Args:
            volume_cm3: Volume in cm³

        Returns:
            Weight in grams or None if density not available
        """
        if not self.has_density() or volume_cm3 <= 0:
            return None

        weight = volume_cm3 * self.density_g_cm3
        return round(weight, 2)

    def validate_consistency(
        self,
        weight_g: Optional[float],
        volume_cm3: Optional[float],
        tolerance_percent: float = 20.0
    ) -> Tuple[bool, str]:
        """Check if weight and volume are consistent with material density.

        Args:
            weight_g: Weight in grams
            volume_cm3: Volume in cm³
            tolerance_percent: Allowed deviation percentage (default 20%)

        Returns:
            Tuple of (is_consistent, message)
        """
        if not (weight_g and volume_cm3 and self.has_density()):
            return True, "Insufficient data for validation"

        if weight_g <= 0 or volume_cm3 <= 0:
            return False, "Weight and volume must be positive"

        calculated_weight = self.calculate_weight_from_volume(volume_cm3)
        if calculated_weight is None:
            return True, ""

        deviation = abs(weight_g - calculated_weight) / calculated_weight
        deviation_percent = deviation * 100

        if deviation_percent > tolerance_percent:
            return False, (
                f"Weight ({weight_g}g) and volume ({volume_cm3}cm³) don't match "
                f"material density ({self.density_g_cm3}g/cm³). "
                f"Expected {calculated_weight}g (deviation: {deviation_percent:.0f}%). "
                f"Check if values are correct."
            )

        return True, ""


def auto_calculate_volume(weight_g: float, density_g_cm3: float) -> Optional[float]:
    """Convenience function: auto-calculate volume from weight."""
    if weight_g <= 0 or density_g_cm3 <= 0:
        return None
    return round(weight_g / density_g_cm3, 2)


def auto_calculate_weight(volume_cm3: float, density_g_cm3: float) -> Optional[float]:
    """Convenience function: auto-calculate weight from volume."""
    if volume_cm3 <= 0 or density_g_cm3 <= 0:
        return None
    return round(volume_cm3 * density_g_cm3, 2)
