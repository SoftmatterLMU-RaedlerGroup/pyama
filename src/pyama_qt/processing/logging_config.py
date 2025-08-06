"""
Centralized logging configuration for PyAMA-Qt processing module.
"""

import logging
import sys
from PySide6.QtCore import QObject, Signal


class QtLogHandler(logging.Handler, QObject):
    """Custom logging handler that emits Qt signals for GUI integration."""
    
    # Signal emitted when a log record is received
    log_message = Signal(str)
    
    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        
    def emit(self, record):
        """Emit the log record as a Qt signal."""
        msg = self.format(record)
        self.log_message.emit(msg)


def setup_logging(use_qt_handler=True):
    """
    Set up logging configuration for the processing module.
    
    Args:
        use_qt_handler: If True, adds QtLogHandler for GUI integration
        
    Returns:
        QtLogHandler instance if use_qt_handler is True, None otherwise
    """
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove any existing handlers
    root_logger.handlers.clear()
    
    # Console handler with simple format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                      datefmt='%H:%M:%S')
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # Qt handler for GUI integration
    qt_handler = None
    if use_qt_handler:
        qt_handler = QtLogHandler()
        qt_handler.setLevel(logging.INFO)
        qt_format = logging.Formatter('%(message)s')  # Simple format for GUI
        qt_handler.setFormatter(qt_format)
        root_logger.addHandler(qt_handler)
    
    # Set specific logger levels
    logging.getLogger('pyama_qt.processing').setLevel(logging.INFO)
    logging.getLogger('pyama_qt.processing.services').setLevel(logging.INFO)
    logging.getLogger('pyama_qt.processing.ui').setLevel(logging.INFO)
    
    return qt_handler


def get_logger(name):
    """Get a logger instance with the given name."""
    return logging.getLogger(name)