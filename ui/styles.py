"""Qt stylesheets for the application."""

# Main application stylesheet
MAIN_STYLE = """
QMainWindow {
    background-color: #f5f5f5;
}

QTabWidget::pane {
    border: 1px solid #c0c0c0;
    background-color: white;
}

QTabBar::tab {
    background-color: #e0e0e0;
    padding: 8px 16px;
    margin-right: 2px;
    border: 1px solid #c0c0c0;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: white;
    border-bottom: 1px solid white;
}

QTabBar::tab:hover:!selected {
    background-color: #d0d0d0;
}

QPushButton {
    background-color: #4472C4;
    color: white;
    border: none;
    padding: 6px 16px;
    border-radius: 4px;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #3461b3;
}

QPushButton:pressed {
    background-color: #2850a2;
}

QPushButton:disabled {
    background-color: #a0a0a0;
}

QTableWidget {
    background-color: white;
    gridline-color: #e0e0e0;
    selection-background-color: #4472C4;
    selection-color: white;
}

QTableWidget::item {
    padding: 4px;
}

QHeaderView::section {
    background-color: #4472C4;
    color: white;
    padding: 6px;
    border: none;
    font-weight: bold;
}

QLineEdit {
    padding: 6px;
    border: 1px solid #c0c0c0;
    border-radius: 4px;
    background-color: white;
}

QLineEdit:focus {
    border: 2px solid #4472C4;
}

QComboBox {
    padding: 6px;
    border: 1px solid #c0c0c0;
    border-radius: 4px;
    background-color: white;
}

QComboBox:focus {
    border: 2px solid #4472C4;
}

QSpinBox, QDoubleSpinBox {
    padding: 6px;
    border: 1px solid #c0c0c0;
    border-radius: 4px;
    background-color: white;
}

QTextEdit {
    border: 1px solid #c0c0c0;
    border-radius: 4px;
    background-color: white;
}

QFrame#DetailsPanel {
    background-color: white;
    border: 1px solid #c0c0c0;
    border-radius: 4px;
}

QStatusBar {
    background-color: #4472C4;
    color: white;
}

QToolBar {
    background-color: #f0f0f0;
    border: none;
    spacing: 4px;
    padding: 4px;
}

QToolBar QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    padding: 4px 8px;
    border-radius: 4px;
}

QToolBar QToolButton:hover {
    background-color: #d0d0d0;
    border: 1px solid #c0c0c0;
}

QMessageBox {
    background-color: white;
}

QMessageBox QPushButton {
    min-width: 80px;
}
"""

# Color constants for status indicators
COLORS = {
    'success': '#70AD47',  # Green
    'warning': '#FFC000',  # Yellow/Orange
    'error': '#FF5050',    # Red
    'info': '#4472C4',     # Blue
    'neutral': '#808080',  # Gray
    'estimated_bg': '#FFD54F',  # Vibrant yellow for estimated values
    'bom_sourced_bg': '#64B5F6',  # Vibrant blue for BOM sourced values
    'missing_row_bg': '#FFE0E0',  # Light red for incomplete rows
}

# Complexity rating colors
COMPLEXITY_COLORS = {
    1: '#70AD47',  # Green - Simple
    2: '#92D050',  # Light green
    3: '#FFC000',  # Yellow - Medium
    4: '#FF8C00',  # Orange
    5: '#FF5050',  # Red - Complex
}


def get_status_style(status: str) -> str:
    """Get stylesheet for a status indicator.

    Args:
        status: Status type ('success', 'warning', 'error', 'info', 'neutral')

    Returns:
        CSS style string
    """
    color = COLORS.get(status, COLORS['neutral'])
    return f"background-color: {color}; color: white; padding: 4px 8px; border-radius: 4px;"


def get_complexity_style(rating: int) -> str:
    """Get stylesheet for complexity rating.

    Args:
        rating: Complexity rating 1-5

    Returns:
        CSS style string
    """
    color = COMPLEXITY_COLORS.get(rating, COLORS['neutral'])
    return f"background-color: {color}; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold;"
