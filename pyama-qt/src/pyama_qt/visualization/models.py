"""Qt models exposing visualization data to the UI.

The visualization feature historically relied on VisualizationState, a
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, QAbstractTableModel, QModelIndex, Qt, Signal
from dataclasses import dataclass

# Import the refactored processing CSV functions
from pyama_core.io.processing_csv import (
    get_dataframe,
    extract_cell_quality_dataframe,
    extract_cell_feature_dataframe,
    extract_cell_position_dataframe,
    write_dataframe,
    update_cell_quality,
)


# Import the Result class to get field definitions
from pyama_core.processing.extraction.trace import Result

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

    def load_processing_csv(
        self,
        csv_path: Path,
        trace_table_model: TraceTableModel,
        trace_feature_model: TraceFeatureModel,
        image_cache_model: ImageCacheModel,
    ) -> bool:
        """Load processing data from CSV file into all relevant models.

        Args:
            csv_path: Path to the processing CSV file
            trace_table_model: TraceTableModel to populate
            trace_feature_model: TraceFeatureModel to populate
            image_cache_model: ImageCacheModel to populate

        Returns:
            True if successful, False otherwise
        """
        self.set_is_loading(True)
        self.set_status_message("Loading processing CSV...")

        try:
            # Load data into trace table model
            if not trace_table_model.load_from_csv(csv_path):
                self.set_error_message("Failed to load trace data from CSV")
                return False

            # Get the processing dataframe from trace table model
            processing_df = trace_table_model.get_processing_dataframe()
            if processing_df is None:
                self.set_error_message("No processing data available")
                return False

            # Load trace positions into image cache model
            if not image_cache_model.load_trace_positions(processing_df):
                logger.warning("Failed to load trace positions")
                # Continue anyway, this is not critical

            # Extract available features and update feature model
            available_features = trace_feature_model.get_available_features_from_df(
                processing_df
            )
            trace_feature_model.availableFeaturesChanged.emit(available_features)

            self.set_status_message(
                f"Successfully loaded {len(available_features)} features from {len(processing_df)} records"
            )
            return True

        except Exception as e:
            error_msg = f"Error loading processing CSV: {str(e)}"
            logger.error(error_msg)
            self.set_error_message(error_msg)
            return False
        finally:
            self.set_is_loading(False)

    def get_inspected_csv_path(self, original_csv_path: Path) -> Path:
        """Get the path where the inspected CSV would be saved.

        Args:
            original_csv_path: Path to the original CSV file

        Returns:
            Path where the inspected CSV would be saved
        """
        return original_csv_path.with_name(
            original_csv_path.stem + "_inspected" + original_csv_path.suffix
        )


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

    def load_trace_positions(self, processing_df: pd.DataFrame) -> bool:
        """Load trace positions from processing dataframe.

        Args:
            processing_df: The processing dataframe containing cell position data

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get unique trace IDs from the dataframe
            unique_cells = processing_df["cell"].unique()

            # Build position data for each trace
            positions = {}
            for cell_id in unique_cells:
                trace_id = str(int(cell_id))
                try:
                    # Extract position dataframe for this cell
                    pos_df = extract_cell_position_dataframe(
                        processing_df, int(cell_id)
                    )

                    # Convert to the expected format (frame -> (x, y) mapping)
                    frame_positions = {}
                    for _, row in pos_df.iterrows():
                        frame = int(row["frame"])
                        x_pos = float(row["position_x"])
                        y_pos = float(row["position_y"])
                        frame_positions[frame] = (x_pos, y_pos)

                    positions[trace_id] = frame_positions

                except ValueError:
                    # Skip cells that don't have position data
                    continue

            # Update the model
            self.set_trace_positions(positions)
            return True

        except Exception as e:
            logger.error(f"Failed to load trace positions: {str(e)}")
            return False


@dataclass
class TraceRecord:
    id: str
    is_good: bool


