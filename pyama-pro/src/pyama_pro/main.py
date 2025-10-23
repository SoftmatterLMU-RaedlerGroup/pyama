#!/usr/bin/env python3
"""Application entry-point wiring together the PyAMA-Pro consolidated widgets."""

# =============================================================================
# IMPORTS
# =============================================================================

import argparse
import logging
import multiprocessing as mp
import sys

from pathlib import Path

from PySide6.QtWidgets import QApplication

from pyama_core.plugin import PluginScanner
from pyama_core.processing.extraction.features import (
    list_features,
    list_phase_features,
    list_fluorescence_features,
)
from pyama_core.analysis.models import list_models
from pyama_pro.main_window import MainWindow


# =============================================================================
# MAIN APPLICATION ENTRY POINT
# =============================================================================


def main() -> None:
    """Spin up the Qt event loop and show the primary application window."""
    # ------------------------------------------------------------------------
    # COMMAND LINE ARGUMENTS
    # ------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="PyAMA-Pro microscopy analysis application"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # ------------------------------------------------------------------------
    # LOGGING CONFIGURATION (do this first!)
    # ------------------------------------------------------------------------
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Suppress noisy matplotlib debug messages
    matplotlib_logger = logging.getLogger("matplotlib.font_manager")
    matplotlib_logger.setLevel(logging.INFO)

    # Also suppress matplotlib verbose output
    verbose_logger = logging.getLogger("matplotlib")
    verbose_logger.setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("Starting PyAMA-Pro application")
    if args.debug:
        logger.debug("Debug logging enabled")

    # ------------------------------------------------------------------------
    # PLUGIN DISCOVERY
    # ------------------------------------------------------------------------
    # Print available features and models before plugin discovery
    logger.info("=" * 70)
    logger.info("BEFORE PLUGIN DISCOVERY:")
    logger.info(f"  Features:     {len(list_features())}")
    logger.info(f"    Phase:      {list_phase_features()}")
    logger.info(f"    Fluorescence: {list_fluorescence_features()}")
    logger.info(f"  Models:       {list_models()}")

    # Load plugins from user's home directory
    try:
        plugin_dir = Path.home() / ".pyama" / "plugins"
        logger.info(f"Loading plugins from: {plugin_dir}")

        scanner = PluginScanner(plugin_dir)
        scanner.scan()

        # Register feature plugins
        from pyama_core.processing.extraction.features import register_plugin_feature
        from pyama_core.analysis.models import register_plugin_model

        for plugin_data in scanner.list_plugins("feature"):
            plugin_name = plugin_data["name"]
            module = plugin_data["module"]
            feature_type = plugin_data["feature_type"]

            try:
                extractor = getattr(module, f"extract_{plugin_name}")
                register_plugin_feature(plugin_name, extractor, feature_type)
                logger.info(
                    f"Registered plugin feature: {plugin_name} ({feature_type})"
                )
            except Exception as e:
                logger.warning(f"Failed to register plugin {plugin_name}: {e}")

        # Register model plugins
        for plugin_data in scanner.list_plugins("model"):
            model_name = plugin_data["name"]
            module = plugin_data["module"]

            try:
                register_plugin_model(model_name, module)
                logger.info(f"Registered plugin model: {model_name}")
            except Exception as e:
                logger.warning(f"Failed to register model {model_name}: {e}")

        logger.info("=" * 70)
        logger.info("AFTER PLUGIN DISCOVERY:")
        logger.info(f"  Features:     {len(list_features())}")
        logger.info(f"    Phase:      {list_phase_features()}")
        logger.info(f"    Fluorescence: {list_fluorescence_features()}")
        logger.info(f"  Models:       {list_models()}")
        logger.info("=" * 70)

    except Exception as e:
        logger.warning(f"Plugin discovery failed: {e}")
        if args.debug:
            logger.exception("Plugin discovery error details")

    # ------------------------------------------------------------------------
    # MULTIPROCESSING CONFIGURATION
    # ------------------------------------------------------------------------
    mp.freeze_support()
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        # Method may already be set in some environments
        pass

    # ------------------------------------------------------------------------
    # QT APPLICATION SETUP
    # ------------------------------------------------------------------------
    app = QApplication(sys.argv)
    app.setApplicationName("PyAMA-Pro")
    app.setQuitOnLastWindowClosed(True)

    # ------------------------------------------------------------------------
    # MAIN WINDOW CREATION AND DISPLAY
    # ------------------------------------------------------------------------
    window = MainWindow()
    window.show()

    # ------------------------------------------------------------------------
    # EVENT LOOP EXECUTION
    # ------------------------------------------------------------------------
    exit_code = app.exec()

    # Clean up
    app.processEvents()
    app.quit()

    sys.exit(exit_code)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
