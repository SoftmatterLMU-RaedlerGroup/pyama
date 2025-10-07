"""Image viewer panel for displaying microscopy images and processing results."""

import logging
from collections.abc import Mapping

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from pyama_qt.models.visualization import PositionData
from ..base import BasePanel
from ..components.mpl_canvas import MplCanvas

logger = logging.getLogger(__name__)


class ImagePanel(BasePanel):
    """Panel for viewing microscopy images and processing results."""

    data_type_selected = Signal(str)
    frame_delta_requested = Signal(int)

    def build(self) -> None:
        layout = QVBoxLayout(self)

        image_group = QGroupBox("Image Viewer")
        image_layout = QVBoxLayout(image_group)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Data Type:"))
        self.data_type_combo = QComboBox()
        controls_layout.addWidget(self.data_type_combo)

        self.prev_frame_10_button = QPushButton("<<")
        controls_layout.addWidget(self.prev_frame_10_button)

        self.prev_frame_button = QPushButton("<")
        controls_layout.addWidget(self.prev_frame_button)

        self.frame_label = QLabel("Frame 0/0")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls_layout.addWidget(self.frame_label)

        self.next_frame_button = QPushButton(">")
        controls_layout.addWidget(self.next_frame_button)

        self.next_frame_10_button = QPushButton(">>")
        controls_layout.addWidget(self.next_frame_10_button)

        image_layout.addLayout(controls_layout)

        self.canvas = MplCanvas(self, width=8, height=6, dpi=100)
        image_layout.addWidget(self.canvas, 1)

        layout.addWidget(image_group)

        self._current_frame_index = 0
        self._max_frame_index = 0
        self._positions_by_cell: dict[str, PositionData] = {}
        self._active_trace_id: str | None = None
        self._current_data_type: str = ""

    def bind(self) -> None:
        self.data_type_combo.currentTextChanged.connect(self.data_type_selected.emit)
        self.prev_frame_button.clicked.connect(
            lambda: self.frame_delta_requested.emit(-1)
        )
        self.next_frame_button.clicked.connect(
            lambda: self.frame_delta_requested.emit(+1)
        )
        self.prev_frame_10_button.clicked.connect(
            lambda: self.frame_delta_requested.emit(-10)
        )
        self.next_frame_10_button.clicked.connect(
            lambda: self.frame_delta_requested.emit(+10)
        )

    # ------------------------------------------------------------------
    # Controller-facing API
    # ------------------------------------------------------------------
    def set_available_data_types(
        self, types: list[str], current: str | None = None
    ) -> None:
        self.data_type_combo.blockSignals(True)
        self.data_type_combo.clear()
        self.data_type_combo.addItems(types)
        if current and current in types:
            self.data_type_combo.setCurrentText(current)
            self._current_data_type = current
        elif types:
            self._current_data_type = types[0]
        else:
            self._current_data_type = ""
        self.data_type_combo.blockSignals(False)

    def set_current_data_type(self, data_type: str) -> None:
        if not data_type:
            return
        self._current_data_type = data_type
        if self.data_type_combo.currentText() == data_type:
            return
        index = self.data_type_combo.findText(data_type)
        if index >= 0:
            self.data_type_combo.blockSignals(True)
            self.data_type_combo.setCurrentIndex(index)
            self.data_type_combo.blockSignals(False)

    def set_frame_info(self, current: int, maximum: int) -> None:
        self._current_frame_index = max(0, current)
        self._max_frame_index = max(0, maximum)
        self._update_frame_label()

    def set_trace_positions(self, positions: Mapping[str, PositionData]) -> None:
        self._positions_by_cell = dict(positions)

    def set_active_trace(self, trace_id: str | None) -> None:
        self._active_trace_id = trace_id

    def render_image(
        self,
        image: np.ndarray,
        *,
        data_type: str,
    ) -> None:
        if image.ndim != 2:
            logger.warning("Expected 2D image slice, received %s", image.shape)
            return

        self._current_data_type = data_type or "Image"
        if self._current_data_type.startswith("seg"):
            vmin = float(image.min())
            vmax = float(image.max())
            self.canvas.plot_image(image, cmap="viridis", vmin=vmin, vmax=vmax)
        else:
            self.canvas.plot_image(image, cmap="gray", vmin=0, vmax=255)

        self._draw_trace_overlays()
        self.canvas.axes.set_title(
            f"{self._current_data_type} - Frame {self._current_frame_index}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _update_frame_label(self) -> None:
        self.frame_label.setText(
            f"Frame {self._current_frame_index}/{self._max_frame_index}"
        )

        if self._current_frame_index <= 0:
            self.prev_frame_button.setToolTip("Already at first frame")
            self.prev_frame_10_button.setToolTip("Already near first frame")
        else:
            self.prev_frame_button.setToolTip("Previous frame")
            self.prev_frame_10_button.setToolTip("Previous 10 frames")

        if self._current_frame_index >= self._max_frame_index:
            self.next_frame_button.setToolTip("Already at last frame")
            self.next_frame_10_button.setToolTip("Already near last frame")
        else:
            self.next_frame_button.setToolTip("Next frame")
            self.next_frame_10_button.setToolTip("Next 10 frames")

    def _draw_trace_overlays(self) -> None:
        """Draw trace position overlays on the image."""
        if not self._positions_by_cell or not self._active_trace_id:
            self.canvas.clear_overlays()
            return

        # Only show the active trace
        if self._active_trace_id in self._positions_by_cell:
            positions = self._positions_by_cell[self._active_trace_id]

            # Check if current frame exists in the PositionData frames array
            frame_indices = positions.frames
            if self._current_frame_index in frame_indices:
                # Find the index of the current frame in the frames array
                frame_array_idx = np.where(frame_indices == self._current_frame_index)[
                    0
                ]
                if len(frame_array_idx) > 0:
                    # Get the x, y coordinates for this frame
                    pos_x = positions.position["x"][frame_array_idx[0]]
                    pos_y = positions.position["y"][frame_array_idx[0]]

                    # Use the built-in overlay functionality with bright colors like the test overlay
                    overlay_properties = {
                        "type": "circle",
                        "xy": (pos_x, pos_y),  # Use non-flipped coordinates
                        "radius": 40,  # Same size as test overlay
                        "edgecolor": "red",  # Bright color for visibility
                        "facecolor": "none",  # Bright fill color
                        "linewidth": 2.0,
                        "zorder": 5,  # High zorder like test overlay
                    }

                    self.canvas.plot_overlay("active_trace", overlay_properties)
                else:
                    self.canvas.clear_overlays()
            else:
                self.canvas.clear_overlays()
        else:
            self.canvas.clear_overlays()
