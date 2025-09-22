"""Image viewer panel for displaying microscopy images and processing results."""

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
from pyama_qt.visualization.state import VisualizationState
from pyama_qt.ui import BasePanel

logger = logging.getLogger(__name__)


class ImagePanel(BasePanel[VisualizationState]):
    """Panel for viewing microscopy images and processing results."""

    def build(self) -> None:
        layout = QVBoxLayout(self)

        # Controls group
        controls_group = QGroupBox("Image Viewer Controls")
        controls_layout = QHBoxLayout(controls_group)

        # Data type selection
        controls_layout.addStretch()
        controls_layout.addWidget(QLabel("Data Type:"))
        self.data_type_combo = QComboBox()
        self.data_type_combo.currentTextChanged.connect(self._on_data_type_changed)
        controls_layout.addWidget(self.data_type_combo)

        # Frame navigation
        controls_layout.addStretch()

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

        controls_layout.addStretch()
        layout.addWidget(controls_group)

        # Image display
        self.canvas = MplCanvas(self, width=8, height=6, dpi=100)
        layout.addWidget(self.canvas, 1)

        # Initialize state
        self._current_frame_index = 0
        self._max_frame_index = 0
        self._positions_by_cell = {}
        self._active_trace_id = None
        self._is_first_plot = True

    def bind(self) -> None:
        # No additional bindings needed for this panel
        pass

    def set_state(self, state: VisualizationState) -> None:
        super().set_state(state)
        
        if not state:
            return

        # Update data type combo
        if state.image_cache:
            available_types = list(state.image_cache.keys())
            current_items = [self.data_type_combo.itemText(i) for i in range(self.data_type_combo.count())]
            
            if available_types != current_items:
                self.data_type_combo.blockSignals(True)
                self.data_type_combo.clear()
                self.data_type_combo.addItems(available_types)
                
                # Set current data type if available
                if state.current_data_type in available_types:
                    self.data_type_combo.setCurrentText(state.current_data_type)
                elif available_types:
                    self.data_type_combo.setCurrentText(available_types[0])
                
                self.data_type_combo.blockSignals(False)

        # Update frame navigation
        self._current_frame_index = state.current_frame_index
        self._max_frame_index = state.max_frame_index
        self._update_frame_navigation()

        # Update trace overlay data
        self._positions_by_cell = state.trace_positions
        self._active_trace_id = state.active_trace_id

        # Update image display
        self._update_image_display()

    def set_active_trace(self, trace_id: str | None) -> None:
        """Set the active trace ID for highlighting."""
        self._active_trace_id = trace_id
        self._update_image_display()

    # Event handlers -------------------------------------------------------
    def _on_data_type_changed(self, data_type: str) -> None:
        """Handle data type selection change."""
        if self._state:
            # Update state through controller would be ideal, but for now update directly
            self._state.current_data_type = data_type
            self._update_image_display()

    def _on_prev_frame(self) -> None:
        """Navigate to previous frame."""
        if self._current_frame_index > 0:
            self._current_frame_index -= 1
            if self._state:
                self._state.current_frame_index = self._current_frame_index
            self._update_frame_navigation()
            self._update_image_display()

    def _on_next_frame(self) -> None:
        """Navigate to next frame."""
        if self._current_frame_index < self._max_frame_index:
            self._current_frame_index += 1
            if self._state:
                self._state.current_frame_index = self._current_frame_index
            self._update_frame_navigation()
            self._update_image_display()

    def _on_prev_frame_10(self) -> None:
        """Navigate 10 frames backward."""
        self._current_frame_index = max(0, self._current_frame_index - 10)
        if self._state:
            self._state.current_frame_index = self._current_frame_index
        self._update_frame_navigation()
        self._update_image_display()

    def _on_next_frame_10(self) -> None:
        """Navigate 10 frames forward."""
        self._current_frame_index = min(self._max_frame_index, self._current_frame_index + 10)
        if self._state:
            self._state.current_frame_index = self._current_frame_index
        self._update_frame_navigation()
        self._update_image_display()

    # Private methods -------------------------------------------------------
    def _update_frame_navigation(self) -> None:
        """Update frame navigation UI based on current frame index."""
        self.prev_frame_10_button.setEnabled(self._current_frame_index > 0)
        self.prev_frame_button.setEnabled(self._current_frame_index > 0)
        self.next_frame_button.setEnabled(self._current_frame_index < self._max_frame_index)
        self.next_frame_10_button.setEnabled(self._current_frame_index < self._max_frame_index)
        
        self.frame_label.setText(f"Frame {self._current_frame_index}/{self._max_frame_index}")

    def _update_image_display(self) -> None:
        """Update the image display with current data."""
        if not self._state or not self._state.image_cache:
            return

        current_data_type = self._state.current_data_type
        if current_data_type not in self._state.image_cache:
            return

        image_data = self._state.image_cache[current_data_type]
        if image_data is None:
            return

        # Clear the plot
        self.canvas.axes.clear()

        # Display the current frame
        if image_data.ndim == 3:  # Time series
            if self._current_frame_index < image_data.shape[0]:
                frame = image_data[self._current_frame_index]
            else:
                frame = image_data[0]
        else:  # Single frame
            frame = image_data

        # Display image
        if current_data_type.startswith("seg"):
            # Segmentation data - use discrete colormap
            im = self.canvas.axes.imshow(frame, cmap='tab20', interpolation='nearest')
        else:
            # Fluorescence/phase contrast - use grayscale
            im = self.canvas.axes.imshow(frame, cmap='gray', interpolation='nearest')

        # Add trace overlays if available
        if self._positions_by_cell and self._current_frame_index is not None:
            self._draw_trace_overlays()

        self.canvas.axes.set_title(f"{current_data_type} - Frame {self._current_frame_index}")
        self.canvas.axes.axis('off')
        self.canvas.draw()

    def _draw_trace_overlays(self) -> None:
        """Draw trace position overlays on the image."""
        if not self._positions_by_cell:
            return

        for cell_id, positions in self._positions_by_cell.items():
            if self._current_frame_index in positions:
                y, x = positions[self._current_frame_index]
                
                # Highlight active trace differently
                if cell_id == self._active_trace_id:
                    self.canvas.axes.plot(x, y, 'ro', markersize=8, markeredgewidth=2, 
                                        markeredgecolor='white', alpha=0.8)
                else:
                    self.canvas.axes.plot(x, y, 'yo', markersize=6, alpha=0.7)
