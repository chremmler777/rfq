"""Configuration settings for RFQ Tool Quoting Software."""

import os
from pathlib import Path

# Default to local directory, can be changed to shared network drive
# Example: DATABASE_PATH = Path("//server/share/rfq_data")
DATABASE_PATH = Path(os.environ.get('RFQ_DATABASE_PATH', Path(__file__).parent / 'data'))

# Database file name
DATABASE_NAME = 'rfq_tools.db'

# Full database file path
DATABASE_FILE = DATABASE_PATH / DATABASE_NAME

# Project files storage (images, CAD files)
PROJECTS_PATH = DATABASE_PATH / 'projects'

# Ensure directories exist
def ensure_directories():
    """Create required directories if they don't exist."""
    DATABASE_PATH.mkdir(parents=True, exist_ok=True)
    PROJECTS_PATH.mkdir(parents=True, exist_ok=True)

# SQLite connection string
def get_database_url():
    """Get SQLAlchemy database URL."""
    ensure_directories()
    return f"sqlite:///{DATABASE_FILE}"

# Application settings
APP_NAME = "RFQ Tool Quoting"
APP_VERSION = "1.0.0"

# Calculation defaults
DEFAULT_SAFETY_FACTOR = 1.2  # 20% safety margin for clamping force
DEFAULT_AVAILABLE_HOURS_PER_WEEK = 120  # 5 days * 24 hours
