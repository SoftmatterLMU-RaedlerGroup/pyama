"""Common base classes and helpers for PyAMA Qt views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from PySide6.QtWidgets import QMessageBox, QWidget


StateT = TypeVar("StateT")


class BaseView(QWidget, Generic[StateT]):
    """Base class for Qt widgets that expose a typed state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state: StateT | None = None
        self.build()
        self.bind()

    # Template methods -----------------------------------------------------
    def build(self) -> None:
        """Hook for building child widgets and layouts."""
        raise NotImplementedError

    def bind(self) -> None:
        """Hook for connecting signals once widgets are built."""

    def update_view(self) -> None:
        """Hook for reacting to state changes."""

    # State management -----------------------------------------------------
    def set_state(self, state: StateT | None) -> None:
        self._state = state
        self.update_view()

    def get_state(self) -> StateT | None:
        return self._state

    # Common helpers -------------------------------------------------------
    def show_error(self, message: str, title: str = "Error") -> None:
        QMessageBox.critical(self, title, message)

    def show_info(self, message: str, title: str = "Info") -> None:
        QMessageBox.information(self, title, message)


class BasePage(BaseView[StateT]):
    """Base class for top-level pages hosted in the main tab widget."""


class BasePanel(BaseView[StateT]):
    """Base class for column-style panels inside a page."""


@dataclass(slots=True)
class DialogRequest:
    """Typed description of a dialog request for controllers."""

    title: str
    message: str
    details: str | None = None
    severity: str = "info"  # info | warning | error
