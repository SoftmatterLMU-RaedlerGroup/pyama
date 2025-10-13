"""Application configuration constants for PyAMA Qt."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
import os
import sys
from pathlib import Path

import yaml

# Configure logging immediately for config messages
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION LOADING
# =============================================================================

def _get_executable_dir() -> Path:
    """Get the directory containing the executable or script."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller executable
        return Path(sys.executable).parent
    else:
        # Running as script - use the directory containing main.py
        return Path(__file__).parent  # This is already the same directory as main.py


def _load_config() -> dict:
    """Load configuration from config.yaml file."""
    config_dir = _get_executable_dir()
    config_file = config_dir / "config.yaml"

    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                logger.info(f"Loaded configuration from {config_file}")
                return config
        except Exception as e:
            logger.warning(f"Failed to load config from {config_file}: {e}")
            return {}
    else:
        logger.info(f"No config file found at {config_file}, using defaults")
        return {}


# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================

# Load configuration
_config = _load_config()

# Default directory for file dialogs
DEFAULT_DIR = os.path.expanduser(_config.get("DEFAULT_DIR", "~"))

# Ensure the default directory exists
Path(DEFAULT_DIR).mkdir(parents=True, exist_ok=True)

logger.info(f"Using DEFAULT_DIR: {DEFAULT_DIR}")
