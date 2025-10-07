"""Processing tab embedding configuration and merge panels."""

from PySide6.QtWidgets import QHBoxLayout

from .merge_panel import ProcessingMergePanel
from .workflow_panel import ProcessingConfigPanel
from ..base import BasePage


class ProcessingPage(BasePage):
    """Embeddable processing page providing workflow and merge tools."""

    def build(self) -> None:
        layout = QHBoxLayout(self)

        self.config_panel = ProcessingConfigPanel(self)
        self.merge_panel = ProcessingMergePanel(self)

        layout.addWidget(self.config_panel, 2)
        layout.addWidget(self.merge_panel, 1)

    def bind(self) -> None:
        """No external connections inside the view; controllers handle wiring."""
        return
