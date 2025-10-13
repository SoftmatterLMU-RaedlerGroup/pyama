"""
Shared and componentized Matplotlib canvas widget for embedding plots in Qt.
"""

import matplotlib
from matplotlib.patches import Circle, Polygon

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal


class MplCanvas(FigureCanvas):
    """A componentized Matplotlib canvas widget providing a high-level plotting API."""

    artist_picked = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        width: int = 5,
        height: int = 3,
        dpi: int = 100,
    ):
        self.fig = Figure(figsize=(width, height), dpi=dpi, constrained_layout=True)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

        self._image_artist = None
        self._overlay_artists = {}

        self.fig.canvas.mpl_connect("pick_event", self._on_pick)

    def _on_pick(self, event):
        if hasattr(event.artist, "get_label"):
            label = event.artist.get_label()
            if label and not label.startswith("_"):
                self.artist_picked.emit(label)

    def clear(self, clear_figure: bool = False) -> None:
        """Clear the axes."""
        self.axes.cla()
        self._image_artist = None
        if clear_figure:
            self.fig.clear()
            self.axes = self.fig.add_subplot(111)
        self.draw_idle()

    # ---- Image API ----
    def plot_image(
        self,
        image_data: np.ndarray,
        cmap: str = "gray",
        vmin: float = 0,
        vmax: float = 255,
    ) -> None:
        """Display an image, creating the artist if it doesn't exist."""
        # Only clear and recreate if necessary
        if self._image_artist is None:
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
                zorder=1,
                extent=[
                    0,
                    image_data.shape[1],
                    image_data.shape[0],
                    0,
                ],  # [left, right, bottom, top]
            )
        else:
            # Update existing artist data
            self._image_artist.set_data(image_data)
            self._image_artist.set_clim(vmin, vmax)
            # Update extent if dimensions changed
            self._image_artist.set_extent(
                [
                    0,
                    image_data.shape[1],
                    image_data.shape[0],
                    0,
                ]
            )
        self.draw_idle()

    def update_image(
        self,
        image_data: np.ndarray,
        vmin: float | None = None,
        vmax: float | None = None,
    ) -> None:
        """Update the data of the existing image plot."""
        if self._image_artist:
            self._image_artist.set_data(image_data)
            if vmin is not None and vmax is not None:
                self._image_artist.set_clim(vmin, vmax)
            # Update extent if dimensions changed
            self._image_artist.set_extent(
                [
                    0,
                    image_data.shape[1],
                    image_data.shape[0],
                    0,
                ]
            )
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
                    picker=True,
                    pickradius=5,
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
                label=overlay_id,
                picker=True,
            )
            self.axes.add_patch(circle)
            self._overlay_artists[overlay_id] = circle
        elif shape_type == "polygon":
            polygon = Polygon(
                properties.get("xy"),
                edgecolor=properties.get("edgecolor", "red"),
                facecolor=properties.get("facecolor", "none"),
                linewidth=properties.get("linewidth", 1.0),
                zorder=properties.get("zorder", 5),
                label=overlay_id,
                picker=True,
            )
            self.axes.add_patch(polygon)
            self._overlay_artists[overlay_id] = polygon
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
            artist = self._overlay_artists[overlay_id]
            try:
                # Try to remove the artist from the axes
                if hasattr(artist, "remove"):
                    artist.remove()
                else:
                    # For patches that don't support remove(), remove from axes manually
                    if artist in self.axes.patches:
                        self.axes.patches.remove(artist)
                    if artist in self.axes.artists:
                        self.axes.artists.remove(artist)
            except (ValueError, KeyError, NotImplementedError, AttributeError):
                # Last resort: just remove from our tracking dict
                pass
            del self._overlay_artists[overlay_id]
            self.draw_idle()

    def clear_overlays(self) -> None:
        """Remove all overlays."""
        for overlay_id in list(self._overlay_artists.keys()):
            self.remove_overlay(overlay_id)
