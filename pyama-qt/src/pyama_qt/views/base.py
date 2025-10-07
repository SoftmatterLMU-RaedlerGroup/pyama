"""Common base classes and helpers for PyAMA Qt views."""

from typing import TypeVar

from PySide6.QtWidgets import QWidget


ModelT = TypeVar("ModelT")


class BasePage(QWidget):
    """Mixin for pages that connect directly to Qt models."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.build()
        self.bind()

    def build(self) -> None:
        """Hook for building child widgets and layouts."""
        raise NotImplementedError

    def bind(self) -> None:
        """Hook for connecting signals once widgets are built."""
        raise NotImplementedError


class BasePanel(QWidget):
    """Mixin for panels bound directly to Qt models."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.build()
        self.bind()

    def build(self) -> None:
        """Hook for building child widgets and layouts."""
        raise NotImplementedError

    def bind(self) -> None:
        """Hook for connecting signals once widgets are built."""
        raise NotImplementedError
