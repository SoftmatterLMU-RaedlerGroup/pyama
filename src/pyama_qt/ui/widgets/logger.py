from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QTextEdit
from PySide6.QtCore import QThread, QObject, Signal, QMutex, QMutexLocker
import os
from datetime import datetime
from queue import Queue, Empty


class LogWriter(QObject):
    """Async log writer that runs in a separate thread"""
    log_written = Signal(str)  # Signal when log is written successfully
    error_occurred = Signal(str)  # Signal when write error occurs
    
    def __init__(self):
        super().__init__()
        self.log_file_path = None
        self.message_queue = Queue()
        self.mutex = QMutex()
        self.running = False
        
    def set_log_file(self, file_path):
        """Set the log file path"""
        with QMutexLocker(self.mutex):
            self.log_file_path = file_path
            
    def add_message(self, message):
        """Add a message to the write queue"""
        self.message_queue.put(message)
        
    def start_writing(self):
        """Start the async writing loop"""
        self.running = True
        self.process_queue()
        
    def stop_writing(self):
        """Stop the async writing loop"""
        self.running = False
        
    def process_queue(self):
        """Process messages from the queue"""
        import time
        while self.running:
            try:
                # Get message with timeout to allow stopping
                message = self.message_queue.get(block=True, timeout=0.1)
                self._write_message(message)
            except Empty:
                # Queue empty or timeout - continue loop
                time.sleep(0.01)
                continue
                
    def _write_message(self, message):
        """Write a single message to file"""
        with QMutexLocker(self.mutex):
            if self.log_file_path:
                try:
                    with open(self.log_file_path, 'a', encoding='utf-8') as f:
                        f.write(message + "\n")
                        f.flush()  # Ensure immediate write
                except Exception as e:
                    self.error_occurred.emit(f"Log write error: {str(e)}")


class Logger(QWidget):
    def __init__(self):
        super().__init__()
        self.log_file_path = None
        self.log_buffer = []  # Store messages before file is created
        
        # Setup async logging
        self.log_thread = QThread()
        self.log_writer = LogWriter()
        self.log_writer.moveToThread(self.log_thread)
        
        # Connect signals
        self.log_thread.started.connect(self.log_writer.start_writing)
        self.log_writer.error_occurred.connect(self._handle_write_error)
        
        # Start the logging thread
        self.log_thread.start()
        
        self.setup_ui()
        
    def __del__(self):
        """Cleanup when logger is destroyed"""
        if hasattr(self, 'log_writer'):
            self.log_writer.stop_writing()
        if hasattr(self, 'log_thread'):
            self.log_thread.quit()
            self.log_thread.wait()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Log area
        log_group = QGroupBox("Processing Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_area = QTextEdit()
        self.log_area.setPlaceholderText("Processing status will appear here...")
        log_layout.addWidget(self.log_area)
        
        layout.addWidget(log_group)
        
    def log_message(self, message):
        """Add a message to the log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        timestamped_message = f"[{timestamp}] {message}"
        
        # Add to UI immediately (synchronous)
        self.log_area.append(timestamped_message)
        
        # Store in buffer or queue for async writing
        if self.log_file_path:
            self.log_writer.add_message(timestamped_message)
        else:
            self.log_buffer.append(timestamped_message)
            
    def _handle_write_error(self, error_message):
        """Handle async write errors"""
        self.log_area.append(f"⚠️ {error_message}")
            
    def start_file_logging(self, output_directory, base_name="pyama_processing"):
        """Start logging to file"""
        # Check if output directory exists and is writable
        if (not os.path.exists(output_directory) or 
            not os.access(output_directory, os.W_OK)):
            # Use /tmp if directory doesn't exist/isn't writable
            log_dir = "/tmp"
            self.log_file_path = os.path.join(log_dir, f"{base_name}_log.log")
            self.log_message("⚠️ Output directory not accessible, using /tmp instead")
        else:
            # Use the actual output directory
            self.log_file_path = os.path.join(output_directory, f"{base_name}_log.log")
        
        # Write header and buffered messages
        try:
            # Create file with header synchronously (one-time operation)
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write("PyAMA Processing Log\n")
                f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                
                # Write buffered messages
                for msg in self.log_buffer:
                    f.write(msg + "\n")
            
            # Set up async writer for future messages
            self.log_writer.set_log_file(self.log_file_path)
            
            self.log_buffer.clear()
            self.log_message(f"📝 Log file created: {self.log_file_path}")
            
        except Exception as e:
            self.log_message(f"⚠️ Failed to create log file: {str(e)}")
            self.log_file_path = None
            
    def clear_log(self):
        """Clear the log area"""
        self.log_area.clear()
        self.log_buffer.clear()
        
    def cleanup(self):
        """Cleanup the async logger"""
        if hasattr(self, 'log_writer'):
            self.log_writer.stop_writing()
        if hasattr(self, 'log_thread') and self.log_thread.isRunning():
            self.log_thread.quit()
            self.log_thread.wait(1000)  # Wait up to 1 second