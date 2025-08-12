"""
Module for parsing and organizing trace data from CSV files.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from pyama_qt.core.cell_feature import FEATURE_EXTRACTORS


@dataclass
class FeatureData:
    """Container for a single feature's data across all cells."""
    name: str
    cell_series: Dict[str, np.ndarray] = field(default_factory=dict)  # {cell_id: time_series}
    
    def get_series(self, cell_id: str) -> Optional[np.ndarray]:
        """Get time series for a specific cell."""
        return self.cell_series.get(cell_id)
    
    def add_series(self, cell_id: str, series: np.ndarray):
        """Add time series for a cell."""
        self.cell_series[cell_id] = series
    
    def clear(self):
        """Clear all series data."""
        self.cell_series.clear()


@dataclass
class PositionData:
    """Container for position data across all cells."""
    cell_positions: Dict[str, Dict[int, Tuple[float, float]]] = field(default_factory=dict)
    
    def get_positions(self, cell_id: str) -> Optional[Dict[int, Tuple[float, float]]]:
        """Get positions for a specific cell."""
        return self.cell_positions.get(cell_id)
    
    def add_position(self, cell_id: str, frame: int, position: Tuple[float, float]):
        """Add a position for a cell at a specific frame."""
        if cell_id not in self.cell_positions:
            self.cell_positions[cell_id] = {}
        self.cell_positions[cell_id][frame] = position
    
    def clear(self):
        """Clear all position data."""
        self.cell_positions.clear()


class TraceData:
    """Container for parsed trace data from CSV files."""
    
    def __init__(self):
        self.unique_ids: List[str] = []
        self.frames_axis: np.ndarray = np.array([])
        self.features: Dict[str, FeatureData] = {}  # {feature_name: FeatureData instance}
        self.positions: PositionData = PositionData()
        self.good_status: Dict[str, bool] = {}  # {cell_id: good/bad status}
        
    def clear(self):
        """Clear all data."""
        self.unique_ids.clear()
        self.frames_axis = np.array([])
        for feature in self.features.values():
            feature.clear()
        self.features.clear()
        self.positions.clear()
        self.good_status.clear()
    
    def get_trace_by_id(self, trace_id: str, trace_type: str = 'intensity_total') -> Optional[np.ndarray]:
        """
        Get a specific trace by ID and type.
        
        Args:
            trace_id: The cell/trace identifier
            trace_type: Type of trace (feature name like 'intensity_total', 'area', etc.)
            
        Returns:
            Numpy array of trace values, or None if not found
        """
        if trace_type in self.feature_series:
            return self.feature_series[trace_type].get(trace_id)
        return None
    
    def get_available_trace_types(self) -> List[str]:
        """Get list of available trace types in this dataset."""
        return self.available_features.copy()
    
    # Backward compatibility properties
    @property
    def intensity_series(self) -> Dict[str, np.ndarray]:
        """Backward compatibility for intensity_series."""
        return self.feature_series.get('intensity_total', {})
    
    @property
    def area_series(self) -> Dict[str, np.ndarray]:
        """Backward compatibility for area_series."""
        return self.feature_series.get('area', {})
    
    @property
    def has_intensity(self) -> bool:
        """Backward compatibility for has_intensity."""
        return 'intensity_total' in self.available_features
    
    @property
    def has_area(self) -> bool:
        """Backward compatibility for has_area."""
        return 'area' in self.available_features


