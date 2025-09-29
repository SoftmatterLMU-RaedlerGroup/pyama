"""
Simple Matplotlib canvas widget for embedding blank plots in Qt.
"""

import matplotlib

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtWidgets import QWidget


class MplCanvas(FigureCanvas):
    """A simple Matplotlib canvas widget for UI display purposes."""

    def __init__(
        self,
        parent: QWidget | None = None,
        width: int = 5,
        height: int = 4,
        dpi: int = 100,
    ):
        self.fig = Figure(figsize=(width, height), dpi=dpi, constrained_layout=True)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

        # Clear the canvas to show blank
        self.clear()

    def clear(self) -> None:
        """Clear the canvas to show blank."""
        self.axes.cla()
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.draw_idle()
