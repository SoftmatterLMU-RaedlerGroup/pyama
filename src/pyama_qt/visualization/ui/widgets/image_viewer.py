"""
Image viewer widget for displaying microscopy images and processing results.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, 
    QComboBox, QPushButton, QCheckBox, QSpinBox, QSlider,
    QScrollArea, QSplitter
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
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Controls group
        controls_group = QGroupBox("Image Viewer Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        # FOV selection
        controls_layout.addWidget(QLabel("FOV:"))
        self.fov_combo = QComboBox()
        self.fov_combo.currentTextChanged.connect(self.on_fov_changed)
        controls_layout.addWidget(self.fov_combo)
        
        controls_layout.addStretch()
        
        # Data type selection
        controls_layout.addWidget(QLabel("Data Type:"))
        self.data_type_combo = QComboBox()
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        controls_layout.addWidget(self.data_type_combo)
        
        controls_layout.addStretch()
        
        # Frame selection
        controls_layout.addWidget(QLabel("Frame:"))
        self.frame_slider = QSlider(Qt.Horizontal)
        self.frame_slider.setMinimum(0)
        self.frame_slider.setMaximum(0)
        self.frame_slider.valueChanged.connect(self.on_frame_changed)
        controls_layout.addWidget(self.frame_slider)
        
        self.frame_label = QLabel("0/0")
        controls_layout.addWidget(self.frame_label)
        
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
        
        # Image info
        self.image_info_label = QLabel("Image info will appear here")
        image_layout.addWidget(self.image_info_label)
        
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
        
        # Populate FOV combo
        self.fov_combo.clear()
        fov_indices = []
        
        for fov_idx, fov_data in project_data['fov_data'].items():
            # Check if FOV has any image data
            image_types = [k for k in fov_data.keys() if k != 'traces']
            if image_types:
                fov_indices.append(fov_idx)
                
        if fov_indices:
            for fov_idx in sorted(fov_indices):
                self.fov_combo.addItem(f"FOV {fov_idx:04d}", fov_idx)
            self.setEnabled(True)
        else:
            self.fov_combo.addItem("No image data found")
            self.setEnabled(False)
            
    def on_fov_changed(self):
        """Handle FOV selection change."""
        if not self.current_project:
            return
            
        fov_idx = self.fov_combo.currentData()
        if fov_idx is None:
            return
            
        # Populate data type combo with available image types
        self.data_type_combo.clear()
        
        fov_data = self.current_project['fov_data'][fov_idx]
        image_types = [k for k in fov_data.keys() if k != 'traces']
        
        for data_type in sorted(image_types):
            display_name = data_type.replace('_', ' ').title()
            self.data_type_combo.addItem(display_name, data_type)
            
    def on_data_type_changed(self):
        """Handle data type selection change."""
        if not self.current_project:
            return
            
        fov_idx = self.fov_combo.currentData()
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

            # Update frame slider
            n_frames = image_data.shape[0] if len(image_data.shape) > 2 else 1
            self.frame_slider.setMaximum(max(0, n_frames - 1))
            self.frame_slider.setValue(0)
            
            # Update display
            self.update_image_display()
            
        except Exception as e:
            print(f"Error loading image data: {e}")
            self.image_label.setText(f"Error loading image: {e}")
            
    def on_frame_changed(self):
        """Handle frame slider change."""
        self.update_image_display()
        
    def update_image_display(self):
        """Update the image display."""
        fov_idx = self.fov_combo.currentData()
        data_type = self.data_type_combo.currentData()
        
        if fov_idx is None or data_type is None:
            return
            
        key = (fov_idx, data_type)
        if key not in self.current_images:
            return
            
        image_data = self.current_images[key]
        frame_idx = self.frame_slider.value()
        
        # Extract frame
        if len(image_data.shape) > 2:
            frame = image_data[frame_idx]
            self.frame_label.setText(f"{frame_idx + 1}/{image_data.shape[0]}")
        else:
            frame = image_data
            self.frame_label.setText("1/1")
            
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
        
        # Update image info
        info_text = (
            f"Data Type: {data_type}\\n"
            f"Dimensions: {frame.shape}\\n"
            f"Data Type: {frame.dtype}\\n"
            f"Min/Max: {frame.min():.2f} / {frame.max():.2f}"
        )
        self.image_info_label.setText(info_text)
        
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
