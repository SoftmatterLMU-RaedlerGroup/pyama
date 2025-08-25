'''
Reusable ProgressIndicator widget.
'''

from PySide6.QtWidgets import QWidget, QProgressBar, QLabel, QVBoxLayout

class ProgressIndicator(QWidget):
    """A widget for displaying progress of long-running tasks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.label = QLabel()
        self.progress_bar = QProgressBar()
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.progress_bar)
        self.hide()

    def set_text(self, text: str):
        self.label.setText(text)

    def set_value(self, value: int):
        if value < 0:
            self.progress_bar.setRange(0, 0) # Indeterminate
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)

    def task_started(self, message: str):
        self.set_text(message)
        self.set_value(-1) # Indeterminate
        self.show()

    def task_finished(self, message: str):
        self.set_text(message)
        self.set_value(100)
        self.hide()
