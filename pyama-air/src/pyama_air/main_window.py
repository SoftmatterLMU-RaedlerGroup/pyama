"""Main window for pyama-air GUI application."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtCore import Slot, Qt
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama_air.components.status_bar import StatusBar, StatusManager
from pyama_air.analysis import AnalysisWizard
from pyama_air.convert import ConvertWizard
from pyama_air.merge import MergeWizard
from pyama_air.workflow import WorkflowWizard

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN WINDOW CLASS
# =============================================================================


class MainWindow(QMainWindow):
    """Main window for pyama-air GUI application."""

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
        self._create_central_widget()
        self._finalize_window()

    def _setup_window(self) -> None:
        """Configure basic window properties."""
        self.setWindowTitle("PyAMA-Air GUI")
        self.resize(600, 400)

    def _create_menu_bar(self) -> None:
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        file_menu.addAction("&Exit", self.close)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        tools_menu.addAction("&Convert Wizard", self._launch_convert_wizard)
        tools_menu.addAction("&Processing Wizard", self._launch_workflow_wizard)
        tools_menu.addAction("&Merge Wizard", self._launch_merge_wizard)
        tools_menu.addAction("&Analysis Wizard", self._launch_analysis_wizard)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("&About", self._show_about)

    def _create_status_bar(self) -> None:
        """Create the status bar."""
        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

    def _create_central_widget(self) -> None:
        """Create the central widget with main buttons."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)

        # Welcome message
        welcome_label = QLabel("Welcome to PyAMA-Air GUI")
        welcome_label.setStyleSheet("QLabel { font-size: 18px; font-weight: bold; }")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(welcome_label)

        # Description
        desc_label = QLabel(
            "Choose a wizard to process, merge, or analyze your microscopy data."
        )
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Button layout
        button_layout = QVBoxLayout()
        button_layout.setSpacing(20)

        # Convert wizard button
        self.convert_btn = QPushButton("Convert Wizard")
        self.convert_btn.setMinimumHeight(60)
        self.convert_btn.clicked.connect(self._launch_convert_wizard)
        button_layout.addWidget(self.convert_btn)

        # Processing wizard button
        self.processing_btn = QPushButton("Processing Wizard")
        self.processing_btn.setMinimumHeight(60)
        self.processing_btn.clicked.connect(self._launch_workflow_wizard)
        button_layout.addWidget(self.processing_btn)

        # Merge wizard button
        self.merge_btn = QPushButton("Merge Wizard")
        self.merge_btn.setMinimumHeight(60)
        self.merge_btn.clicked.connect(self._launch_merge_wizard)
        button_layout.addWidget(self.merge_btn)

        # Analysis wizard button
        self.analysis_btn = QPushButton("Analysis Wizard")
        self.analysis_btn.setMinimumHeight(60)
        self.analysis_btn.clicked.connect(self._launch_analysis_wizard)
        button_layout.addWidget(self.analysis_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

    def _finalize_window(self) -> None:
        """Finalize window setup."""
        pass

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect all signals."""
        self.status_manager.status_message.connect(self._on_status_message)
        self.status_manager.status_cleared.connect(self._on_status_cleared)

    @Slot(str)
    def _on_status_message(self, message: str) -> None:
        """Handle status message display."""
        self.status_bar.show_status_message(message)

    @Slot()
    def _on_status_cleared(self) -> None:
        """Handle status clearing."""
        self.status_bar.clear_status()

    # ------------------------------------------------------------------------
    # MENU ACTIONS
    # ------------------------------------------------------------------------
    @Slot()
    def _launch_workflow_wizard(self) -> None:
        """Launch the workflow wizard."""
        wizard = WorkflowWizard(self)
        wizard.workflow_finished.connect(self._on_workflow_finished)
        wizard.exec()

    @Slot()
    def _launch_merge_wizard(self) -> None:
        """Launch the merge wizard."""
        wizard = MergeWizard(self)
        wizard.merge_finished.connect(self._on_merge_finished)
        wizard.exec()

    @Slot()
    def _show_about(self) -> None:
        """Show about dialog."""
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.about(
            self,
            "About PyAMA-Air GUI",
            "PyAMA-Air GUI\n\n"
            "Interactive GUI for PyAMA workflows and data merging.\n\n"
            "Version 0.1.0",
        )

    # ------------------------------------------------------------------------
    # WIZARD HANDLERS
    # ------------------------------------------------------------------------
    @Slot(bool, str)
    def _on_workflow_finished(self, success: bool, message: str) -> None:
        """Handle workflow completion."""
        if success:
            self.status_manager.show_message(f"Workflow completed: {message}")
        else:
            self.status_manager.show_message(f"Workflow failed: {message}")

    @Slot(bool, str)
    def _on_merge_finished(self, success: bool, message: str) -> None:
        """Handle merge completion."""
        if success:
            self.status_manager.show_message(f"Merge completed: {message}")
        else:
            self.status_manager.show_message(f"Merge failed: {message}")

    @Slot()
    def _launch_analysis_wizard(self) -> None:
        """Launch the analysis wizard."""
        wizard = AnalysisWizard(self)
        wizard.analysis_finished.connect(self._on_analysis_finished)
        wizard.exec()

    @Slot(bool, str)
    def _on_analysis_finished(self, success: bool, message: str) -> None:
        """Handle analysis completion."""
        if success:
            self.status_manager.show_message(f"Analysis completed: {message}")
        else:
            self.status_manager.show_message(f"Analysis failed: {message}")

    @Slot()
    def _launch_convert_wizard(self) -> None:
        """Launch the convert wizard."""
        wizard = ConvertWizard(self)
        wizard.convert_finished.connect(self._on_convert_finished)
        wizard.exec()

    @Slot(bool, str)
    def _on_convert_finished(self, success: bool, message: str) -> None:
        """Handle convert completion."""
        if success:
            self.status_manager.show_message(f"Conversion completed: {message}")
        else:
            self.status_manager.show_message(f"Conversion failed: {message}")


