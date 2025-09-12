"""
Copy service for extracting frames from ND2 files to NPY format.
"""

from __future__ import annotations

from pathlib import Path
from functools import partial
import numpy as np
from numpy.lib.format import open_memmap
import logging

from pyama_core.workflow.services.base import BaseProcessingService
from pyama_core.processing.copying import copy_npy
from pyama_core.io import ND2Metadata, load_nd2, get_nd2_time_stack
from pyama_core.workflow import ProcessingContext


logger = logging.getLogger(__name__)


class CopyingService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Copy"

    def process_fov(
        self,
        metadata: ND2Metadata,
        context: ProcessingContext,
        output_dir: Path,
        f: int,
    ) -> None:
        da, _ = load_nd2(metadata.nd2_path)
        fov_dir = output_dir / f"fov_{f:04d}"
        fov_dir.mkdir(parents=True, exist_ok=True)
        T, H, W = metadata.n_frames, metadata.height, metadata.width
        base_name = metadata.base_name

        channels_ctx = context.setdefault(
            "channels", {"phase_contrast": None, "fluorescence": []}
        )
        npy_paths_ctx = context.setdefault("npy_paths", {})
        npy_paths_ctx.setdefault(f, {"fluorescence": []})

        plan: list[tuple[str, int]] = []
        pc_idx = channels_ctx.get("phase_contrast")
        fl_list = channels_ctx.get("fluorescence")
        if isinstance(pc_idx, int):
            plan.append(("phase_contrast", pc_idx))
        if isinstance(fl_list, list) and fl_list:
            # For now, copy only the first fluorescence channel; extend later if needed
            plan.append(("fluorescence", int(fl_list[0])))

        if not plan:
            logger.info(f"FOV {f}: No channels selected to copy. Skipping.")
            return

        for kind, ch in plan:
            ch_path = fov_dir / f"{base_name}_fov{f:04d}_{kind}_raw.npy"
            ch_memmap = open_memmap(
                ch_path, mode="w+", dtype=np.uint16, shape=(T, H, W)
            )

            copy_npy(
                get_nd2_time_stack(da, f, ch),
                ch_memmap,
                progress_callback=partial(self.progress_callback, f=f),
            )
            ch_memmap.close()

            if kind == "fluorescence":
                fl_list_out = npy_paths_ctx[f].setdefault("fluorescence", [])
                fl_list_out.append(ch_path)
            else:
                npy_paths_ctx[f][kind] = ch_path

        logger.info(f"FOV {f} copy completed")
