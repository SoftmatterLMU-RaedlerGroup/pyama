"""FOV assignment and CSV merging utilities."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
import yaml
from pathlib import Path
from typing import Any, Sequence

from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QTableWidget,
    QHeaderView,
    QTableWidgetItem,
    QWidget,
)

from pyama_core.io.processing_csv import get_dataframe
from pyama_core.io.results_yaml import (
    load_processing_results_yaml,
    get_channels_from_yaml,
    get_time_units_from_yaml,
)

from pyama_qt.constants import DEFAULT_DIR
from pyama_qt.services import WorkerHandle, start_worker
from pyama_qt.types.processing import MergeRequest, FeatureMaps

logger = logging.getLogger(__name__)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_available_features() -> list[str]:
    """Get list of available feature extractors."""
    try:
        from pyama_core.processing.extraction.feature import list_features

        return list_features()
    except ImportError:
        # Fallback for testing
        return ["intensity_total", "area"]


def read_yaml_config(path: Path) -> dict[str, Any]:
    """Read YAML config file with samples specification."""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        if not isinstance(data, dict) or "samples" not in data:
            raise ValueError("YAML must contain a top-level 'samples' key")
        return data


def parse_fov_range(text: str) -> list[int]:
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


def parse_fovs_field(fovs_value) -> list[int]:
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


def read_trace_csv(path: Path) -> list[dict[str, Any]]:
    """Read trace CSV file with dynamic feature columns."""
    df = get_dataframe(path)
    return df.to_dict("records")


def _format_timepoints(timepoints: Sequence[float]) -> str:
    """Format timepoints for display."""
    values = list(timepoints)
    if not values:
        return "<none>"

    def _format_value(value: float) -> str:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return f"{value:g}"

    if len(values) <= 4:
        return ", ".join(_format_value(v) for v in values)

    head = ", ".join(_format_value(v) for v in values[:3])
    tail = _format_value(values[-1])
    return f"{head}, ..., {tail}"


# =============================================================================
# FEATURE PROCESSING FUNCTIONS
# =============================================================================


def build_feature_maps(
    rows: list[dict[str, Any]], feature_names: list[str]
) -> FeatureMaps:
    """Build feature maps from trace CSV rows, filtering by 'good' column."""
    feature_maps: dict[str, dict[tuple[float, int], float]] = {}
    times_set = set()
    cells_set = set()

    # Initialize feature maps
    for feature_name in feature_names:
        feature_maps[feature_name] = {}

    # Process rows, filtering by 'good' column if it exists
    for r in rows:
        # Skip rows where 'good' column is False
        if "good" in r and not r["good"]:
            continue

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
    feature_maps_by_fov: dict[int, FeatureMaps], fovs: list[int]
) -> list[float]:
    """Get all unique time points across the specified FOVs."""
    all_times = set()
    for fov in fovs:
        if fov in feature_maps_by_fov:
            all_times.update(feature_maps_by_fov[fov].times)
    return sorted(all_times)


def write_feature_csv(
    out_path: Path,
    times: list[float],
    fovs: list[int],
    feature_name: str,
    feature_maps_by_fov: dict[int, FeatureMaps],
    channel: int,
    time_units: str | None = None,
) -> None:
    """Write feature data to CSV file in wide format."""
    import pandas as pd

    # Create header: first column is time, then one column per cell across all FOVs
    all_cells = set()
    for fov in fovs:
        if fov in feature_maps_by_fov:
            all_cells.update(feature_maps_by_fov[fov].cells)

    all_cells_sorted = sorted(all_cells)

    # Create column names: cell IDs include FOV prefix
    columns = ["time"]
    for fov in fovs:
        for cell in all_cells_sorted:
            columns.append(f"fov_{fov:03d}_cell_{cell}")

    # Build rows
    rows = []
    for time in times:
        row = [time]
        for fov in fovs:
            feature_maps = feature_maps_by_fov.get(fov)
            for cell in all_cells_sorted:
                value = None
                if feature_maps and feature_name in feature_maps.features:
                    value = feature_maps.features[feature_name].get((time, cell))
                row.append(value)
        rows.append(row)

    # Create DataFrame and save
    df = pd.DataFrame(rows, columns=columns)

    # Add time units comment if provided
    if time_units:
        with out_path.open("w") as f:
            f.write(f"# Time units: {time_units}\n")
            df.to_csv(f, index=False, float_format="%.6f")
    else:
        df.to_csv(out_path, index=False, float_format="%.6f")


def _find_trace_csv_file(
    processing_results_data: dict[str, Any], input_dir: Path, fov: int, channel: int
) -> Path | None:
    """Find the trace CSV file for a specific FOV and channel."""
    # In the original YAML, FOV keys are simple strings like "0", "1", etc.
    fov_key = str(fov)
    # Use the original YAML structure under "results_paths"
    fov_data = processing_results_data.get("results_paths", {}).get(fov_key, {})

    traces_csv_list = fov_data.get("traces_csv", [])

    # Look for the specific channel in traces_csv list
    # traces_csv is a list of [channel, path] pairs
    for trace_item in traces_csv_list:
        if isinstance(trace_item, (list, tuple)) and len(trace_item) == 2:
            trace_channel, trace_path = trace_item
            if int(trace_channel) == channel:
                path = Path(trace_path)
                # If path is relative, resolve it relative to input_dir
                if not path.is_absolute():
                    path = input_dir / path

                # Check if an inspected version exists and prefer it
                inspected_path = path.with_name(path.stem + "_inspected" + path.suffix)
                if inspected_path.exists():
                    return inspected_path
                else:
                    return path

    return None


# =============================================================================
# MERGE LOGIC
# =============================================================================


def run_merge(
    sample_yaml: Path,
    processing_results: Path,
    input_dir: Path,
    output_dir: Path,
) -> str:
    """Execute merge logic - return success message or raise error."""
    config = read_yaml_config(sample_yaml)
    samples = config["samples"]

    proc_results = load_processing_results_yaml(processing_results)
    channels = get_channels_from_yaml(proc_results)
    if not channels:
        raise ValueError("No fluorescence channels found in processing results")

    time_units = get_time_units_from_yaml(proc_results)

    # Load the original YAML data to access multi-channel traces_csv structure
    with processing_results.open("r", encoding="utf-8") as f:
        original_yaml_data = yaml.safe_load(f)

    available_features = get_available_features()

    all_fovs = set()
    for sample in samples:
        fovs = parse_fovs_field(sample.get("fovs", []))
        all_fovs.update(fovs)

    feature_maps_by_fov_channel = {}

    for fov in sorted(all_fovs):
        for channel in channels:
            csv_path = _find_trace_csv_file(original_yaml_data, input_dir, fov, channel)
            if csv_path is None or not csv_path.exists():
                logger.warning("No trace CSV for FOV %s, channel %s", fov, channel)
                continue

            rows = read_trace_csv(csv_path)
            feature_maps_by_fov_channel[(fov, channel)] = build_feature_maps(
                rows, available_features
            )

    output_dir.mkdir(parents=True, exist_ok=True)

    created_files = []
    total_samples = len(samples)
    total_channels = len(channels)
    total_features = len(available_features)

    logger.info(
        f"Starting merge for {total_samples} samples, {total_channels} channels, {total_features} features"
    )

    for sample in samples:
        sample_name = sample["name"]
        sample_fovs = parse_fovs_field(sample.get("fovs", []))
        logger.info(f"Processing sample '{sample_name}' with FOVs: {sample_fovs}")

        for channel in channels:
            channel_feature_maps = {}
            for fov in sample_fovs:
                key = (fov, channel)
                if key in feature_maps_by_fov_channel:
                    channel_feature_maps[fov] = feature_maps_by_fov_channel[key]

            if not channel_feature_maps:
                logger.warning(
                    "No data for sample %s, channel %s", sample_name, channel
                )
                continue

            times = get_all_times(channel_feature_maps, sample_fovs)
            logger.info(
                f"Sample '{sample_name}', channel {channel}: found {len(times)} time points across {len(channel_feature_maps)} FOVs"
            )

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
                created_files.append(output_path)
                logger.info(f"Created: {output_filename}")

    logger.info("Merge completed successfully!")
    logger.info(f"Created {len(created_files)} files in {output_dir}:")
    for file_path in created_files:
        logger.info(f"  - {file_path.name}")

    return f"Merge completed. Created {len(created_files)} files in {output_dir}"


# =============================================================================
# BACKGROUND WORKER
# =============================================================================


class MergeRunner(QObject):
    """Background worker for running the merge process."""

    # Signals
    finished = Signal(bool, str)

    def __init__(self, request):
        super().__init__()
        self._request = request

    def run(self) -> None:
        """Execute the merge process."""
        try:
            message = run_merge(
                self._request.sample_yaml,
                self._request.processing_results_yaml,
                self._request.input_dir,
                self._request.output_dir,
            )
            self.finished.emit(True, message)
        except Exception as e:
            logger.exception("Merge failed")
            self.finished.emit(False, str(e))


# =============================================================================
# CUSTOM TABLE WIDGET
# =============================================================================


class SampleTable(QTableWidget):
    """Custom table widget for sample configuration."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 2, parent)
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # TABLE SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Configure table appearance and behavior."""
        self.setHorizontalHeaderLabels(["Sample Name", "FOVs (e.g., 0-5, 7, 9-11)"])

        # Configure header resizing
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # Configure appearance
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)

    def _connect_signals(self) -> None:
        """Connect signals for the table widget."""
        pass

    # ------------------------------------------------------------------------
    # ROW MANAGEMENT
    # ------------------------------------------------------------------------
    def add_empty_row(self) -> None:
        """Add a new empty row to the table."""
        row = self.rowCount()
        self.insertRow(row)

        # Create editable items
        name_item = QTableWidgetItem("")
        fovs_item = QTableWidgetItem("")
        name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
        fovs_item.setFlags(fovs_item.flags() | Qt.ItemFlag.ItemIsEditable)

        # Add items to table
        self.setItem(row, 0, name_item)
        self.setItem(row, 1, fovs_item)
        self.setCurrentCell(row, 0)

    def add_row(self, name: str, fovs_text: str) -> None:
        """Add a new row with the given data."""
        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, QTableWidgetItem(name))
        self.setItem(row, 1, QTableWidgetItem(fovs_text))

    def remove_selected_row(self) -> None:
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return
        for id in sorted(indexes, key=lambda i: i.row(), reverse=True):
            self.removeRow(id.row())

    def to_samples(self) -> list[dict[str, Any]]:
        """Convert table data to samples list with validation. Emit error if invalid."""
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

            samples.append({"name": name, "fovs": fovs_text})

        return samples

    def load_samples(self, samples: list[dict[str, Any]]) -> None:
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


