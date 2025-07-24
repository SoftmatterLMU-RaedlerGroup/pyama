from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLabel, QLineEdit, 
                             QFileDialog, QTextEdit, QProgressBar, QFrame)
from PySide6.QtCore import Signal, Qt, QTimer


class Workflow(QWidget):
    process_requested = Signal(dict)
    log_message = Signal(str)  # Signal to send log messages to fileloader
    start_file_logging = Signal(str, str)  # Signal to start file logging (output_dir, base_name)
    
    def __init__(self):
        super().__init__()
        self.data_info = None
        self.signal_lights = {}
        self.log_area = None  # Will be set by main window
        self.setup_ui()
        
    def set_log_area(self, log_area):
        """Set reference to the log area widget"""
        self.log_area = log_area
        
    def log_message_to_area(self, message):
        """Log message to the log area"""
        # Always emit the signal to ensure proper logging
        self.log_message.emit(message)
        
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
        self.output_dir_button.clicked.connect(self.fake_select_directory)
        
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
        self.process_button.clicked.connect(self.start_fake_processing)  # Connected to fake method
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
            
    def fake_select_directory(self):
        """Fake directory selection for UI testing"""
        fake_directory = "/Users/researcher/microscopy_output"
        self.output_dir.setText(fake_directory)
        self.log_message_to_area("📂 Output directory selected:")
        self.log_message_to_area(f"  • Path: {fake_directory}")
        self.log_message_to_area("✅ Ready to start processing workflow")
            
    def start_processing(self):
        """Start the complete workflow processing"""
        if not self.data_info:
            return
            
        # Validate inputs
        output_dir = self.output_dir.text().strip()
        if not output_dir:
            self.log_message_to_area("Error: Please select an output directory")
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
            'div_horiz': 7,
            'div_vert': 5,
            'use_memmap': True,
            'max_displacement': 20,
            'memory_frames': 3,
        }
        
        # Start file logging
        base_name = params['base_name']
        output_dir = params['output_dir']
        self.start_file_logging.emit(output_dir, base_name)
        
        # Emit signal to start processing
        self.process_requested.emit(params)
        
        # Update UI for processing state
        self.process_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_message_to_area("Starting complete workflow...")
        self.log_message_to_area("Processing: Segmentation → Background Correction → Tracking → Bounding Box")
        
    def start_fake_processing(self):
        """Start fake processing for UI testing"""
        if not self.data_info:
            return
            
        # Validate inputs
        output_dir = self.output_dir.text().strip()
        if not output_dir:
            self.log_message_to_area("Error: Please select an output directory")
            return
            
        # Start file logging
        base_name = self.data_info.get('filename', 'test_data').split('.')[0] if self.data_info else 'pyama_processing'
        self.start_file_logging.emit(output_dir, base_name)
        
        # Start fake processing
        self.run_fake_processing()
        
    def update_progress(self, value, message=""):
        """Update progress bar and status"""
        self.progress_bar.setValue(value)
        if message:
            self.log_message_to_area(message)
            
    def update_step_status(self, step, status, message=""):
        """Update step status and signal light"""
        self.set_signal_light_status(step, status)
        if message:
            self.log_message_to_area(message)
            
    def processing_finished(self, success, message=""):
        """Called when processing is complete"""
        self.process_button.setEnabled(True)
        
        if success:
            self.progress_bar.setValue(100)
            self.log_message_to_area("✓ Complete workflow finished successfully")
            if message:
                self.log_message_to_area(message)
        else:
            self.log_message_to_area(f"✗ Workflow failed: {message}")
            
    def processing_error(self, error_message):
        """Called when processing encounters an error"""
        self.processing_finished(False, error_message)
        
    def run_fake_processing(self):
        """Run fake processing for UI testing"""
        self.process_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_message_to_area("Starting complete workflow...")
        self.log_message_to_area("Processing: Segmentation → Background Correction → Tracking → Bounding Box")
        self.log_message_to_area("⚠️  FAKE PROCESSING MODE - For UI testing only")
        self.log_message_to_area("📊 Processing 5 fields of view (FOVs)")
        
        # Define fake processing steps for 5 FOVs
        steps = [
            ('segmentation', 'Step 1: Segmentation (Binarization)'),
            ('background_correction', 'Step 2: Background Correction'), 
            ('tracking', 'Step 3: Cell Tracking'),
            ('bounding_box', 'Step 4: Pickle Maximum Bounding Box')
        ]
        
        self.num_fovs = 5
        self.current_fov = 0
        self.current_step = 0
        self.fake_steps = steps
        self.total_steps = len(steps) * self.num_fovs
        self.completed_steps = 0
        
        self.fake_timer = QTimer()
        self.fake_timer.timeout.connect(self.process_fake_step)
        self.fake_timer.start(1500)  # Process step every 1.5 seconds
        
    def process_fake_step(self):
        """Process one fake step"""
        if self.current_fov >= self.num_fovs:
            self.fake_timer.stop()
            self.fake_processing_complete()
            return
            
        step_id, step_name = self.fake_steps[self.current_step]
        
        # Set step to processing
        self.set_signal_light_status(step_id, 'processing')
        self.log_message_to_area(f"🔄 FOV {self.current_fov + 1}/5: {step_name}...")
        
        # Wait a bit then complete the step
        QTimer.singleShot(1000, lambda: self.complete_fake_step(step_id, step_name))
        
    def complete_fake_step(self, step_id, step_name):
        """Complete a fake processing step"""
        self.set_signal_light_status(step_id, 'completed')
        self.completed_steps += 1
        
        # Calculate progress percentage
        progress = int((self.completed_steps / self.total_steps) * 100)
        self.progress_bar.setValue(progress)
        self.log_message_to_area(f"✓ FOV {self.current_fov + 1}/5: {step_name} completed")
        
        # Move to next step
        self.current_step += 1
        
        # If we've completed all steps for this FOV, move to next FOV
        if self.current_step >= len(self.fake_steps):
            self.current_step = 0
            self.current_fov += 1
            
            # Reset signal lights for next FOV (except if we're done)
            if self.current_fov < self.num_fovs:
                self.log_message_to_area(f"📍 Moving to FOV {self.current_fov + 1}/5...")
                QTimer.singleShot(500, self.reset_signal_lights)
        
    def fake_processing_complete(self):
        """Complete fake processing"""
        self.process_button.setEnabled(True)
        self.progress_bar.setValue(100)
        self.log_message_to_area("✓ Complete workflow finished successfully")
        self.log_message_to_area("📊 Processed all 5 fields of view")
        self.log_message_to_area("📁 Output files would be saved to: " + self.output_dir.text())
        self.log_message_to_area("🎉 Fake processing complete - UI test successful!")