class TraceTableModel(QAbstractTableModel):
    """Table model exposing trace IDs and good/bad selection."""

    GoodRole = Qt.ItemDataRole.UserRole + 1

    goodStateChanged = Signal(str, bool)
    tracesReset = Signal()
    csvLoadError = Signal(str)
    # Removed dataModified signal - save button should always be enabled

    def __init__(self) -> None:
        super().__init__()
        self._records: list[TraceRecord] = []
        self._headers = ["Good", "Trace ID"]
        self._processing_df: pd.DataFrame | None = None
        # Removed _is_modified flag - save button should always be enabled

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

        # Removed modification tracking - save button should always be enabled

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
        # Removed modification tracking - save button should always be enabled

    def traces(self) -> list[TraceRecord]:
        return list(self._records)

    def set_good_state(self, trace_id: str, is_good: bool) -> None:
        for row, record in enumerate(self._records):
            if record.id == trace_id and record.is_good != is_good:
                index = self.index(row, 0)
                self._records[row] = dataclasses.replace(record, is_good=is_good)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
                break

    def load_from_csv(self, csv_path: Path) -> bool:
        """Load trace data from a processing CSV file.

        Args:
            csv_path: Path to the processing CSV file

        Returns:
            True if successful, False otherwise
        """
        if not csv_path.exists():
            error_msg = f"CSV file does not exist: {csv_path}"
            logger.error(error_msg)
            self.csvLoadError.emit(error_msg)
            return False

        try:
            # Load the dataframe using the processing CSV functions
            self._processing_df = get_dataframe(csv_path)

            # Validate all Result fields exist
            basic_cols = [f.name for f in Result.__dataclass_fields__.values()]
            if not set(basic_cols).issubset(self._processing_df.columns):
                missing = set(basic_cols) - set(self._processing_df.columns)
                error_msg = f"Missing required columns in CSV: {missing}"
                logger.error(error_msg)
                self.csvLoadError.emit(error_msg)
                return False

            # Extract cell quality information
            quality_df = extract_cell_quality_dataframe(self._processing_df)

            # Validate we got data
            if quality_df.empty:
                error_msg = "No valid cell quality data found in CSV"
                logger.error(error_msg)
                self.csvLoadError.emit(error_msg)
                return False

            # Convert to TraceRecord objects
            traces = []
            for _, row in quality_df.iterrows():
                trace_id = str(int(row["cell"]))
                is_good = bool(row["good"])
                traces.append(TraceRecord(id=trace_id, is_good=is_good))

            # Validate we have traces
            if not traces:
                error_msg = "No valid traces found in CSV"
                logger.error(error_msg)
                self.csvLoadError.emit(error_msg)
                return False

            # Reset the model with new data
            self.reset_traces(traces)
            logger.info(f"Successfully loaded {len(traces)} traces from CSV")
            return True

        except Exception as e:
            error_msg = f"Failed to load CSV file: {str(e)}"
            logger.error(error_msg)
            self.csvLoadError.emit(error_msg)
            return False

    def get_processing_dataframe(self) -> pd.DataFrame | None:
        """Get the underlying processing dataframe."""
        return self._processing_df

    def save_inspected_data(self, original_csv_path: Path) -> bool:
        """Save the current trace quality modifications to a new CSV file with _inspected suffix.

        Args:
            original_csv_path: Path to the original CSV file

        Returns:
            True if successful, False otherwise
        """
        if self._processing_df is None:
            logger.error("No processing dataframe available to save")
            return False

        try:
            # Create updated cell quality dataframe from current trace records
            updated_quality_df = pd.DataFrame(
                [
                    {"cell": int(record.id), "good": record.is_good}
                    for record in self._records
                ]
            )

            # Update the processing dataframe with new quality information
            updated_df = update_cell_quality(self._processing_df, updated_quality_df)

            # Create output path with _inspected suffix
            output_path = original_csv_path.with_name(
                original_csv_path.stem + "_inspected" + original_csv_path.suffix
            )

            # Write the updated dataframe to CSV
            write_dataframe(updated_df, output_path)

            logger.info(f"Successfully saved inspected data to: {output_path}")
            return True

        except Exception as e:
            error_msg = f"Failed to save inspected data: {str(e)}"
            logger.error(error_msg)
            return False

    def get_inspected_csv_path(self, original_csv_path: Path) -> Path:
        """Get the path where the inspected CSV would be saved.

        Args:
            original_csv_path: Path to the original CSV file

        Returns:
            Path where the inspected CSV would be saved
        """
        return original_csv_path.with_name(
            original_csv_path.stem + "_inspected" + original_csv_path.suffix
        )

    def is_modified(self) -> bool:
        """Check if the trace data has been modified.

        Note: Always returns False since save button should always be enabled.
        """
        return False  # Save button should always be enabled


class TraceFeatureModel(QObject):
    """Encapsulates trace feature time series for plotting."""

    availableFeaturesChanged = Signal(list)
    featureDataChanged = Signal(dict)
    featureLoadError = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._feature_series: dict[str, dict[str, np.ndarray]] = {}
        self._processing_df: pd.DataFrame | None = None

    def available_features(self) -> list[str]:
        return list(self._feature_series.keys())

    def set_feature_series(self, series: dict[str, dict[str, np.ndarray]]) -> None:
        self._feature_series = series
        self.availableFeaturesChanged.emit(self.available_features())
        self.featureDataChanged.emit(series)

    def series_for(self, feature_name: str) -> dict[str, np.ndarray] | None:
        return self._feature_series.get(feature_name)

    def load_trace_features(self, processing_df: pd.DataFrame, trace_id: str) -> bool:
        """Load feature data for a specific trace from processing dataframe.

        Args:
            processing_df: The processing dataframe containing all cell data
            trace_id: The ID of the trace to load features for

        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert trace_id to int for cell lookup
            cell_id = int(trace_id)

            # Extract feature dataframe for this cell
            feature_df = extract_cell_feature_dataframe(processing_df, cell_id)

            # Convert to the expected format (dict of time series)
            feature_series = {}

            # Get time array
            time_array = feature_df["time"].values

            # Process each feature column
            for col in feature_df.columns:
                if col != "time":
                    feature_series[col] = {
                        "time": time_array,
                        "values": feature_df[col].values,
                    }

            # Update the model
            self.set_feature_series(feature_series)
            self._processing_df = processing_df
            return True

        except Exception as e:
            error_msg = f"Failed to load features for trace {trace_id}: {str(e)}"
            logger.error(error_msg)
            self.featureLoadError.emit(error_msg)
            return False

    def get_available_features_from_df(self, processing_df: pd.DataFrame) -> list[str]:
        """Get available feature columns from a processing dataframe.

        Args:
            processing_df: The processing dataframe

        Returns:
            List of available feature column names
        """
        basic_cols = [f.name for f in Result.__dataclass_fields__.values()]
        return [col for col in processing_df.columns if col not in basic_cols]


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
