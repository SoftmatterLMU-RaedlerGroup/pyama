"""Utilities to embed PyAMA workflows inside Cell-ACDC's UI."""

from __future__ import annotations

from functools import partial
from typing import Callable, Sequence

try:
    from qtpy.QtWidgets import (
        QAction,
        QDialog,
        QDialogButtonBox,
        QLabel,
        QMenu,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - handled at runtime
    raise ImportError(
        "qtpy is required to use pyama_acdc's integration helpers"
    ) from exc

try:  # pragma: no cover - optional when running outside Cell-ACDC
    from cellacdc import _base_widgets as cellacdc_base_widgets
except Exception:  # pragma: no cover - fallback when Cell-ACDC isn't importable
    cellacdc_base_widgets = None

_PlaceholderBase = (
    cellacdc_base_widgets.QBaseDialog if cellacdc_base_widgets is not None else QDialog
)


class PyamaPlaceholderDialog(_PlaceholderBase):
    """Simple placeholder dialog with Cell-ACDC styling when available."""

    def __init__(
        self,
        title: str,
        message: str,
        parent: QWidget | None = None,
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
        else:  # pragma: no cover - base dialog already defined a layout
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        message_label = QLabel(message)
        message_label.setWordWrap(True)

        layout.addWidget(message_label)
        layout.addStretch(1)


class PyamaWorkflowDialog(QDialog):
    """Dialog exposing PyAMA workflow shortcuts inside Cell-ACDC."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        steps: Sequence[tuple[str, Callable[[], None] | None]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PyAMA Workflow")
        self.setModal(False)

        layout = QVBoxLayout(self)

        for text, callback in steps or ():
            button = QPushButton(text)
            if callback is None:
                button.setEnabled(False)
                button.setToolTip("Coming soon")
            else:
                button.clicked.connect(partial(self._invoke_step, callback, text))
            layout.addWidget(button)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _invoke_step(self, callback: Callable[[], None] | None, text: str) -> None:
        if callback is not None:
            callback()


def _build_measurements_launcher(main_window: QWidget) -> Callable[[], None]:
    """Return a callback that opens Cell-ACDC's SetMeasurements dialog."""

    def _launch() -> None:
        gui_windows = getattr(main_window, "guiWins", []) or []
        if not gui_windows:
            launch_gui_cb = getattr(main_window, "launchGui", None)
            if launch_gui_cb is None:
                QMessageBox.warning(
                    main_window,
                    "PyAMA Workflow",
                    "Cannot launch the GUI automatically. Open the Cell-ACDC GUI manually, load a position, then use Measurements -> Set measurements...",
                )
                return

            launch_gui_cb()
            QMessageBox.information(
                main_window,
                "PyAMA Workflow",
                "GUI launched. Load a dataset in the GUI, then use Measurements -> Set measurements... to configure metrics.",
            )
            return

        gui_win = gui_windows[-1]
        if hasattr(gui_win, "show"):
            gui_win.show()
        if hasattr(gui_win, "raise_"):
            gui_win.raise_()
        if hasattr(gui_win, "activateWindow"):
            gui_win.activateWindow()

        QMessageBox.information(
            main_window,
            "PyAMA Workflow",
            "In the GUI window, open Measurements -> Set measurements... to configure metrics just like the stock app.",
        )

    return _launch


def _build_placeholder_launcher(
    main_window: QWidget, title: str, message: str
) -> Callable[[], None]:
    """Return a callback that shows a Cell-ACDC styled placeholder dialog."""

    def _launch() -> None:
        dialogs = getattr(main_window, "_pyamaPlaceholderDialogs", None)
        if dialogs is None:
            dialogs = {}
            setattr(main_window, "_pyamaPlaceholderDialogs", dialogs)

        dialog = dialogs.get(title)
        if dialog is None:
            dialog = PyamaPlaceholderDialog(title, message, parent=main_window)
            dialogs[title] = dialog

        dialog.show()
        if hasattr(dialog, "raise_"):
            dialog.raise_()
        if hasattr(dialog, "activateWindow"):
            dialog.activateWindow()

    return _launch



def add_pyama_workflow_action(
    main_window: QWidget,
    *,
    menu: QMenu | None = None,
    action_text: str = "PyAMA Workflow...",
) -> QAction:
    """Attach a menu action that opens :class:`PyamaWorkflowDialog`.

    Parameters
    ----------
    main_window:
        The Cell-ACDC main window instance (typically ``mainWin``).
    menu:
        Optional menu to attach the action to. Defaults to
        ``main_window.utilsMenu``.
    action_text:
        Text shown in the Utilities menu.

    Returns
    -------
    QAction
        The created action so callers can further customize it.
    """

    target_menu = menu or getattr(main_window, "utilsMenu", None)
    if target_menu is None:
        raise AttributeError(
            "main_window has no utilsMenu. Pass a QMenu via the `menu` argument."
        )

    dialog = getattr(main_window, "_pyamaWorkflowDialog", None)
    if dialog is None:
        steps: list[tuple[str, Callable[[], None] | None]] = []

        data_struct_cb = getattr(main_window, "_showDataStructWin", None)
        steps.append(
            (
                "Step 0 · Create data structure from microscopy/image file(s)...",
                data_struct_cb,
            )
        )

        segm_cb = getattr(main_window, "launchSegm", None)
        steps.append(
            (
                "Step 1 · Launch segmentation module...",
                segm_cb,
            )
        )

        from .dialogs import PyamaCustomPreprocessDialog

        def _launch_preprocess_dialog() -> None:
            dialog = getattr(main_window, "_pyamaPreprocessDialog", None)
            if dialog is None:
                dialog = PyamaCustomPreprocessDialog(parent=main_window)
                setattr(main_window, "_pyamaPreprocessDialog", dialog)

            dialog.show()
            if hasattr(dialog, "raise_"):
                dialog.raise_()
            if hasattr(dialog, "activateWindow"):
                dialog.activateWindow()

        steps.append(
            (
                "Step 2 · Launch preprocess module...",
                _launch_preprocess_dialog,
            )
        )

        measurements_cb = _build_measurements_launcher(main_window)
        steps.append(
            (
                "Step 3 · Launch measurement module...",
                measurements_cb,
            )
        )

        merging_cb = _build_placeholder_launcher(
            main_window,
            "PyAMA merging module (coming soon)",
            "PyAMA's merging module is still under development. Use Cell-ACDC's native combining utilities for now.",
        )
        steps.append(
            (
                "Step 4 · Launch merging module...",
                merging_cb,
            )
        )

        analysis_cb = _build_placeholder_launcher(
            main_window,
            "PyAMA analysis module (coming soon)",
            "PyAMA's analysis helpers are coming soon. Use Cell-ACDC's GUI or external notebooks to inspect measurements in the meantime.",
        )
        steps.append(
            (
                "Step 5 · Launch analysis module...",
                analysis_cb,
            )
        )

        dialog = PyamaWorkflowDialog(
            parent=main_window,
            steps=steps,
        )
        setattr(main_window, "_pyamaWorkflowDialog", dialog)

    action = target_menu.addAction(action_text)
    action.triggered.connect(dialog.show)
    return action
