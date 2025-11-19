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

    logger.info("Loading plugins from %s", plugin_dir)

    # Create and scan the directory
    scanner = PluginScanner(plugin_dir)
    scanner.scan()

    # Register feature plugins
    feature_plugins = scanner.list_plugins("feature")
    feature_names = [plugin["name"] for plugin in feature_plugins]
    logger.info(
        "Found %d feature plugin(s)%s",
        len(feature_plugins),
        f": {sorted(feature_names)}" if feature_names else "",
    )

    for plugin_data in feature_plugins:
        plugin_name = plugin_data["name"]
        module = plugin_data["module"]
        feature_type = plugin_data["feature_type"]

        try:
            extractor = getattr(module, f"extract_{plugin_name}")
            register_plugin_feature(plugin_name, extractor, feature_type)
            logger.debug(
                "Registered feature plugin '%s' (%s) from %s",
                plugin_name,
                feature_type,
                plugin_data.get("path", plugin_dir),
            )
        except Exception as e:
            logger.error(
                "Failed to register feature plugin '%s' (%s): %s",
                plugin_name,
                feature_type,
                e,
            )

    # Log model plugins (for future use)
    model_plugins = scanner.list_plugins("model")
    if model_plugins:
        model_names = [plugin["name"] for plugin in model_plugins]
        logger.info(
            "Found %d model plugin(s)%s",
            len(model_plugins),
            f": {sorted(model_names)}" if model_names else "",
        )
        logger.debug("Model plugin registration not yet implemented")

    logger.info(
        "Plugin loading complete: %d plugin(s) registered "
        "(features=%d, models=%d, dir=%s)",
        len(scanner.plugins),
        len(feature_plugins),
        len(model_plugins),
        plugin_dir,
    )

    return scanner
