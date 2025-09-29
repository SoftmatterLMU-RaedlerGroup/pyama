"""Processing tab embedding configuration and merge panels."""

import logging

from PySide6.QtWidgets import QHBoxLayout

from pyama_qt.processing.controller import ProcessingController
from pyama_qt.processing.panels import ProcessingConfigPanel, ProcessingMergePanel
from pyama_qt.ui import ModelBoundPage

logger = logging.getLogger(__name__)


class ProcessingPage(ModelBoundPage):
    """Embeddable processing page providing workflow and merge tools."""

    def __init__(self, parent=None):
        self.controller = ProcessingController()
        super().__init__(parent)
        logger.info("PyAMA Processing Page loaded")

    # BasePage hooks -------------------------------------------------------
    def build(self) -> None:
        layout = QHBoxLayout(self)

        self.config_panel = ProcessingConfigPanel(self)
        self.merge_panel = ProcessingMergePanel(self)

        layout.addWidget(self.config_panel, 2)
        layout.addWidget(self.merge_panel, 1)

    def bind(self) -> None:
        self._bind_models()
        self.controller.workflow_failed.connect(self._on_workflow_failed)

        self.config_panel.file_selected.connect(self.controller.load_microscopy)
        self.config_panel.output_dir_selected.connect(
            self.controller.set_output_directory
        )
        self.config_panel.channels_changed.connect(self._on_channels_changed)
        self.config_panel.parameters_changed.connect(self._on_parameters_changed)
        self.config_panel.process_requested.connect(self.controller.start_workflow)

        self.merge_panel.load_samples_requested.connect(self.controller.load_samples)
        self.merge_panel.save_samples_requested.connect(
            lambda path: self.controller.save_samples(
                path, self.merge_panel.table.to_samples()
            )
        )
        self.merge_panel.merge_requested.connect(self.controller.run_merge)
        self.controller.load_samples_success.connect(self._on_load_samples_success)
        self.controller.save_samples_success.connect(self._on_save_samples_success)
        self.controller.merge_finished.connect(self._on_merge_finished)

    def _bind_models(self) -> None:
        self.config_panel.set_models(
            self.controller.config_model, self.controller.status_model
        )

    def _on_load_samples_success(self, samples: list, path: str) -> None:
        self.merge_panel.table.load_samples(samples)
        self.merge_panel.sample_edit.setText(path)

    def _on_merge_finished(self, success: bool, message: str) -> None:
        """Handle merge completion with user feedback."""
        if success:
            logger.info(f"Merge operation completed successfully: {message}")
        else:
            logger.error(f"Merge operation failed: {message}")

    def _on_save_samples_success(self, path: str) -> None:
        pass

    # Signal adapters ------------------------------------------------------
    def _on_channels_changed(self, selection) -> None:
        self.controller.update_channels(selection.phase, selection.fluorescence)

    def _on_parameters_changed(self, params) -> None:
        self.controller.update_parameters(params)

    def _on_workflow_failed(self, message: str) -> None:
        pass
