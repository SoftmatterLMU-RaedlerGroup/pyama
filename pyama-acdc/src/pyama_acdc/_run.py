"""Runtime helpers to show PyAMA workflow UIs."""

from __future__ import annotations

import sys

from qtpy import QtCore, QtGui, QtWidgets

from . import icon_path as PACKAGE_ICON_PATH
from .gui import pyAMA_Win


class PyamaWorkflowWin(pyAMA_Win):
    """Non-modal workflow dialog that emits a close signal."""

    sigClosed = QtCore.Signal(object)

    def __init__(self, *args, icon_path: str | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        icon = icon_path or PACKAGE_ICON_PATH
        if icon:
            self.setWindowIcon(QtGui.QIcon(icon))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[name-defined]
        try:
            self.sigClosed.emit(self)
        finally:
            super().closeEvent(event)


def run_gui(
    *,
    debug: bool | None = None,
    app: QtWidgets.QApplication | None = None,
    mainWin=None,
    launcherSlot=None,
    icon_path: str | None = None,
):
    """Launch the PyAMA workflow dialog and return the window instance."""

    # Reuse the current QApplication if available, otherwise create one so we
    # can run outside Cell-ACDC for debugging.
    owns_app = False
    if app is None:
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication(sys.argv)
            owns_app = True

    win = PyamaWorkflowWin(parent=mainWin, icon_path=icon_path)
    win.launcherSlot = launcherSlot
    win.show()
    if hasattr(win, "raise_"):
        win.raise_()
    if hasattr(win, "activateWindow"):
        win.activateWindow()

    if owns_app:
        sys.exit(app.exec_())
    return win
