"""
Workflow pipeline for microscopy image analysis.
Consolidates types, helpers, and the orchestration function.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Mapping
import threading
import logging
from pathlib import Path
import yaml

from pyama_core.io import MicroscopyMetadata
from pyama_core.processing.workflow.services import (
    CopyingService,
    SegmentationService,
    CorrectionService,
    TrackingService,
    ExtractionService,
    ProcessingContext,
    ensure_context,
    ensure_results_entry,
)
from pyama_core.processing.workflow.services.types import (
    ChannelSelection,
    Channels,
)

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
    start_id = 0
    for i in range(n_workers):
        count = fovs_per_worker + (1 if i < remainder else 0)
        if count > 0:
            end_id = start_id + count
            worker_ranges.append(fovs[start_id:end_id])
            start_id = end_id
    return worker_ranges


def _merge_contexts(parent: ProcessingContext, child: ProcessingContext) -> None:
    """Merge a worker's context into the parent context in-place.

    - output_dir and channels: keep parent if present; fill from child if missing
    - params: add keys from child if missing in parent
    - results: per-FOV merge; for fluorescence and other tuple lists, union and de-duplicate
    """
    parent = ensure_context(parent)
    child = ensure_context(child)

    if parent.output_dir is None and child.output_dir is not None:
        parent.output_dir = child.output_dir

    if child.channels is not None:
        if parent.channels is None:
            parent.channels = Channels()
        parent.channels.merge_from(child.channels)

    if child.params:
        for key, value in child.params.items():
            parent.params.setdefault(key, value)

    # Merge time_units - if parent has no time_units, use child's time_units
    if child.time_units is not None:
        parent.time_units = child.time_units

    if child.results:
        for fov, child_entry in child.results.items():
            parent_entry = parent.results.setdefault(fov, ensure_results_entry())

            if child_entry.pc is not None and parent_entry.pc is None:
                parent_entry.pc = child_entry.pc

            if child_entry.seg is not None and parent_entry.seg is None:
                parent_entry.seg = child_entry.seg

            if child_entry.seg_labeled is not None and parent_entry.seg_labeled is None:
                parent_entry.seg_labeled = child_entry.seg_labeled

            if child_entry.fl_corrected:
                existing = {(id, str(path)) for id, path in parent_entry.fl_corrected}
                for id, path in child_entry.fl_corrected:
                    key = (id, str(path))
                    if key not in existing:
                        parent_entry.fl_corrected.append((id, path))
                        existing.add(key)

            if child_entry.fl:
                existing = {(id, str(path)) for id, path in parent_entry.fl}
                for id, path in child_entry.fl:
                    key = (id, str(path))
                    if key not in existing:
                        parent_entry.fl.append((id, path))
                        existing.add(key)

            if child_entry.traces and parent_entry.traces is None:
                parent_entry.traces = child_entry.traces


def _serialize_for_yaml(obj):
    """Convert context to a YAML-friendly representation.

    - pathlib.Path -> str
    - set -> list (sorted for determinism)
    - tuple -> list
    - dict/list: recurse
    - dataclasses: convert to dict
    """
    try:
        if isinstance(obj, ChannelSelection):
            return obj.to_payload()
        if isinstance(obj, Channels):
            return obj.to_raw()
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
    cancel_event: threading.Event | None = None,
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

        output_dir = context.output_dir
        if output_dir is None:
            raise ValueError("Processing context missing output_dir")

        logger.info(f"Processing FOVs {fovs[0]}-{fovs[-1]}")

        # Check for cancellation before starting processing
        if cancel_event and cancel_event.is_set():
            logger.info(
                f"Worker for FOVs {fovs[0]}-{fovs[-1]} cancelled before processing"
            )
            # Commented out cleanup to preserve partial results for debugging
            # _cleanup_fov_folders(output_dir, fovs[0], fovs[-1])
            return (fovs, 0, len(fovs), "Cancelled before processing", context)

        logger.info(f"Starting Segmentation for FOVs {fovs[0]}-{fovs[-1]}")
        segmentation.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fovs[0],
            fov_end=fovs[-1],
            cancel_event=cancel_event,
        )
        # Context merge happens automatically since we're using threads
        # No need to send context through queue

        # Check for cancellation after segmentation
        if cancel_event and cancel_event.is_set():
            logger.info(
                f"Worker for FOVs {fovs[0]}-{fovs[-1]} cancelled after segmentation"
            )
            # Commented out cleanup to preserve partial results for debugging
            # _cleanup_fov_folders(output_dir, fovs[0], fovs[-1])
            return (fovs, 1, len(fovs) - 1, "Cancelled after segmentation", context)

        logger.info(f"Starting Correction for FOVs {fovs[0]}-{fovs[-1]}")
        correction.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fovs[0],
            fov_end=fovs[-1],
            cancel_event=cancel_event,
        )
        # Context merge happens automatically since we're using threads
        # No need to send context through queue

        # Check for cancellation after correction
        if cancel_event and cancel_event.is_set():
            logger.info(
                f"Worker for FOVs {fovs[0]}-{fovs[-1]} cancelled after correction"
            )
            # Commented out cleanup to preserve partial results for debugging
            # _cleanup_fov_folders(output_dir, fovs[0], fovs[-1])
            return (fovs, 2, len(fovs) - 2, "Cancelled after correction", context)

        logger.info(f"Starting Tracking for FOVs {fovs[0]}-{fovs[-1]}")
        tracking.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fovs[0],
            fov_end=fovs[-1],
            cancel_event=cancel_event,
        )
        # Context merge happens automatically since we're using threads
        # No need to send context through queue

        # Check for cancellation after tracking
        if cancel_event and cancel_event.is_set():
            logger.info(
                f"Worker for FOVs {fovs[0]}-{fovs[-1]} cancelled after tracking"
            )
            # Commented out cleanup to preserve partial results for debugging
            # _cleanup_fov_folders(output_dir, fovs[0], fovs[-1])
            return (fovs, 3, len(fovs) - 3, "Cancelled after tracking", context)

        logger.info(f"Starting Extraction for FOVs {fovs[0]}-{fovs[-1]}")
        trace_extraction.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fovs[0],
            fov_end=fovs[-1],
            cancel_event=cancel_event,
        )
        # Context merge happens automatically since we're using threads
        # No need to send context through queue

        successful_count = len(fovs)
        success_msg = f"Completed processing FOVs {fovs[0]}-{fovs[-1]}"
        logger.info(success_msg)
        return fovs, successful_count, 0, success_msg, context

    except Exception as e:
        logger.exception(f"Error processing FOVs {fovs[0]}-{fovs[-1]}")
        error_msg = f"Error processing FOVs {fovs[0]}-{fovs[-1]}: {str(e)}"
        return fovs, 0, len(fovs), error_msg, context


def _cleanup_fov_folders(output_dir: Path, fov_start: int, fov_end: int) -> None:
    """Clean up FOV folders created during processing when cancelled.

    Args:
        output_dir: Output directory containing FOV folders
        fov_start: Starting FOV index
        fov_end: Ending FOV index
    """
    try:
        if not output_dir or not output_dir.exists():
            return

        logger.info("Cleaning up FOV folders after cancellation")

        # Remove only FOV directories for the range that was being processed
        for fov_idx in range(fov_start, fov_end + 1):
            fov_dir = output_dir / f"fov_{fov_idx:03d}"
            if fov_dir.exists() and fov_dir.is_dir():
                try:
                    import shutil

                    shutil.rmtree(fov_dir)
                    logger.debug("Removed FOV directory: %s", fov_dir)
                except Exception as e:
                    logger.warning("Failed to remove FOV directory %s: %s", fov_dir, e)

    except Exception as e:
        logger.warning("Error during FOV folder cleanup: %s", e)


def run_complete_workflow(
    metadata: MicroscopyMetadata,
    context: ProcessingContext,
    fov_start: int | None = None,
    fov_end: int | None = None,
    batch_size: int = 2,
    n_workers: int = 2,
    cancel_event: threading.Event | None = None,
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

        for batch_id, batch_fovs in enumerate(batches):
            # Check for cancellation before starting batch
            if cancel_event and cancel_event.is_set():
                logger.info("Workflow cancelled before batch processing")
                # Commented out cleanup to preserve partial results for debugging
                # _cleanup_fov_folders(output_dir, fov_start, fov_end)
                return False

            logger.info(f"Extracting batch: FOVs {batch_fovs[0]}-{batch_fovs[-1]}")
            try:
                copy_service.process_all_fovs(
                    metadata=metadata,
                    context=context,
                    output_dir=output_dir,
                    fov_start=batch_fovs[0],
                    fov_end=batch_fovs[-1],
                    cancel_event=cancel_event,
                )
                # logger.info(f"After Copy context:\n{pformat(context)}")
            except Exception as e:
                logger.error(
                    f"Failed to extract batch starting at FOV {batch_fovs[0]}: {e}"
                )
                return False

            # Check for cancellation after copying
            if cancel_event and cancel_event.is_set():
                logger.info(
                    "Workflow cancelled after copying, before parallel processing"
                )
                # Commented out cleanup to preserve partial results for debugging
                # _cleanup_fov_folders(output_dir, fov_start, fov_end)
                return False

            logger.info(f"Processing batch in parallel with {n_workers} workers")

            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                worker_ranges = precomputed_worker_ranges[batch_id]

                futures = {
                    executor.submit(
                        run_single_worker,
                        fov_range,
                        metadata,
                        context,
                        cancel_event,
                    ): fov_range
                    for fov_range in worker_ranges
                    if fov_range
                }

                # Process futures with cancellation support
                # No timeout - let users cancel manually if needed
                for future in as_completed(futures):
                    # Check for cancellation after each future completes
                    if cancel_event and cancel_event.is_set():
                        logger.info("Workflow cancelled during parallel processing")
                        # Cancel remaining futures
                        for remaining_future in futures:
                            if not remaining_future.done():
                                remaining_future.cancel()
                        # Commented out cleanup to preserve partial results for debugging
                        # _cleanup_fov_folders(output_dir, fov_start, fov_end)
                        return False

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

        # Final cancellation check after all batches
        if cancel_event and cancel_event.is_set():
            logger.info("Workflow cancelled after batch processing")
            # Commented out cleanup to preserve partial results for debugging
            # _cleanup_fov_folders(output_dir, fov_start, fov_end)
            return False

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

    channels_data = data.get("channels")
    if channels_data is None:
        context.channels = Channels()
    elif isinstance(channels_data, Mapping):
        context.channels = Channels.from_serialized(channels_data)
    else:
        raise ValueError("Invalid 'channels' section when deserializing context")

    results_block = data.get("results") or data.get("results_paths")
    if results_block:
        context.results = {}
        for fov_str, fov_data in results_block.items():
            fov = int(fov_str)
            fov_entry = ensure_results_entry()

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

            traces_value = fov_data.get("traces")
            if isinstance(traces_value, (str, Path)):
                fov_entry.traces = Path(traces_value)
            elif fov_data.get("traces_csv"):
                for trace_item in fov_data["traces_csv"]:
                    if isinstance(trace_item, (list, tuple)) and len(trace_item) == 2:
                        # Legacy structure; keep first path encountered
                        fov_entry.traces = Path(trace_item[1])
                        break

        context.results[fov] = fov_entry

    context.params = data.get("params", {})
    context.time_units = data.get("time_units")

    return context


__all__ = [
    "run_complete_workflow",
]
