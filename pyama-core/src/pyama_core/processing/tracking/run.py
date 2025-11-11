"""IoU-based cell tracking using Hungarian assignment.

This module extracts connected components per frame, builds a cost matrix
from bounding-box IoU between consecutive frames, solves an optimal one-to-one
assignment, and writes consistent cell IDs into a labeled ``(T, H, W)`` stack.

The public entrypoint is ``track_cell`` which operates in-place on the
preallocated output array.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np
from skimage.measure import label, regionprops
from scipy.optimize import linear_sum_assignment

from pyama_core.processing.types import Region

# type aliases (kept simple and compatible with the algorithm below)
LabeledRegions = dict[int, Region]  # label -> region
Trace = dict[int, int]  # frame -> label
TraceMap = dict[int, int]  # label -> trace


@dataclass
class IterationState:
    """State carried across frame-to-frame assignment iterations.

    Attributes:
        traces: List of per-cell traces storing ``frame -> label`` mappings.
        prev_map: Mapping from region label in previous frame to trace index.
        prev_regions: Regions from the previous frame indexed by label.
    """

    traces: list[Trace]
    prev_map: TraceMap
    prev_regions: LabeledRegions


def _extract_regions(frame: np.ndarray) -> LabeledRegions:
    """Extract connected components from a 2D binary frame.

    Args:
        frame: 2D boolean array ``(H, W)``; nonzero values indicate foreground.

    Returns:
        Mapping ``label -> Region`` with area, bbox and pixel coordinates.
    """
    labeled = label(frame, connectivity=1)
    regions = {}
    for p in regionprops(labeled):
        regions[p.label] = Region(
            area=int(p.area),
            bbox=(int(p.bbox[0]), int(p.bbox[1]), int(p.bbox[2]), int(p.bbox[3])),
            coords=p.coords,
        )
    return regions


def _iou_from_bboxes(
    a: tuple[int, int, int, int], b: tuple[int, int, int, int]
) -> float:
    """Compute IoU for two bounding boxes.

    Args:
        a: Bounding box ``(y0, x0, y1, x1)`` with exclusive end indices.
        b: Bounding box ``(y0, x0, y1, x1)`` with exclusive end indices.

    Returns:
        Intersection-over-Union value in ``[0.0, 1.0]``. Returns ``0.0`` when
        boxes do not overlap or union is zero.
    """
    ay0, ax0, ay1, ax1 = a
    by0, bx0, by1, bx1 = b

    inter_y0 = max(ay0, by0)
    inter_x0 = max(ax0, bx0)
    inter_y1 = min(ay1, by1)
    inter_x1 = min(ax1, bx1)

    inter_h = inter_y1 - inter_y0
    inter_w = inter_x1 - inter_x0
    if inter_h <= 0 or inter_w <= 0:
        return 0.0
    inter_area = int(inter_h) * int(inter_w)

    a_area = max(0, (ay1 - ay0) * (ax1 - ax0))
    b_area = max(0, (by1 - by0) * (bx1 - bx0))
    union = a_area + b_area - inter_area
    if union <= 0:
        return 0.0
    return float(inter_area) / float(union)


def _build_cost_matrix(
    prev_regions: list[Region],
    curr_regions: list[Region],
    min_iou: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Create cost and validity masks for previous vs. current regions.

    Args:
        prev_regions: Regions from the previous frame in matching order.
        curr_regions: Regions from the current frame in matching order.
        min_iou: Minimum IoU to consider a pair as a valid candidate.

    Returns:
        Tuple ``(cost, valid)`` where:
        - ``cost`` is a float array shaped ``(len(prev), len(curr))`` with
          values ``1 - IoU`` for valid pairs and ``1.0`` otherwise.
        - ``valid`` is a boolean mask of the same shape indicating candidate
          pairs that meet ``min_iou``.
    """
    n_prev = len(prev_regions)
    n_curr = len(curr_regions)
    if n_prev == 0 or n_curr == 0:
        return np.ones((n_prev, n_curr), dtype=float), np.zeros(
            (n_prev, n_curr), dtype=bool
        )

    cost = np.ones((n_prev, n_curr), dtype=float)  # default high cost
    valid = np.zeros((n_prev, n_curr), dtype=bool)

    # Gate by bbox overlap first to prune pairs, then compute bbox-only IoU
    for i, pr in enumerate(prev_regions):
        for j, cr in enumerate(curr_regions):
            # Use bbox-only IoU instead of expensive index intersection
            iou = _iou_from_bboxes(pr.bbox, cr.bbox)
            if iou >= min_iou:
                cost[i, j] = 1.0 - iou
                valid[i, j] = True

    return cost, valid


