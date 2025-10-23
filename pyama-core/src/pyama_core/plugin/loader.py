"""Plugin loading and registration for PyAMA.

Handles discovering and registering plugins at application startup.
"""

import logging
from pathlib import Path

from pyama_core.plugin.scanner import PluginScanner
from pyama_core.processing.extraction.features import register_plugin_feature

logger = logging.getLogger(__name__)


def load_plugins(plugin_dir: Path | None = None) -> PluginScanner:
    """Load and register all plugins from the plugin directory.

    This function:
    1. Scans the plugin directory for valid plugin files
    2. Registers feature plugins with the extraction system
    3. Returns the scanner for later queries

    Args:
        plugin_dir: Path to plugin directory. Defaults to ~/.pyama/plugins

    Returns:
        Loaded PluginScanner instance with all discovered plugins
    """
    if plugin_dir is None:
        plugin_dir = Path.home() / ".pyama" / "plugins"

    logger.info(f"Loading plugins from {plugin_dir}")

    # Create and scan the directory
    scanner = PluginScanner(plugin_dir)
    scanner.scan()

    # Register feature plugins
    feature_plugins = scanner.list_plugins("feature")
    logger.info(f"Found {len(feature_plugins)} feature plugin(s)")

    for plugin_data in feature_plugins:
        plugin_name = plugin_data["name"]
        module = plugin_data["module"]
        feature_type = plugin_data["feature_type"]

        try:
            # Get the extractor function
            extractor = getattr(module, f"extract_{plugin_name}")

            # Register it
            register_plugin_feature(plugin_name, extractor, feature_type)
            logger.info(
                f"Registered feature plugin '{plugin_name}' "
                f"({feature_type} feature)"
            )
        except Exception as e:
            logger.error(f"Failed to register feature plugin '{plugin_name}': {e}")

    # Log model plugins (for future use)
    model_plugins = scanner.list_plugins("model")
    if model_plugins:
        logger.info(f"Found {len(model_plugins)} model plugin(s)")
        logger.debug("Model plugin registration not yet implemented")

    logger.info(f"Plugin loading complete: {len(scanner.plugins)} plugin(s) registered")

    return scanner
