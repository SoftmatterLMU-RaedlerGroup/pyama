"""Visualization page for image and trace viewing."""

from PySide6.QtWidgets import QHBoxLayout, QStatusBar, QWidget

from ..panels import ImagePanel, ProjectPanel, TracePanel


class VisualizationPage(QWidget):
    """Visualization page comprising image, project, and trace panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self._status_bar = QStatusBar(self)
        layout = QHBoxLayout(self)

        self.project_panel = ProjectPanel(self)
        self.image_panel = ImagePanel(self)
        self.trace_panel = TracePanel(self)

        layout.addWidget(self.project_panel, 1)
        layout.addWidget(self.image_panel, 1)
        layout.addWidget(self.trace_panel, 1)
        layout.addWidget(self._status_bar)
