"""
Image viewer widget for displaying microscopy images and processing results.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
import numpy as np
import logging

 
 


class ImageViewer(QWidget):
    """Widget for viewing microscopy images and processing results."""
    
    def __init__(self):
        super().__init__()
        self.current_project = None
        self.current_images = {}  # {data_type: np.ndarray} - shared cache owned by main window
        self.stack_min = 0
        self.stack_max = 1
        self.current_frame_index = 0
        self.max_frame_index = 0
        self._current_fov = None  # Hidden state to store current FOV
        self.logger = logging.getLogger(__name__)
        
        # Note: Worker and thread are managed by the main window
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Controls group
        controls_group = QGroupBox("Image Viewer Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        # Data type selection
        controls_layout.addStretch()
        controls_layout.addWidget(QLabel("Data Type:"))
        self.data_type_combo = QComboBox()
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        controls_layout.addWidget(self.data_type_combo)
        
        # Frame navigation with improved layout
        controls_layout.addStretch()
        
        # Previous 10 frames button
        self.prev_frame_10_button = QPushButton("<<")
        self.prev_frame_10_button.clicked.connect(self.on_prev_frame_10)
        controls_layout.addWidget(self.prev_frame_10_button)
        
        # Previous frame button
        self.prev_frame_button = QPushButton("<")
        self.prev_frame_button.clicked.connect(self.on_prev_frame)
        controls_layout.addWidget(self.prev_frame_button)
        
        # Frame label
        self.frame_label = QLabel("Frame 0/0")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls_layout.addWidget(self.frame_label)
        
        # Next frame button
        self.next_frame_button = QPushButton(">")
        self.next_frame_button.clicked.connect(self.on_next_frame)
        controls_layout.addWidget(self.next_frame_button)
        
        # Next 10 frames button
        self.next_frame_10_button = QPushButton(">>")
        self.next_frame_10_button.clicked.connect(self.on_next_frame_10)
        controls_layout.addWidget(self.next_frame_10_button)
        
        controls_layout.addStretch()
        
        # Store current frame index
        self.current_frame_index = 0
        
        layout.addWidget(controls_group)

        # Image display area
        image_group = QGroupBox("Image Display")
        image_layout = QVBoxLayout(image_group)
        
        # Scroll area for image
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setText("No image loaded")
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setStyleSheet("border: 1px solid gray;")
        
        scroll_area.setWidget(self.image_label)
        image_layout.addWidget(scroll_area)
        
        # Image info table
        self.image_info_table = QTableWidget(2, 4)  # 2 rows, 4 columns

        # Make read-only
        self.image_info_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Hide column and row headers
        self.image_info_table.horizontalHeader().setVisible(False)
        self.image_info_table.verticalHeader().setVisible(False)

        # Evenly distribute width
        self.image_info_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Limit the height
        self.image_info_table.setMaximumHeight(64)
        image_layout.addWidget(self.image_info_table)
        
        layout.addWidget(image_group)
        
        # Initially disable everything until project is loaded
        self.setEnabled(False)
        
    def load_project(self, project_data: dict):
        """
        Load project data and populate controls.
        
        Args:
            project_data: Project data dictionary
        """
        self.current_project = project_data
        # Do not replace current_images; it's a shared cache reference set by main window
        
        # Don't enable the viewer here - it should only be enabled after FOV data is preloaded
        # has_image_data = False
        # for fov_data in project_data['fov_data'].values():
        #     image_types = [k for k in fov_data.keys() if k != 'traces']
        #     if image_types:
        #         has_image_data = True
        #         break
        #
        # self.setEnabled(has_image_data)
             
    def load_fov_data(self, project_data: dict, fov_idx: int):
        """
        Load data for a specific FOV asynchronously.
        
        Args:
            project_data: Project data dictionary
            fov_idx: Index of the FOV to load
        """
        self.current_project = project_data
        
        # Set current FOV
        self._current_fov = fov_idx
        
        # Show progress bar and disable controls during loading
        self.data_type_combo.setEnabled(False)
        # Gray out the entire viewer until preprocessing completes
        self.setEnabled(False)
        
        # Thread and worker are created and started by the main window
        
    def _on_progress_updated(self, message: str):
        """Handle progress updates from the worker."""
        # Progress bar is handled in the project loader panel
        
    def _on_fov_data_loaded(self, fov_idx: int):
        """Handle FOV data loaded notification (shared cache has been updated)."""
        
        # Enable the viewer now that data is ready
        self.setEnabled(True)

        # Clear and populate data type combo with available image types for this FOV only
        self.data_type_combo.clear()
        
        if fov_idx in self.current_project['fov_data']:
            fov_data = self.current_project['fov_data'][fov_idx]
            image_types = [k for k in fov_data.keys() if k != 'traces']
            
            for data_type in sorted(image_types):
                display_name = data_type.replace('_', ' ').title()
                self.data_type_combo.addItem(display_name, data_type)
            
            # Enable controls
            self.data_type_combo.setEnabled(True)
        else:
            self.data_type_combo.addItem("No data for this FOV")
            self.data_type_combo.setEnabled(False)
            
        # Progress bar handled elsewhere
        
        # If there's a default data type, select it and update display
        if self.data_type_combo.count() > 0 and self.data_type_combo.itemData(0) is not None:
            self.data_type_combo.setCurrentIndex(0)
            self.on_data_type_changed()
            
    def _on_worker_finished(self):
        """Handle worker finished signal."""
        # Other UI updates are handled elsewhere
        
    def _on_worker_error(self, error_message: str):
        """Handle worker error signal."""
        self.logger.error(f"Error during preprocessing: {error_message}")
        # Enable the viewer to allow user interaction despite the error
        self.setEnabled(True)
        self.data_type_combo.setEnabled(True)
        self.image_label.setText(f"Error loading data: {error_message}")
        
    def on_data_type_changed(self):
        """Handle data type selection change."""
        if not self.current_project or self._current_fov is None:
            return
            
        fov_idx = self._current_fov
        data_type = self.data_type_combo.currentData()
        
        if fov_idx is None or data_type is None:
            return
            
        # Use preloaded image data
        if data_type not in self.current_images:
            self.logger.error(f"Data not preloaded for FOV {fov_idx}, data type {data_type}")
            self.image_label.setText(f"Error: Data not preloaded for {data_type}")
            return
                
        # Get image data from preloaded cache (shared cache stores current FOV only)
        image_data = self.current_images[data_type]
        
        # For preprocessed data, min/max are fixed (0-255 for uint8)
        self.stack_min = 0
        self.stack_max = 255

        # Update frame navigation
        n_frames = image_data.shape[0] if len(image_data.shape) > 2 else 1
        self.max_frame_index = max(0, n_frames - 1)
        
        # Update display
        self.update_frame_navigation()
        self.update_image_display()
            
    def update_image_display(self):
        """Update the image display."""
        if self._current_fov is None:
            return
            
        fov_idx = self._current_fov
        data_type = self.data_type_combo.currentData()
        
        if fov_idx is None or data_type is None:
            return
            
        if data_type not in self.current_images:
            return
            
        image_data = self.current_images[data_type]
        frame_idx = self.current_frame_index
        
        # Extract frame
        if len(image_data.shape) > 2:
            frame = image_data[frame_idx]
            self.frame_label.setText(f"Frame {frame_idx + 1}/{image_data.shape[0]}")
        else:
            frame = image_data
            self.frame_label.setText("Frame 1/1")
            
        # Convert to displayable format
        qimage = self.numpy_to_qimage(frame)
        pixmap = QPixmap.fromImage(qimage)
        
        # Scale to fit while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.image_label.setPixmap(scaled_pixmap)
        
        # Update image info table
        # First row: property names
        self.image_info_table.setItem(0, 0, QTableWidgetItem("Data Type"))
        self.image_info_table.setItem(0, 1, QTableWidgetItem("Dimensions"))
        self.image_info_table.setItem(0, 2, QTableWidgetItem("Array Data Type"))
        self.image_info_table.setItem(0, 3, QTableWidgetItem("Min/Max"))
        
        # Second row: values
        self.image_info_table.setItem(1, 0, QTableWidgetItem(data_type))
        self.image_info_table.setItem(1, 1, QTableWidgetItem(str(frame.shape)))
        self.image_info_table.setItem(1, 2, QTableWidgetItem(str(frame.dtype)))
        # For preprocessed data, min/max are fixed (0-255 for uint8)
        self.image_info_table.setItem(1, 3, QTableWidgetItem("0 / 255"))
            
    def on_prev_frame(self):
        """Handle previous frame button click."""
        if self.current_frame_index > 0:
            self.current_frame_index -= 1
            self.update_frame_navigation()
            self.update_image_display()
            
    def on_next_frame(self):
        """Handle next frame button click."""
        if self.current_frame_index < self.max_frame_index:
            self.current_frame_index += 1
            self.update_frame_navigation()
            self.update_image_display()
            
    def on_prev_frame_10(self):
        """Handle previous 10 frames button click."""
        new_index = max(0, self.current_frame_index - 10)
        if new_index != self.current_frame_index:
            self.current_frame_index = new_index
            self.update_frame_navigation()
            self.update_image_display()
            
    def on_next_frame_10(self):
        """Handle next 10 frames button click."""
        new_index = min(self.max_frame_index, self.current_frame_index + 10)
        if new_index != self.current_frame_index:
            self.current_frame_index = new_index
            self.update_frame_navigation()
            self.update_image_display()
            
    def update_frame_navigation(self):
        """Update frame navigation UI based on current frame index."""
        # Update button states
        self.prev_frame_10_button.setEnabled(self.current_frame_index > 0)
        self.prev_frame_button.setEnabled(self.current_frame_index > 0)
        self.next_frame_button.setEnabled(self.current_frame_index < self.max_frame_index)
        self.next_frame_10_button.setEnabled(self.current_frame_index < self.max_frame_index)
        
        # Update frame label
        total_frames = self.max_frame_index + 1
        self.frame_label.setText(f"Frame {self.current_frame_index + 1}/{total_frames}")
        
    def numpy_to_qimage(self, array: np.ndarray) -> QImage:
        """
        Convert numpy array to QImage for display.
        Array is expected to be preprocessed and normalized to uint8.
        
        Args:
            array: Input numpy array (uint8)
            
        Returns:
            QImage for display
        """
        # Array is expected to be preprocessed and normalized to uint8
        # Create QImage directly from uint8 data
        height, width = array.shape
        bytes_per_line = width
        
        qimage = QImage(
            array.data.tobytes(),
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_Grayscale8
        )
        
        return qimage
