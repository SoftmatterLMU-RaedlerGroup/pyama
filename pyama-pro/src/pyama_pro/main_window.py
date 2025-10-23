"""Primary application window hosting all PyAMA views without MVC separation."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
import shutil
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QStatusBar,
    QLabel,
    QMenuBar,
    QMessageBox,
    QFileDialog,
)

from pyama_pro.analysis.main_tab import AnalysisTab
from pyama_pro.processing.main_tab import ProcessingTab
from pyama_pro.visualization.main_tab import VisualizationTab

logger = logging.getLogger(__name__)


# =============================================================================
# STATUS MANAGER
# =============================================================================


class StatusManager(QObject):
    """Status manager for showing user-friendly messages."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    status_message = Signal(str)  # message
    status_cleared = Signal()  # Clear the status

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    # ------------------------------------------------------------------------
    # STATUS METHODS
    # ------------------------------------------------------------------------
    def show_message(self, message: str) -> None:
        """Show a status message."""
        logger.debug("Status Bar: Showing message - %s", message)
        self.status_message.emit(message)

    def clear_status(self) -> None:
        """Clear the status message."""
        logger.debug("Status Bar: Clearing status")
        self.status_cleared.emit()


# =============================================================================
# STATUS BAR
# =============================================================================


class StatusBar(QStatusBar):
    """Status bar for displaying status messages only."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Set up the status bar UI components."""
        # Main status label
        self._status_label = QLabel("Ready")
        self.addWidget(self._status_label)

    def _connect_signals(self) -> None:
        """Connect signals for the status bar."""
        pass

    # ------------------------------------------------------------------------
    # STATUS UPDATES
    # ------------------------------------------------------------------------
    def show_status_message(self, message: str) -> None:
        """Display status message."""
        self._status_label.setText(message)

    def clear_status(self) -> None:
        """Clear status and show ready state."""
        self._status_label.setText("Ready")

# =============================================================================
# MAIN WINDOW CLASS
# =============================================================================


