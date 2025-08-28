"""
Module for parsing and organizing trace data from CSV files.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from pyama_core.analysis.features import FEATURE_EXTRACTORS
from pyama_core.io.processing_csv import ProcessingCSVLoader


@dataclass
class FeatureData:
    name: str
    cell_series: dict[str, np.ndarray] = field(default_factory=dict)

    def get_series(self, cell_id: str) -> np.ndarray | None:
        return self.cell_series.get(cell_id)

    def add_series(self, cell_id: str, series: np.ndarray):
        self.cell_series[cell_id] = series

    def clear(self):
        self.cell_series.clear()


@dataclass
class PositionData:
    cell_positions: dict[str, dict[int, tuple[float, float]]] = field(default_factory=dict)

    def get_positions(self, cell_id: str) -> dict[int, tuple[float, float]] | None:
        return self.cell_positions.get(cell_id)

    def add_position(self, cell_id: str, frame: int, position: tuple[float, float]):
        if cell_id not in self.cell_positions:
            self.cell_positions[cell_id] = {}
        self.cell_positions[cell_id][frame] = position

    def clear(self):
        self.cell_positions.clear()


class TraceData:
    def __init__(self):
        self.unique_ids: list[str] = []
        self.frames_axis: np.ndarray = np.array([])
        self.features: dict[str, FeatureData] = {}
        self.positions: PositionData = PositionData()
        self.good_status: dict[str, bool] = {}
        self.feature_series: dict[str, dict[str, np.ndarray]] = {}
        self.available_features: list[str] = []

    def clear(self):
        self.unique_ids.clear()
        self.frames_axis = np.array([])
        for feature in self.features.values():
            feature.clear()
        self.features.clear()
        self.positions.clear()
        self.good_status.clear()
        self.feature_series.clear()
        self.available_features.clear()

    def get_trace_by_id(self, trace_id: str, trace_type: str = "intensity_total") -> np.ndarray | None:
        if trace_type in self.feature_series:
            return self.feature_series[trace_type].get(trace_id)
        return None

    def get_available_trace_types(self) -> list[str]:
        return self.available_features.copy()

    @property
    def intensity_series(self) -> dict[str, np.ndarray]:
        return self.feature_series.get("intensity_total", {})

    @property
    def area_series(self) -> dict[str, np.ndarray]:
        return self.feature_series.get("area", {})

    @property
    def has_intensity(self) -> bool:
        return "intensity_total" in self.available_features

    @property
    def has_area(self) -> bool:
        return "area" in self.available_features


class TraceParser:
    @staticmethod
    def parse_csv(csv_path: Path) -> TraceData:
        data = TraceData()
        try:
            # Use ProcessingCSVLoader for consistent CSV loading and validation
            loader = ProcessingCSVLoader()
            df = loader.load_fov_traces(csv_path)
            
            if "cell_id" not in df.columns:
                return data

            unique_ids_raw = []
            seen = set()
            for value in df["cell_id"].tolist():
                if value not in seen:
                    seen.add(value)
                    unique_ids_raw.append(value)
            data.unique_ids = [str(v) for v in unique_ids_raw]

            if "good" in df.columns:
                for cid in unique_ids_raw:
                    cell_df = df[df["cell_id"] == cid]
                    if not cell_df.empty:
                        good_value = cell_df["good"].iloc[0]
                        data.good_status[str(cid)] = bool(good_value)
            else:
                for cid in unique_ids_raw:
                    data.good_status[str(cid)] = True

            if "frame" not in df.columns:
                if "position_x" in df.columns and "position_y" in df.columns:
                    TraceParser._extract_positions_only(df, data, unique_ids_raw)
                return data

            try:
                max_frame = int(df["frame"].max())
            except Exception:
                max_frame = 0
            data.frames_axis = np.arange(max_frame + 1)

            if "position_x" in df.columns and "position_y" in df.columns:
                TraceParser._extract_positions(df, data, unique_ids_raw)

            for feature_name in FEATURE_EXTRACTORS:
                if feature_name in df.columns:
                    data.feature_series[feature_name] = {}
                    data.available_features.append(feature_name)
                    TraceParser._extract_series(
                        df,
                        unique_ids_raw,
                        feature_name,
                        data.frames_axis,
                        data.feature_series[feature_name],
                    )
        except Exception:
            data.clear()
        return data

    @staticmethod
    def _extract_series(
        df: pd.DataFrame,
        unique_ids: list,
        value_column: str,
        frames_axis: np.ndarray,
        output_dict: dict[str, np.ndarray],
    ):
        for cid in unique_ids:
            sub = df[df["cell_id"] == cid].sort_values("frame")
            frame_to_val = {}
            for rf, rv in zip(sub["frame"], sub[value_column]):
                try:
                    frame_to_val[int(rf)] = float(rv)
                except (ValueError, TypeError):
                    continue
            series = np.array([frame_to_val.get(fi, np.nan) for fi in frames_axis])
            output_dict[str(cid)] = series

    @staticmethod
    def _extract_positions(df: pd.DataFrame, data: TraceData, unique_ids: list):
        if "position_x" not in df.columns or "position_y" not in df.columns:
            return
        for cid in unique_ids:
            sub = df[df["cell_id"] == cid]
            cell_positions = {}
            if "frame" in df.columns:
                for _, row in sub.iterrows():
                    try:
                        frame = int(row["frame"])
                        px = float(row["position_x"])
                        py = float(row["position_y"])
                        cell_positions[frame] = (px, py)
                    except (ValueError, TypeError, KeyError):
                        continue
            else:
                try:
                    px = float(sub["position_x"].iloc[0])
                    py = float(sub["position_y"].iloc[0])
                    cell_positions[0] = (px, py)
                except (ValueError, TypeError, IndexError):
                    pass
            if cell_positions:
                data.positions.cell_positions[str(cid)] = cell_positions

    @staticmethod
    def _extract_positions_only(df: pd.DataFrame, data: TraceData, unique_ids: list):
        if "position_x" not in df.columns or "position_y" not in df.columns:
            return
        for cid in unique_ids:
            sub = df[df["cell_id"] == cid]
            cell_positions = {}
            for _, row in sub.iterrows():
                try:
                    px = float(row["position_x"])
                    py = float(row["position_y"])
                    cell_positions[0] = (px, py)
                    break
                except (ValueError, TypeError):
                    continue
            if cell_positions:
                data.positions.cell_positions[str(cid)] = cell_positions


