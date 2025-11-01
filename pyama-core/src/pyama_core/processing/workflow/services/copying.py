"""
Copy service for extracting frames from ND2 files to NPY format.
"""

from pathlib import Path
import numpy as np
import logging
from numpy.lib.format import open_memmap

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
        cancel_event=None,
    ) -> None:
        context = ensure_context(context)
        img, _ = load_microscopy_file(metadata.file_path)
        fov_dir = output_dir / f"fov_{fov:03d}"
        fov_dir.mkdir(parents=True, exist_ok=True)
        T, H, W = metadata.n_frames, metadata.height, metadata.width
        base_name = metadata.base_name

        plan: list[tuple[str, int]] = []
        context_channels = context.get("channels")
        if context_channels:
            pc_selection = context_channels.get("pc")
            if pc_selection is not None:
                plan.append(("pc", pc_selection.get("channel", 0)))
            for selection in context_channels.get("fl", []):
                plan.append(("fl", selection.get("channel", 0)))

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
                context_results = context.setdefault("results", {})
                fov_paths = context_results.setdefault(fov, ensure_results_entry())
                if kind == "fl":
                    fl_list = fov_paths.setdefault("fl", [])
                    fl_list.append((int(ch), str(ch_path)))
                elif kind == "pc":
                    fov_paths["pc"] = (int(ch), str(ch_path))
                continue

            # Create memory-mapped array and write data
            logger.info(f"FOV {fov}: Copying {kind.upper()} channel {ch}...")
            ch_memmap = None
            try:
                ch_memmap = open_memmap(
                    ch_path, mode="w+", dtype=np.uint16, shape=(T, H, W)
                )
                for t in range(T):
                    # Check for cancellation before processing each frame
                    if cancel_event and cancel_event.is_set():
                        logger.info(
                            f"Copying cancelled at FOV {fov}, channel {ch}, frame {t}"
                        )
                        # Clean up the memmap file since copying was interrupted
                        try:
                            del ch_memmap
                            ch_path.unlink(missing_ok=True)  # Remove partial file
                        except Exception:
                            pass
                        return

                    ch_memmap[t] = get_microscopy_frame(img, fov, ch, t)
                    self.progress_callback(fov, t, T, "Copying")
                # Flush changes to disk
                ch_memmap.flush()
            except Exception:
                if ch_memmap is not None:
                    try:
                        del ch_memmap
                    except Exception:
                        pass
                raise
            finally:
                if ch_memmap is not None:
                    try:
                        del ch_memmap
                    except Exception:
                        pass

            context_results = context.setdefault("results", {})
            fov_paths = context_results.setdefault(fov, ensure_results_entry())
            if kind == "fl":
                fl_list = fov_paths.setdefault("fl", [])
                fl_list.append((int(ch), str(ch_path)))
            elif kind == "pc":
                fov_paths["pc"] = (int(ch), str(ch_path))

        logger.info(f"FOV {fov} copy completed")
