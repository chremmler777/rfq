"""Color coding utilities for source tracking and validation status."""

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox, QTableWidgetItem
from database.models import Part


# Color constants - using vibrant, high-contrast colors
COLOR_ESTIMATED_BG = QColor("#FFD54F")  # Vibrant yellow (Material Design Amber 300)
COLOR_BOM_BG = QColor("#64B5F6")  # Vibrant blue (Material Design Light Blue 300)
COLOR_MISSING_TEXT = QColor("#FF5050")  # Red text
COLOR_MISSING_ROW_BG = QColor("#FFE0E0")  # Light red background
COLOR_COMPLETE_BG = QColor("#E6F4E6")  # Light green


def get_source_color(source: str) -> QColor:
    """Get background color for a data source.

    Args:
        source: One of "data", "bom", "estimated", or other (returns white)

    Returns:
        QColor for the background
    """
    source_lower = (source or "").lower()
    if source_lower == "estimated":
        return COLOR_ESTIMATED_BG
    elif source_lower == "bom":
        return COLOR_BOM_BG
    else:
        return QColor("white")


def apply_source_color_to_widget(widget, source: str):
    """Apply source color to a widget (QSpinBox, QLineEdit, QComboBox, etc).

    Args:
        widget: The widget to colorize
        source: One of "data", "bom", "estimated"
    """
    color = get_source_color(source)

    # For white (normal data), reset to default styling
    if color.name() == "#ffffff":
        widget.setStyleSheet("")
    else:
        # For colored backgrounds, ensure dark text for contrast
        stylesheet = f"""
            background-color: {color.name()};
            color: #000000;
            border: 1px solid #999999;
            border-radius: 4px;
            padding: 6px;
        """
        widget.setStyleSheet(stylesheet)


def apply_source_color_to_table_item(item: QTableWidgetItem, source: str):
    """Apply source color to a table item.

    Args:
        item: The QTableWidgetItem to colorize
        source: One of "data", "bom", "estimated"
    """
    color = get_source_color(source)
    item.setBackground(color)
    # Ensure text is readable - use dark text on colored backgrounds
    item.setForeground(QColor("#000000"))


def get_missing_fields(part: Part) -> list:
    """Get list of missing required fields for a part.

    Required fields: name, volume_cm3, material_id, parts_over_runtime (total demand)

    Args:
        part: The Part object to check

    Returns:
        List of missing field names (empty if complete)
    """
    missing = []

    if not part.name or not part.name.strip():
        missing.append("Name")

    if not part.volume_cm3 or part.volume_cm3 <= 0:
        missing.append("Volume")

    if not part.material_id:
        missing.append("Material")

    if not part.parts_over_runtime or part.parts_over_runtime <= 0:
        missing.append("Total Demand")

    return missing


def is_part_complete(part: Part) -> bool:
    """Check if part has all required fields.

    Args:
        part: The Part object to check

    Returns:
        True if all required fields are filled
    """
    return len(get_missing_fields(part)) == 0