def _filter_regions_by_size(
    regions: LabeledRegions, min_size: int | None, max_size: int | None
) -> LabeledRegions:
    """Filter regions by pixel area.

    Args:
        regions: Mapping ``label -> Region``.
        min_size: Minimum area in pixels (inclusive). ``None`` disables lower bound.
        max_size: Maximum area in pixels (inclusive). ``None`` disables upper bound.

    Returns:
        Filtered mapping with regions outside bounds removed.
    """
    out: LabeledRegions = {}
    for lbl, r in regions.items():
        if max_size and r.area > max_size:
            continue
        if min_size and r.area < min_size:
            continue
        out[lbl] = r
    return out


def _assign_prev_to_curr(
    *,
    row_ind: np.ndarray,
    col_ind: np.ndarray,
    valid: np.ndarray,
    prev_labels: list[int],
    curr_labels: list[int],
    curr_regions: list[Region],
    state: IterationState,
    frame: int,
) -> tuple[dict[int, int], LabeledRegions]:
    """Apply assignment to update traces and build next-iteration state.

    Args:
        row_ind: Row indices from the assignment solution.
        col_ind: Column indices from the assignment solution.
        valid: Boolean mask indicating which pairs are valid.
        prev_labels: Ordered labels corresponding to ``prev_regions`` rows.
        curr_labels: Ordered labels corresponding to ``curr_regions`` cols.
        curr_regions: Regions for the current frame.
        state: Mutable iteration state to update in-place.
        frame: Current frame index being processed.

    Returns:
        Tuple ``(new_prev_map, new_prev_regions)`` used for the next frame.
    """
    new_prev_map: dict[int, int] = {}
    new_prev_regions: LabeledRegions = {}

    for r, c in zip(row_ind, col_ind):
        if not valid[r, c]:
            continue
        # Guard against mismatched indexing between prev_labels and prev_regions
        if r >= len(prev_labels):
            # skip any spurious assignment rows that don't map to a previous label
            continue

        prev_lbl = prev_labels[r]
        curr_lbl = curr_labels[c]

        trace = state.prev_map.get(prev_lbl)
        if trace is None:
            continue

        # record mapping for this trace at current frame
        state.traces[trace][frame] = curr_lbl

        # prepare next-iteration prev mapping
        new_prev_map[curr_lbl] = trace
        new_prev_regions[curr_lbl] = curr_regions[c]

    return new_prev_map, new_prev_regions


def _process_frame(
    state: IterationState,
    regions_all: list[LabeledRegions],
    min_iou: float,
    frame: int,
) -> None:
    """Update state with matches between previous and current frame.

    Args:
        state: Iteration state that holds traces and previous frame mapping.
        regions_all: List of labeled regions for all frames.
        min_iou: Minimum IoU to consider a pair as a valid candidate.
        frame: Index of the current frame within ``regions_all``.

    Returns:
        None. ``state`` is updated in-place.
    """
    # derive ordered previous labels from the mapping
    prev_labels = list(state.prev_map.keys())
    prev_regions_list = [state.prev_regions[lbl] for lbl in prev_labels]

    curr_frame_props = regions_all[frame]
    curr_labels = list(curr_frame_props.keys())
    curr_regions = list(curr_frame_props.values())

    # Build cost matrix and solve assignment
    cost, valid = _build_cost_matrix(prev_regions_list, curr_regions, min_iou=min_iou)

    if cost.size == 0:
        # no valid candidate pairs — clear previous state
        state.prev_map = {}
        state.prev_regions = {}
        return

    row_ind, col_ind = linear_sum_assignment(cost)

    # apply assignment results and prepare next-iteration mapping
    new_prev_map, new_prev_regions = _assign_prev_to_curr(
        row_ind=row_ind,
        col_ind=col_ind,
        valid=valid,
        prev_labels=prev_labels,
        curr_labels=curr_labels,
        curr_regions=curr_regions,
        state=state,
        frame=frame,
    )

    state.prev_map = new_prev_map
    state.prev_regions = new_prev_regions


