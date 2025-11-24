"""Bayesian tracking (btrack) for actively moving cells.

This module uses BayesianTracker for tracking cells that move more actively.
btrack uses probabilistic models and Kalman filtering to handle complex motion
patterns, making it suitable for cells with rapid movement, occlusions, and
non-linear trajectories.

The public entrypoint is ``track_cell`` which operates in-place on the
preallocated output array.
"""

import numpy as np
from typing import Callable
import logging

logger = logging.getLogger(__name__)

# Try to import btrack, raise informative error if not available
try:
    from btrack import BayesianTracker
    from btrack.io import segmentation_to_objects
    from btrack.utils import update_segmentation
    from btrack import constants
    BTRACK_AVAILABLE = True
except ImportError:
    BTRACK_AVAILABLE = False
    BayesianTracker = None
    segmentation_to_objects = None
    update_segmentation = None
    constants = None


def track_cell(
    image: np.ndarray,
    out: np.ndarray,
    min_size: int | None = None,
    max_size: int | None = None,
    progress_callback: Callable | None = None,
    cancel_event=None,
    motion_model=None,
    object_model=None,
    hypothesis_model=None,
    tracking_updates=None,
    volume=None,
    max_search_radius: float | None = None,
    **tracker_kwargs,
) -> None:
    """Track cells across frames using BayesianTracker.

    Extracts regions per frame, converts them to trackable objects, and uses
    BayesianTracker with probabilistic models to maintain consistent cell IDs
    across frames. Writes results into ``out`` in-place.

    Args:
        image: 3D boolean array ``(T, H, W)`` with segmented foreground.
        out: Preallocated integer array ``(T, H, W)`` to receive labeled IDs.
        min_size: Minimum region size to track in pixels (inclusive).
            Regions smaller than this are filtered out before tracking.
        max_size: Maximum region size to track in pixels (inclusive).
            Regions larger than this are filtered out before tracking.
        progress_callback: Optional callable ``(t, total, msg)`` for progress.
        cancel_event: Optional threading.Event for cancellation support.
        motion_model: Optional btrack MotionModel. If None, uses default.
        object_model: Optional btrack ObjectModel. If None, uses default.
        hypothesis_model: Optional btrack HypothesisModel. If None, uses default.
        tracking_updates: Optional list of tracking update features to use.
            See btrack.constants.BayesianUpdateFeatures for options.
        volume: Optional imaging volume tuple. If None, auto-detected from image.
        max_search_radius: Maximum search radius for linking (pixels).
            If None, uses btrack default.
        **tracker_kwargs: Additional keyword arguments passed to BayesianTracker.

    Returns:
        None. Results are written to ``out``.

    Raises:
        ImportError: If btrack is not installed.
        ValueError: If ``image`` and ``out`` are not 3D or shapes differ.
    """
    if not BTRACK_AVAILABLE:
        raise ImportError(
            "btrack is not installed. Install it with: pip install btrack"
        )

    if image.ndim != 3 or out.ndim != 3:
        raise ValueError("image and out must be 3D arrays")

    if out.shape != image.shape:
        raise ValueError("image and out must have the same shape (T, H, W)")

    image = image.astype(bool, copy=False)
    out = out.astype(np.uint16, copy=False)

    n_frames, height, width = image.shape

    # Convert segmentation to labeled format for btrack
    # btrack expects labeled segmentation (each object has unique ID)
    from skimage.measure import label

    labeled_segmentation = np.zeros_like(image, dtype=np.uint16)
    for t in range(n_frames):
        # Check for cancellation
        if cancel_event and cancel_event.is_set():
            logger.info("Tracking cancelled at frame %d", t)
            return

        # Label connected components in this frame
        frame_labeled = label(image[t], connectivity=1)

        # Filter by size if specified
        if min_size is not None or max_size is not None:
            from skimage.measure import regionprops

            props = regionprops(frame_labeled)
            filtered_frame = np.zeros_like(frame_labeled)
            current_label = 1

            for prop in props:
                area = prop.area
                if min_size is not None and area < min_size:
                    continue
                if max_size is not None and area > max_size:
                    continue

                # Keep this region, relabel it
                mask = frame_labeled == prop.label
                filtered_frame[mask] = current_label
                current_label += 1

            labeled_segmentation[t] = filtered_frame
        else:
            labeled_segmentation[t] = frame_labeled

        if progress_callback is not None:
            progress_callback(t, n_frames, "Labeling")

    # Set up imaging volume if not provided
    if volume is None:
        volume = ((0, width), (0, height), (-1e5, 1e5))  # 2D + dummy Z

    # Initialize BayesianTracker
    tracker = BayesianTracker(verbose=False, **tracker_kwargs)

    # Set volume (must be set before appending objects)
    tracker.volume = volume

    # Set models if provided (configure before tracking)
    if motion_model is not None:
        tracker.motion_model = motion_model
    if object_model is not None:
        tracker.object_model = object_model
    if hypothesis_model is not None:
        tracker.hypothesis_model = hypothesis_model

    # Set tracking updates if provided
    if tracking_updates is not None:
        tracker.configuration.tracking_updates = tracking_updates

    # Set search radius if provided
    if max_search_radius is not None:
        tracker.configuration.max_search_radius = max_search_radius

    logger.info("Converting segmentation to trackable objects...")

    # Convert segmentation to trackable objects
    # segmentation_to_objects expects T(Z)YX format
    objects = segmentation_to_objects(
        labeled_segmentation,
        properties=("area", "centroid"),
        use_weighted_centroid=False,
    )

    if cancel_event and cancel_event.is_set():
        logger.info("Tracking cancelled during object conversion")
        return

    logger.info("Found %d objects across %d frames", len(objects), n_frames)

    # Append all objects to tracker
    tracker.append(objects)

    if cancel_event and cancel_event.is_set():
        logger.info("Tracking cancelled before tracking")
        return

    # Run tracking
    logger.info("Running Bayesian tracking...")
    tracker.track(step_size=100)

    if cancel_event and cancel_event.is_set():
        logger.info("Tracking cancelled during tracking")
        return

    # Get tracks
    tracks = tracker.tracks
    logger.info("Found %d tracks", len(tracks))

    # Map tracks back to segmentation
    # update_segmentation expects T(Z)YX format and returns relabeled segmentation
    tracked_segmentation = update_segmentation(
        labeled_segmentation,
        tracks,
        color_by="ID",
    )

    # Copy results to output array
    out[...] = tracked_segmentation

    logger.info("Bayesian tracking completed")
