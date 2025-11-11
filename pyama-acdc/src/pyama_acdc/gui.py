"""Qt widgets for the PyAMA ↔ Cell-ACDC integration."""

from __future__ import annotations

from typing import Optional

from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:  # pragma: no cover - optional when running outside Cell-ACDC
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


class PyamaPlaceholderDialog(_DialogBase):
    """Generic placeholder dialog with Cell-ACDC styling when available."""

    def __init__(
        self,
        title: str,
        message: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle(title)
        self.setModal(False)
        self.setMinimumSize(420, 220)

        layout = self.layout()
        if layout is None:
            layout = QVBoxLayout()
            layout.setContentsMargins(30, 30, 30, 30)
            self.setLayout(layout)
        else:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        label = QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)


class pyAMA_Win(QDialog):
    """Dialog exposing PyAMA workflow shortcuts inside Cell-ACDC."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PyAMA Workflow")
        self.setModal(False)

        layout = QVBoxLayout(self)
        main_window = parent

        # Step 0 · data structure
        step0Button = QPushButton(
            "Step 0 · Create data structure from microscopy/image file(s)..."
        )
        step0_cb = getattr(main_window, "_showDataStructWin", None) if main_window else None
        if step0_cb is None:
            step0Button.setEnabled(False)
            step0Button.setToolTip("Unavailable in this session")
        else:
            step0Button.clicked.connect(step0_cb)
        layout.addWidget(step0Button)

        # Step 1 · segmentation
        step1Button = QPushButton("Step 1 · Launch segmentation module...")
        step1_cb = getattr(main_window, "launchSegm", None) if main_window else None
        if step1_cb is None:
            step1Button.setEnabled(False)
            step1Button.setToolTip("Unavailable in this session")
        else:
            step1Button.clicked.connect(step1_cb)
        layout.addWidget(step1Button)

        # Step 2 · preprocess placeholder
        step2Button = QPushButton("Step 2 · Launch preprocess module...")
        step2Button.clicked.connect(
            lambda *_: PyamaCustomPreprocessDialog(parent=self).show()
        )
        layout.addWidget(step2Button)

        # Step 3 · measurements
        step3Button = QPushButton("Step 3 · Launch measurement module...")
        step3_cb = (
            None if main_window is None else getattr(main_window, "launchGui", None)
        )
        if step3_cb is None:
            step3Button.setEnabled(False)
            step3Button.setToolTip("Unavailable in this session")
        else:
            step3Button.clicked.connect(step3_cb)
        layout.addWidget(step3Button)

        # Step 4 · merging placeholder
        step4Button = QPushButton("Step 4 · Launch merging module...")
        step4Button.clicked.connect(
            lambda *_: PyamaPlaceholderDialog(
                "PyAMA merging module (coming soon)",
                (
                    "PyAMA's merging module is still under development. "
                    "Use Cell-ACDC's native combining utilities for now."
                ),
                parent=self,
            ).show()
        )
        layout.addWidget(step4Button)

        # Step 5 · analysis placeholder
        step5Button = QPushButton("Step 5 · Launch analysis module...")
        step5Button.clicked.connect(
            lambda *_: PyamaPlaceholderDialog(
                "PyAMA analysis module (coming soon)",
                (
                    "PyAMA's analysis helpers are coming soon. "
                    "Use Cell-ACDC's GUI or external notebooks "
                    "to inspect measurements in the meantime."
                ),
                parent=self,
            ).show()
        )
        layout.addWidget(step5Button)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
