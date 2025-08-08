"""
Image viewer widget for displaying microscopy images and processing results.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QPushButton, QCheckBox, QSpinBox, QSlider,
    QScrollArea, QSplitter, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage
import numpy as np
from pathlib import Path

from ....core.data_loading import load_image_data


class ImageViewer(QWidget):
    """Widget for viewing microscopy images and processing results."""
    
    def __init__(self):
        super().__init__()
        self.current_project = None
        self.current_images = {}  # {(fov_idx, data_type): np.ndarray}
        self.stack_min = 0
        self.stack_max = 1
        self.current_frame_index = 0
        self.max_frame_index = 0
        self._current_fov = None  # Hidden state to store current FOV
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
        self.frame_label.setAlignment(Qt.AlignCenter)
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
        scroll_area.setAlignment(Qt.AlignCenter)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText("No image loaded")
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setStyleSheet("border: 1px solid gray;")
        
        scroll_area.setWidget(self.image_label)
        image_layout.addWidget(scroll_area)
        
        # Image info table
        self.image_info_table = QTableWidget(2, 4)  # 2 rows, 4 columns
        self.image_info_table.setEditTriggers(QTableWidget.NoEditTriggers)  # Make read-only
        self.image_info_table.horizontalHeader().hide()  # Hide column headers
        self.image_info_table.verticalHeader().hide()  # Hide row headers
        self.image_info_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # Evenly distribute width
        self.image_info_table.setMaximumHeight(64)  # Limit the height
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
        self.current_images = {}
        
        # Enable the viewer if project has image data
        has_image_data = False
        for fov_data in project_data['fov_data'].values():
            image_types = [k for k in fov_data.keys() if k != 'traces']
            if image_types:
                has_image_data = True
                break
                
        self.setEnabled(has_image_data)
            
    def load_fov_data(self, project_data: dict, fov_idx: int):
        """
        Load data for a specific FOV.
        
        Args:
            project_data: Project data dictionary
            fov_idx: Index of the FOV to load
        """
        self.current_project = project_data
        self.current_images = {}
        
        # Set current FOV
        self._current_fov = fov_idx
        
        # Clear and populate data type combo with available image types for this FOV only
        self.data_type_combo.clear()
        
        if fov_idx in project_data['fov_data']:
            fov_data = project_data['fov_data'][fov_idx]
            image_types = [k for k in fov_data.keys() if k != 'traces']
            
            for data_type in sorted(image_types):
                display_name = data_type.replace('_', ' ').title()
                self.data_type_combo.addItem(display_name, data_type)
            
            # Enable the viewer and other controls
            self.setEnabled(True)
        else:
            self.data_type_combo.addItem("No data for this FOV")
            self.setEnabled(False)
            
    def on_data_type_changed(self):
        """Handle data type selection change."""
        if not self.current_project or self._current_fov is None:
            return
            
        fov_idx = self._current_fov
        data_type = self.data_type_combo.currentData()
        
        if fov_idx is None or data_type is None:
            return
            
        # Load image data
        try:
            fov_data = self.current_project['fov_data'][fov_idx]
            image_path = fov_data[data_type]
            
            image_data = load_image_data(image_path)
            self.current_images[(fov_idx, data_type)] = image_data
            
            # Calculate stack-wide min/max for normalization
            self.stack_min = image_data.min()
            self.stack_max = image_data.max()

            # Update frame navigation
            n_frames = image_data.shape[0] if len(image_data.shape) > 2 else 1
            self.max_frame_index = max(0, n_frames - 1)
            
            # Update display
            self.update_frame_navigation()
            self.update_image_display()
            
        except Exception as e:
            print(f"Error loading image data: {e}")
            self.image_label.setText(f"Error loading image: {e}")
            
    def update_image_display(self):
        """Update the image display."""
        if self._current_fov is None:
            return
            
        fov_idx = self._current_fov
        data_type = self.data_type_combo.currentData()
        
        if fov_idx is None or data_type is None:
            return
            
        key = (fov_idx, data_type)
        if key not in self.current_images:
            return
            
        image_data = self.current_images[key]
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
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
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
        self.image_info_table.setItem(1, 3, QTableWidgetItem(f"{frame.min():.2f} / {frame.max():.2f}"))
            
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
        
        Args:
            array: Input numpy array
            
        Returns:
            QImage for display
        """
        # Handle different data types
        if array.dtype == np.bool_ or array.dtype == bool:
            # Binary image
            array = (array * 255).astype(np.uint8)
        elif array.dtype == np.float32 or array.dtype == np.float64:
            # Normalize float data to 0-255 using stack-wide min/max
            if self.stack_max > self.stack_min:
                array = ((array - self.stack_min) / (self.stack_max - self.stack_min) * 255).astype(np.uint8)
            else:
                array = np.zeros_like(array, dtype=np.uint8)
        elif array.dtype == np.uint16:
            # Scale 16-bit to 8-bit
            array = (array >> 8).astype(np.uint8)
        elif array.dtype != np.uint8:
            # Convert other types to uint8
            array = array.astype(np.uint8)
            
        # Create QImage
        height, width = array.shape
        bytes_per_line = width
        
        qimage = QImage(
            array.data.tobytes(),
            width,
            height,
            bytes_per_line,
            QImage.Format_Grayscale8
        )
        
        return qimage
