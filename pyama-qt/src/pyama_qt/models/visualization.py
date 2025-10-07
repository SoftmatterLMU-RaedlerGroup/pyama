"""Qt models exposing visualization data to the UI.

The visualization feature historically relied on VisualizationState, a
"""

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


@dataclass
class PositionData:
    """Data structure for cell position information."""

    frames: np.ndarray
    position: dict[str, np.ndarray]  # {"x": array, "y": array}


@dataclass
class FeatureData:
    """Data structure for cell feature time series."""

    time_points: np.ndarray
    features: dict[
        str, np.ndarray
    ]  # {"feature_name1": array, "feature_name2": array, ...}


@dataclass
class CellQuality:
    """Data structure for cell quality information."""

    cell_id: int
    good: bool


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
        self._trace_positions: dict[str, PositionData] = {}
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

    def trace_positions(self) -> dict[str, PositionData]:
        return self._trace_positions

    def set_trace_positions(self, positions: dict[str, PositionData]) -> None:
        self._trace_positions = positions
        self.tracePositionsChanged.emit(positions)

    def get_position_data(self, trace_id: str) -> PositionData | None:
        """Get position data for a specific trace."""
        return self._trace_positions.get(trace_id)

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

                    if pos_df.empty:
                        continue

                    # Sort by frame to ensure proper order
                    pos_df_sorted = pos_df.sort_values("frame")

                    # Extract data as numpy arrays
                    frames = pos_df_sorted["frame"].values
                    x_positions = pos_df_sorted["position_x"].values
                    y_positions = pos_df_sorted["position_y"].values

                    # Create PositionData object
                    position_data = PositionData(
                        frames=frames, position={"x": x_positions, "y": y_positions}
                    )

                    positions[trace_id] = position_data

                except ValueError:
                    # Skip cells that don't have position data
                    continue

            # Update the model
            self.set_trace_positions(positions)
            return True

        except Exception as e:
            logger.error(f"Failed to load trace positions: {str(e)}")
            return False


# TraceRecord is now replaced by CellQuality dataclass defined above


