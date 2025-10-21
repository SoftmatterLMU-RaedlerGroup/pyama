"""Main window for pyama-air GUI application."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from pyama_air.gui.merge_wizard import MergeWizard
from pyama_air.gui.workflow_wizard import WorkflowWizard

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
        self._status_label = QLabel("Ready")
        self.addWidget(self._status_label)

    # ------------------------------------------------------------------------
    # STATUS METHODS
    # ------------------------------------------------------------------------
    def show_status_message(self, message: str) -> None:
        """Show a status message."""
        self._status_label.setText(message)

    def clear_status(self) -> None:
        """Clear the status message."""
        self._status_label.setText("Ready")


# =============================================================================
# MAIN WINDOW
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
        self.setWindowTitle("PyAMA-Chat GUI")
        self.resize(600, 400)

    def _create_menu_bar(self) -> None:
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        file_menu.addAction("&Exit", self.close)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        tools_menu.addAction("&Workflow Wizard", self._launch_workflow_wizard)
        tools_menu.addAction("&Merge Wizard", self._launch_merge_wizard)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("&About", self._show_about)

    def _create_status_bar(self) -> None:
        """Create the status bar."""
        self.status_bar = StatusBar()
        self.setStatusBar(self.status_bar)

    def _create_central_widget(self) -> None:
        """Create the central widget with main buttons."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)

        # Welcome message
        welcome_label = QLabel("Welcome to PyAMA-Chat GUI")
        welcome_label.setStyleSheet("QLabel { font-size: 18px; font-weight: bold; }")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(welcome_label)

        # Description
        desc_label = QLabel(
            "Choose a tool to get started with PyAMA workflows or data merging."
        )
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)

        # Workflow wizard button
        self.workflow_btn = QPushButton("Workflow Wizard")
        self.workflow_btn.setMinimumHeight(60)
        self.workflow_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.workflow_btn.clicked.connect(self._launch_workflow_wizard)
        button_layout.addWidget(self.workflow_btn)

        # Merge wizard button
        self.merge_btn = QPushButton("Merge Wizard")
        self.merge_btn.setMinimumHeight(60)
        self.merge_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        self.merge_btn.clicked.connect(self._launch_merge_wizard)
        button_layout.addWidget(self.merge_btn)

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
            "About PyAMA-Chat GUI",
            "PyAMA-Chat GUI\n\n"
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


# =============================================================================
# APPLICATION ENTRY POINT
# =============================================================================


def main() -> None:
    """Main entry point for pyama-air GUI."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("PyAMA-Chat GUI")
    app.setQuitOnLastWindowClosed(True)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    exit_code = app.exec()

    # Cleanup
    app.processEvents()
    app.quit()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
