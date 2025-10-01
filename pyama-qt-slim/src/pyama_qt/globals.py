"""Global configurations and constants for PyAMA Qt."""

import os
from pathlib import Path


# Application constants
APP_NAME = "PyAMA-Qt"
APP_VERSION = "1.0.0"
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 640

# Default paths
DEFAULT_DATA_DIR = Path.home() / "PyAMA" / "data"
DEFAULT_RESULTS_DIR = Path.home() / "PyAMA" / "results"

# Ensure directories exist
DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Logging configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# UI Configuration
TAB_ORDER = ["Processing", "Analysis", "Visualization"]
DEFAULT_TAB_POSITION = "North"  # PySide6.QtWidgets.QTabWidget.TabPosition

# Processing configuration
MAX_WORKERS = min(32, (os.cpu_count() or 1) + 4)

# Display settings
CHART_DPI = 100
PLOT_STYLE = "default"
