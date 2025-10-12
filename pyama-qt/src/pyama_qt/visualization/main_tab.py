"""Visualization page composed of project, image, and trace panels."""

from PySide6.QtWidgets import QHBoxLayout, QStatusBar, QWidget

from .image import ImagePanel
from .project import ProjectPanel
from .trace import TracePanel


class VisualizationTab(QWidget):
    """
    Embeddable visualization page comprising consolidated project, image, and trace panels.
    This tab orchestrates the interactions between the panels.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()
        self._bind()

    def _build(self) -> None:
        layout = QHBoxLayout(self)

        self.project_panel = ProjectPanel(self)
        self.image_panel = ImagePanel(self)
        self.trace_panel = TracePanel(self)

        layout.addWidget(self.project_panel, 1)
        layout.addWidget(self.image_panel, 2)  # Give image panel more space
        layout.addWidget(self.trace_panel, 1)

        # A central status bar can be added to the main window if needed
        # and connected via signals from the panels.

    def _bind(self) -> None:
        """
        Wire up the signals and slots between the panels to create the application logic.
        """
        # --- Project Panel -> Image Panel ---
        # When a project is loaded and user requests visualization, start image loading
        self.project_panel.visualizationRequested.connect(
            lambda fov_idx, channels: self.image_panel.on_visualization_requested(
                self.project_panel._project_data, fov_idx, channels
            )
        )

        # --- Image Panel -> Trace Panel ---
        # When FOV image data is loaded, notify the trace panel to load corresponding trace data
        self.image_panel.fovDataLoaded.connect(self.trace_panel.on_fov_data_loaded)

        # --- Trace Panel -> Image Panel ---
        # When a trace is selected in the table, highlight it on the image
        self.trace_panel.activeTraceChanged.connect(self.image_panel.on_active_trace_changed)

        # --- Status/Error Handling (Example of connecting to a central status bar) ---
        # You could have a status bar in the main window and connect to it like this:
        # main_window_status_bar = self.window().statusBar()
        # self.project_panel.statusMessage.connect(main_window_status_bar.showMessage)
        # self.image_panel.statusMessage.connect(main_window_status_bar.showMessage)
        # self.trace_panel.statusMessage.connect(main_window_status_bar.showMessage)
        # self.project_panel.errorMessage.connect(lambda msg: main_window_status_bar.showMessage(f"Error: {msg}", 5000))
        # self.image_panel.errorMessage.connect(lambda msg: main_window_status_bar.showMessage(f"Error: {msg}", 5000))