class ProcessingMergePanel(QWidget):
    """Panel responsible for FOV assignment and CSV merging utilities."""

    # Signals
    merge_started = Signal()  # Merge has started
    merge_finished = Signal(bool, str)  # Merge finished (success, message)
    status_message = Signal(str)  # Status message to display

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._table: SampleTable | None = None
        self._merge_runner: WorkerHandle | None = None
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        """Build UI components for the merge panel."""
        main_layout = QVBoxLayout(self)

        # Create the two main sections
        assign_group = self._create_assign_group()
        merge_group = self._create_merge_group()

        # Add to main layout with equal stretch
        main_layout.addWidget(assign_group, 1)
        main_layout.addWidget(merge_group, 1)

    def _connect_signals(self) -> None:
        """Connect all signals for the merge panel."""
        # Table buttons
        self._add_btn.clicked.connect(self._on_add_row)
        self._remove_btn.clicked.connect(self._on_remove_row)
        self._load_btn.clicked.connect(self._on_load_requested)
        self._save_btn.clicked.connect(self._on_save_requested)

        # Merge button
        self.run_btn.clicked.connect(self._on_merge_requested)

    def _create_assign_group(self) -> QGroupBox:
        """Create the FOV assignment section."""
        group = QGroupBox("Assign FOVs")
        layout = QVBoxLayout(group)

        # Table
        if self._table is None:
            self._table = SampleTable(self)
        layout.addWidget(self._table)

        # Create buttons
        self._add_btn = QPushButton("Add Sample")
        self._remove_btn = QPushButton("Remove Selected")
        self._load_btn = QPushButton("Load from YAML")
        self._save_btn = QPushButton("Save to YAML")

        # Arrange buttons in rows
        btn_row1 = QHBoxLayout()
        btn_row1.addWidget(self._add_btn)
        btn_row1.addWidget(self._remove_btn)

        btn_row2 = QHBoxLayout()
        btn_row2.addWidget(self._load_btn)
        btn_row2.addWidget(self._save_btn)

        layout.addLayout(btn_row1)
        layout.addLayout(btn_row2)

        return group

    def _create_merge_group(self) -> QGroupBox:
        """Create the merge samples section."""
        group = QGroupBox("Merge Samples")
        layout = QVBoxLayout(group)

        # File/folder selectors
        # Sample YAML selector
        sample_row = QHBoxLayout()
        sample_row.addWidget(QLabel("Sample YAML:"))
        sample_row.addStretch()
        sample_browse_btn = QPushButton("Browse")
        sample_browse_btn.clicked.connect(self._choose_sample)
        sample_row.addWidget(sample_browse_btn)
        layout.addLayout(sample_row)
        self.sample_edit = QLineEdit()
        layout.addWidget(self.sample_edit)

        # Processing Results YAML selector
        processing_results_row = QHBoxLayout()
        processing_results_row.addWidget(QLabel("Processing Results YAML:"))
        processing_results_row.addStretch()
        processing_results_browse_btn = QPushButton("Browse")
        processing_results_browse_btn.clicked.connect(self._choose_processing_results)
        processing_results_row.addWidget(processing_results_browse_btn)
        layout.addLayout(processing_results_row)
        self.processing_results_edit = QLineEdit()
        layout.addWidget(self.processing_results_edit)

        # CSV folder selector
        data_row = QHBoxLayout()
        data_row.addWidget(QLabel("CSV folder:"))
        data_row.addStretch()
        data_browse_btn = QPushButton("Browse")
        data_browse_btn.clicked.connect(self._choose_data_dir)
        data_row.addWidget(data_browse_btn)
        layout.addLayout(data_row)
        self.data_edit = QLineEdit()
        layout.addWidget(self.data_edit)

        # Output folder selector
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Output folder:"))
        output_row.addStretch()
        output_browse_btn = QPushButton("Browse")
        output_browse_btn.clicked.connect(self._choose_output_dir)
        output_row.addWidget(output_browse_btn)
        layout.addLayout(output_row)
        self.output_edit = QLineEdit()
        layout.addWidget(self.output_edit)

        # Run button
        actions = QHBoxLayout()
        self.run_btn = QPushButton("Run Merge")
        actions.addWidget(self.run_btn)
        layout.addLayout(actions)

        return group

    # ------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------

    @Slot()
    def _on_add_row(self) -> None:
        """Add a new row to the table."""
        self._table.add_empty_row()

    @Slot()
    def _on_remove_row(self) -> None:
        """Remove selected row from the table."""
        self._table.remove_selected_row()

    @Slot()
    def _on_load_requested(self) -> None:
        """Load samples from YAML file."""
        logger.debug("UI Click: Load samples button")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open sample.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self._load_samples(Path(file_path))

    @Slot()
    def _on_save_requested(self) -> None:
        """Save samples to YAML file."""
        logger.debug("UI Click: Save samples button")
        try:
            samples = self.current_samples()
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save sample.yaml",
                DEFAULT_DIR,
                "YAML Files (*.yaml *.yml);;All Files (*)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if file_path:
                self._save_samples(Path(file_path), samples)
        except ValueError as exc:
            logger.error("Failed to save samples: %s", exc)
            self.status_message.emit(f"Failed to save samples: {exc}")

    def _load_samples(self, path: Path) -> None:
        """Load samples from YAML file."""
        try:
            data = read_yaml_config(path)
            samples = data.get("samples", [])
            if not isinstance(samples, list):
                raise ValueError("Invalid YAML: 'samples' must be list")
            self.load_samples(samples)
            self.set_sample_yaml_path(path)
            self.status_message.emit(f"Loaded samples from {path.name}")
        except Exception as exc:
            logger.error("Failed to load samples from %s: %s", path, exc)
            self.status_message.emit(f"Failed to load samples: {exc}")

    def _save_samples(self, path: Path, samples: list[dict[str, Any]]) -> None:
        """Save samples to YAML file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                yaml.safe_dump({"samples": samples}, f, sort_keys=False)
            logger.info("Saved samples to %s", path)
            self.set_sample_yaml_path(path)
            self.status_message.emit(f"Saved samples to {path.name}")
        except Exception as exc:
            logger.error("Failed to save samples to %s: %s", path, exc)
            self.status_message.emit(f"Failed to save samples: {exc}")

    def _on_merge_requested(self) -> None:
        """Run merge after validation."""
        logger.debug("UI Click: Run merge button")

        if self._merge_runner:
            logger.warning("Merge already running")
            self.status_message.emit("Merge already running")
            return

        try:
            sample_text = self.sample_edit.text().strip()
            processing_text = self.processing_results_edit.text().strip()
            data_text = self.data_edit.text().strip()
            output_text = self.output_edit.text().strip()

            if not all([sample_text, processing_text, data_text, output_text]):
                self.status_message.emit("All paths must be specified")
                return

            request = MergeRequest(
                sample_yaml=Path(sample_text).expanduser(),
                processing_results_yaml=Path(processing_text).expanduser(),
                input_dir=Path(data_text).expanduser(),
                output_dir=Path(output_text).expanduser(),
            )

            # Run merge in background
            worker = MergeRunner(request)
            worker.finished.connect(self._on_merge_finished)
            handle = start_worker(
                worker,
                start_method="run",
                finished_callback=self._clear_merge_handle,
            )
            self._merge_runner = handle
            self.status_message.emit("Running merge…")
            self.merge_started.emit()

        except Exception as exc:
            logger.error("Failed to start merge: %s", exc)
            self.status_message.emit(f"Failed to start merge: {exc}")

    def _on_merge_finished(self, success: bool, message: str) -> None:
        """Handle merge completion."""
        if success:
            logger.info("Merge completed: %s", message)
            self.status_message.emit(message)
        else:
            logger.error("Merge failed: %s", message)
            self.status_message.emit(f"Merge failed: {message}")
        self.merge_finished.emit(success, message)

    def _clear_merge_handle(self) -> None:
        """Clear merge handle."""
        logger.info("Merge thread finished")
        self._merge_runner = None

    def _choose_sample(self) -> None:
        """Browse for sample YAML file."""
        logger.debug("UI Click: Browse sample YAML button")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select sample.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            logger.debug("UI Action: Set sample YAML path - %s", path)
            self.sample_edit.setText(path)

    def _choose_processing_results(self) -> None:
        """Browse for processing results YAML file."""
        logger.debug("UI Click: Browse processing results YAML button")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select processing_results.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            logger.debug("UI Action: Set processing results YAML path - %s", path)
            self.processing_results_edit.setText(path)

    def _choose_data_dir(self) -> None:
        """Browse for CSV data directory."""
        logger.debug("UI Click: Browse CSV data directory button")
        path = QFileDialog.getExistingDirectory(
            self,
            "Select FOV CSV folder",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            logger.debug("UI Action: Set CSV data directory - %s", path)
            self.data_edit.setText(path)

    def _choose_output_dir(self) -> None:
        """Browse for output directory."""
        logger.debug("UI Click: Browse output directory button")
        path = QFileDialog.getExistingDirectory(
            self,
            "Select output folder",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            logger.debug("UI Action: Set output directory - %s", path)
            self.output_edit.setText(path)

    # ------------------------------------------------------------------
    # Controller helpers
    # ------------------------------------------------------------------
    def load_samples(self, samples: list[dict[str, Any]]) -> None:
        """Populate the sample table with controller-supplied content."""
        if self.table is None:
            self.table = SampleTable(self)
        self.table.load_samples(samples)

    def current_samples(self) -> list[dict[str, Any]]:
        """Return the current sample definitions."""
        if self.table is None:
            return []
        return self.table.to_samples()

    def set_sample_yaml_path(self, path: Path | str) -> None:
        self.sample_edit.setText(str(path))

    def set_processing_results_path(self, path: Path | str) -> None:
        self.processing_results_edit.setText(str(path))

    def set_data_directory(self, path: Path | str) -> None:
        self.data_edit.setText(str(path))

    def set_output_directory(self, path: Path | str) -> None:
        self.output_edit.setText(str(path))