class MainWindow(QMainWindow):
    """Top-level window assembling the Processing, Analysis, and Visualization tabs."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self) -> None:
        super().__init__()
        self.status_manager = StatusManager()
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # UI BUILDING
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build all UI components for the main window."""
        self._setup_window()
        self._create_menu_bar()
        self._create_status_bar()
        self._create_tabs()
        self._finalize_window()

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect all signals and establish communication between components."""
        self._connect_tabs()

    # ------------------------------------------------------------------------
    # WINDOW SETUP
    # ------------------------------------------------------------------------
    def _setup_window(self) -> None:
        """Configure basic window properties."""
        self.setWindowTitle("PyAMA-Pro")
        self.resize(1600, 800)

    # ------------------------------------------------------------------------
    # MENU BAR SETUP
    # ------------------------------------------------------------------------
    def _create_menu_bar(self) -> None:
        """Create and configure the menu bar."""
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        # File menu
        file_menu = menu_bar.addMenu("&File")

        # Install Plugin action
        install_plugin_action = file_menu.addAction("Install Plugin...")
        install_plugin_action.setShortcut("Ctrl+I")
        install_plugin_action.setStatusTip(
            "Install a custom feature or model plugin from a Python file"
        )
        install_plugin_action.triggered.connect(self._on_install_plugin)

    # ------------------------------------------------------------------------
    # STATUS BAR SETUP
    # ------------------------------------------------------------------------
    def _create_status_bar(self) -> None:
        """Create and configure the status bar."""
        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

        # Connect status manager signals to status bar
        self.status_manager.status_message.connect(self._on_status_message)
        self.status_manager.status_cleared.connect(self._on_status_cleared)

    # ------------------------------------------------------------------------
    # TAB CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_tabs(self) -> None:
        """Establish communication between tabs."""
        # Connect processing signals to disable other tabs
        self.processing_tab.processing_started.connect(self._on_processing_started)
        self.processing_tab.processing_finished.connect(self._on_processing_finished)

        # Connect analysis signals to disable other tabs
        self.analysis_tab.processing_started.connect(self._on_processing_started)
        self.analysis_tab.processing_finished.connect(self._on_processing_finished)

        # Connect status manager to tabs for simple message display
        self.processing_tab.set_status_manager(self.status_manager)
        self.analysis_tab.set_status_manager(self.status_manager)
        self.visualization_tab.set_status_manager(self.status_manager)

        # Connect tab change signal for debugging
        self.tabs.currentChanged.connect(self._on_tab_changed)

    # ------------------------------------------------------------------------
    # TAB CREATION
    # ------------------------------------------------------------------------
    def _create_tabs(self) -> None:
        """Create the tab widget and individual tabs."""
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(False)
        self.tabs.setTabsClosable(False)
        self.tabs.setDocumentMode(True)

        # Instantiate the new, consolidated tab widgets
        self.processing_tab = ProcessingTab(self)
        self.analysis_tab = AnalysisTab(self)
        self.visualization_tab = VisualizationTab(self)

    @Slot()
    def _on_status_message(self, message: str) -> None:
        """Handle status message display."""
        self.status_bar.show_status_message(message)

    @Slot()
    def _on_status_cleared(self) -> None:
        """Handle status clearing."""
        self.status_bar.clear_status()

    @Slot(int)
    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change events."""
        tab_name = self.tabs.tabText(index)
        logger.debug("UI Event: Tab changed to - %s (index %d)", tab_name, index)

    @Slot()
    def _on_processing_started(self) -> None:
        """Disable tab switching during processing."""
        logger.debug("Processing started, disabling tab switching")
        self.tabs.tabBar().setEnabled(False)  # Only disable tab bar, not content

    @Slot()
    def _on_processing_finished(self) -> None:
        """Re-enable tab switching when processing finishes."""
        logger.debug("Processing finished, re-enabling tab switching")
        self.tabs.tabBar().setEnabled(True)  # Re-enable tab bar only

    @Slot()
    def _on_install_plugin(self) -> None:
        """Handle the Install Plugin menu action."""
        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Plugin File",
            str(Path.home()),
            "Python Files (*.py)",
        )

        if not file_path:
            return

        try:
            plugin_file = Path(file_path)

            # Validate the plugin before installing
            from pyama_core.plugin import PluginScanner

            temp_scanner = PluginScanner(plugin_file.parent)
            temp_scanner._load_plugin(plugin_file)

            if plugin_file.stem not in temp_scanner.plugins:
                error_msg = temp_scanner.errors.get(
                    plugin_file.stem,
                    "Plugin validation failed. Check file format.",
                )
                QMessageBox.warning(
                    self,
                    "Invalid Plugin",
                    f"Plugin validation failed:\n{error_msg}",
                )
                return

            # Determine destination directory based on plugin type
            plugin_data = temp_scanner.plugins[plugin_file.stem]
            plugin_type = plugin_data["type"]

            plugin_base_dir = Path.home() / ".pyama" / "plugins"

            if plugin_type == "feature":
                feature_type = plugin_data.get("feature_type", "unknown")
                if feature_type == "phase":
                    dest_dir = plugin_base_dir / "features" / "phase_contrast"
                elif feature_type == "fluorescence":
                    dest_dir = plugin_base_dir / "features" / "fluorescence"
                else:
                    dest_dir = plugin_base_dir / "features"
            elif plugin_type == "model":
                dest_dir = plugin_base_dir / "fitting"
            else:
                dest_dir = plugin_base_dir

            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / plugin_file.name
            shutil.copy2(plugin_file, dest_path)

            # Reload plugins
            self._reload_plugins()

            # Show success message
            plugin_name = temp_scanner.plugins[plugin_file.stem]["name"]
            self.status_manager.show_message(
                f"Plugin '{plugin_name}' installed successfully!"
            )

        except Exception as e:
            logger.exception("Plugin installation failed")
            QMessageBox.critical(
                self,
                "Installation Failed",
                f"Failed to install plugin:\n{str(e)}",
            )

    def _reload_plugins(self) -> None:
        """Reload plugins and update feature/model lists."""
        from pyama_core.plugin import PluginScanner
        from pyama_core.processing.extraction.features import (
            register_plugin_feature,
        )
        from pyama_core.analysis.models import register_plugin_model

        plugin_dir = Path.home() / ".pyama" / "plugins"
        scanner = PluginScanner(plugin_dir)
        scanner.scan()

        # Register feature plugins
        for plugin_data in scanner.list_plugins("feature"):
            plugin_name = plugin_data["name"]
            module = plugin_data["module"]
            feature_type = plugin_data["feature_type"]

            try:
                extractor = getattr(module, f"extract_{plugin_name}")
                register_plugin_feature(plugin_name, extractor, feature_type)
                logger.info(
                    f"Reloaded plugin feature: {plugin_name} ({feature_type})"
                )
            except Exception as e:
                logger.warning(f"Failed to reload plugin {plugin_name}: {e}")

        # Register model plugins
        for plugin_data in scanner.list_plugins("model"):
            model_name = plugin_data["name"]
            module = plugin_data["module"]

            try:
                register_plugin_model(model_name, module)
                logger.info(f"Reloaded plugin model: {model_name}")
            except Exception as e:
                logger.warning(f"Failed to reload model {model_name}: {e}")

    # ------------------------------------------------------------------------
    # WINDOW FINALIZATION
    # ------------------------------------------------------------------------
    def _finalize_window(self) -> None:
        """Add tabs to window and complete setup."""
        self.tabs.addTab(self.processing_tab, "Processing")
        self.tabs.addTab(self.visualization_tab, "Visualization")
        self.tabs.addTab(self.analysis_tab, "Analysis")

        self.setCentralWidget(self.tabs)
