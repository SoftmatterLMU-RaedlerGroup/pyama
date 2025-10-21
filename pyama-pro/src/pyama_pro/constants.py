"""Application constants for PyAMA Qt."""

import os
from pathlib import Path

# Default directory for file dialogs
DEFAULT_DIR = os.path.expanduser("~")

# Ensure the default directory exists
Path(DEFAULT_DIR).mkdir(parents=True, exist_ok=True)
