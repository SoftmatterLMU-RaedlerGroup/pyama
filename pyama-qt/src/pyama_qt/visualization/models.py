"""Qt models exposing visualization data to the UI.

The visualization feature historically relied on VisualizationState, a
"""

import dataclasses
from dataclasses import dataclass
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, QAbstractTableModel, QModelIndex, Qt, Signal


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
        self.project_path: Any | None = None
        self.project_data: dict[str, Any] | None = None
        self.available_channels: list[str] = []
        self.status_message: str = ""
        self.error_message: str = ""
        self.is_loading = False

    def project_path(self) -> Any | None:
        return self.project_path

    def set_project_path(self, path: Any | None) -> None:
        if self.project_path == path:
            return
        self.project_path = path
        self.projectPathChanged.emit(path)

    def project_data(self) -> dict[str, Any] | None:
        return self.project_data

    def set_project_data(self, data: dict[str, Any] | None) -> None:
        if self.project_data == data:
            return
        self.project_data = data
        self.projectDataChanged.emit(data or {})

    def available_channels(self) -> list[str]:
        return self.available_channels

    def set_available_channels(self, channels: list[str]) -> None:
        if self.available_channels == channels:
            return
        self.available_channels = channels
        self.availableChannelsChanged.emit(channels)

    def status_message(self) -> str:
        return self.status_message

    def set_status_message(self, message: str) -> None:
        if self.status_message == message:
            return
        self.status_message = message
        self.statusMessageChanged.emit(message)

    def error_message(self) -> str:
        return self.error_message

    def set_error_message(self, message: str) -> None:
        if self.error_message == message:
            return
        self.error_message = message
        self.errorMessageChanged.emit(message)

    def is_loading(self) -> bool:
        return self.is_loading

    def set_is_loading(self, value: bool) -> None:
        if self.is_loading == value:
            return
        self.is_loading = value
        self.isLoadingChanged.emit(value)