class TraceTableModel(QAbstractTableModel):
    """Table model exposing trace IDs and good/bad selection."""

    GoodRole = Qt.ItemDataRole.UserRole + 1

    goodStateChanged = Signal(str, bool)
    tracesReset = Signal()
    csvLoadError = Signal(str)
    # Removed dataModified signal - save button should always be enabled

    def __init__(self) -> None:
        super().__init__()
        self._records: list[CellQuality] = []
        self._headers = ["Good", "Trace ID"]
        self._processing_df: pd.DataFrame | None = None
        self._original_csv_path: Path | None = None
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
                return str(record.cell_id)
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            return Qt.CheckState.Checked if record.good else Qt.CheckState.Unchecked
        if role == self.GoodRole:
            return record.good
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
        if record.good == is_good:
            return False
        self._records[index.row()] = dataclasses.replace(record, good=is_good)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        self.goodStateChanged.emit(str(record.cell_id), is_good)

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

    def reset_traces(self, traces: list[CellQuality]) -> None:
        self.beginResetModel()
        self._records = traces
        self.endResetModel()
        self.tracesReset.emit()
        # Removed modification tracking - save button should always be enabled

    def traces(self) -> list[CellQuality]:
        return list(self._records)

    def set_good_state(self, trace_id: str, is_good: bool) -> None:
        for row, record in enumerate(self._records):
            if str(record.cell_id) == trace_id and record.good != is_good:
                index = self.index(row, 0)
                self._records[row] = dataclasses.replace(record, good=is_good)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
                break

    def load_from_csv(self, csv_path: Path) -> bool:
        """Load trace data from a processing CSV file.

        If an inspected version of the file exists, it will be loaded instead.

        Args:
            csv_path: Path to the processing CSV file

        Returns:
            True if successful, False otherwise
        """
        # Check if an inspected version exists and prefer it
        inspected_path = self.get_inspected_csv_path(csv_path)
        actual_path = inspected_path if inspected_path.exists() else csv_path

        if not actual_path.exists():
            error_msg = f"CSV file does not exist: {actual_path}"
            logger.error(error_msg)
            self.csvLoadError.emit(error_msg)
            return False

        if actual_path != csv_path:
            logger.info(f"Loading inspected CSV file: {actual_path}")

        # Store the original path for saving purposes
        self._original_csv_path = csv_path

        try:
            # Load the dataframe using the processing CSV functions
            self._processing_df = get_dataframe(actual_path)

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

            # Convert to CellQuality objects
            traces = []
            for _, row in quality_df.iterrows():
                cell_id = int(row["cell"])
                is_good = bool(row["good"])
                traces.append(CellQuality(cell_id=cell_id, good=is_good))

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
                    {"cell": record.cell_id, "good": record.good}
                    for record in self._records
                ]
            )

            # Update the processing dataframe with new quality information
            updated_df = update_cell_quality(self._processing_df, updated_quality_df)

            # Use the stored original path if available, otherwise use the provided path
            # This prevents double _inspected suffixes
            base_path = (
                self._original_csv_path
                if self._original_csv_path
                else original_csv_path
            )

            # Create output path with _inspected suffix
            output_path = base_path.with_name(
                base_path.stem + "_inspected" + base_path.suffix
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
        # Use the stored original path if available, otherwise use the provided path
        # This prevents double _inspected suffixes
        base_path = (
            self._original_csv_path if self._original_csv_path else original_csv_path
        )

        return base_path.with_name(base_path.stem + "_inspected" + base_path.suffix)

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
        self._trace_features: dict[str, FeatureData] = {}  # trace_id -> FeatureData
        self._processing_df: pd.DataFrame | None = None

    def available_features(self) -> list[str]:
        """Get list of available feature names across all traces."""
        if not self._trace_features:
            return []
        # Get feature names from the first trace
        first_trace_id = next(iter(self._trace_features.keys()))
        return list(self._trace_features[first_trace_id].features.keys())

    def set_trace_features(self, trace_features: dict[str, FeatureData]) -> None:
        """Set feature data for all traces."""
        self._trace_features = trace_features
        self.availableFeaturesChanged.emit(self.available_features())
        self.featureDataChanged.emit(trace_features)

    def get_feature_data(self, trace_id: str) -> FeatureData | None:
        """Get complete feature data for a specific trace."""
        return self._trace_features.get(trace_id)

    def get_time_points(self, trace_id: str) -> np.ndarray | None:
        """Get time data for a specific trace."""
        feature_data = self._trace_features.get(trace_id)
        return feature_data.time_points if feature_data else None

    def get_feature_values(self, trace_id: str, feature_name: str) -> np.ndarray | None:
        """Get feature values for a specific trace and feature."""
        feature_data = self._trace_features.get(trace_id)
        if feature_data and feature_name in feature_data.features:
            return feature_data.features[feature_name]
        return None

    def load_trace_features(
        self, processing_df: pd.DataFrame, trace_ids: list[str]
    ) -> bool:
        """Load feature data for multiple traces from processing dataframe.

        Args:
            processing_df: The processing dataframe containing all cell data
            trace_ids: List of trace IDs to load features for

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get available features from the dataframe
            available_features = self.get_available_features_from_df(processing_df)

            loaded_count = 0
            for trace_id in trace_ids:
                try:
                    # Convert trace_id to int for cell lookup
                    cell_id = int(trace_id)

                    # Extract feature dataframe for this specific cell
                    feature_df = extract_cell_feature_dataframe(processing_df, cell_id)

                    if feature_df.empty:
                        logger.warning(f"No feature data found for trace {trace_id}")
                        continue

                    # Extract time data
                    time_points = (
                        feature_df["time"].values
                        if "time" in feature_df.columns
                        else np.array([])
                    )

                    # Extract feature data
                    features = {}
                    for col in feature_df.columns:
                        if col != "time" and col in available_features:
                            features[col] = feature_df[col].values

                    # Create FeatureData object for this trace
                    feature_data = FeatureData(
                        time_points=time_points, features=features
                    )
                    self._trace_features[trace_id] = feature_data

                    loaded_count += 1

                except ValueError as e:
                    logger.warning(f"Invalid trace ID {trace_id}: {str(e)}")
                    continue

            if loaded_count == 0:
                error_msg = f"No feature data could be loaded for any of the {len(trace_ids)} traces"
                logger.error(error_msg)
                self.featureLoadError.emit(error_msg)
                return False

            # Update the model signals
            self._processing_df = processing_df
            self.availableFeaturesChanged.emit(self.available_features())
            self.featureDataChanged.emit(self._trace_features)
            logger.info(
                f"Successfully loaded features for {loaded_count}/{len(trace_ids)} traces"
            )
            return True

        except Exception as e:
            error_msg = f"Failed to load features for traces {trace_ids}: {str(e)}"
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
        # Also exclude metadata columns that are not features
        metadata_cols = basic_cols + ["fov"]
        return [col for col in processing_df.columns if col not in metadata_cols]


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

    def time_units(self) -> str | None:
        """Get time units from project data."""
        if self._project_data:
            return self._project_data.get("time_units")
        return None

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

            # Extract available features and load them into the feature model
            available_features = trace_feature_model.get_available_features_from_df(
                processing_df
            )

            if available_features:
                # Get unique cell IDs
                unique_cells = processing_df["cell"].unique()

                # Create FeatureData objects for all traces
                trace_features = {}
                for cell_id in unique_cells:
                    trace_id = str(int(cell_id))
                    # Get data for this specific cell
                    cell_data = processing_df[processing_df["cell"] == cell_id]

                    if not cell_data.empty:
                        # Sort by time to ensure proper order
                        cell_data_sorted = cell_data.sort_values("time")

                        # Extract time data
                        time_points = cell_data_sorted["time"].values

                        # Extract feature data
                        features = {}
                        for feature_name in available_features:
                            if feature_name in cell_data_sorted.columns:
                                features[feature_name] = cell_data_sorted[
                                    feature_name
                                ].values

                        # Create FeatureData object
                        feature_data = FeatureData(
                            time_points=time_points, features=features
                        )
                        trace_features[trace_id] = feature_data

                # Set the feature data in the model
                if trace_features:
                    trace_feature_model.set_trace_features(trace_features)
                    logger.info(
                        f"Successfully loaded feature data for {len(trace_features)} traces with {len(available_features)} features"
                    )
                else:
                    # Fallback: just emit available features without data
                    trace_feature_model.availableFeaturesChanged.emit(
                        available_features
                    )
                    logger.warning(
                        "No feature data could be extracted from processing dataframe"
                    )
            else:
                logger.warning("No available features found in processing dataframe")

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
