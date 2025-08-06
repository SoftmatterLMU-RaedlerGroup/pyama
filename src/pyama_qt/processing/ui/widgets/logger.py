from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QTextEdit
from datetime import datetime


class Logger(QWidget):
    """Simple logger widget for displaying processing messages."""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Log area
        log_group = QGroupBox("Processing Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_area = QTextEdit()
        self.log_area.setPlaceholderText("Processing status will appear here...")
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area)
        
        layout.addWidget(log_group)
        
    def log_message(self, message):
        """Add a message to the log with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        timestamped_message = f"[{timestamp}] {message}"
        self.log_area.append(timestamped_message)
        
    def clear_log(self):
        """Clear the log area."""
        self.log_area.clear()