class ImageCacheModel(QObject):
    """Model providing access to preprocessed image data per type."""

    cacheReset = Signal()
    dataTypeAdded = Signal(str)
    frameBoundsChanged = Signal(int, int)
    currentDataTypeChanged = Signal(str)
    currentFrameChanged = Signal(int)
    activeTraceChanged = Signal(str)
    tracePositionsChanged = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.image_cache: dict[str, np.ndarray] = {}
        self.current_data_type: str = ""
        self.current_frame_index = 0
        self.max_frame_index = 0
        self.trace_positions: dict[str, dict[int, tuple[float, float]]] = {}
        self.active_trace_id: str | None = None

    def available_types(self) -> list[str]:
        return list(self.image_cache.keys())

    def set_images(self, mapping: dict[str, np.ndarray]) -> None:
        self.image_cache = dict(mapping)
        self.max_frame_index = self._compute_max_frame()
        self.current_frame_index = 0
        next_type = next(iter(self.image_cache.keys()), "")
        if self.current_data_type != next_type:
            self.current_data_type = next_type
            self.currentDataTypeChanged.emit(self.current_data_type)
        self.frameBoundsChanged.emit(self.current_frame_index, self.max_frame_index)
        self.currentFrameChanged.emit(self.current_frame_index)
        self.cacheReset.emit()

    def update_image(self, key: str, data: np.ndarray) -> None:
        self.image_cache[key] = data
        if not self.current_data_type:
            self.current_data_type = key
            self.currentDataTypeChanged.emit(key)
        self.max_frame_index = self._compute_max_frame()
        self.frameBoundsChanged.emit(self.current_frame_index, self.max_frame_index)
        self.dataTypeAdded.emit(key)

    def remove_images(self) -> None:
        self.image_cache.clear()
        self.current_data_type = ""
        self.current_frame_index = 0
        self.max_frame_index = 0
        self.frameBoundsChanged.emit(0, 0)
        self.currentFrameChanged.emit(0)
        self.currentDataTypeChanged.emit("")
        self.cacheReset.emit()

    def current_data_type(self) -> str:
        return self.current_data_type

    def set_current_data_type(self, data_type: str) -> None:
        if self.current_data_type == data_type:
            return
        if data_type and data_type not in self.image_cache:
            return
        self.current_data_type = data_type
        self.currentDataTypeChanged.emit(data_type)

    def image_for_current_type(self) -> np.ndarray | None:
        if not self.current_data_type:
            return None
        return self.image_cache.get(self.current_data_type)

    def frame_bounds(self) -> tuple[int, int]:
        return (self.current_frame_index, self.max_frame_index)

    def set_current_frame(self, index: int) -> None:
        index = max(0, min(index, self.max_frame_index))
        if index == self.current_frame_index:
            return
        self.current_frame_index = index
        self.currentFrameChanged.emit(index)

    def set_max_frame_index(self, index: int) -> None:
        index = max(index, 0)
        if index == self.max_frame_index:
            return
        self.max_frame_index = index
        self.frameBoundsChanged.emit(self.current_frame_index, index)

    def trace_positions(self) -> dict[str, dict[int, tuple[float, float]]]:
        return self.trace_positions

    def set_trace_positions(
        self, positions: dict[str, dict[int, tuple[float, float]]]
    ) -> None:
        self.trace_positions = positions
        self.tracePositionsChanged.emit(positions)

    def set_active_trace(self, trace_id: str | None) -> None:
        if self.active_trace_id == trace_id:
            return
        self.active_trace_id = trace_id
        self.activeTraceChanged.emit(trace_id)

    def active_trace_id(self) -> str | None:
        return self.active_trace_id

    def _compute_max_frame(self) -> int:
        max_index = 0
        for array in self.image_cache.values():
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
        self.records: list[TraceRecord] = []
        self.headers = ["Good", "Trace ID"]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa:N802
        if parent.isValid():
            return 0
        return len(self.records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa:N802
        if parent.isValid():
            return 0
        return 2

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa:N802
        if not index.isValid():
            return None
        record = self.records[index.row()]

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
        record = self.records[index.row()]
        is_good = value == Qt.CheckState.Checked
        if record.is_good == is_good:
            return False
        self.records[index.row()] = dataclasses.replace(record, is_good=is_good)
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
            if 0 <= section < len(self.headers):
                return self.headers[section]
        return None

    def reset_traces(self, traces: list[TraceRecord]) -> None:
        self.beginResetModel()
        self.records = traces
        self.endResetModel()
        self.tracesReset.emit()

    def traces(self) -> list[TraceRecord]:
        return list(self.records)

    def set_good_state(self, trace_id: str, is_good: bool) -> None:
        for row, record in enumerate(self.records):
            if record.id == trace_id and record.is_good != is_good:
                index = self.index(row, 0)
                self.records[row] = dataclasses.replace(record, is_good=is_good)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
                break


class TraceFeatureModel(QObject):
    """Encapsulates trace feature time series for plotting."""

    availableFeaturesChanged = Signal(list)
    featureDataChanged = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.feature_series: dict[str, dict[str, np.ndarray]] = {}

    def available_features(self) -> list[str]:
        return list(self.feature_series.keys())

    def set_feature_series(self, series: dict[str, dict[str, np.ndarray]]) -> None:
        self.feature_series = series
        self.availableFeaturesChanged.emit(self.available_features())
        self.featureDataChanged.emit(series)

    def series_for(self, feature_name: str) -> dict[str, np.ndarray] | None:
        return self.feature_series.get(feature_name)


class TraceSelectionModel(QObject):
    """Tracks the currently active trace."""

    activeTraceChanged = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.active_trace_id: str | None = None

    def active_trace(self) -> str | None:
        return self.active_trace_id

    def set_active_trace(self, trace_id: str) -> None:
        if self.active_trace_id == trace_id:
            return
        self.active_trace_id = trace_id
        self.activeTraceChanged.emit(trace_id)
