"""PyAMA-specific Qt dialogs."""

from __future__ import annotations

from typing import Optional

from qtpy.QtWidgets import QLabel, QDialog, QVBoxLayout, QWidget

try:  # pragma: no cover - only available inside Cell-ACDC runtime
    from cellacdc import _base_widgets as cellacdc_base_widgets
except Exception:  # pragma: no cover - fallback when Cell-ACDC isn't importable
    cellacdc_base_widgets = None

_DialogBase = (
    cellacdc_base_widgets.QBaseDialog if cellacdc_base_widgets is not None else QDialog
)


class PyamaCustomPreprocessDialog(_DialogBase):
    """Placeholder dialog for future PyAMA preprocessing UI."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle("PyAMA Preprocess")
        self.setModal(False)
        self.setMinimumSize(420, 260)

        layout = self.layout()
        if layout is None:
            layout = QVBoxLayout()
            layout.setContentsMargins(30, 30, 30, 30)
            self.setLayout(layout)

        label = QLabel("Custom PyAMA preprocessing configuration will appear here.")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)
