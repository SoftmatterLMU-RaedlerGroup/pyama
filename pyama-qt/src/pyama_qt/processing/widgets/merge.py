from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, TypedDict

from PySide6 import QtCore, QtWidgets
import yaml


class TraceCsvRow(TypedDict, total=False):
    """Row structure for trace CSV files with dynamic feature columns."""

    fov: int
    cell: int
    time: float
    good: bool
    position_x: float
    position_y: float
    # Dynamic feature columns (e.g., intensity_total, area)
    # Will be populated based on available features


class SampleTable(QtWidgets.QTableWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["Sample Name", "FOVs (e.g., 0-5, 7, 9-11)"])
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)

    def add_empty_row(self) -> None:
        row = self.rowCount()
        self.insertRow(row)
        name_item = QtWidgets.QTableWidgetItem("")
        fovs_item = QtWidgets.QTableWidgetItem("")
        name_item.setFlags(name_item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
        fovs_item.setFlags(fovs_item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, 0, name_item)
        self.setItem(row, 1, fovs_item)
        self.setCurrentCell(row, 0)

    def add_row(self, name: str, fovs_text: str) -> None:
        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
        self.setItem(row, 1, QtWidgets.QTableWidgetItem(fovs_text))

    def remove_selected_row(self) -> None:
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return
        for idx in sorted(indexes, key=lambda i: i.row(), reverse=True):
            self.removeRow(idx.row())

    def to_samples(self) -> List[Dict[str, Any]]:
        """Convert table data to samples list with validation."""
        samples = []
        seen_names = set()

        for row in range(self.rowCount()):
            name_item = self.item(row, 0)
            fovs_item = self.item(row, 1)
            name = (name_item.text() if name_item else "").strip()
            fovs_text = (fovs_item.text() if fovs_item else "").strip()

            # Validate name
            if not name:
                raise ValueError(f"Row {row + 1}: Sample name is required")
            if name in seen_names:
                raise ValueError(f"Row {row + 1}: Duplicate sample name '{name}'")
            seen_names.add(name)

            # Parse and validate FOVs
            if not fovs_text:
                raise ValueError(
                    f"Row {row + 1} ('{name}'): At least one FOV is required"
                )

            try:
                fovs = parse_fov_range(fovs_text)
            except ValueError as e:
                raise ValueError(f"Row {row + 1} ('{name}'): {e}") from e

            if not fovs:
                raise ValueError(
                    f"Row {row + 1} ('{name}'): At least one FOV is required"
                )

            samples.append({"name": name, "fovs": fovs})

        return samples

    def load_samples(self, samples: List[Dict[str, Any]]) -> None:
        """Load samples data into the table."""
        self.setRowCount(0)
        for sample in samples:
            name = str(sample.get("name", ""))
            fovs_val = sample.get("fovs", [])

            if isinstance(fovs_val, list):
                fovs_text = ", ".join(str(int(v)) for v in fovs_val)
            elif isinstance(fovs_val, str):
                fovs_text = fovs_val
            else:
                fovs_text = ""

            self.add_row(name, fovs_text)


def parse_bool(s: str) -> bool:
    """Parse string to boolean (case-insensitive 'true')."""
    return str(s).strip().lower() == "true"


def get_available_features() -> List[str]:
    """Get list of available feature extractors."""
    try:
        from pyama_core.processing.extraction.feature import list_features

        return list_features()
    except ImportError:
        # Fallback for testing
        return ["intensity_total", "area"]


def read_yaml_config(path: Path) -> Dict[str, Any]:
    """Read YAML config file with samples specification."""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        if not isinstance(data, dict) or "samples" not in data:
            raise ValueError("YAML must contain a top-level 'samples' key")
        return data


def read_processing_results(path: Path) -> Dict[str, Any]:
    """Read processing results YAML file."""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("Processing results file must be a valid YAML dictionary")
        return data


def read_trace_csv(path: Path) -> List[TraceCsvRow]:
    """Read trace CSV file with dynamic feature columns."""
    rows: List[TraceCsvRow] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required_fields = {"fov", "cell", "time", "good"}
        fieldnames = set(reader.fieldnames or [])
        missing = required_fields - fieldnames
        if missing:
            raise ValueError(
                f"CSV {path} is missing required fields: {sorted(missing)}"
            )

        for r in reader:
            row: TraceCsvRow = {
                "fov": int(r["fov"]),
                "time": float(r["time"]),
                "cell": int(r["cell"]),
                "good": parse_bool(r["good"]),
            }

            # Add optional position fields if available
            if "position_x" in r:
                row["position_x"] = float(r["position_x"])
            if "position_y" in r:
                row["position_y"] = float(r["position_y"])

            # Add all feature columns dynamically
            for field in fieldnames:
                if field not in {
                    "fov",
                    "cell",
                    "time",
                    "good",
                    "position_x",
                    "position_y",
                }:
                    # This is a feature column
                    val_str = r[field].strip()
                    if val_str == "" or val_str.lower() == "nan":
                        row[field] = float("nan")
                    else:
                        row[field] = float(val_str)

            rows.append(row)
    return rows


@dataclass(frozen=True)
class FeatureMaps:
    """Maps for feature data organized by (time, cell) tuples."""

    features: Dict[
        str, Dict[Tuple[float, int], float]
    ]  # feature_name -> (time, cell) -> value
    times: List[float]
    cells: List[int]


def parse_fov_range(text: str) -> List[int]:
    """Parse FOV specification like '0-5, 7, 9-11' into list of integers."""
    if not text.strip():
        return []

    normalized = text.replace(" ", "")
    if ";" in normalized:
        raise ValueError("Use commas to separate FOVs (semicolons not allowed)")

    fovs = []
    parts = [p for p in normalized.split(",") if p]

    for part in parts:
        if "-" in part:
            try:
                start_str, end_str = part.split("-", 1)
                if not start_str or not end_str:
                    raise ValueError(f"Invalid range '{part}': missing start or end")

                start, end = int(start_str), int(end_str)
                if start < 0 or end < 0:
                    raise ValueError(
                        f"Invalid range '{part}': negative values not allowed"
                    )
                if start > end:
                    raise ValueError(f"Invalid range '{part}': start must be <= end")

                fovs.extend(range(start, end + 1))
            except ValueError as e:
                if "invalid literal" in str(e):
                    raise ValueError(f"Invalid range '{part}': must be integers") from e
                raise
        else:
            try:
                fov = int(part)
                if fov < 0:
                    raise ValueError(f"FOV '{part}' must be >= 0")
                fovs.append(fov)
            except ValueError:
                raise ValueError(f"FOV '{part}' must be a non-negative integer")

    return sorted(set(fovs))


def build_feature_maps(
    rows: List[TraceCsvRow], feature_names: List[str]
) -> FeatureMaps:
    """Build feature maps from trace CSV rows."""
    feature_maps: Dict[str, Dict[Tuple[float, int], float]] = {}
    times_set = set()
    cells_set = set()

    # Initialize feature maps
    for feature_name in feature_names:
        feature_maps[feature_name] = {}

    # Process rows
    for r in rows:
        key = (r["time"], r["cell"])
        times_set.add(r["time"])
        cells_set.add(r["cell"])

        # Store feature values
        for feature_name in feature_names:
            if feature_name in r:
                feature_maps[feature_name][key] = r[feature_name]

    times = sorted(times_set)
    cells = sorted(cells_set)
    return FeatureMaps(feature_maps, times, cells)


def get_all_times(
    feature_maps_by_fov: Dict[int, FeatureMaps], fovs: List[int]
) -> List[float]:
    """Get all unique time points across the specified FOVs."""
    all_times = set()
    for fov in fovs:
        if fov in feature_maps_by_fov:
            all_times.update(feature_maps_by_fov[fov].times)
    return sorted(all_times)


def parse_fovs_field(fovs_value) -> List[int]:
    """Parse FOV specification from various input types."""
    if isinstance(fovs_value, list):
        fovs = []
        for v in fovs_value:
            try:
                fov = int(v)
                if fov < 0:
                    raise ValueError(f"FOV value '{fov}' must be >= 0")
                fovs.append(fov)
            except (ValueError, TypeError) as e:
                raise ValueError(f"FOV value '{v}' is not a valid integer") from e
        return sorted(set(fovs))

    elif isinstance(fovs_value, str):
        if not fovs_value.strip():
            raise ValueError("FOV specification cannot be empty")
        return parse_fov_range(fovs_value)

    else:
        raise ValueError(
            "FOV spec must be a list of integers or a comma-separated string"
        )


def write_feature_csv(
    out_path: Path,
    times: List[float],
    fovs: List[int],
    feature_name: str,
    feature_maps_by_fov: Dict[int, FeatureMaps],
    channel: int,
    time_units: Optional[str] = None,
) -> None:
    """Write feature data to CSV file in wide format."""
    # Build column names
    column_names = ["time"]
    cells_by_fov = {}

    for fov in fovs:
        feature_map = feature_maps_by_fov.get(fov)
        if feature_map is None:
            cells_by_fov[fov] = []
        else:
            cells_by_fov[fov] = feature_map.cells

        for cell in cells_by_fov[fov]:
            column_names.append(f"fov_{fov:03d}_cell_{cell:03d}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        # Write time units comment if available
        if time_units:
            f.write(f"# Time units: {time_units}\n")

        writer = csv.DictWriter(f, fieldnames=column_names)
        writer.writeheader()

        # Write data rows
        for t in times:
            row = {"time": t}
            for fov in fovs:
                fm = feature_maps_by_fov.get(fov)
                cells = cells_by_fov.get(fov, [])

                for cell in cells:
                    column_key = f"fov_{fov:03d}_cell_{cell:03d}"

                    if fm is None or feature_name not in fm.features:
                        row[column_key] = ""
                        continue

                    feature_map = fm.features[feature_name]
                    val = feature_map.get((t, cell))

                    if val is None:
                        row[column_key] = ""
                    elif isinstance(val, float) and math.isnan(val):
                        row[column_key] = "NaN"
                    else:
                        row[column_key] = val

            writer.writerow(row)


def run_merge(
    root: Path,
    sample_yaml: Optional[Path] = None,
    processing_results: Optional[Path] = None,
    input_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> None:
    """Run the merge process to combine FOV data into sample-specific CSV files."""
    input_dir = input_dir or (root / "data")
    output_dir = output_dir or (root / "processed")
    config_path = sample_yaml or (input_dir / "sample.yaml")
    results_path = processing_results or (input_dir / "processing_results.yaml")

    # Load configuration
    config = read_yaml_config(config_path)
    samples = config["samples"]

    # Load processing results to get file paths and channels
    proc_results = read_processing_results(results_path)
    channels = proc_results.get("channels", {}).get("fl", [])
    if not channels:
        raise ValueError("No fluorescence channels found in processing results")

    # Get time units from processing results
    time_units = proc_results.get("time_units")

    # Get available features
    available_features = get_available_features()

    # Find all required FOVs
    all_fovs = set()
    for sample in samples:
        fovs = parse_fovs_field(sample.get("fovs", []))
        all_fovs.update(fovs)

    # Load feature maps for all FOVs and channels
    feature_maps_by_fov_channel = {}  # (fov, channel) -> FeatureMaps

    for fov in sorted(all_fovs):
        for channel in channels:
            # Find trace CSV file for this FOV and channel
            csv_path = _find_trace_csv_file(input_dir, fov, channel)
            if csv_path is None:
                print(f"Warning: No trace CSV found for FOV {fov}, channel {channel}")
                continue

            if not csv_path.exists():
                print(f"Warning: CSV file does not exist: {csv_path}")
                continue

            rows = read_trace_csv(csv_path)
            feature_maps_by_fov_channel[(fov, channel)] = build_feature_maps(
                rows, available_features
            )

    # Process each sample
    output_dir.mkdir(parents=True, exist_ok=True)
    for sample in samples:
        sample_name = sample["name"]
        sample_fovs = parse_fovs_field(sample.get("fovs", []))

        # Process each channel
        for channel in channels:
            # Get feature maps for this channel
            channel_feature_maps = {}
            for fov in sample_fovs:
                if (fov, channel) in feature_maps_by_fov_channel:
                    channel_feature_maps[fov] = feature_maps_by_fov_channel[
                        (fov, channel)
                    ]

            if not channel_feature_maps:
                print(
                    f"Warning: No data found for sample {sample_name}, channel {channel}"
                )
                continue

            times = get_all_times(channel_feature_maps, sample_fovs)

            # Write feature files for each available feature
            for feature_name in available_features:
                output_filename = f"{sample_name}_{feature_name}_ch_{channel}.csv"
                output_path = output_dir / output_filename
                write_feature_csv(
                    output_path,
                    times,
                    sample_fovs,
                    feature_name,
                    channel_feature_maps,
                    channel,
                    time_units,
                )


def _find_trace_csv_file(input_dir: Path, fov: int, channel: int) -> Optional[Path]:
    """Find the trace CSV file for a specific FOV and channel."""
    # Look for files matching the pattern: *fov_{fov:03d}*traces_ch_{channel}.csv
    pattern = f"*fov_{fov:03d}*traces_ch_{channel}.csv"
    matches = list(input_dir.rglob(pattern))

    if matches:
        return matches[0]

    return None


class MergePanel(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
        self._initialize_fields()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        main_layout = QtWidgets.QVBoxLayout(self)

        # Create the two main sections
        assign_group = self._create_assign_group()
        merge_group = self._create_merge_group()

        # Add to main layout with equal stretch
        main_layout.addWidget(assign_group, 1)
        main_layout.addWidget(merge_group, 1)

    def _create_assign_group(self) -> QtWidgets.QGroupBox:
        """Create the FOV assignment section."""
        group = QtWidgets.QGroupBox("Assign FOVs")
        layout = QtWidgets.QVBoxLayout(group)

        self.table = SampleTable()

        # Create buttons
        self.add_btn = QtWidgets.QPushButton("Add Sample")
        self.remove_btn = QtWidgets.QPushButton("Remove Selected")
        self.load_btn = QtWidgets.QPushButton("Load from YAML")
        self.save_btn = QtWidgets.QPushButton("Save to YAML")

        # Arrange buttons in rows
        btn_row1 = QtWidgets.QHBoxLayout()
        btn_row1.addWidget(self.add_btn)
        btn_row1.addWidget(self.remove_btn)

        btn_row2 = QtWidgets.QHBoxLayout()
        btn_row2.addWidget(self.load_btn)
        btn_row2.addWidget(self.save_btn)

        layout.addLayout(btn_row1)
        layout.addLayout(btn_row2)
        layout.addWidget(self.table)

        return group

    def _create_merge_group(self) -> QtWidgets.QGroupBox:
        """Create the merge samples section."""
        group = QtWidgets.QGroupBox("Merge Samples")
        layout = QtWidgets.QVBoxLayout(group)

        # File/folder selectors
        self.sample_edit = self._create_file_selector(
            layout, "Sample YAML:", self._choose_sample
        )
        self.processing_results_edit = self._create_file_selector(
            layout, "Processing Results YAML:", self._choose_processing_results
        )
        self.data_edit = self._create_folder_selector(
            layout, "CSV folder:", self._choose_data_dir
        )
        self.output_edit = self._create_folder_selector(
            layout, "Output folder:", self._choose_output_dir
        )

        # Run button
        actions = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("Run Merge")
        actions.addWidget(self.run_btn)
        layout.addLayout(actions)

        return group

    def _create_file_selector(
        self, parent_layout: QtWidgets.QVBoxLayout, label_text: str, browse_callback
    ) -> QtWidgets.QLineEdit:
        """Create a file selector with label, edit field, and browse button."""
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel(label_text))
        row.addStretch()

        browse_btn = QtWidgets.QPushButton("Browse")
        browse_btn.clicked.connect(browse_callback)
        row.addWidget(browse_btn)

        parent_layout.addLayout(row)

        edit_field = QtWidgets.QLineEdit()
        parent_layout.addWidget(edit_field)

        return edit_field

    def _create_folder_selector(
        self, parent_layout: QtWidgets.QVBoxLayout, label_text: str, browse_callback
    ) -> QtWidgets.QLineEdit:
        """Create a folder selector with label, edit field, and browse button."""
        return self._create_file_selector(parent_layout, label_text, browse_callback)

    def _connect_signals(self) -> None:
        """Connect UI signals to handlers."""
        # Table buttons
        self.add_btn.clicked.connect(self.table.add_empty_row)
        self.remove_btn.clicked.connect(self.table.remove_selected_row)
        self.load_btn.clicked.connect(self.on_load)
        self.save_btn.clicked.connect(self.on_save)

        # Merge button
        self.run_btn.clicked.connect(self._run_merge)

    def _initialize_fields(self) -> None:
        """Initialize form fields to empty state."""
        self.sample_edit.clear()
        self.processing_results_edit.clear()
        self.data_edit.clear()
        self.output_edit.clear()

    def on_load(self) -> None:
        """Load samples from YAML file."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open sample.yaml",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*)",
        )
        if not file_path:
            return

        try:
            path = Path(file_path)
            data = read_yaml_config(path)
            samples = data.get("samples", [])

            if not isinstance(samples, list):
                raise ValueError("Invalid YAML format: 'samples' must be a list")

            self.table.load_samples(samples)
            self.sample_edit.setText(str(path))

            QtWidgets.QMessageBox.information(
                self, "Load", f"Loaded samples from:\n{path}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Load Error", str(e))

    def on_save(self) -> None:
        """Save current samples to YAML file."""
        try:
            # Convert table to samples format (with validation)
            samples_data = []
            seen_names = set()

            for row in range(self.table.rowCount()):
                name_item = self.table.item(row, 0)
                fovs_item = self.table.item(row, 1)
                name = (name_item.text() if name_item else "").strip()
                fovs_text = (fovs_item.text() if fovs_item else "").strip()

                if not name:
                    raise ValueError(f"Row {row + 1}: Sample name is required")
                if name in seen_names:
                    raise ValueError(f"Row {row + 1}: Duplicate sample name '{name}'")
                if not fovs_text:
                    raise ValueError(
                        f"Row {row + 1} ('{name}'): FOVs field is required"
                    )

                seen_names.add(name)
                samples_data.append({"name": name, "fovs": fovs_text})

            # Choose save location
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save sample.yaml",
                "",
                "YAML Files (*.yaml *.yml);;All Files (*)",
            )
            if not file_path:
                return

            # Save file
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with path.open("w", encoding="utf-8") as f:
                yaml.safe_dump({"samples": samples_data}, f, sort_keys=False)

            self.sample_edit.setText(str(path))
            QtWidgets.QMessageBox.information(self, "Saved", f"Wrote YAML to:\n{path}")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save Error", str(e))

    def _choose_sample(self) -> None:
        """Browse for sample YAML file."""
        current_path = self.sample_edit.text()
        start_dir = str(Path(current_path).parent) if current_path else ""

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select sample.yaml",
            start_dir,
            "YAML Files (*.yaml *.yml)",
        )
        if path:
            self.sample_edit.setText(path)

    def _choose_processing_results(self) -> None:
        """Browse for processing results YAML file."""
        current_path = self.processing_results_edit.text()
        start_dir = str(Path(current_path).parent) if current_path else ""

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select processing_results.yaml",
            start_dir,
            "YAML Files (*.yaml *.yml)",
        )
        if path:
            self.processing_results_edit.setText(path)

    def _choose_data_dir(self) -> None:
        """Browse for CSV data directory."""
        current_path = self.data_edit.text()
        start_dir = current_path if current_path else str(Path.cwd())

        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select FOV CSV folder",
            start_dir,
        )
        if path:
            self.data_edit.setText(path)

    def _choose_output_dir(self) -> None:
        """Browse for output directory."""
        current_path = self.output_edit.text()
        start_dir = current_path if current_path else str(Path.cwd())

        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select output folder",
            start_dir,
        )
        if path:
            self.output_edit.setText(path)

    def _run_merge(self) -> None:
        """Execute the merge process."""
        # Get and validate paths
        try:
            sample_path = Path(self.sample_edit.text()).expanduser()
            processing_results_path = Path(
                self.processing_results_edit.text()
            ).expanduser()
            data_dir = Path(self.data_edit.text()).expanduser()
            output_dir = Path(self.output_edit.text()).expanduser()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Invalid path specification: {e}"
            )
            return

        # Validate inputs
        if not sample_path.exists():
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Sample YAML not found:\n{sample_path}"
            )
            return

        if not processing_results_path.exists():
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Processing results YAML not found:\n{processing_results_path}",
            )
            return

        if not data_dir.exists() or not data_dir.is_dir():
            QtWidgets.QMessageBox.critical(
                self, "Error", f"CSV folder is invalid:\n{data_dir}"
            )
            return

        # Run merge process
        try:
            run_merge(
                root=Path.cwd(),
                sample_yaml=sample_path,
                processing_results=processing_results_path,
                input_dir=data_dir,
                output_dir=output_dir,
            )
            QtWidgets.QMessageBox.information(
                self, "Success", f"Merge completed. Files written to:\n{output_dir}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Merge Failed", f"An error occurred:\n{e}"
            )
