"""
Copy service for extracting frames from ND2 files to NPY format.
"""

from __future__ import annotations

from pathlib import Path
from functools import partial
import numpy as np
from numpy.lib.format import open_memmap
import logging

from .base import BaseProcessingService
from pyama_core.processing.copying import copy_npy
from pyama_core.io import (
    MicroscopyMetadata,
    load_microscopy_file,
    get_microscopy_time_stack,
)
from .types import ProcessingContext


logger = logging.getLogger(__name__)


class CopyingService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Copy"

    def process_fov(
        self,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        output_dir: Path,
        fov: int,
    ) -> None:
        img, _ = load_microscopy_file(metadata.file_path)
        fov_dir = output_dir / f"fov_{fov:03d}"
        fov_dir.mkdir(parents=True, exist_ok=True)
        T, H, W = metadata.n_frames, metadata.height, metadata.width
        base_name = metadata.base_name

        channels_ctx = context.setdefault("channels", {"pc": None, "fl": []})
        results_paths_ctx = context.setdefault("results_paths", {})
        results_paths_ctx.setdefault(
            fov,
            {
                "fl": [],
                "fl_corrected": [],
                "traces_csv": [],
            },
        )

        plan: list[tuple[str, int]] = []
        pc_idx = channels_ctx.get("pc")
        fl_list = channels_ctx.get("fl")
        if isinstance(pc_idx, int):
            plan.append(("pc", pc_idx))
        if isinstance(fl_list, list) and fl_list:
            for ch in fl_list:
                try:
                    plan.append(("fl", int(ch)))
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
            # Simple, consistent filenames
            token = "pc" if kind == "pc" else "fl"
            ch_path = fov_dir / f"{base_name}_fov_{fov:03d}_{token}_ch_{ch}.npy"

            # If output already exists, record it and skip processing for this channel
            if Path(ch_path).exists():
                logger.info(
                    f"FOV {fov}: {token.upper()} channel {ch} already exists, skipping copy"
                )
                if kind == "fl":
                    fl_list_out = results_paths_ctx[fov].setdefault("fl", [])
                    fl_list_out.append((ch, ch_path))
                elif kind == "pc":
                    results_paths_ctx[fov]["pc"] = (ch, ch_path)
                continue

            ch_memmap = open_memmap(
                ch_path, mode="w+", dtype=np.uint16, shape=(T, H, W)
            )

            copy_npy(
                get_microscopy_time_stack(img, fov, ch),
                ch_memmap,
                progress_callback=partial(self.progress_callback, fov),
            )
            # Ensure data is written and release the memmap
            try:
                ch_memmap.flush()
            except Exception:
                pass
            del ch_memmap

            if kind == "fl":
                fl_list_out = results_paths_ctx[fov].setdefault("fl", [])
                fl_list_out.append((ch, ch_path))
            elif kind == "pc":
                results_paths_ctx[fov]["pc"] = (ch, ch_path)

        logger.info(f"FOV {fov} copy completed")
