"""Image viewer panel for displaying microscopy images and processing results.

This variant avoids explicit enable/disable toggles on navigation buttons.
Navigation remains driven by the current frame index and click handlers.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QComboBox,
    QPushButton,
)
from PySide6.QtCore import Qt
import logging

from pyama_qt.components import MplCanvas
from pyama_qt.visualization.models import ImageCacheModel, TraceSelectionModel
from pyama_qt.ui import ModelBoundPanel

logger = logging.getLogger(__name__)


class ImagePanel(ModelBoundPanel):
    """Panel for viewing microscopy images and processing results."""

    def build(self) -> None:
        layout = QVBoxLayout(self)

        # Image group
        image_group = QGroupBox("Image Viewer")
        image_layout = QVBoxLayout(image_group)

        # Controls layout
        controls_layout = QHBoxLayout()

        # Data type selection
        controls_layout.addWidget(QLabel("Data Type:"))
        self.data_type_combo = QComboBox()
        self.data_type_combo.currentTextChanged.connect(self._on_data_type_changed)
        controls_layout.addWidget(self.data_type_combo)

        # Frame navigation

        # Previous 10 frames button
        self.prev_frame_10_button = QPushButton("<<")
        self.prev_frame_10_button.clicked.connect(self._on_prev_frame_10)
        controls_layout.addWidget(self.prev_frame_10_button)

        # Previous frame button
        self.prev_frame_button = QPushButton("<")
        self.prev_frame_button.clicked.connect(self._on_prev_frame)
        controls_layout.addWidget(self.prev_frame_button)

        # Frame label
        self.frame_label = QLabel("Frame 0/0")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls_layout.addWidget(self.frame_label)

        # Next frame button
        self.next_frame_button = QPushButton(">")
        self.next_frame_button.clicked.connect(self._on_next_frame)
        controls_layout.addWidget(self.next_frame_button)

        # Next 10 frames button
        self.next_frame_10_button = QPushButton(">>")
        self.next_frame_10_button.clicked.connect(self._on_next_frame_10)
        controls_layout.addWidget(self.next_frame_10_button)

        image_layout.addLayout(controls_layout)

        # Image display
        self.canvas = MplCanvas(self, width=8, height=6, dpi=100)
        image_layout.addWidget(self.canvas, 1)

        layout.addWidget(image_group)

        # Initialize state
        self._current_frame_index = 0
        self._max_frame_index = 0
        self._positions_by_cell: dict[str, dict[int, tuple[float, float]]] = {}
        self._active_trace_id: str | None = None
        self._image_model: ImageCacheModel | None = None
        self._trace_selection: TraceSelectionModel | None = None

    def bind(self) -> None:
        # No additional bindings needed for this panel
        pass

    def set_models(
        self,
        image_model: ImageCacheModel,
        trace_selection: TraceSelectionModel,
    ) -> None:
        self._image_model = image_model
        self._trace_selection = trace_selection

        image_model.cacheReset.connect(self._refresh_data_types)
        image_model.dataTypeAdded.connect(self._on_data_type_added)
        image_model.currentFrameChanged.connect(self._on_frame_changed)
        image_model.frameBoundsChanged.connect(self._on_frame_bounds_changed)
        image_model.tracePositionsChanged.connect(self._on_trace_positions_changed)
        image_model.activeTraceChanged.connect(self._on_active_trace_changed)
        image_model.currentDataTypeChanged.connect(self._on_current_data_type)

        trace_selection.activeTraceChanged.connect(self._on_active_trace_changed)
        self._refresh_data_types()

    def set_active_trace(self, trace_id: str | None) -> None:
        self._active_trace_id = trace_id
        if self._image_model:
            self._image_model.set_active_trace(trace_id)
        self._update_image_display()

    # Event handlers -------------------------------------------------------
    def _on_data_type_changed(self, data_type: str) -> None:
        """Handle data type selection change."""
        if self._image_model:
            self._image_model.set_current_data_type(data_type)

    def _on_prev_frame(self) -> None:
        """Navigate to previous frame."""
        if self._current_frame_index > 0 and self._image_model:
            self._image_model.set_current_frame(self._current_frame_index - 1)
        self._update_frame_navigation()
        self._update_image_display()

    def _on_next_frame(self) -> None:
        """Navigate to next frame."""
        if self._current_frame_index < self._max_frame_index and self._image_model:
            self._image_model.set_current_frame(self._current_frame_index + 1)
        self._update_frame_navigation()
        self._update_image_display()

    def _on_prev_frame_10(self) -> None:
        """Navigate 10 frames backward."""
        if self._image_model:
            self._image_model.set_current_frame(self._current_frame_index - 10)
        self._update_frame_navigation()
        self._update_image_display()

    def _on_next_frame_10(self) -> None:
        """Navigate 10 frames forward."""
        if self._image_model:
            self._image_model.set_current_frame(self._current_frame_index + 10)
        self._update_frame_navigation()
        self._update_image_display()

    # Private methods -------------------------------------------------------
    def _update_frame_navigation(self) -> None:
        """Update frame navigation UI based on current frame index.

        Note: We intentionally do not call `setEnabled` here. Button
        behavior is driven by the current frame index and click handlers.
        """
        # Update frame label to reflect current position/limits
        self.frame_label.setText(
            f"Frame {self._current_frame_index}/{self._max_frame_index}"
        )

        # Optionally adjust button tooltips to communicate state to the user.
        # We avoid disabling buttons; handlers will ignore clicks outside valid ranges.
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

    def _update_image_display(self) -> None:
        """Update the image display with current data."""
        if not self._image_model:
            return
        image_data = self._image_model.image_for_current_type()
        if image_data is None:
            return

        # Display the current frame
        if image_data.ndim == 3:  # Time series
            if self._current_frame_index < image_data.shape[0]:
                frame = image_data[self._current_frame_index]
            else:
                frame = image_data[0]
        else:  # Single frame
            frame = image_data

        # Calculate min/max from entire image data for consistent scaling
        data_min, data_max = int(image_data.min()), int(image_data.max())

        # Display image using built-in method
        current_data_type = self._image_model.current_data_type()
        if current_data_type.startswith("seg"):
            # Segmentation data - use discrete colormap with consistent scaling
            self.canvas.plot_image(frame, cmap="viridis", vmin=data_min, vmax=data_max)
        else:
            # Fluorescence/phase contrast - use actual data range instead of hardcoded 0-255
            self.canvas.plot_image(frame, cmap="gray", vmin=data_min, vmax=data_max)

        # Add trace overlays if available
        if self._positions_by_cell and self._current_frame_index is not None:
            self._draw_trace_overlays()

        # Set title
        self.canvas.axes.set_title(
            f"{current_data_type} - Frame {self._current_frame_index}"
        )
        self.canvas.draw_idle()

    def _refresh_data_types(self) -> None:
        if not self._image_model:
            return
        types = self._image_model.available_types()
        self.data_type_combo.blockSignals(True)
        self.data_type_combo.clear()
        self.data_type_combo.addItems(types)
        if types:
            current = self._image_model.current_data_type()
            if current:
                self.data_type_combo.setCurrentText(current)
        self.data_type_combo.blockSignals(False)
        self._on_frame_bounds_changed(*self._image_model.frame_bounds())
        self._positions_by_cell = self._image_model.trace_positions()
        self._active_trace_id = self._image_model.active_trace_id()
        self._update_image_display()

    def _on_data_type_added(self, data_type: str) -> None:
        if self.data_type_combo.findText(data_type) == -1:
            self.data_type_combo.addItem(data_type)

    def _on_frame_changed(self, frame: int) -> None:
        self._current_frame_index = frame
        self._update_frame_navigation()
        self._update_image_display()

    def _on_frame_bounds_changed(self, current: int, max_frame: int) -> None:
        self._current_frame_index = current
        self._max_frame_index = max_frame
        self._update_frame_navigation()

    def _on_trace_positions_changed(
        self, positions: dict[str, dict[int, tuple[float, float]]]
    ) -> None:
        self._positions_by_cell = positions
        self._update_image_display()

    def _on_active_trace_changed(self, trace_id: str | None) -> None:
        self._active_trace_id = trace_id
        self._update_image_display()

    def _on_current_data_type(self, data_type: str) -> None:
        if data_type and self.data_type_combo.currentText() != data_type:
            index = self.data_type_combo.findText(data_type)
            if index >= 0:
                self.data_type_combo.blockSignals(True)
                self.data_type_combo.setCurrentIndex(index)
                self.data_type_combo.blockSignals(False)
        self._update_image_display()

    def _draw_trace_overlays(self) -> None:
        """Draw trace position overlays on the image."""
        if not self._positions_by_cell or not self._active_trace_id:
            self.canvas.clear_overlays()
            return

        # Only show the active trace
        if self._active_trace_id in self._positions_by_cell:
            positions = self._positions_by_cell[self._active_trace_id]

            # Debug: print available frames for this trace
            print(
                f"Available frames for trace {self._active_trace_id}: {list(positions.keys())}"
            )
            print(f"Current frame: {self._current_frame_index}")

            if self._current_frame_index in positions:
                # Positions are stored as (x, y) from CSV
                pos_x, pos_y = positions[self._current_frame_index]

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
                print(
                    f"Drawing overlay at ({pos_x}, {pos_y}) for frame {self._current_frame_index}"
                )
            else:
                print(f"No position data for frame {self._current_frame_index}")
                self.canvas.clear_overlays()
        else:
            print(f"No active trace or positions data")
            self.canvas.clear_overlays()
