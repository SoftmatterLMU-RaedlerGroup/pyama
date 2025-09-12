"""
Workflow coordination for microscopy image analysis.
"""

from __future__ import annotations

from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import logging
from typing import TypedDict

from pyama_core.io.nikon import ND2Metadata
from pyama_core.workflow.services.copying import CopyingService
from pyama_core.workflow.worker import process_fov_range


class Channels(TypedDict, total=False):
    phase_contrast: int
    fluorescence: list[int]


class NpyPathsForFov(TypedDict, total=False):
    phase_contrast: Path
    fluorescence: list[Path]


class ProcessingContext(TypedDict, total=False):
    output_dir: Path
    channels: Channels
    npy_paths: dict[int, NpyPathsForFov]
    params: dict


logger = logging.getLogger(__name__)


class ProcessingWorkflow:
    def __init__(self) -> None:
        self.copy_service = CopyingService()

    def run_complete_workflow(
        self,
        metadata: ND2Metadata,
        context: ProcessingContext,
        fov_start: int | None = None,
        fov_end: int | None = None,
        batch_size: int = 4,
        n_workers: int = 4,
    ) -> bool:
        overall_success = False

        try:
            output_dir = context["output_dir"]
            output_dir.mkdir(parents=True, exist_ok=True)

            n_fov = int(metadata.n_fovs)
            if fov_start is None:
                fov_start = 0
            if fov_end is None:
                fov_end = n_fov - 1

            if fov_start < 0 or fov_end >= n_fov or fov_start > fov_end:
                logger.error(
                    f"Invalid FOV range: {fov_start}-{fov_end} (file has {n_fov} FOVs)"
                )
                return False

            total_fovs = fov_end - fov_start + 1
            fov_indices = list(range(fov_start, fov_end + 1))

            completed_fovs = 0
            for batch_start in range(0, total_fovs, batch_size):
                batch_end = min(batch_start + batch_size, total_fovs)
                batch_fovs = fov_indices[batch_start:batch_end]

                logger.info(f"Extracting batch: FOVs {batch_fovs[0]}-{batch_fovs[-1]}")
                try:
                    self.copy_service.process_all_fovs(
                        metadata=metadata,
                        context=context,
                        output_dir=output_dir,
                        fov_start=batch_fovs[0],
                        fov_end=batch_fovs[-1],
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to extract batch starting at FOV {batch_fovs[0]}: {e}"
                    )
                    return False

                logger.info(f"Processing batch in parallel with {n_workers} workers")

                ctx = mp.get_context("spawn")
                with ProcessPoolExecutor(
                    max_workers=n_workers, mp_context=ctx
                ) as executor:
                    fovs_per_worker = len(batch_fovs) // n_workers
                    remainder = len(batch_fovs) % n_workers

                    worker_ranges = []
                    start_idx = 0
                    for i in range(n_workers):
                        count = fovs_per_worker + (1 if i < remainder else 0)
                        if count > 0:
                            end_idx = start_idx + count
                            worker_ranges.append(batch_fovs[start_idx:end_idx])
                            start_idx = end_idx

                    futures = {
                        executor.submit(
                            process_fov_range,
                            fov_range,
                            metadata,
                            context,
                        ): fov_range
                        for fov_range in worker_ranges
                        if fov_range
                    }

                    for future in as_completed(futures):
                        fov_range = futures[future]
                        try:
                            fov_indices_res, successful, failed, message = (
                                future.result()
                            )
                            logger.info(message)
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

            overall_success = completed_fovs == total_fovs
            logger.info(f"Completed processing {completed_fovs}/{total_fovs} FOVs")
            return overall_success
        except Exception as e:
            error_msg = f"Error in parallel workflow: {str(e)}"
            logger.exception(error_msg)
            return False
