"""
Workflow pipeline for microscopy image analysis.
Consolidates types, helpers, and the orchestration function.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import logging
import threading
from pathlib import Path
import yaml

from pyama_core.io import MicroscopyMetadata
from .services import (
    CopyingService,
    SegmentationService,
    CorrectionService,
    TrackingService,
    ExtractionService,
    ProcessingContext,
    ensure_context,
    ensure_results_paths_entry,
)
from .services.types import Channels

logger = logging.getLogger(__name__)


def _compute_batches(fovs: list[int], batch_size: int) -> list[list[int]]:
    """Split FOV indices into contiguous batches of size ``batch_size``.

    Example:
    fovs = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    batch_size = 3
    Returns [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
    """
    batches: list[list[int]] = []
    total_fovs = len(fovs)
    for batch_start in range(0, total_fovs, batch_size):
        batch_end = min(batch_start + batch_size, total_fovs)
        batches.append(fovs[batch_start:batch_end])
    return batches


def _split_worker_ranges(fovs: list[int], n_workers: int) -> list[list[int]]:
    """Split FOV indices into up to ``n_workers`` contiguous, evenly sized ranges.

    If ``n_workers`` <= 0, returns ``[fovs]`` if ``fovs`` is non-empty, otherwise ``[]``.

    Example:
    fovs = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    n_workers = 3
    Returns [[0, 1, 2, 3], [4, 5, 6], [7, 8, 9]]
    """
    if n_workers <= 0:
        return [fovs] if fovs else []
    fovs_per_worker = len(fovs) // n_workers
    remainder = len(fovs) % n_workers
    worker_ranges: list[list[int]] = []
    start_idx = 0
    for i in range(n_workers):
        count = fovs_per_worker + (1 if i < remainder else 0)
        if count > 0:
            end_idx = start_idx + count
            worker_ranges.append(fovs[start_idx:end_idx])
            start_idx = end_idx
    return worker_ranges


def _merge_contexts(parent: ProcessingContext, child: ProcessingContext) -> None:
    """Merge a worker's context into the parent context in-place.

    - output_dir and channels: keep parent if present; fill from child if missing
    - params: add keys from child if missing in parent
    - results_paths: per-FOV merge; for fluorescence and other tuple lists, union and de-duplicate
    """
    parent = ensure_context(parent)
    child = ensure_context(child)

    if parent.output_dir is None and child.output_dir is not None:
        parent.output_dir = child.output_dir

    if child.channels is not None and parent.channels is not None:
        if child.channels.pc is not None and parent.channels.pc is None:
            parent.channels.pc = child.channels.pc
        if child.channels.fl:
            existing_fl = {int(ch) for ch in parent.channels.fl}
            for ch in child.channels.fl:
                ch_int = int(ch)
            if ch_int not in existing_fl:
                parent.channels.fl.append(ch_int)
                existing_fl.add(ch_int)

    if child.params:
        for key, value in child.params.items():
            parent.params.setdefault(key, value)

    # Merge time_units - if parent has no time_units, use child's time_units
    if child.time_units is not None:
        parent.time_units = child.time_units

    if child.results_paths:
        for fov, child_entry in child.results_paths.items():
            parent_entry = parent.results_paths.setdefault(
                fov, ensure_results_paths_entry()
            )

            if child_entry.pc is not None and parent_entry.pc is None:
                parent_entry.pc = child_entry.pc

            if child_entry.seg is not None and parent_entry.seg is None:
                parent_entry.seg = child_entry.seg

            if child_entry.seg_labeled is not None and parent_entry.seg_labeled is None:
                parent_entry.seg_labeled = child_entry.seg_labeled

            if child_entry.fl_corrected:
                existing = {(idx, str(path)) for idx, path in parent_entry.fl_corrected}
                for idx, path in child_entry.fl_corrected:
                    key = (idx, str(path))
                    if key not in existing:
                        parent_entry.fl_corrected.append((idx, path))
                        existing.add(key)

            if child_entry.fl:
                existing = {(idx, str(path)) for idx, path in parent_entry.fl}
                for idx, path in child_entry.fl:
                    key = (idx, str(path))
                    if key not in existing:
                        parent_entry.fl.append((idx, path))
                        existing.add(key)

            if child_entry.traces_csv:
                existing = {(idx, str(path)) for idx, path in parent_entry.traces_csv}
                for idx, path in child_entry.traces_csv:
                    key = (idx, str(path))
                    if key not in existing:
                        parent_entry.traces_csv.append((idx, path))
                        existing.add(key)


def _serialize_for_yaml(obj):
    """Convert context to a YAML-friendly representation.

    - pathlib.Path -> str
    - set -> list (sorted for determinism)
    - tuple -> list
    - dict/list: recurse
    - dataclasses: convert to dict
    """
    try:
        # Handle dataclasses
        if hasattr(obj, "__dataclass_fields__"):
            result = {}
            for field_name in obj.__dataclass_fields__:
                field_value = getattr(obj, field_name)
                result[field_name] = _serialize_for_yaml(field_value)
            return result
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, dict):
            return {str(k): _serialize_for_yaml(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_serialize_for_yaml(v) for v in obj]
        if isinstance(obj, set):
            return [
                _serialize_for_yaml(v) for v in sorted(list(obj), key=lambda x: str(x))
            ]
        return obj
    except Exception:
        # Fallback to string if anything goes wrong
        try:
            return str(obj)
        except Exception:
            return None


def run_single_worker(
    fovs: list[int],
    metadata: MicroscopyMetadata,
    context: ProcessingContext,
    progress_queue,
) -> tuple[list[int], int, int, str, ProcessingContext]:
    """Process a contiguous range of FOV indices through all pipeline steps.

    Returns a tuple of (fovs, successful_count, failed_count, message).
    """
    logger = logging.getLogger(__name__)
    successful_count = 0

    try:
        context = ensure_context(context)
        segmentation = SegmentationService()
        correction = CorrectionService()
        tracking = TrackingService()
        trace_extraction = ExtractionService()

        def _report(event):
            try:
                progress_queue.put(event)
            except Exception:
                pass

        segmentation.set_progress_reporter(_report)
        correction.set_progress_reporter(_report)
        tracking.set_progress_reporter(_report)
        trace_extraction.set_progress_reporter(_report)

        output_dir = context.output_dir
        if output_dir is None:
            raise ValueError("Processing context missing output_dir")

        logger.info(f"Processing FOVs {fovs[0]}-{fovs[-1]}")

        logger.info(f"Starting Segmentation for FOVs {fovs[0]}-{fovs[-1]}")
        segmentation.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fovs[0],
            fov_end=fovs[-1],
        )
        try:
            progress_queue.put({"step": "Segmentation", "context": context})
        except Exception:
            pass

        logger.info(f"Starting Correction for FOVs {fovs[0]}-{fovs[-1]}")
        correction.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fovs[0],
            fov_end=fovs[-1],
        )
        try:
            progress_queue.put({"step": "Correction", "context": context})
        except Exception:
            pass

        logger.info(f"Starting Tracking for FOVs {fovs[0]}-{fovs[-1]}")
        tracking.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fovs[0],
            fov_end=fovs[-1],
        )
        try:
            progress_queue.put({"step": "Tracking", "context": context})
        except Exception:
            pass

        logger.info(f"Starting Extraction for FOVs {fovs[0]}-{fovs[-1]}")
        trace_extraction.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fovs[0],
            fov_end=fovs[-1],
        )
        try:
            progress_queue.put({"step": "Extraction", "context": context})
        except Exception:
            pass

        successful_count = len(fovs)
        success_msg = f"Completed processing FOVs {fovs[0]}-{fovs[-1]}"
        logger.info(success_msg)
        return fovs, successful_count, 0, success_msg, context

    except Exception as e:
        logger.exception(f"Error processing FOVs {fovs[0]}-{fovs[-1]}")
        error_msg = f"Error processing FOVs {fovs[0]}-{fovs[-1]}: {str(e)}"
        return fovs, 0, len(fovs), error_msg, context


def run_complete_workflow(
    metadata: MicroscopyMetadata,
    context: ProcessingContext,
    fov_start: int | None = None,
    fov_end: int | None = None,
    batch_size: int = 2,
    n_workers: int = 2,
) -> bool:
    context = ensure_context(context)
    overall_success = False

    copy_service = CopyingService()

    try:
        output_dir = context.output_dir
        if output_dir is None:
            raise ValueError("Processing context missing output_dir")
        output_dir.mkdir(parents=True, exist_ok=True)

        n_fov = metadata.n_fovs
        # Handle None or -1 as "process all FOVs"
        if fov_start is None or fov_start == -1:
            fov_start = 0
        if fov_end is None or fov_end == -1:
            fov_end = n_fov - 1

        if fov_start < 0 or fov_end >= n_fov or fov_start > fov_end:
            logger.error(
                f"Invalid FOV range: {fov_start}-{fov_end} (file has {n_fov} FOVs)"
            )
            return False

        total_fovs = fov_end - fov_start + 1
        fov_indices = list(range(fov_start, fov_end + 1))

        # logger.info(f"Initial context:\n{pformat(context)}")

        completed_fovs = 0

        batches = _compute_batches(fov_indices, batch_size)
        precomputed_worker_ranges = [
            _split_worker_ranges(batch_fovs, n_workers) for batch_fovs in batches
        ]

        for batch_idx, batch_fovs in enumerate(batches):
            logger.info(f"Extracting batch: FOVs {batch_fovs[0]}-{batch_fovs[-1]}")
            try:
                copy_service.process_all_fovs(
                    metadata=metadata,
                    context=context,
                    output_dir=output_dir,
                    fov_start=batch_fovs[0],
                    fov_end=batch_fovs[-1],
                )
                # logger.info(f"After Copy context:\n{pformat(context)}")
            except Exception as e:
                logger.error(
                    f"Failed to extract batch starting at FOV {batch_fovs[0]}: {e}"
                )
                return False

            logger.info(f"Processing batch in parallel with {n_workers} workers")

            ctx = mp.get_context("spawn")
            # Create a manager-backed queue so worker processes can report progress
            manager = ctx.Manager()
            progress_queue = manager.Queue()

            # Start a lightweight drainer thread to log worker progress
            stop_event = threading.Event()

            def _drain_progress():
                while not stop_event.is_set():
                    try:
                        event = progress_queue.get(timeout=0.5)
                    except Exception:
                        continue
                    if event is None:
                        break
                    try:
                        if "context" in event:
                            pass
                            # step = event.get("step", "?")
                            # logger.info(
                            #     f"[Worker] {step} context:\n{pformat(event['context'])}"
                            # )
                        else:
                            fov = event.get("fov")
                            t = event.get("t")
                            T = event.get("T")
                            message = event.get("message")
                            logger.info(f"FOV {fov}: {message} {t}/{T}")
                    except Exception:
                        # Never crash on malformed event
                        pass

            drainer = threading.Thread(target=_drain_progress, daemon=True)
            drainer.start()

            with ProcessPoolExecutor(max_workers=n_workers, mp_context=ctx) as executor:
                worker_ranges = precomputed_worker_ranges[batch_idx]

                futures = {
                    executor.submit(
                        run_single_worker,
                        fov_range,
                        metadata,
                        context,
                        progress_queue,
                    ): fov_range
                    for fov_range in worker_ranges
                    if fov_range
                }

                for future in as_completed(futures):
                    fov_range = futures[future]
                    try:
                        fov_indices_res, successful, failed, message, worker_ctx = (
                            future.result()
                        )
                        logger.info(
                            f"Merged context from worker {fov_indices_res[0]}-{fov_indices_res[-1]}"
                        )
                        # Merge worker's context back into parent
                        try:
                            _merge_contexts(context, worker_ctx)
                        except Exception:
                            logger.warning(
                                f"Failed to merge context from worker {fov_indices_res[0]}-{fov_indices_res[-1]}"
                            )
                        completed_fovs += successful
                        if failed > 0:
                            logger.error(
                                f"{failed} FOVs failed in range {fov_indices_res[0]}-{fov_indices_res[-1]}"
                            )
                    except Exception as e:
                        error_msg = f"Worker exception for FOVs {fov_range[0]}-{fov_range[-1]}: {str(e)}"
                        logger.error(error_msg)

                    progress = int(completed_fovs / total_fovs * 100)
                    logger.info(f"Progress: {progress}%")

            # Stop the drainer and shutdown manager
            try:
                progress_queue.put(None)
            except Exception:
                pass
            stop_event.set()
            drainer.join(timeout=2.0)
            try:
                manager.shutdown()
            except Exception:
                pass

        overall_success = completed_fovs == total_fovs
        logger.info(f"Completed processing {completed_fovs}/{total_fovs} FOVs")

        # Persist merged final context for downstream consumers
        try:
            yaml_path = output_dir / "processing_results.yaml"

            # Read existing results if file exists
            existing_context = ProcessingContext()
            if yaml_path.exists():
                try:
                    with yaml_path.open("r", encoding="utf-8") as f:
                        existing_dict = yaml.safe_load(f) or {}
                    logger.info(f"Loaded existing results from {yaml_path}")

                    # Convert dict back to ProcessingContext
                    existing_context = _deserialize_from_dict(existing_dict)
                except Exception as e:
                    logger.warning(f"Could not read existing {yaml_path}: {e}")
                    existing_context = ProcessingContext()

            # Merge new context into existing context
            merged_context = ensure_context(existing_context)
            _merge_contexts(merged_context, context)

            # Add time units to the merged context
            merged_context.time_units = "min"  # Time is in minutes for PyAMA

            safe_context = _serialize_for_yaml(merged_context)
            with yaml_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(
                    safe_context,
                    f,
                    sort_keys=False,
                    default_flow_style=False,
                    allow_unicode=True,
                )
            logger.info(f"Wrote processing results to {yaml_path}")
        except Exception as e:
            logger.warning(f"Failed to write processing_results.yaml: {e}")

        return overall_success
    except Exception as e:
        error_msg = f"Error in workflow pipeline: {str(e)}"
        logger.exception(error_msg)
        return False


def _deserialize_from_dict(data: dict) -> ProcessingContext:
    """Convert a dict back to a ProcessingContext object."""
    context = ProcessingContext()

    if not isinstance(data, dict):
        return context

    context.output_dir = (
        Path(data.get("output_dir")) if data.get("output_dir") else None
    )

    if data.get("channels"):
        channels_data = data["channels"]
        context.channels = Channels()
        context.channels.pc = channels_data.get("pc")
        context.channels.fl = channels_data.get("fl", [])

    if data.get("results_paths"):
        context.results_paths = {}
        for fov_str, fov_data in data["results_paths"].items():
            fov = int(fov_str)
            fov_entry = ensure_results_paths_entry()

            if fov_data.get("pc"):
                pc_data = fov_data["pc"]
                if isinstance(pc_data, (list, tuple)) and len(pc_data) == 2:
                    fov_entry.pc = (int(pc_data[0]), Path(pc_data[1]))

            if fov_data.get("fl"):
                for fl_item in fov_data["fl"]:
                    if isinstance(fl_item, (list, tuple)) and len(fl_item) == 2:
                        fov_entry.fl.append((int(fl_item[0]), Path(fl_item[1])))

            if fov_data.get("seg"):
                seg_data = fov_data["seg"]
                if isinstance(seg_data, (list, tuple)) and len(seg_data) == 2:
                    fov_entry.seg = (int(seg_data[0]), Path(seg_data[1]))

            if fov_data.get("seg_labeled"):
                seg_labeled_data = fov_data["seg_labeled"]
                if (
                    isinstance(seg_labeled_data, (list, tuple))
                    and len(seg_labeled_data) == 2
                ):
                    fov_entry.seg_labeled = (
                        int(seg_labeled_data[0]),
                        Path(seg_labeled_data[1]),
                    )

            if fov_data.get("fl_corrected"):
                for fl_corr_item in fov_data["fl_corrected"]:
                    if (
                        isinstance(fl_corr_item, (list, tuple))
                        and len(fl_corr_item) == 2
                    ):
                        fov_entry.fl_corrected.append(
                            (int(fl_corr_item[0]), Path(fl_corr_item[1]))
                        )

            if fov_data.get("traces_csv"):
                for trace_item in fov_data["traces_csv"]:
                    if isinstance(trace_item, (list, tuple)) and len(trace_item) == 2:
                        fov_entry.traces_csv.append(
                            (int(trace_item[0]), Path(trace_item[1]))
                        )

            context.results_paths[fov] = fov_entry

    context.params = data.get("params", {})
    context.time_units = data.get("time_units")

    return context


__all__ = [
    "run_complete_workflow",
]
