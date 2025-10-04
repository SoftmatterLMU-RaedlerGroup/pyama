"""Configuration management for PyAMA Qt."""

import json
from pathlib import Path
from typing import Any, Dict

from ..app.globals import DEFAULT_DATA_DIR, DEFAULT_RESULTS_DIR


class Config:
    """Configuration manager for PyAMA Qt."""

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            config_path = Path.home() / ".pyama" / "config.json"

        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._config = {}
        else:
            self._config = {}

    def _save_config(self) -> None:
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, "w") as f:
                json.dump(self._config, f, indent=2)
        except IOError:
            pass  # Silently fail for config saves

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self._config[key] = value
        self._save_config()

    def get_data_dir(self) -> Path:
        """Get the data directory path."""
        return Path(self.get("data_dir", str(DEFAULT_DATA_DIR)))

    def set_data_dir(self, path: Path) -> None:
        """Set the data directory path."""
        self.set("data_dir", str(path))

    def get_results_dir(self) -> Path:
        """Get the results directory path."""
        return Path(self.get("results_dir", str(DEFAULT_RESULTS_DIR)))

    def set_results_dir(self, path: Path) -> None:
        """Set the results directory path."""
        self.set("results_dir", str(path))


# Global config instance
_config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return _config


def get_data_dir() -> Path:
    """Get the current data directory."""
    return _config.get_data_dir()


def get_results_dir() -> Path:
    """Get the current results directory."""
    return _config.get_results_dir()
