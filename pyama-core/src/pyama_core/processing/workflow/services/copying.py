"""
Copy service for extracting frames from ND2 files to NPY format.
"""

from pathlib import Path
import numpy as np
from numpy.lib.format import open_memmap
import logging

from pyama_core.processing.workflow.services.base import BaseProcessingService
from pyama_core.io import (
    MicroscopyMetadata,
    load_microscopy_file,
    get_microscopy_frame,
)
from pyama_core.processing.workflow.services.types import (
    ProcessingContext,
    ensure_context,
    ensure_results_entry,
)


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
        context = ensure_context(context)
        img, _ = load_microscopy_file(metadata.file_path)
        fov_dir = output_dir / f"fov_{fov:03d}"
        fov_dir.mkdir(parents=True, exist_ok=True)
        T, H, W = metadata.n_frames, metadata.height, metadata.width
        base_name = metadata.base_name

        plan: list[tuple[str, int]] = []
        pc_id = context.channels.pc
        fl_features = context.channels.fl_features
        if isinstance(pc_id, int):
            plan.append(("pc", pc_id))
        if fl_features:
            for ch in fl_features.keys():
                plan.append(("fl", int(ch)))

        if not plan:
            logger.info(f"FOV {fov}: No channels selected to copy. Skipping.")
            return

        for kind, ch in plan:
            logger.info(f"FOV {fov}: Processing {kind.upper()} channel {ch}")
            # Simple, consistent filenames
            token = "pc" if kind == "pc" else "fl"
            ch_path = fov_dir / f"{base_name}_fov_{fov:03d}_{token}_ch_{ch}.npy"

            # If output already exists, record it and skip processing for this channel
            if Path(ch_path).exists():
                logger.info(
                    f"FOV {fov}: {token.upper()} channel {ch} already exists, skipping copy"
                )
                fov_paths = context.results.setdefault(fov, ensure_results_entry())
                if kind == "fl":
                    fov_paths.fl.append((int(ch), Path(ch_path)))
                elif kind == "pc":
                    fov_paths.pc = (int(ch), Path(ch_path))
                continue

            ch_memmap = open_memmap(
                ch_path, mode="w+", dtype=np.uint16, shape=(T, H, W)
            )

            logger.info(f"FOV {fov}: Copying {kind.upper()} channel {ch}...")
            for t in range(T):
                ch_memmap[t] = get_microscopy_frame(img, fov, ch, t)
                self.progress_callback(fov, t, T, "Copying")
            # Ensure data is written and release the memmap
            try:
                ch_memmap.flush()
            except Exception:
                pass
            del ch_memmap

            fov_paths = context.results.setdefault(fov, ensure_results_entry())
            if kind == "fl":
                fov_paths.fl.append((int(ch), Path(ch_path)))
            elif kind == "pc":
                fov_paths.pc = (int(ch), Path(ch_path))

        logger.info(f"FOV {fov} copy completed")
