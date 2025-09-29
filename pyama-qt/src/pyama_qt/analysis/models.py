from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Tuple, Dict

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, QAbstractTableModel, QModelIndex, Qt, Signal

from pyama_core.io.analysis_csv import load_analysis_csv

logger = logging.getLogger(__name__)


class AnalysisDataModel(QObject):
    """Model holding raw trace data and plot configuration."""

    rawDataChanged = Signal(pd.DataFrame)
    plotDataChanged = Signal(
        object
    )  # List[Tuple[np.ndarray, np.ndarray, Dict[str, Any]]]
    plotTitleChanged = Signal(str)
    selectedCellChanged = Signal(object)
    rawCsvPathChanged = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._raw_data: pd.DataFrame | None = None
        self._plot_data: List[Tuple[np.ndarray, np.ndarray, Dict[str, Any]]] | None = (
            None
        )
        self._plot_title: str = ""
        self._selected_cell: str | None = None
        self._raw_csv_path: Path | None = None

    def raw_data(self) -> pd.DataFrame | None:
        return self._raw_data

    def raw_csv_path(self) -> Path | None:
        return self._raw_csv_path

    def load_csv(self, path: Path) -> None:
        """Load CSV data and prepare initial plot."""
        logger.info("Loading analysis CSV from %s", path)
        try:
            # Use the analysis_csv loader which handles time unit parsing and conversion to hours
            df = load_analysis_csv(path)
            self._raw_data = df
            self.rawDataChanged.emit(df)
            self._raw_csv_path = path
            self.rawCsvPathChanged.emit(path)
            self._prepare_all_plot()
        except Exception:
            logger.exception("Failed to load analysis CSV")
            raise

    def prepare_all_plot(self) -> None:
        """Prepare plot data for all traces."""
        if self._raw_data is None:
            self._plot_data = None
            self._plot_title = ""
            self.plotDataChanged.emit(None)
            self.plotTitleChanged.emit("")
            return

        data = self._raw_data
        time_values = data.index.values
        lines: List[Tuple[np.ndarray, np.ndarray, Dict[str, Any]]] = []
        for col in data.columns:
            lines.append(
                (
                    time_values,
                    data[col].values,
                    {"color": "gray", "alpha": 0.2, "linewidth": 0.5},
                )
            )
        # Mean line
        if not data.empty:
            mean = data.mean(axis=1).values
            lines.append(
                (time_values, mean, {"color": "red", "linewidth": 2, "label": "Mean"})
            )
        self._plot_data = lines
        self._plot_title = f"All Sequences ({len(data.columns)} cells)"
        self.plotDataChanged.emit(lines)
        self.plotTitleChanged.emit(self._plot_title)

    def highlight_cell(self, cell_id: str) -> None:
        """Highlight a specific cell in the plot."""
        if self._raw_data is None or cell_id not in self._raw_data.columns:
            return
        self._selected_cell = cell_id
        self.selectedCellChanged.emit(cell_id)

        data = self._raw_data
        time_values = data.index.values
        lines: List[Tuple[np.ndarray, np.ndarray, Dict[str, Any]]] = []
        for other_id in data.columns:
            if other_id != cell_id:
                lines.append(
                    (
                        time_values,
                        data[other_id].values,
                        {"color": "gray", "alpha": 0.1, "linewidth": 0.5},
                    )
                )
        lines.append(
            (
                time_values,
                data[cell_id].values,
                {"color": "blue", "linewidth": 2, "label": f"Cell {cell_id}"},
            )
        )
        self._plot_data = lines
        self._plot_title = f"Cell {cell_id} Highlighted"
        self.plotDataChanged.emit(lines)
        self.plotTitleChanged.emit(self._plot_title)

    def get_random_cell(self) -> str | None:
        """Get a random cell ID."""
        if self._raw_data is None or self._raw_data.empty:
            return None
        return str(np.random.choice(self._raw_data.columns))

    def _prepare_all_plot(self) -> None:
        self.prepare_all_plot()


class FittingModel(QObject):
    """Model for fitting configuration and status."""

    isFittingChanged = Signal(bool)
    statusMessageChanged = Signal(str)
    errorMessageChanged = Signal(str)
    modelTypeChanged = Signal(str)
    modelParamsChanged = Signal(dict)
    modelBoundsChanged = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._is_fitting: bool = False
        self._status_message: str = ""
        self._error_message: str = ""
        self._model_type: str = "trivial"
        self._model_params: Dict[str, float] = {}
        self._model_bounds: Dict[str, tuple[float, float]] = {}

    def is_fitting(self) -> bool:
        return self._is_fitting

    def set_is_fitting(self, value: bool) -> None:
        if self._is_fitting == value:
            return
        self._is_fitting = value
        self.isFittingChanged.emit(value)

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

    def model_type(self) -> str:
        return self._model_type

    def set_model_type(self, model_type: str) -> None:
        if self._model_type == model_type:
            return
        self._model_type = model_type
        self.modelTypeChanged.emit(model_type)

    def model_params(self) -> Dict[str, float]:
        return self._model_params

    def set_model_params(self, params: Dict[str, float]) -> None:
        if self._model_params == params:
            return
        self._model_params = params
        self.modelParamsChanged.emit(params)

    def model_bounds(self) -> Dict[str, tuple[float, float]]:
        return self._model_bounds

    def set_model_bounds(self, bounds: Dict[str, tuple[float, float]]) -> None:
        if self._model_bounds == bounds:
            return
        self._model_bounds = bounds
        self.modelBoundsChanged.emit(bounds)


class FittedResultsModel(QAbstractTableModel):
    """Table model for fitted results DataFrame."""

    resultsReset = Signal()
    resultsChanged = Signal()  # For incremental updates if needed

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._df: pd.DataFrame | None = None
        self._headers: List[str] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if self._df is None:
            return 0
        return len(self._df)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if self._df is None:
            return 0
        return len(self._df.columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or self._df is None:
            return None

        if role in (Qt.DisplayRole, Qt.EditRole):
            value = self._df.iloc[index.row(), index.column()]
            return str(value) if pd.notna(value) else ""

        # Custom role for success (e.g., for coloring)
        if role == Qt.UserRole and index.column() == self._df.columns.get_loc(
            "success"
        ):
            return self._df.iloc[index.row()]["success"]

        # Custom role for r_squared
        if role == (Qt.UserRole + 1) and index.column() == self._df.columns.get_loc(
            "r_squared"
        ):
            return self._df.iloc[index.row()]["r_squared"]

        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        # Read-only for now; can add editing later if needed
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:
        if self._df is None:
            return None
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            elif orientation == Qt.Vertical:
                return str(section + 1)  # Row numbers
        return None

    def set_results(self, df: pd.DataFrame) -> None:
        """Set or update the fitted results DataFrame."""
        self.beginResetModel()
        self._df = df
        self._headers = list(df.columns) if df is not None else []
        self.endResetModel()
        self.resultsReset.emit()

    def results(self) -> pd.DataFrame | None:
        return self._df

    def load_from_csv(self, path: Path) -> None:
        """Load fitted results from CSV file."""
        try:
            df = pd.read_csv(path)
            self.set_results(df)
        except Exception as e:
            logger.warning("Failed to load fitted results: %s", e)

    def clear_results(self) -> None:
        """Clear all fitted results."""
        self.set_results(pd.DataFrame())
