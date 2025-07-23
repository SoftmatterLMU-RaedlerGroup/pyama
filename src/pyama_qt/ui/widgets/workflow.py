from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLabel, QLineEdit, 
                             QFileDialog, QTextEdit, QProgressBar, QFrame)
from PySide6.QtCore import Signal, Qt


class Workflow(QWidget):
    process_requested = Signal(dict)
    
    def __init__(self):
        super().__init__()
        self.data_info = None
        self.signal_lights = {}
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Workflow steps
        self.setup_workflow_steps(layout)
        
        # Output section
        self.setup_output_section(layout)
        
        # Processing section
        self.setup_processing_section(layout)
        
        # Stretch to push everything to top
        layout.addStretch()
        
        
    def setup_workflow_steps(self, layout):
        """Set up the main workflow steps"""
        workflow_group = QGroupBox("Processing Workflow")
        workflow_layout = QVBoxLayout(workflow_group)
        
        # Step 1: Segmentation (Binarization)  
        step1_layout = QHBoxLayout()
        self.signal_lights['segmentation'] = self.create_signal_light()
        step1_label = QLabel("Step 1: Segmentation (Binarization)")
        step1_layout.addWidget(self.signal_lights['segmentation'])
        step1_layout.addWidget(step1_label)
        step1_layout.addStretch()
        workflow_layout.addLayout(step1_layout)
        
        # Separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.HLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        workflow_layout.addWidget(separator1)
        
        # Step 2: Background Correction
        step2_layout = QHBoxLayout()
        self.signal_lights['background_correction'] = self.create_signal_light()
        step2_label = QLabel("Step 2: Background Correction")
        step2_layout.addWidget(self.signal_lights['background_correction'])
        step2_layout.addWidget(step2_label)
        step2_layout.addStretch()
        workflow_layout.addLayout(step2_layout)
        
        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        workflow_layout.addWidget(separator2)
        
        # Step 3: Tracking
        step3_layout = QHBoxLayout()
        self.signal_lights['tracking'] = self.create_signal_light()
        step3_label = QLabel("Step 3: Cell Tracking")
        step3_layout.addWidget(self.signal_lights['tracking'])
        step3_layout.addWidget(step3_label)
        step3_layout.addStretch()
        workflow_layout.addLayout(step3_layout)
        
        # Separator
        separator3 = QFrame()
        separator3.setFrameShape(QFrame.Shape.HLine)
        separator3.setFrameShadow(QFrame.Shadow.Sunken)
        workflow_layout.addWidget(separator3)
        
        # Step 4: Pickle Bounding Box
        step4_layout = QHBoxLayout()
        self.signal_lights['bounding_box'] = self.create_signal_light()
        step4_label = QLabel("Step 4: Pickle Maximum Bounding Box")
        step4_layout.addWidget(self.signal_lights['bounding_box'])
        step4_layout.addWidget(step4_label)
        step4_layout.addStretch()
        workflow_layout.addLayout(step4_layout)
        
        layout.addWidget(workflow_group)
        
        
    def setup_output_section(self, layout):
        """Set up output settings section"""
        output_group = QGroupBox("Output Settings")
        output_layout = QVBoxLayout(output_group)
        
        # Base output directory
        dir_layout = QHBoxLayout()
        self.output_dir = QLineEdit()
        self.output_dir.setPlaceholderText("Select output directory...")
        self.output_dir_button = QPushButton("Browse...")
        self.output_dir_button.clicked.connect(self.select_output_directory)
        
        dir_layout.addWidget(QLabel("Output Directory:"))
        dir_layout.addWidget(self.output_dir, 1)
        dir_layout.addWidget(self.output_dir_button)
        output_layout.addLayout(dir_layout)
        
        # File naming info
        naming_info = QLabel("Output files will use ND2 filename as base (e.g., filename_segmented.npz)")
        naming_info.setStyleSheet("QLabel { font-style: italic; color: gray; }")
        output_layout.addWidget(naming_info)
        
        layout.addWidget(output_group)
        
    def setup_processing_section(self, layout):
        """Set up processing controls section"""
        process_group = QGroupBox("Processing Control")
        process_layout = QVBoxLayout(process_group)
        
        # Process button
        self.process_button = QPushButton("Start Complete Workflow")
        self.process_button.setEnabled(False)
        self.process_button.clicked.connect(self.start_processing)
        self.process_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        process_layout.addWidget(self.process_button)
        
        # Overall progress bar
        self.progress_bar = QProgressBar()
        process_layout.addWidget(self.progress_bar)
        
        # Status/log area
        self.log_area = QTextEdit()
        self.log_area.setMaximumHeight(150)
        self.log_area.setPlaceholderText("Processing status will appear here...")
        process_layout.addWidget(self.log_area)
        
        layout.addWidget(process_group)
        
    def create_signal_light(self):
        """Create a signal light indicator"""
        light = QLabel("●")
        light.setAlignment(Qt.AlignmentFlag.AlignCenter)
        light.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        light.setFixedSize(30, 20)
        return light
        
    def set_signal_light_status(self, step, status):
        """Set signal light status: 'pending', 'processing', 'completed', 'failed'"""
        if step not in self.signal_lights:
            return
            
        colors = {
            'pending': '#cccccc',     # Gray
            'processing': '#FFA500',  # Orange
            'completed': '#4CAF50',   # Green
            'failed': '#F44336'       # Red
        }
        
        color = colors.get(status, '#cccccc')
        self.signal_lights[step].setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        
    def reset_signal_lights(self):
        """Reset all signal lights to pending state"""
        for step in self.signal_lights:
            self.set_signal_light_status(step, 'pending')
            
    def set_data_available(self, available, data_info=None):
        """Called when data becomes available or unavailable"""
        self.data_info = data_info
        
        if available and data_info:
            # Enable processing if we have at least one channel
            pc_channel = data_info.get('pc_channel')
            fl_channel = data_info.get('fl_channel')
            can_process = pc_channel is not None or fl_channel is not None
            self.process_button.setEnabled(can_process)
            
            # Reset signal lights when new data loads
            self.reset_signal_lights()
            
        else:
            self.process_button.setEnabled(False)
            
    def select_output_directory(self):
        """Open directory dialog to select output directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", "")
        
        if directory:
            self.output_dir.setText(directory)
            
    def start_processing(self):
        """Start the complete workflow processing"""
        if not self.data_info:
            return
            
        # Validate inputs
        output_dir = self.output_dir.text().strip()
        if not output_dir:
            self.log_area.append("Error: Please select an output directory")
            return
            
        # Use ND2 filename as base name
        base_name = self.data_info['filename'].split('.')[0]
            
        # All steps are enabled by default
        enabled_steps = ['segmentation', 'background_correction', 'tracking', 'bounding_box']
            
        # Prepare processing parameters with default values
        params = {
            'data_info': self.data_info,
            'output_dir': output_dir,
            'base_name': base_name,
            'enabled_steps': enabled_steps,
            
            # Default parameters for all steps
            'mask_size': 3,
            'binarization_method': 'log_std',  # Use logarithmic std dev for phase contrast
            'div_horiz': 7,
            'div_vert': 5,
            'use_memmap': True,
            'max_displacement': 20,
            'memory_frames': 3,
        }
        
        # Emit signal to start processing
        self.process_requested.emit(params)
        
        # Update UI for processing state
        self.process_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_area.append("Starting complete workflow...")
        self.log_area.append("Processing: Segmentation → Background Correction → Tracking → Bounding Box")
        
    def update_progress(self, value, message=""):
        """Update progress bar and status"""
        self.progress_bar.setValue(value)
        if message:
            self.log_area.append(message)
            
    def update_step_status(self, step, status, message=""):
        """Update step status and signal light"""
        self.set_signal_light_status(step, status)
        if message:
            self.log_area.append(message)
            
    def processing_finished(self, success, message=""):
        """Called when processing is complete"""
        self.process_button.setEnabled(True)
        
        if success:
            self.progress_bar.setValue(100)
            self.log_area.append("✓ Complete workflow finished successfully")
            if message:
                self.log_area.append(message)
        else:
            self.log_area.append(f"✗ Workflow failed: {message}")
            
    def processing_error(self, error_message):
        """Called when processing encounters an error"""
        self.processing_finished(False, error_message)