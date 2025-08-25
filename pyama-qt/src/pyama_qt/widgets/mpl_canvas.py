"""
Shared and componentized Matplotlib canvas widget for embedding plots in Qt.
"""

import matplotlib
from matplotlib.artist import Artist
from matplotlib.patches import Circle
from PySide6.QtWidgets import QGraphicsOpacityEffect

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np


class MplCanvas(FigureCanvas):
    """A componentized Matplotlib canvas widget providing a high-level plotting API."""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, constrained_layout=True)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        self._image_artist = None
        self._overlay_artists = {}

    def clear(self, clear_figure: bool = False) -> None:
        """Clear the axes and make the canvas transparent."""
        self._opacity_effect.setOpacity(0.0)
        self.axes.cla()
        self._image_artist = None
        if clear_figure:
            self.fig.clear()
            self.axes = self.fig.add_subplot(111)
        self.draw_idle()

    def _set_visible(self):
        """Helper to make the canvas visible."""
        if self._opacity_effect.opacity() == 0.0:
            self._opacity_effect.setOpacity(1.0)

    # ---- Image API ----
    def plot_image(
        self,
        image_data: np.ndarray,
        cmap: str = "gray",
        vmin: float = 0,
        vmax: float = 255,
    ) -> None:
        """Display an image, creating the artist if it doesn't exist."""
        self._set_visible()
        self.axes.cla()
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.axes.set_aspect("equal")
        self._image_artist = self.axes.imshow(
            image_data,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            origin="upper",
            interpolation="nearest",
        )
        self.draw_idle()

    def update_image(
        self, image_data: np.ndarray, vmin: float | None = None, vmax: float | None = None
    ) -> None:
        """Update the data of the existing image plot."""
        if self._image_artist:
            self._image_artist.set_data(image_data)
            if vmin is not None and vmax is not None:
                self._image_artist.set_clim(vmin, vmax)
            self.draw_idle()

    # ---- Line & Scatter API ----
    def plot_lines(
        self,
        lines_data: list,
        styles_data: list,
        title: str = "",
        x_label: str = "",
        y_label: str = "",
    ) -> None:
        """Plot multiple lines or scatter plots, each with its own style."""
        self._set_visible()
        self.axes.cla()
        self.axes.set_title(title)
        self.axes.set_xlabel(x_label)
        self.axes.set_ylabel(y_label)
        self.axes.grid(True, linestyle=":", linewidth=0.5)

        for i, (x_data, y_data) in enumerate(lines_data):
            style = styles_data[i] if i < len(styles_data) else {}
            plot_style = style.get("plot_style", "line")

            if plot_style == "line":
                self.axes.plot(
                    x_data,
                    y_data,
                    color=style.get("color", "blue"),
                    linewidth=style.get("linewidth", 1.0),
                    alpha=style.get("alpha", 1.0),
                    label=style.get("label", None),
                )
            elif plot_style == "scatter":
                self.axes.scatter(
                    x_data,
                    y_data,
                    s=style.get("s", 20),
                    color=style.get("color", "blue"),
                    alpha=style.get("alpha", 0.6),
                    label=style.get("label", None),
                )

        if any(style.get("label") for style in styles_data):
            self.axes.legend()

        self.draw_idle()

    # ---- Histogram API ----
    def plot_histogram(
        self, data: np.ndarray, bins: int, title: str, x_label: str, y_label: str
    ) -> None:
        """Plot a histogram."""
        self._set_visible()
        self.axes.cla()
        self.axes.set_title(title)
        self.axes.set_xlabel(x_label)
        self.axes.set_ylabel(y_label)
        self.axes.grid(True, linestyle=":", linewidth=0.5)
        self.axes.hist(data, bins=bins, alpha=0.75)
        self.draw_idle()

    # ---- Overlay API ----
    def plot_overlay(self, overlay_id: str, properties: dict) -> None:
        """Add a new overlay to the plot."""
        self._set_visible()
        if overlay_id in self._overlay_artists:
            self.remove_overlay(overlay_id)

        shape_type = properties.get("type", "circle")
        if shape_type == "circle":
            circle = Circle(
                properties.get("xy", (0, 0)),
                radius=properties.get("radius", 10),
                edgecolor=properties.get("edgecolor", "red"),
                facecolor=properties.get("facecolor", "none"),
                linewidth=properties.get("linewidth", 2.0),
                zorder=properties.get("zorder", 5),
            )
            self.axes.add_patch(circle)
            self._overlay_artists[overlay_id] = circle
        else:
            pass
        self.draw_idle()

    def update_overlay(self, overlay_id: str, properties: dict) -> None:
        """Update properties of an existing overlay."""
        if overlay_id not in self._overlay_artists:
            return

        artist = self._overlay_artists[overlay_id]
        if isinstance(artist, Circle):
            if "xy" in properties:
                artist.set_center(properties["xy"])
            if "radius" in properties:
                artist.set_radius(properties["radius"])
        self.draw_idle()

    def remove_overlay(self, overlay_id: str) -> None:
        """Remove a specific overlay by its ID."""
        if overlay_id in self._overlay_artists:
            try:
                self._overlay_artists[overlay_id].remove()
            except (ValueError, KeyError):
                pass
            del self._overlay_artists[overlay_id]
            self.draw_idle()

    def clear_overlays(self) -> None:
        """Remove all overlays."""
        for overlay_id in list(self._overlay_artists.keys()):
            self.remove_overlay(overlay_id)