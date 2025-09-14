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
from pyama_core.workflow.services.types import ProcessingContext


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
        fov: int,
    ) -> None:
        da, _ = load_nd2(metadata.nd2_path)
        fov_dir = output_dir / f"fov_{fov:04d}"
        fov_dir.mkdir(parents=True, exist_ok=True)
        T, H, W = metadata.n_frames, metadata.height, metadata.width
        base_name = metadata.base_name

        channels_ctx = context.setdefault(
            "channels", {"phase_contrast": None, "fluorescence": []}
        )
        npy_paths_ctx = context.setdefault("npy_paths", {})
        npy_paths_ctx.setdefault(
            fov,
            {
                "fluorescence": [],
                "fluorescence_corrected": [],
                "traces_csv": [],
            },
        )

        plan: list[tuple[str, int]] = []
        pc_idx = channels_ctx.get("phase_contrast")
        fl_list = channels_ctx.get("fluorescence")
        if isinstance(pc_idx, int):
            plan.append(("phase_contrast", pc_idx))
        if isinstance(fl_list, list) and fl_list:
            for ch in fl_list:
                try:
                    plan.append(("fluorescence", int(ch)))
                except Exception:
                    continue

        if not plan:
            logger.info(f"FOV {fov}: No channels selected to copy. Skipping.")
            return

        def _sanitize(name: str) -> str:
            try:
                safe = "".join(
                    c if c.isalnum() or c in ("-", "_") else "_" for c in name
                )
                while "__" in safe:
                    safe = safe.replace("__", "_")
                return safe.strip("_") or "unnamed"
            except Exception:
                return "unnamed"

        for kind, ch in plan:
            # Include channel index and, if available, channel label in filename
            label = None
            try:
                label = (
                    metadata.channel_names[ch]
                    if 0 <= ch < len(metadata.channel_names)
                    else None
                )
            except Exception:
                label = None
            label_part = f"_{_sanitize(label)}" if label else ""
            ch_path = (
                fov_dir / f"{base_name}_fov{fov:04d}_{kind}_c{ch}{label_part}_raw.npy"
            )
            ch_memmap = open_memmap(
                ch_path, mode="w+", dtype=np.uint16, shape=(T, H, W)
            )

            copy_npy(
                get_nd2_time_stack(da, fov, ch),
                ch_memmap,
                progress_callback=partial(self.progress_callback, fov),
            )
            # Ensure data is written and release the memmap
            try:
                ch_memmap.flush()
            except Exception:
                pass
            del ch_memmap

            if kind == "fluorescence":
                fl_list_out = npy_paths_ctx[fov].setdefault("fluorescence", [])
                fl_list_out.append((ch, ch_path))
            elif kind == "phase_contrast":
                npy_paths_ctx[fov][kind] = (ch, ch_path)

        logger.info(f"FOV {fov} copy completed")
