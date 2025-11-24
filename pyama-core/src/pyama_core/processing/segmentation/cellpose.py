"""CellPose-SAM-based segmentation (functional API).

Pipeline per frame:
- convert grayscale image to 3-channel format (CellPose-SAM requirement)
- apply CellPose-SAM model to detect cell boundaries
- convert labeled masks to binary foreground/background masks

This implementation is optimized for unpatterned surfaces with clustering cells.
CellPose-SAM uses deep learning to identify cell boundaries, making it effective
for dense cell cultures where traditional thresholding methods struggle.

This implementation processes 3D inputs frame-by-frame to keep peak memory low
and provides an optional progress callback.

Note: CellPose-SAM (v4+) requires 3-channel images. Grayscale images are
automatically converted to 3-channel by replicating the channel.
"""

import numpy as np
from typing import Callable
import logging

logger = logging.getLogger(__name__)

# Try to import CellPose, raise informative error if not available
try:
    from cellpose import models
    from cellpose.core import assign_device
    CELLPOSE_AVAILABLE = True
except ImportError:
    CELLPOSE_AVAILABLE = False
    models = None
    assign_device = None


def segment_cell(
    image: np.ndarray,
    out: np.ndarray,
    progress_callback: Callable | None = None,
    cancel_event=None,
    pretrained_model: str = "cpsam",
    diameter: float | None = None,
    flow_threshold: float = 0.4,
    cellprob_threshold: float = 0.0,
    min_size: int = 15,
    max_size_fraction: float = 0.4,
    normalize: bool | dict = True,
    gpu: bool | None = None,
    device=None,
) -> None:
    """Segment a 3D stack using CellPose-SAM deep learning model.

    For each frame, converts grayscale to 3-channel format, applies CellPose-SAM
    to detect cell boundaries, and converts the labeled masks to binary
    foreground/background masks. Writes results into ``out`` in-place.

    Args:
        image: 3D float-like array ``(T, H, W)``. Grayscale images will be
            converted to 3-channel format automatically.
        out: Preallocated boolean array ``(T, H, W)`` for masks.
        progress_callback: Optional callable ``(t, total, msg)`` for progress.
        cancel_event: Optional threading.Event for cancellation support.
        pretrained_model: CellPose model path or name. Default is 'cpsam'
            (CellPose-SAM, recommended for cell segmentation).
        diameter: Expected cell diameter in pixels. If None, CellPose will estimate.
        flow_threshold: Flow error threshold for mask filtering (0-1). Lower values
            are more permissive. Default 0.4.
        cellprob_threshold: Cell probability threshold. Lower values include more
            pixels as cells. Default 0.0 (uses CellPose default).
        min_size: Minimum mask size in pixels. Masks smaller than this are
            discarded. Default 15.
        max_size_fraction: Maximum mask size as fraction of image size. Masks
            larger than this fraction are removed. Default 0.4.
        normalize: Normalization settings. If True, uses default normalization.
            Can also pass a dict with normalization parameters. Default True.
        gpu: Whether to use GPU if available. If None, auto-detects GPU availability.
        device: PyTorch device (e.g., torch.device("cuda")). Overrides gpu parameter.

    Returns:
        None. Results are written to ``out``.

    Raises:
        ImportError: If CellPose is not installed.
        ValueError: If ``image`` and ``out`` are not 3D arrays or shapes differ.
    """
    if not CELLPOSE_AVAILABLE:
        raise ImportError(
            "CellPose is not installed. Install it with: pip install cellpose"
        )

    if image.ndim != 3 or out.ndim != 3:
        raise ValueError("image and out must be 3D arrays")

    if out.shape != image.shape:
        raise ValueError("image and out must have the same shape (T, H, W)")

    # Convert to float32 for processing (view if possible, copy if needed)
    image = image.astype(np.float32, copy=False)
    out = out.astype(bool, copy=False)

    # Initialize CellPose-SAM model (reuse across frames for efficiency)
    # CellPose v4+ uses assign_device instead of use_gpu
    if device is None:
        if gpu is None:
            # Auto-detect GPU
            device, gpu = assign_device(gpu=False)
        else:
            device, _ = assign_device(gpu=gpu)
    
    logger.info("Initializing CellPose-SAM model '%s' (device: %s)", pretrained_model, device)
    model = models.CellposeModel(pretrained_model=pretrained_model, device=device)

    n_frames = image.shape[0]
    for t in range(n_frames):
        # Check for cancellation before processing each frame
        if cancel_event and cancel_event.is_set():
            logger.info("Segmentation cancelled at frame %d", t)
            return

        # Extract single frame (copy to avoid modifying input)
        frame = image[t].copy()
        
        # CellPose-SAM requires 3-channel images (C, H, W format)
        # Convert grayscale (H, W) to 3-channel (3, H, W) by replicating
        if frame.ndim == 2:
            # Grayscale: replicate to 3 channels
            frame = np.stack([frame, frame, frame], axis=0)  # (3, H, W)
        elif frame.ndim == 3:
            # Already has channels, ensure it's (C, H, W) format
            if frame.shape[0] != 3:
                # Assume (H, W, C) format, transpose to (C, H, W)
                if frame.shape[2] == 3:
                    frame = frame.transpose(2, 0, 1)  # (C, H, W)
                else:
                    raise ValueError(
                        f"Frame {t} has unexpected shape: {frame.shape}. "
                        "Expected (H, W) grayscale or (H, W, 3) RGB or (3, H, W) RGB."
                    )
        else:
            raise ValueError(f"Frame {t} has unexpected dimensions: {frame.shape}")

        # Run CellPose-SAM segmentation
        # CellPose-SAM expects (C, H, W) format where C=3
        # Returns: masks (labeled), flows, styles
        result = model.eval(
            frame,  # (3, H, W) array
            diameter=diameter,
            flow_threshold=flow_threshold,
            cellprob_threshold=cellprob_threshold,
            min_size=min_size,
            max_size_fraction=max_size_fraction,
            normalize=normalize,
            channel_axis=0,  # Channels are in first dimension
            compute_masks=True,
        )

        # Handle return value: for single image, returns (masks, flows, styles)
        # masks is a 2D array (H, W) with labeled regions
        if isinstance(result, tuple):
            masks = result[0]
        else:
            masks = result

        # Convert labeled masks to binary (foreground = any cell)
        # CellPose-SAM returns masks where 0 is background and >0 are cell IDs
        binary_mask = masks > 0
        out[t] = binary_mask

        if progress_callback is not None:
            progress_callback(t, n_frames, "CellPose-SAM Segmentation")

    logger.info("CellPose-SAM segmentation completed for %d frames", n_frames)
