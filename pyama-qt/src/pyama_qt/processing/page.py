"""
Main window for PyAMA-Qt processing application.
"""

import logging

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
)

from .widgets import WorkflowPanel, MergePanel


logger = logging.getLogger(__name__)


class ProcessingPage(QWidget):
    """Embeddable processing page (QWidget) that contains the full Processing UI and logic."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        logging.basicConfig(level=logging.INFO)

        # Store loaded source info and constructed ND2 metadata
        self._source_info = None
        self._metadata = None

        self.setup_ui()
        logger.info("PyAMA Processing Page loaded")

    def setup_ui(self):
        """Set up the UI layout."""
        # Overall two-column horizontal layout
        main_layout = QHBoxLayout(self)

        # Column 1: Processing (Unified WorkflowPanel)
        self.workflow_panel = WorkflowPanel(self)

        # Column 2: Combined FOV assignment and merge panel
        self.assign_and_merge_panel = MergePanel(self)

        # Add the two columns to the main layout with stretch factors
        main_layout.addWidget(self.workflow_panel, 2)
        main_layout.addWidget(self.assign_and_merge_panel, 1)
