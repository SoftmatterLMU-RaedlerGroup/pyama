"""Plugin system for PyAMA.

Provides plugin discovery and registration for features and models.
Compatible with PyInstaller and frozen applications.

Example:
    Load plugins on application startup::

        from pyama_core.plugin import load_plugins

        scanner = load_plugins()  # Scans ~/.pyama/plugins by default
        feature_names = scanner.list_plugins("feature")
"""

from pyama_core.plugin.scanner import PluginScanner
from pyama_core.plugin.loader import load_plugins

__all__ = ["PluginScanner", "load_plugins"]
