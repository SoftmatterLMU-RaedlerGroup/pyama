"""Plugin discovery and loading for PyAMA.

Uses importlib.util for file-based loading, compatible with PyInstaller.
"""

import importlib.util
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class PluginScanner:
    """Safe plugin scanner that works with PyInstaller.

    Scans a directory for .py files and validates them as either
    feature or model plugins. Uses importlib.util for PyInstaller
    compatibility.
    """

    def __init__(self, plugin_dir: Path):
        """Initialize scanner with a plugin directory.

        Args:
            plugin_dir: Path to directory containing .py plugin files
        """
        self.plugin_dir = Path(plugin_dir)
        self.plugins: dict[str, object] = {}
        self.errors: dict[str, str] = {}

    def scan(self) -> None:
        """Scan plugin directory and load all valid plugins."""
        if not self.plugin_dir.exists():
            logger.debug(f"Plugin directory does not exist: {self.plugin_dir}")
            return

        logger.info(f"Scanning for plugins in {self.plugin_dir}")

        # Find all .py files (exclude __pycache__, __init__.py, etc.)
        plugin_files = [
            f for f in self.plugin_dir.glob("*.py")
            if not f.name.startswith("_")
        ]

        logger.debug(f"Found {len(plugin_files)} potential plugin files")

        for plugin_file in plugin_files:
            self._load_plugin(plugin_file)

        logger.info(f"Loaded {len(self.plugins)} valid plugins")
        if self.errors:
            logger.warning(f"Failed to load {len(self.errors)} plugins")
            for name, error in self.errors.items():
                logger.debug(f"  {name}: {error}")

    def _load_plugin(self, plugin_file: Path) -> None:
        """Load a single plugin file using importlib (PyInstaller compatible).

        Args:
            plugin_file: Path to .py file
        """
        plugin_name = plugin_file.stem  # filename without .py

        try:
            # Load module from file path (works with PyInstaller!)
            spec = importlib.util.spec_from_file_location(
                plugin_name,
                plugin_file
            )

            if spec is None or spec.loader is None:
                raise ValueError("Could not create module spec")

            module = importlib.util.module_from_spec(spec)

            # Add to sys.modules temporarily to handle internal imports
            sys.modules[plugin_name] = module

            try:
                spec.loader.exec_module(module)
            except Exception as e:
                del sys.modules[plugin_name]
                raise e

            # Validate plugin structure
            plugin_data = self._validate_plugin(plugin_name, module)

            if plugin_data:
                self.plugins[plugin_name] = plugin_data
                logger.info(
                    f"Loaded plugin: {plugin_name} "
                    f"({plugin_data['type']} v{plugin_data['version']})"
                )
            else:
                self.errors[plugin_name] = "Invalid plugin structure"

        except Exception as e:
            self.errors[plugin_name] = str(e)
            logger.debug(f"Error loading {plugin_name}: {e}")

    def _validate_plugin(self, name: str, module: object) -> dict[str, object] | None:
        """Validate plugin has required attributes.

        Args:
            name: Plugin name
            module: Loaded module

        Returns:
            Plugin metadata dict if valid, None otherwise
        """
        # Check for required metadata
        required_attrs = ["PLUGIN_NAME", "PLUGIN_TYPE"]
        for attr in required_attrs:
            if not hasattr(module, attr):
                logger.debug(f"{name}: Missing {attr}")
                return None

        plugin_type = getattr(module, "PLUGIN_TYPE")

        if plugin_type == "feature":
            return self._validate_feature_plugin(name, module)
        elif plugin_type == "model":
            return self._validate_model_plugin(name, module)
        else:
            logger.debug(f"{name}: Invalid PLUGIN_TYPE: {plugin_type}")
            return None

    def _validate_feature_plugin(
        self, name: str, module: object
    ) -> dict[str, object] | None:
        """Validate feature plugin structure.

        Args:
            name: Plugin name
            module: Loaded module

        Returns:
            Plugin metadata dict if valid, None otherwise
        """
        # Check for PLUGIN_FEATURE_TYPE
        if not hasattr(module, "PLUGIN_FEATURE_TYPE"):
            logger.debug(f"{name}: Missing PLUGIN_FEATURE_TYPE")
            return None

        feature_type = getattr(module, "PLUGIN_FEATURE_TYPE")
        if feature_type not in ("phase", "fluorescence"):
            logger.debug(f"{name}: Invalid PLUGIN_FEATURE_TYPE: {feature_type}")
            return None

        # Check for extract_* function
        extract_func = getattr(module, f"extract_{name}", None)
        if not extract_func or not callable(extract_func):
            logger.debug(f"{name}: Missing extract_{name}() function")
            return None

        return {
            "name": getattr(module, "PLUGIN_NAME", name),
            "type": "feature",
            "feature_type": feature_type,
            "version": getattr(module, "PLUGIN_VERSION", "0.0.1"),
            "module": module,
            "path": getattr(module, "__file__", "unknown"),
        }

    def _validate_model_plugin(
        self, name: str, module: object
    ) -> dict[str, object] | None:
        """Validate model plugin structure.

        Model plugins require:
        - Params dataclass
        - Bounds dataclass
        - DEFAULTS (Params instance)
        - BOUNDS (Bounds instance)
        - eval(t, params) function

        Args:
            name: Plugin name
            module: Loaded module

        Returns:
            Plugin metadata dict if valid, None otherwise
        """
        # Check for required model components
        required = ["Params", "Bounds", "DEFAULTS", "BOUNDS", "eval"]
        for attr in required:
            if not hasattr(module, attr):
                logger.debug(f"{name}: Missing {attr}")
                return None

        # Verify eval is callable
        eval_func = getattr(module, "eval", None)
        if not callable(eval_func):
            logger.debug(f"{name}: eval is not callable")
            return None

        return {
            "name": getattr(module, "PLUGIN_NAME", name),
            "type": "model",
            "version": getattr(module, "PLUGIN_VERSION", "0.0.1"),
            "module": module,
            "path": getattr(module, "__file__", "unknown"),
        }

    def get_plugin(self, name: str) -> dict[str, object] | None:
        """Get a loaded plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin metadata dict or None if not found
        """
        return self.plugins.get(name)

    def list_plugins(self, plugin_type: str | None = None) -> list[dict[str, object]]:
        """List all loaded plugins, optionally filtered by type.

        Args:
            plugin_type: Optional filter ("feature" or "model")

        Returns:
            List of plugin metadata dicts
        """
        plugins = list(self.plugins.values())
        if plugin_type:
            plugins = [p for p in plugins if p["type"] == plugin_type]
        return plugins

    def get_feature_plugins(self, feature_type: str | None = None) -> list[dict[str, object]]:
        """Get feature plugins, optionally filtered by feature type.

        Args:
            feature_type: Optional filter ("phase" or "fluorescence")

        Returns:
            List of feature plugin metadata dicts
        """
        plugins = [p for p in self.plugins.values() if p["type"] == "feature"]
        if feature_type:
            plugins = [p for p in plugins if p.get("feature_type") == feature_type]
        return plugins
