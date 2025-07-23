# PyAMA-Qt Development Notes

## PySide6 Signal Usage

When using PySide6, signals should be defined using `Signal` instead of `pyqtSignal`:

```python
from PySide6.QtCore import Signal

class MyWidget(QObject):
    # Correct - PySide6 syntax
    my_signal = Signal(int)
    
    # Incorrect - PyQt syntax
    # my_signal = pyqtSignal(int)  # This will cause import errors
```

**Important:** PySide6 uses `Signal` while PyQt uses `pyqtSignal`. Since this project uses PySide6, always use `Signal` for signal definitions.

## QThread Usage Pattern

For background processing, use the worker-thread pattern instead of moving existing objects to threads:

```python
from PySide6.QtCore import QThread, QObject, Signal

class Worker(QObject):
    """Worker class for background processing."""
    finished = Signal(bool, str)  # success, message
    
    def __init__(self, params):
        super().__init__()
        self.params = params
    
    def run_processing(self):
        """Main processing method."""
        try:
            # Do processing work here
            success = True
            self.finished.emit(success, "Processing completed")
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")

# In main window:
def start_background_work(self, params):
    # Create thread and worker
    self.thread = QThread()
    self.worker = Worker(params)
    
    # Move worker to thread
    self.worker.moveToThread(self.thread)
    
    # Connect signals
    self.thread.started.connect(self.worker.run_processing)
    self.worker.finished.connect(self.thread.quit)
    self.worker.finished.connect(self.worker.deleteLater)
    self.thread.finished.connect(self.thread.deleteLater)
    
    # Start processing
    self.thread.start()
```

**Avoid:** Moving existing objects with complex signal connections to threads using `moveToThread()`.