def track_cell(
    image: np.ndarray,
    out: np.ndarray,
    min_size: int | None = None,
    max_size: int | None = None,
    min_iou: float = 0.1,
    progress_callback: Callable | None = None,
    cancel_event=None,
) -> None:
    """Track cells across frames using IoU-based Hungarian assignment.

    Extracts regions per frame, builds an IoU-based cost matrix between
    consecutive frames, and solves an optimal assignment to maintain
    consistent cell IDs. Writes results into ``out`` in-place.

    Args:
        image: 3D boolean array ``(T, H, W)`` with segmented foreground.
        out: Preallocated integer array ``(T, H, W)`` to receive labeled IDs.
        min_size: Minimum region size to track in pixels (inclusive).
        max_size: Maximum region size to track in pixels (inclusive).
        min_iou: Minimum IoU threshold for candidate matches.
        progress_callback: Optional callable ``(t, total, msg)`` for progress.
        cancel_event: Optional threading.Event for cancellation support.

    Returns:
        None. Results are written to ``out``.

    Raises:
        ValueError: If ``image`` and ``out`` are not 3D or shapes differ.
    """
    if image.ndim != 3 or out.ndim != 3:
        raise ValueError("image and out must be 3D arrays")

    if out.shape != image.shape:
        raise ValueError("image and out must have the same shape (T, H, W)")

    image = image.astype(bool, copy=False)
    out = out.astype(np.uint16, copy=False)

    # Extract and prefilter regions for all frames
    regions_all: list[LabeledRegions] = []
    for t in range(image.shape[0]):
        # Check for cancellation before processing each frame
        if cancel_event and cancel_event.is_set():
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"Tracking cancelled at frame {t}")
            return

        regions = _extract_regions(image[t])
        regions = _filter_regions_by_size(regions, min_size, max_size)
        regions_all.append(regions)
        if progress_callback is not None:
            progress_callback(t, image.shape[0], "Labeling")

    # Initialize iteration state with frame 0 regions
    # NOTE: traces are seeded only from frame 0. Regions that first appear
    # in later frames will NOT be assigned new trace IDs by this algorithm.
    # This means newborn regions are ignored unless they overlap a region
    # from the previous frame and become matched via IoU assignment.
    init_prev_labels = list(regions_all[0].keys())
    init_prev_regions = regions_all[0]
    # Each trace stores mapping frame_id -> label
    init_traces: list[Trace] = [{0: lbl} for lbl in init_prev_labels]

    # Build initial mapping from prev frame label -> trace index
    init_prev_map: dict[int, int] = {lbl: i for i, lbl in enumerate(init_prev_labels)}

    state = IterationState(
        traces=init_traces,
        prev_map=init_prev_map,
        prev_regions=init_prev_regions,
    )

    # Process subsequent frames
    for t in range(1, image.shape[0]):
        # Check for cancellation before processing each frame
        if cancel_event and cancel_event.is_set():
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"Tracking cancelled at frame {t}")
            return

        _process_frame(state=state, regions_all=regions_all, min_iou=min_iou, frame=t)
        # progress reporting is the caller's responsibility; always report generic tracking
        if progress_callback is not None:
            progress_callback(t, image.shape[0], "Tracking")

    out[...] = 0
    for cell, trace in enumerate(state.traces, start=1):
        for frame, lbl in trace.items():
            frame_props = regions_all[frame]
            region = frame_props.get(lbl)
            if region is None:
                continue
            coords = region.coords
            ys, xs = coords[:, 0], coords[:, 1]
            out[frame, ys, xs] = cell
