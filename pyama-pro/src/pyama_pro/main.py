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
    logger.info(
        "Starting PyAMA-Pro (level=%s, debug=%s)",
        logging.getLevelName(log_level),
        args.debug,
    )
    if args.debug:
        logger.debug("Debug logging enabled via --debug flag")

    # ------------------------------------------------------------------------
    # PLUGIN DISCOVERY
    # ------------------------------------------------------------------------
    # Load plugins from user's home directory
    try:
        plugin_dir = Path.home() / ".pyama" / "plugins"
        logger.info("Loading plugins from %s", plugin_dir)

        builtin_phase_features = set(list_phase_features())
        builtin_fluorescence_features = set(list_fluorescence_features())
        builtin_models = set(list_models())

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
                    "Registered plugin feature %s (type=%s) from %s",
                    plugin_name,
                    feature_type,
                    plugin_dir,
                )
            except Exception as e:
                logger.warning(
                    "Failed to register feature plugin %s from %s: %s",
                    plugin_name,
                    plugin_dir,
                    e,
                )

        # Register model plugins
        for plugin_data in scanner.list_plugins("model"):
            model_name = plugin_data["name"]
            module = plugin_data["module"]

            try:
                register_plugin_model(model_name, module)
                logger.info(
                    "Registered plugin model %s from %s", model_name, plugin_dir
                )
            except Exception as e:
                logger.warning(
                    "Failed to register model plugin %s from %s: %s",
                    model_name,
                    plugin_dir,
                    e,
                )

        all_phase_features = set(list_phase_features())
        all_fluorescence_features = set(list_fluorescence_features())
        all_models = set(list_models())

        plugin_phase_features = all_phase_features - builtin_phase_features
        plugin_fluorescence_features = (
            all_fluorescence_features - builtin_fluorescence_features
        )
        plugin_models = all_models - builtin_models

        logger.info(
            "Registry ready: features (phase=%s, fl=%s), models=%s",
            sorted(all_phase_features),
            sorted(all_fluorescence_features),
            sorted(all_models),
        )
        logger.debug(
            (
                "Registry sources: builtin(features: phase=%s, fl=%s; models=%s); "
                "plugins(features: phase=%s, fl=%s; models=%s)"
            ),
            sorted(builtin_phase_features),
            sorted(builtin_fluorescence_features),
            sorted(builtin_models),
            sorted(plugin_phase_features),
            sorted(plugin_fluorescence_features),
            sorted(plugin_models),
        )

    except Exception as e:
        logger.warning("Plugin discovery failed: %s", e)
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
