"""Processing page for workflow management."""

from PySide6.QtWidgets import QHBoxLayout, QStatusBar, QWidget

from ..panels import WorkflowPanel, MergePanel


class ProcessingPage(QWidget):
    """Processing page comprising workflow and merge panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self._status_bar = QStatusBar(self)
        layout = QHBoxLayout(self)

        self.workflow_panel = WorkflowPanel(self)
        self.merge_panel = MergePanel(self)

        layout.addWidget(self.workflow_panel, 1)
        layout.addWidget(self.merge_panel, 1)
        layout.addWidget(self._status_bar)
