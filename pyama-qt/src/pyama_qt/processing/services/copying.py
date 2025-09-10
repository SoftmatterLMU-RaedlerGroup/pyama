"""
Copy service for extracting frames from ND2 files to NPY format.
"""

from pathlib import Path
from PySide6.QtCore import QObject
from functools import partial
import numpy as np
from numpy.lib.format import open_memmap

from .base import BaseProcessingService
from pyama_core.processing.copying import copy_npy
import logging
from pyama_core.io.nikon import ND2Metadata, load_nd2, get_nd2_time_stack
from typing import Any

logger = logging.getLogger(__name__)


class CopyingService(BaseProcessingService):
    """Service for copying channels from ND2 files to NPY files.

    Context contract (read/write):
    - Read:  context["channels"] = {"phase_contrast": int | None, "fluorescence": int | None}
             Channel indices refer to ND2 channels; either can be None.
    - Write: context["npy_paths"][fov] = {
                "phase_contrast": Path | None,
                "fluorescence": Path | None,
             }
    """

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.name = "Copy"

    def process_fov(
        self,
        metadata: ND2Metadata,
        context: dict[str, Any],
        output_dir: Path,
        f: int,
    ) -> None:
        """
        Process a single field of view: extract and save channel data.

        Args:
            metadata: Metadata from file loading
            context: Context for the processing
            output_dir: Output directory for results
            f: Field of view index to process

        Returns:
            None
        """
        try:
            # Always use ND2Metadata
            da, _ = load_nd2(metadata.nd2_path)
            fov_dir = output_dir / f"fov_{f:04d}"
            fov_dir.mkdir(parents=True, exist_ok=True)
            T, H, W = metadata.n_frames, metadata.height, metadata.width
            base_name = metadata.base_name
            channel_names = list(metadata.channel_names)

            # Ensure context structure exists
            channels_ctx = context.setdefault(
                "channels", {"phase_contrast": None, "fluorescence": None}
            )
            npy_paths_ctx = context.setdefault("npy_paths", {})
            npy_paths_ctx.setdefault(f, {"phase_contrast": None, "fluorescence": None})

            # Build channel plan: only copy selected channels
            plan: list[tuple[str, int]] = []
            pc_idx = channels_ctx.get("phase_contrast")
            fl_idx = channels_ctx.get("fluorescence")
            if isinstance(pc_idx, int):
                plan.append(("phase_contrast", pc_idx))
            if isinstance(fl_idx, int):
                plan.append(("fluorescence", fl_idx))

            # Nothing to copy
            if not plan:
                logger.info(f"FOV {f}: No channels selected to copy. Skipping.")
                return

            for kind, ch in plan:
                # Standardized filename pattern used by downstream steps
                ch_path = fov_dir / f"{base_name}_fov{f:04d}_{kind}_raw.npy"
                ch_memmap = open_memmap(
                    ch_path, mode="w+", dtype=np.uint16, shape=(T, H, W)
                )

                copy_npy(
                    get_nd2_time_stack(da, f, ch),
                    ch_memmap,
                    progress_callback=partial(self.progress_callback, f=f),
                )
                # Close memmap to ensure header is flushed to disk
                ch_memmap.close()

                # Record path in context for later steps
                npy_paths_ctx[f][kind] = ch_path

            logger.info(f"FOV {f} copy completed")
        except Exception as e:
            logger.exception(f"Error copying FOV {f}: {str(e)}")
            raise e
