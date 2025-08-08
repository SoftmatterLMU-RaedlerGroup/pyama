"""
Image viewer widget for displaying microscopy images and processing results.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QPushButton, QCheckBox, QSpinBox, QSlider,
    QScrollArea, QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPixmap, QImage
import numpy as np
from pathlib import Path
import logging

from ....core.data_loading import load_image_data
from .preprocessing_worker import PreprocessingWorker


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
        self.logger = logging.getLogger(__name__)
        
        # Worker and thread for async processing
        self.worker = None
        self.thread = None
        
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
        
        # Progress bar for preprocessing
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        layout.addWidget(self.progress_bar)
        
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
        self.progress_bar.setVisible(False)
        
    def load_project(self, project_data: dict):
        """
        Load project data and populate controls.
        
        Args:
            project_data: Project data dictionary
        """
        self.current_project = project_data
        self.current_images = {}
        
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
        # Clean up any existing worker
        self._cleanup_worker()
        
        self.current_project = project_data
        self.current_images = {}
        
        # Set current FOV
        self._current_fov = fov_idx
        
        # Show progress bar and disable controls during loading
        self.progress_bar.setVisible(True)
        self.progress_bar.setFormat(f"Loading FOV {fov_idx:04d}...")
        self.data_type_combo.setEnabled(False)
        self.setEnabled(True)  # Enable the widget to show the progress bar
        
        # Create and start worker thread
        self.thread = QThread()
        self.worker = PreprocessingWorker(project_data, fov_idx)
        self.worker.moveToThread(self.thread)
        
        # Connect signals
        self.thread.started.connect(self.worker.process_fov_data)
        self.worker.progress_updated.connect(self._on_progress_updated)
        self.worker.fov_data_loaded.connect(self._on_fov_data_loaded)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error_occurred.connect(self._on_worker_error)
        
        # Start the thread
        self.thread.start()
        
    def _on_progress_updated(self, message: str):
        """Handle progress updates from the worker."""
        self.progress_bar.setFormat(message)
        
    def _on_fov_data_loaded(self, result: dict):
        """Handle FOV data loaded from the worker."""
        fov_idx = result['fov_idx']
        self.current_images = result['images']
        
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
            
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # If there's a default data type, select it and update display
        if self.data_type_combo.count() > 0 and self.data_type_combo.itemData(0) is not None:
            self.data_type_combo.setCurrentIndex(0)
            self.on_data_type_changed()
            
    def _on_worker_finished(self):
        """Handle worker finished signal."""
        self._cleanup_worker()
        
    def _on_worker_error(self, error_message: str):
        """Handle worker error signal."""
        self.logger.error(f"Error during preprocessing: {error_message}")
        self.progress_bar.setVisible(False)
        self.data_type_combo.setEnabled(True)
        self.image_label.setText(f"Error loading data: {error_message}")
        self._cleanup_worker()
        
    def _cleanup_worker(self):
        """Clean up worker and thread."""
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
            
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait()
            self.thread.deleteLater()
            self.thread = None
            
    def _preload_fov_data(self, project_data: dict, fov_idx: int):
        """
        Preload all image data for a specific FOV using memory mapping for better performance.
        Data is preprocessed and normalized to uint8 for visualization.
        
        Args:
            project_data: Project data dictionary
            fov_idx: Index of the FOV to preload
        """
        if fov_idx not in project_data['fov_data']:
            return
            
        fov_data = project_data['fov_data'][fov_idx]
        image_types = [k for k in fov_data.keys() if k != 'traces']
        
        self.logger.info(f"Preloading {len(image_types)} data types for FOV {fov_idx}")
        
        # Load and preprocess all image data
        for data_type in image_types:
            try:
                image_path = fov_data[data_type]
                # Use memory mapping for efficient loading of large files
                if image_path.suffix.lower() == '.npy':
                    image_data = load_image_data(image_path, mmap_mode='r')
                elif image_path.suffix.lower() == '.npz':
                    # For NPZ files, we still need to load the data but can do it once
                    image_data = load_image_data(image_path)
                else:
                    # For other formats, use the existing loader
                    image_data = load_image_data(image_path)
                
                # Preprocess data for visualization (normalize to uint8)
                processed_data = self._preprocess_for_visualization(image_data, data_type)
                
                self.current_images[(fov_idx, data_type)] = processed_data
                self.logger.info(f"Preloaded and processed {data_type} data: shape {processed_data.shape}, dtype {processed_data.dtype}")
                
            except Exception as e:
                self.logger.error(f"Error preloading {data_type} data for FOV {fov_idx}: {e}")
                # Continue with other data types even if one fails
                continue
                
        self.logger.info(f"Completed preloading data for FOV {fov_idx}")
        
    def _preprocess_for_visualization(self, image_data: np.ndarray, data_type: str) -> np.ndarray:
        """
        Preprocess image data for visualization by normalizing to int8.
        
        Args:
            image_data: Input image data
            data_type: Type of data (for special handling)
            
        Returns:
            Preprocessed image data as int8
        """
        # Handle different data types
        if image_data.dtype == np.bool_ or image_data.dtype == bool or 'binarized' in data_type:
            # Binary image - convert to uint8 directly
            return (image_data * 255).astype(np.uint8)
        else:
            # For other data types, normalize to uint8
            # Calculate min/max for normalization
            data_min = np.nanmin(image_data)
            data_max = np.nanmax(image_data)
            
            # Avoid division by zero
            if data_max > data_min:
                # Normalize to 0-255 range
                normalized = ((image_data - data_min) / (data_max - data_min) * 255).astype(np.uint8)
            else:
                normalized = np.zeros_like(image_data, dtype=np.uint8)
                
            return normalized
            
    def on_data_type_changed(self):
        """Handle data type selection change."""
        if not self.current_project or self._current_fov is None:
            return
            
        fov_idx = self._current_fov
        data_type = self.data_type_combo.currentData()
        
        if fov_idx is None or data_type is None:
            return
            
        # Use preloaded image data
        key = (fov_idx, data_type)
        if key not in self.current_images:
            self.logger.error(f"Data not preloaded for FOV {fov_idx}, data type {data_type}")
            self.image_label.setText(f"Error: Data not preloaded for {data_type}")
            return
                
        # Get image data from preloaded cache
        image_data = self.current_images[key]
        
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
            QImage.Format_Grayscale8
        )
        
        return qimage
