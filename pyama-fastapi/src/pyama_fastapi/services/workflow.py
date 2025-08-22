from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import logging
import multiprocessing as mp
from logging.handlers import QueueHandler
from pathlib import Path
from typing import Any

from pyama_qt.processing.services.copy import CopyService
from pyama_qt.processing.services.binarization import BinarizationService
from pyama_qt.processing.services.background_correction import BackgroundCorrectionService
from pyama_qt.processing.services.trace_extraction import TraceExtractionService


def _process_fov_range_worker(
    fov_indices: list[int],
    data_info: dict[str, Any],
    output_dir: Path,
    params: dict[str, Any],
    log_queue: mp.Queue,
) -> tuple[list[int], int, int, str]:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not root_logger.handlers:
        handler = QueueHandler(log_queue)
        root_logger.addHandler(handler)

    logger = logging.getLogger(__name__)

    try:
        binarization = BinarizationService(None)
        background_correction = BackgroundCorrectionService(None)
        trace_extraction = TraceExtractionService(None)

        logger.info(f"Processing FOVs {fov_indices[0]}-{fov_indices[-1]}")

        success = binarization.process_all_fovs(
            data_info=data_info,
            output_dir=output_dir,
            params={
                "mask_size": params.get("mask_size", 3),
                "binarization_method": params.get("binarization_method", "log-std"),
            },
            fov_start=fov_indices[0],
            fov_end=fov_indices[-1],
        )
        if not success:
            return fov_indices, 0, len(fov_indices), "Binarization failed"

        bg_correction_method = params.get("background_correction_method", "None")
        if bg_correction_method != "None":
            success = background_correction.process_all_fovs(
                data_info=data_info,
                output_dir=output_dir,
                params={
                    "div_horiz": params.get("div_horiz", 7),
                    "div_vert": params.get("div_vert", 5),
                    "background_correction_method": bg_correction_method,
                    "footprint_size": params.get("footprint_size", 25),
                },
                fov_start=fov_indices[0],
                fov_end=fov_indices[-1],
            )
            if not success:
                return fov_indices, 0, len(fov_indices), "Background correction failed"

        success = trace_extraction.process_all_fovs(
            data_info=data_info,
            output_dir=output_dir,
            params={
                "min_trace_length": params.get("min_trace_length", 20),
                "background_correction_method": params.get("background_correction_method", "None"),
            },
            fov_start=fov_indices[0],
            fov_end=fov_indices[-1],
        )
        if not success:
            return fov_indices, 0, len(fov_indices), "Trace extraction failed"

        return fov_indices, len(fov_indices), 0, "ok"
    except Exception as e:
        return fov_indices, 0, len(fov_indices), f"Error: {e}"


def run_complete_workflow_headless(
    nd2_path: str,
    data_info: dict[str, Any],
    output_dir: Path,
    params: dict[str, Any],
    fov_start: int | None = None,
    fov_end: int | None = None,
    batch_size: int = 4,
    n_workers: int = 4,
) -> tuple[bool, str]:
    log_queue = mp.Manager().Queue()

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        n_fov = int(data_info["metadata"]["n_fov"])  # type: ignore[index]
        if fov_start is None:
            fov_start = 0
        if fov_end is None:
            fov_end = n_fov - 1
        if fov_start < 0 or fov_end >= n_fov or fov_start > fov_end:
            return False, f"Invalid FOV range: {fov_start}-{fov_end}"

        total_fovs = fov_end - fov_start + 1
        fov_indices = list(range(fov_start, fov_end + 1))

        copy_service = CopyService(None)

        completed_fovs = 0
        for batch_start in range(0, total_fovs, batch_size):
            batch_end = min(batch_start + batch_size, total_fovs)
            batch_fovs = fov_indices[batch_start:batch_end]

            extraction_success = copy_service.process_batch(
                nd2_path, batch_fovs, data_info, output_dir, params
            )
            if not extraction_success:
                return False, f"Copy failed for FOVs {batch_fovs[0]}-{batch_fovs[-1]}"

            ctx = mp.get_context("spawn")
            with ProcessPoolExecutor(max_workers=n_workers, mp_context=ctx) as executor:
                fovs_per_worker = len(batch_fovs) // n_workers
                remainder = len(batch_fovs) % n_workers
                worker_ranges: list[list[int]] = []
                start_idx = 0
                for i in range(n_workers):
                    count = fovs_per_worker + (1 if i < remainder else 0)
                    if count > 0:
                        end_idx = start_idx + count
                        worker_ranges.append(batch_fovs[start_idx:end_idx])
                        start_idx = end_idx

                futures = {
                    executor.submit(
                        _process_fov_range_worker,
                        fov_range,
                        data_info,
                        output_dir,
                        params,
                        log_queue,
                    ): fov_range
                    for fov_range in worker_ranges
                    if fov_range
                }

                for future in as_completed(futures):
                    fov_range = futures[future]
                    try:
                        _fov_idx, successful, failed, message = future.result()
                        completed_fovs += successful
                        if failed > 0:
                            return False, message
                    except Exception as e:
                        return False, f"Worker exception for FOVs {fov_range[0]}-{fov_range[-1]}: {e}"

        success = completed_fovs == total_fovs
        return (True, f"Completed processing {completed_fovs}/{total_fovs} FOVs") if success else (False, f"Completed {completed_fovs}/{total_fovs} with failures")
    except Exception as e:
        return False, f"Error: {e}"



