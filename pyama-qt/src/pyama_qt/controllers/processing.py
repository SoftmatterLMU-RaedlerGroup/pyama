"""Controller coordinating processing UI actions and background work."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from pyama_core.io import load_microscopy_file, MicroscopyMetadata
from pyama_core.io.processing_csv import get_dataframe
from pyama_core.io.results_yaml import (
    load_processing_results_yaml,
    get_channels_from_yaml,
    get_time_units_from_yaml,
)
from pyama_core.processing.workflow import ensure_context, run_complete_workflow
from pyama_core.processing.workflow.services.types import Channels, ProcessingContext
from pyama_qt.models.processing import ProcessingConfigModel, WorkflowStatusModel
from pyama_qt.models.processing_requests import MergeRequest
from pyama_qt.services import WorkerHandle, start_worker
from .processing_utils import parse_fov_range
import yaml

from pyama_qt.views.processing.page import ProcessingPage

logger = logging.getLogger(__name__)


# Move helpers here from merge_panel
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


def read_trace_csv(path: Path) -> list[dict[str, Any]]:
    """Read trace CSV file with dynamic feature columns."""
    df = get_dataframe(path)
    return df.to_dict("records")


def _format_timepoints(timepoints: Sequence[float]) -> str:
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


@dataclass(frozen=True)
class FeatureMaps:
    """Maps for feature data organized by (time, cell) tuples."""

    features: dict[
        str, dict[tuple[float, int], float]
    ]  # feature_name -> (time, cell) -> value
    times: list[float]
    cells: list[int]


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


def _run_merge(  # Renamed from run_merge for private
    sample_yaml: Path,
    processing_results: Path,
    input_dir: Path,
    output_dir: Path,
) -> str:
    """Internal merge logic - return success message or raise error."""
    # Adapted from original run_merge, but no root param, direct paths
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
                logger.warning(f"No trace CSV for FOV {fov}, channel {channel}")
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
                logger.warning(f"No data for sample {sample_name}, channel {channel}")
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


class ProcessingController(QObject):
    """Controller coordinating processing workflow UI interactions."""

    def __init__(self, view: ProcessingPage) -> None:
        super().__init__()
        self._view = view
        self._config_model = ProcessingConfigModel()
        self._status_model = WorkflowStatusModel()
        self._microscopy_loader: WorkerHandle | None = None
        self._workflow_runner: WorkerHandle | None = None
        self._merge_runner: WorkerHandle | None = None

        self._connect_view_signals()
        self._connect_model_signals()
        self._initialise_view_state()

    # ------------------------------------------------------------------
    # Signal wiring helpers
    # ------------------------------------------------------------------
    def _connect_view_signals(self) -> None:
        config_panel = self._view.config_panel
        merge_panel = self._view.merge_panel

        config_panel.file_selected.connect(self._on_microscopy_selected)
        config_panel.output_dir_selected.connect(self._on_output_directory_selected)
        config_panel.channels_changed.connect(self._on_channels_changed)
        config_panel.parameters_changed.connect(self._on_parameters_changed)
        config_panel.process_requested.connect(self._on_process_requested)

        merge_panel.load_samples_requested.connect(self._on_samples_load_requested)
        merge_panel.save_samples_requested.connect(self._on_samples_save_requested)
        merge_panel.merge_requested.connect(self._on_merge_requested)

    def _connect_model_signals(self) -> None:
        config_panel = self._view.config_panel

        self._config_model.microscopyPathChanged.connect(
            config_panel.display_microscopy_path
        )
        self._config_model.outputDirChanged.connect(
            config_panel.display_output_directory
        )
        self._config_model.metadataChanged.connect(self._on_metadata_changed)
        self._config_model.phaseChanged.connect(self._sync_channel_selection)
        self._config_model.fluorescenceChanged.connect(self._sync_channel_selection)
        self._config_model.fovStartChanged.connect(
            lambda value: config_panel.set_parameter_value("fov_start", value)
        )
        self._config_model.fovEndChanged.connect(
            lambda value: config_panel.set_parameter_value("fov_end", value)
        )
        self._config_model.batchSizeChanged.connect(
            lambda value: config_panel.set_parameter_value("batch_size", value)
        )
        self._config_model.nWorkersChanged.connect(
            lambda value: config_panel.set_parameter_value("n_workers", value)
        )

        self._status_model.isProcessingChanged.connect(
            config_panel.set_processing_active
        )
        self._status_model.isProcessingChanged.connect(
            lambda active: config_panel.set_process_enabled(not active)
        )

    def _initialise_view_state(self) -> None:
        panel = self._view.config_panel
        panel.display_microscopy_path(self._config_model.microscopy_path())
        panel.display_output_directory(self._config_model.output_dir())
        self._on_metadata_changed(self._config_model.metadata())
        self._sync_channel_selection()
        panel.set_parameter_value("fov_start", self._config_model.fov_start())
        panel.set_parameter_value("fov_end", self._config_model.fov_end())
        panel.set_parameter_value("batch_size", self._config_model.batch_size())
        panel.set_parameter_value("n_workers", self._config_model.n_workers())
        active = self._status_model.is_processing()
        panel.set_processing_active(active)
        panel.set_process_enabled(not active)

    # ------------------------------------------------------------------
    # View → Controller handlers
    # ------------------------------------------------------------------
    def _on_microscopy_selected(self, path: Path) -> None:
        self._load_microscopy(path)

    def _on_output_directory_selected(self, directory: Path) -> None:
        logger.info("Selected output directory: %s", directory)
        self._config_model.set_output_dir(directory)
        self._status_model.set_error_message("")

    def _on_channels_changed(self, payload: Any) -> None:
        phase = getattr(payload, "phase", None)
        fluorescence = list(getattr(payload, "fluorescence", [])) if payload else []
        self._config_model.update_channels(phase, fluorescence)

    def _on_parameters_changed(self, param_dict: dict[str, Any]) -> None:
        fov_start = param_dict.get("fov_start", 0)
        fov_end = param_dict.get("fov_end", 99)
        batch_size = param_dict.get("batch_size", 2)
        n_workers = param_dict.get("n_workers", 2)
        self._config_model.update_parameters(
            fov_start=fov_start,
            fov_end=fov_end,
            batch_size=batch_size,
            n_workers=n_workers,
        )

    def _on_process_requested(self) -> None:
        if self._status_model.is_processing():
            logger.warning("Workflow already running; ignoring start request")
            return

        try:
            self._validate_ready()
        except ValueError as exc:
            logger.error("Cannot start workflow: %s", exc)
            self._status_model.set_error_message(str(exc))
            return

        metadata = self._config_model.metadata()
        assert metadata is not None

        context = ProcessingContext(
            output_dir=self._config_model.output_dir(),
            channels=Channels(
                pc=(
                    self._config_model.phase()
                    if self._config_model.phase() is not None
                    else 0
                ),
                fl=list(self._config_model.fluorescence() or []),
            ),
            params={},
            time_units="",
        )

        worker = _WorkflowRunner(
            metadata=metadata,
            context=context,
            fov_start=self._config_model.fov_start(),
            fov_end=self._config_model.fov_end(),
            batch_size=self._config_model.batch_size(),
            n_workers=self._config_model.n_workers(),
        )
        worker.finished.connect(self._on_workflow_finished)

        handle = start_worker(
            worker,
            start_method="run",
            finished_callback=self._clear_workflow_handle,
        )
        self._workflow_runner = handle
        self._status_model.set_is_processing(True)
        self._status_model.set_status_message("Running workflow…")
        self._status_model.set_error_message("")

    def _on_samples_load_requested(self, path: Path) -> None:
        self._load_samples(path)

    def _on_samples_save_requested(self, path: Path) -> None:
        try:
            samples = self._view.merge_panel.current_samples()
        except ValueError as exc:
            logger.error("Failed to save samples: %s", exc)
            self._status_model.set_error_message(str(exc))
            return
        self._save_samples(path, samples)

    def _on_merge_requested(self, payload: Any) -> None:
        sample_yaml = Path(getattr(payload, "sample_yaml"))
        processing_yaml = Path(getattr(payload, "processing_results_yaml"))
        data_dir = Path(getattr(payload, "data_dir"))
        output_dir = Path(getattr(payload, "output_dir"))

        panel = self._view.merge_panel
        panel.set_sample_yaml_path(sample_yaml)
        panel.set_processing_results_path(processing_yaml)
        panel.set_data_directory(data_dir)
        panel.set_output_directory(output_dir)

        request = MergeRequest(
            sample_yaml=sample_yaml,
            processing_results=processing_yaml,
            input_dir=data_dir,
            output_dir=output_dir,
        )
        self._run_merge(request)

    # ------------------------------------------------------------------
    # Model → Controller helpers
    # ------------------------------------------------------------------
    def _sync_channel_selection(self, *_args) -> None:
        selection = self._config_model.channels()
        self._view.config_panel.apply_selected_channels(
            phase=selection.phase,
            fluorescence=selection.fluorescence,
        )

    def _on_metadata_changed(self, metadata) -> None:
        channel_names = getattr(metadata, "channel_names", None) if metadata else None
        phase_options: list[tuple[str, int | None]] = [("None", None)]
        fluorescence_options: list[tuple[str, int]] = []
        if channel_names:
            for idx, name in enumerate(channel_names):
                label = f"Channel {idx}: {name}"
                phase_options.append((label, idx))
                fluorescence_options.append((label, idx))
        self._view.config_panel.set_channel_options(
            phase_channels=phase_options,
            fluorescence_channels=fluorescence_options,
        )
        self._sync_channel_selection()

        # Update FOV defaults when metadata is loaded
        if metadata and hasattr(metadata, "n_fovs"):
            n_fovs = metadata.n_fovs
            if n_fovs > 0:
                # Set FOV range to include all available FOVs
                self._config_model.update_parameters(fov_start=0, fov_end=n_fovs - 1)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_microscopy(self, path: Path) -> None:
        logger.info("Loading microscopy metadata from %s", path)
        self._config_model.load_microscopy(path)
        self._status_model.set_status_message("Loading microscopy metadata…")
        self._status_model.set_error_message("")

        worker = _MicroscopyLoaderWorker(path)
        worker.loaded.connect(self._on_microscopy_loaded)
        worker.failed.connect(self._on_microscopy_failed)
        handle = start_worker(
            worker,
            start_method="run",
            finished_callback=self._on_loader_finished,
        )
        self._microscopy_loader = handle

    def _load_samples(self, path: Path) -> None:
        try:
            data = read_yaml_config(path)
            samples = data.get("samples", [])
            if not isinstance(samples, list):
                raise ValueError("Invalid YAML: 'samples' must be list")
            self._view.merge_panel.load_samples(samples)
            self._view.merge_panel.set_sample_yaml_path(path)
        except Exception as exc:
            logger.error("Failed to load samples from %s: %s", path, exc)
            self._status_model.set_error_message(str(exc))

    def _save_samples(self, path: Path, samples: list[dict[str, Any]]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                yaml.safe_dump({"samples": samples}, f, sort_keys=False)
            logger.info("Saved samples to %s", path)
            self._view.merge_panel.set_sample_yaml_path(path)
        except Exception as exc:
            logger.error("Failed to save samples to %s: %s", path, exc)
            self._status_model.set_error_message(str(exc))

    def _run_merge(self, request: MergeRequest) -> None:
        if self._merge_runner:
            logger.warning("Merge already running")
            return

        worker = _MergeRunner(request)
        worker.finished.connect(self._on_merge_finished)
        handle = start_worker(
            worker,
            start_method="run",
            finished_callback=self._clear_merge_handle,
        )
        self._merge_runner = handle
        self._status_model.set_status_message("Running merge…")
        self._status_model.set_error_message("")

    def _validate_ready(self) -> None:
        metadata = self._config_model.metadata()
        if metadata is None:
            raise ValueError("Load an ND2 file before starting the workflow")
        if self._config_model.output_dir() is None:
            raise ValueError("Select an output directory before starting the workflow")
        channels = self._config_model.channels()
        if channels.phase is None and not channels.fluorescence:
            raise ValueError("Select at least one channel to process")

        params = self._config_model.parameters()
        n_fovs = getattr(metadata, "n_fovs", 0)

        if params.fov_start != -1 or params.fov_end != -1:
            if params.fov_start < 0:
                raise ValueError("FOV start must be >= 0 or -1 for all")
            if params.fov_end < params.fov_start:
                raise ValueError("FOV end must be >= start")
            if params.fov_end >= n_fovs:
                raise ValueError(
                    f"FOV end ({params.fov_end}) must be less than total FOVs ({n_fovs})"
                )

        if params.batch_size <= 0:
            raise ValueError("Batch size must be positive")
        if params.n_workers <= 0:
            raise ValueError("Number of workers must be positive")

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------
    def _on_microscopy_loaded(self, metadata: MicroscopyMetadata) -> None:
        logger.info("Microscopy metadata loaded")
        self._config_model.set_metadata(metadata)
        self._status_model.set_status_message("ND2 ready")
        self._status_model.set_error_message("")

    def _on_microscopy_failed(self, message: str) -> None:
        logger.error("Failed to load ND2: %s", message)
        self._status_model.set_status_message("")
        self._status_model.set_error_message(message)

    def _on_loader_finished(self) -> None:
        logger.info("ND2 loader thread finished")
        self._microscopy_loader = None

    def _on_workflow_finished(self, success: bool, message: str) -> None:
        logger.info("Workflow finished (success=%s): %s", success, message)
        self._status_model.set_is_processing(False)
        self._status_model.set_status_message(message)
        if not success:
            self._status_model.set_error_message(message)

    def _clear_workflow_handle(self) -> None:
        logger.info("Workflow thread finished")
        self._workflow_runner = None

    def _on_merge_finished(self, success: bool, message: str) -> None:
        if success:
            logger.info("Merge completed: %s", message)
            self._status_model.set_status_message(message)
            self._status_model.set_error_message("")
        else:
            logger.error("Merge failed: %s", message)
            self._status_model.set_error_message(message)


class _MicroscopyLoaderWorker(QObject):
    loaded = Signal(object)
    failed = Signal(str)
    finished = Signal()  # Signal to indicate work is complete

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._cancelled = False

    def cancel(self) -> None:
        """Mark this worker as cancelled."""
        self._cancelled = True

    def run(self) -> None:
        try:
            if self._cancelled:
                self.finished.emit()
                return
            _img, metadata = load_microscopy_file(self._path)
            if not self._cancelled:
                self.loaded.emit(metadata)
        except Exception as exc:  # pragma: no cover - propagate to UI
            if not self._cancelled:
                self.failed.emit(str(exc))
        finally:
            # Always emit finished to quit the thread
            self.finished.emit()


class _WorkflowRunner(QObject):
    finished = Signal(bool, str)

    def __init__(
        self,
        *,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        fov_start: int,
        fov_end: int,
        batch_size: int,
        n_workers: int,
    ) -> None:
        super().__init__()
        self._metadata = metadata
        self._context = ensure_context(context)
        self._fov_start = fov_start
        self._fov_end = fov_end
        self._batch_size = batch_size
        self._n_workers = n_workers

    def run(self) -> None:
        try:
            success = run_complete_workflow(
                self._metadata,
                self._context,
                fov_start=self._fov_start,
                fov_end=self._fov_end,
                batch_size=self._batch_size,
                n_workers=self._n_workers,
            )
            if success:
                output_dir = self._context.output_dir or "output directory"
                message = f"Results saved to {output_dir}"
                self.finished.emit(True, message)
            else:  # pragma: no cover - defensive branch
                self.finished.emit(False, "Workflow reported failure")
        except Exception as exc:  # pragma: no cover - propagate to UI
            logger.exception("Workflow execution failed")
            self.finished.emit(False, f"Workflow error: {exc}")


class _MergeRunner(QObject):
    finished = Signal(bool, str)

    def __init__(self, request: MergeRequest):
        super().__init__()
        self._request = request

    def run(self) -> None:
        try:
            message = _run_merge(
                self._request.sample_yaml,
                self._request.processing_results,
                self._request.input_dir,
                self._request.output_dir,
            )
            self.finished.emit(True, message)
        except Exception as e:
            logger.exception("Merge failed")
            self.finished.emit(False, str(e))
