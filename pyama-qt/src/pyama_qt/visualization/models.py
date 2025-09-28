"""Qt models exposing visualization data to the UI.

The visualization feature historically relied on VisualizationState, a
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, QAbstractTableModel, QModelIndex, Qt, Signal
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ProjectModel(QObject):
    """Project-level metadata and selection state."""

    projectPathChanged = Signal(object)
    projectDataChanged = Signal(dict)
    availableChannelsChanged = Signal(list)
    statusMessageChanged = Signal(str)
    errorMessageChanged = Signal(str)
    isLoadingChanged = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._project_path: Any | None = None
        self._project_data: dict[str, Any] | None = None
        self._available_channels: list[str] = []
        self._status_message: str = ""
        self._error_message: str = ""
        self._is_loading = False

    def project_path(self) -> Any | None:
        return self._project_path

    def set_project_path(self, path: Any | None) -> None:
        if self._project_path == path:
            return
        self._project_path = path
        self.projectPathChanged.emit(path)

    def project_data(self) -> dict[str, Any] | None:
        return self._project_data

    def set_project_data(self, data: dict[str, Any] | None) -> None:
        if self._project_data == data:
            return
        self._project_data = data
        self.projectDataChanged.emit(data or {})

    def available_channels(self) -> list[str]:
        return self._available_channels

    def set_available_channels(self, channels: list[str]) -> None:
        if self._available_channels == channels:
            return
        self._available_channels = channels
        self.availableChannelsChanged.emit(channels)

    def status_message(self) -> str:
        return self._status_message

    def set_status_message(self, message: str) -> None:
        if self._status_message == message:
            return
        self._status_message = message
        self.statusMessageChanged.emit(message)

    def error_message(self) -> str:
        return self._error_message

    def set_error_message(self, message: str) -> None:
        if self._error_message == message:
            return
        self._error_message = message
        self.errorMessageChanged.emit(message)

    def is_loading(self) -> bool:
        return self._is_loading

    def set_is_loading(self, value: bool) -> None:
        if self._is_loading == value:
            return
        self._is_loading = value
        self.isLoadingChanged.emit(value)


class ImageCacheModel(QObject):
    """Model providing access to preprocessed image data per type."""

    cacheReset = Signal()
    dataTypeAdded = Signal(str)
    frameBoundsChanged = Signal(int, int)
    currentDataTypeChanged = Signal(str)
    currentFrameChanged = Signal(int)
    activeTraceChanged = Signal(object)
    tracePositionsChanged = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._image_cache: dict[str, np.ndarray] = {}
        self._current_data_type: str = ""
        self._current_frame_index = 0
        self._max_frame_index = 0
        self._trace_positions: dict[str, dict[int, tuple[float, float]]] = {}
        self._active_trace_id: str | None = None

    def available_types(self) -> list[str]:
        return list(self._image_cache.keys())

    def set_images(self, mapping: dict[str, np.ndarray]) -> None:
        self._image_cache = dict(mapping)
        self._max_frame_index = self._compute_max_frame()
        self._current_frame_index = 0
        next_type = next(iter(self._image_cache.keys()), "")
        if self._current_data_type != next_type:
            self._current_data_type = next_type
            self.currentDataTypeChanged.emit(self._current_data_type)
        self.frameBoundsChanged.emit(self._current_frame_index, self._max_frame_index)
        self.currentFrameChanged.emit(self._current_frame_index)
        self.cacheReset.emit()

    def update_image(self, key: str, data: np.ndarray) -> None:
        self._image_cache[key] = data
        if not self._current_data_type:
            self._current_data_type = key
            self.currentDataTypeChanged.emit(key)
        self._max_frame_index = self._compute_max_frame()
        self.frameBoundsChanged.emit(self._current_frame_index, self._max_frame_index)
        self.dataTypeAdded.emit(key)

    def remove_images(self) -> None:
        self._image_cache.clear()
        self._current_data_type = ""
        self._current_frame_index = 0
        self._max_frame_index = 0
        self.frameBoundsChanged.emit(0, 0)
        self.currentFrameChanged.emit(0)
        self.currentDataTypeChanged.emit("")
        self.cacheReset.emit()

    def current_data_type(self) -> str:
        return self._current_data_type

    def set_current_data_type(self, data_type: str) -> None:
        if self._current_data_type == data_type:
            return
        if data_type and data_type not in self._image_cache:
            return
        self._current_data_type = data_type
        self.currentDataTypeChanged.emit(data_type)

    def image_for_current_type(self) -> np.ndarray | None:
        if not self._current_data_type:
            return None
        return self._image_cache.get(self._current_data_type)

    def frame_bounds(self) -> tuple[int, int]:
        return (self._current_frame_index, self._max_frame_index)

    def set_current_frame(self, index: int) -> None:
        index = max(0, min(index, self._max_frame_index))
        if index == self._current_frame_index:
            return
        self._current_frame_index = index
        self.currentFrameChanged.emit(index)

    def set_max_frame_index(self, index: int) -> None:
        index = max(index, 0)
        if index == self._max_frame_index:
            return
        self._max_frame_index = index
        self.frameBoundsChanged.emit(self._current_frame_index, index)

    def trace_positions(self) -> dict[str, dict[int, tuple[float, float]]]:
        return self._trace_positions

    def set_trace_positions(
        self, positions: dict[str, dict[int, tuple[float, float]]]
    ) -> None:
        self._trace_positions = positions
        self.tracePositionsChanged.emit(positions)

    def set_active_trace(self, trace_id: str | None) -> None:
        if self._active_trace_id == trace_id:
            return
        self._active_trace_id = trace_id
        self.activeTraceChanged.emit(trace_id)

    def active_trace_id(self) -> str | None:
        return self._active_trace_id

    def _compute_max_frame(self) -> int:
        max_index = 0
        for array in self._image_cache.values():
            if array is None:
                continue
            if array.ndim >= 3:
                max_index = max(max_index, array.shape[0] - 1)
        return max_index


@dataclass
class TraceRecord:
    id: str
    is_good: bool


class TraceTableModel(QAbstractTableModel):
    """Table model exposing trace IDs and good/bad selection."""

    GoodRole = Qt.ItemDataRole.UserRole + 1

    goodStateChanged = Signal(str, bool)
    tracesReset = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._records: list[TraceRecord] = []
        self._headers = ["Good", "Trace ID"]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa:N802
        if parent.isValid():
            return 0
        return len(self._records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa:N802
        if parent.isValid():
            return 0
        return 2

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa:N802
        if not index.isValid():
            return None
        record = self._records[index.row()]

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if index.column() == 1:
                return record.id
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            return Qt.CheckState.Checked if record.is_good else Qt.CheckState.Unchecked
        if role == self.GoodRole:
            return record.is_good
        return None

    def setData(
        self,
        index: QModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:  # noqa:N802
        if not index.isValid() or index.column() != 0:
            return False
        if role != Qt.ItemDataRole.CheckStateRole:
            return False
        record = self._records[index.row()]
        is_good = value == Qt.CheckState.Checked
        if record.is_good == is_good:
            return False
        self._records[index.row()] = dataclasses.replace(record, is_good=is_good)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        self.goodStateChanged.emit(record.id, is_good)
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # noqa:N802
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        if index.column() == 0:
            return (
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def headerData(self, section: int, orientation: Qt.Orientation, role: int) -> Any:  # noqa:N802
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None

    def reset_traces(self, traces: list[TraceRecord]) -> None:
        self.beginResetModel()
        self._records = traces
        self.endResetModel()
        self.tracesReset.emit()

    def traces(self) -> list[TraceRecord]:
        return list(self._records)

    def set_good_state(self, trace_id: str, is_good: bool) -> None:
        for row, record in enumerate(self._records):
            if record.id == trace_id and record.is_good != is_good:
                index = self.index(row, 0)
                self._records[row] = dataclasses.replace(record, is_good=is_good)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
                break


class TraceFeatureModel(QObject):
    """Encapsulates trace feature time series for plotting."""

    availableFeaturesChanged = Signal(list)
    featureDataChanged = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._feature_series: dict[str, dict[str, np.ndarray]] = {}

    def available_features(self) -> list[str]:
        return list(self._feature_series.keys())

    def set_feature_series(self, series: dict[str, dict[str, np.ndarray]]) -> None:
        self._feature_series = series
        self.availableFeaturesChanged.emit(self.available_features())
        self.featureDataChanged.emit(series)

    def series_for(self, feature_name: str) -> dict[str, np.ndarray] | None:
        return self._feature_series.get(feature_name)


class TraceSelectionModel(QObject):
    """Tracks the currently active trace."""

    activeTraceChanged = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._active_trace_id: str | None = None

    def active_trace(self) -> str | None:
        return self._active_trace_id

    def set_active_trace(self, trace_id: str | None) -> None:
        if self._active_trace_id == trace_id:
            return
        self._active_trace_id = trace_id
        self.activeTraceChanged.emit(trace_id)