class TraceParser:
    """Parser for extracting trace data from CSV files."""
    
    @staticmethod
    def parse_csv(csv_path: Path) -> TraceData:
        """
        Parse a CSV file and extract trace data.
        
        Args:
            csv_path: Path to the CSV file containing trace data
            
        Returns:
            TraceData object containing parsed information
        """
        data = TraceData()
        
        try:
            df = pd.read_csv(csv_path)
            
            # Check for required columns
            if 'cell_id' not in df.columns:
                return data  # Return empty data if no cell_id column
            
            # Extract unique IDs preserving order of appearance
            unique_ids_raw = []
            seen = set()
            for value in df['cell_id'].tolist():
                if value not in seen:
                    seen.add(value)
                    unique_ids_raw.append(value)
            data.unique_ids = [str(v) for v in unique_ids_raw]
            
            # Extract 'good' status if column exists (default to True if not present)
            if 'good' in df.columns:
                for cid in unique_ids_raw:
                    # Get the good status for this cell (use first occurrence if multiple)
                    cell_df = df[df['cell_id'] == cid]
                    if not cell_df.empty:
                        # Get the first good value for this cell
                        good_value = cell_df['good'].iloc[0]
                        # Convert to boolean (handle various input types)
                        data.good_status[str(cid)] = bool(good_value)
            else:
                # Default all cells to good=True if column doesn't exist
                for cid in unique_ids_raw:
                    data.good_status[str(cid)] = True
            
            # Check if we have frame column for time series
            if 'frame' not in df.columns:
                # Still extract position data if centroid feature is available
                if 'centroid' in FEATURE_EXTRACTORS:
                    TraceParser._extract_positions_only(df, data, unique_ids_raw)
                return data
            
            # Build frame axis
            try:
                max_frame = int(df['frame'].max())
            except Exception:
                max_frame = 0
            data.frames_axis = np.arange(max_frame + 1)
            
            # Loop through all features defined in FEATURE_EXTRACTORS
            for feature_name in FEATURE_EXTRACTORS:
                # Special handling for centroid (extracts to centroid_x and centroid_y)
                if feature_name == 'centroid':
                    if 'centroid_x' in df.columns and 'centroid_y' in df.columns:
                        TraceParser._extract_positions(df, data, unique_ids_raw)
                else:
                    # Regular features - check if column exists in dataframe
                    if feature_name in df.columns:
                        # Initialize series storage for this feature
                        data.feature_series[feature_name] = {}
                        data.available_features.append(feature_name)
                        
                        # Extract the series
                        TraceParser._extract_series(
                            df, unique_ids_raw, feature_name,
                            data.frames_axis, data.feature_series[feature_name]
                        )
            
        except Exception as e:
            # Return empty data on any parsing error
            print(f"Error parsing CSV: {e}")
            data.clear()
            
        return data
    
    
    @staticmethod
    def _extract_series(
        df: pd.DataFrame, 
        unique_ids: List,
        value_column: str,
        frames_axis: np.ndarray,
        output_dict: Dict[str, np.ndarray]
    ):
        """Extract time series data for each cell ID."""
        for cid in unique_ids:
            sub = df[df['cell_id'] == cid].sort_values('frame')
            
            # Create frame-to-value mapping
            frame_to_val = {}
            for rf, rv in zip(sub['frame'], sub[value_column]):
                try:
                    frame_to_val[int(rf)] = float(rv)
                except (ValueError, TypeError):
                    continue
            
            # Build aligned series with NaN for missing frames
            series = np.array([
                frame_to_val.get(fi, np.nan) for fi in frames_axis
            ])
            output_dict[str(cid)] = series
    
    @staticmethod
    def _extract_positions(
        df: pd.DataFrame,
        data: TraceData,
        unique_ids: List
    ):
        """Extract centroid position data for each cell."""
        # Columns already verified in caller
        if 'centroid_x' not in df.columns or 'centroid_y' not in df.columns:
            return
        
        for cid in unique_ids:
            sub = df[df['cell_id'] == cid]
            cell_positions = {}
            
            if 'frame' in df.columns:
                # Extract positions with frame information
                for _, row in sub.iterrows():
                    try:
                        frame = int(row['frame'])
                        cx = float(row['centroid_x'])
                        cy = float(row['centroid_y'])
                        cell_positions[frame] = (cx, cy)
                    except (ValueError, TypeError, KeyError):
                        continue
            else:
                # Single position per cell (no time series)
                try:
                    cx = float(sub['centroid_x'].iloc[0])
                    cy = float(sub['centroid_y'].iloc[0])
                    cell_positions[0] = (cx, cy)
                except (ValueError, TypeError, IndexError):
                    pass
            
            if cell_positions:
                data.positions_by_cell[str(cid)] = cell_positions
    
    @staticmethod
    def _extract_positions_only(
        df: pd.DataFrame,
        data: TraceData,
        unique_ids: List
    ):
        """Extract only position data when no frame column exists."""
        if 'centroid_x' not in df.columns or 'centroid_y' not in df.columns:
            return
        
        for cid in unique_ids:
            sub = df[df['cell_id'] == cid]
            cell_positions = {}
            
            for _, row in sub.iterrows():
                try:
                    cx = float(row['centroid_x'])
                    cy = float(row['centroid_y'])
                    # Use index as pseudo-frame when no frame column
                    cell_positions[0] = (cx, cy)
                    break  # Only take first position
                except (ValueError, TypeError):
                    continue
            
            if cell_positions:
                data.positions_by_cell[str(cid)] = cell_positions