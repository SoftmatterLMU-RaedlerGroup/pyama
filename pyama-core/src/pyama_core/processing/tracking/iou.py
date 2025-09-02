"""IoU-based cell tracking using Hungarian assignment.

Extract regions per frame, form a bbox-IoU cost matrix between
consecutive frames, solve optimal one-to-one matchings, and assemble
per-cell traces into a labeled (T, H, W) stack.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np
from skimage.measure import label, regionprops
from scipy.optimize import linear_sum_assignment


@dataclass
class Region:
    area: int
    bbox: tuple[int, int, int, int]
    coords: np.ndarray

# type aliases (kept simple and compatible with the algorithm below)
LabeledRegions = dict[int, Region]  # label -> region
Trace = dict[int, int]  # frame_idx -> label
TraceMap = dict[int, int]  # label -> trace_idx


@dataclass
class IterationState:
    traces: list[Trace]
    prev_map: TraceMap
    prev_regions: LabeledRegions


def _extract_regions(frame: np.ndarray) -> LabeledRegions:
    """Return labeled regions for a 2D binary frame.

    Produces a mapping label -> Region containing `area`, `bbox`, and
    `coords` for downstream IoU and tracing logic.
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


def _iou_from_bboxes(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """Compute IoU for two boxes in (y0, x0, y1, x1) format.

    Returns 0.0 if boxes do not overlap or if union is zero.
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
    """Create (cost, valid_mask) matrices for prev x curr region pairs.

    For pairs with bbox IoU >= `min_iou`, cost = 1 - IoU and mask=True.
    Other pairs receive a high cost (1.0) and mask=False.
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
    """Return regions filtered by `min_size` and `max_size`.

    Regions with area outside the bounds are omitted.
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
    frame_idx: int,
) -> tuple[dict[int, int], LabeledRegions]:
    """Apply assignment pairs to `state` and return the next prev mapping.

    Writes matched labels into `state.traces[trace_idx][frame_idx]` and
    builds `new_prev_map` and `new_prev_regions` for the next iteration.
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

        trace_idx = state.prev_map.get(prev_lbl)
        if trace_idx is None:
            continue

        # record mapping for this trace at current frame
        state.traces[trace_idx][frame_idx] = curr_lbl

        # prepare next-iteration prev mapping
        new_prev_map[curr_lbl] = trace_idx
        new_prev_regions[curr_lbl] = curr_regions[c]

    return new_prev_map, new_prev_regions


def _process_frame(
    state: IterationState,
    regions_all: list[LabeledRegions],
    min_iou: float,
    frame_idx: int,
) -> None:
    """Update `state` with matches between previous and current frame.

    `regions_all` is the list of labeled regions for all frames; the current
    frame is selected by `frame_idx`. This function clears the previous
    state when no valid candidates exist and otherwise updates
    `state.prev_map` and `state.prev_regions` for the next iteration.
    """
    # derive ordered previous labels from the mapping
    prev_labels = list(state.prev_map.keys())
    prev_regions_list = [state.prev_regions[lbl] for lbl in prev_labels]

    curr_frame_props = regions_all[frame_idx]
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
        frame_idx=frame_idx,
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
) -> None:
    """Track cells across frames using IoU-based Hungarian assignment.

    Extracts regions per frame, builds cost matrix from IoU similarities,
    and solves optimal assignment to maintain consistent cell IDs.

    Parameters
    - image: 3D (T, H, W) boolean array of segmented frames
    - min_size: minimum region size to track (pixels)
    - max_size: maximum region size to track (pixels)
    - min_iou: minimum IoU threshold for valid matches
    - progress_callback: optional callback function for progress updates

    Returns
    - labeled_stack: (T, H, W) int32 array with consistent cell IDs
    """
    if image.ndim != 3 or out.ndim != 3:
        raise ValueError("image and out must be 3D arrays")

    if out.shape != image.shape:
        raise ValueError("image and out must have the same shape (T, H, W)")

    image = image.astype(bool, copy=False)
    out = out.astype(np.int16, copy=False)

    # Extract and prefilter regions for all frames
    regions_all: list[LabeledRegions] = []
    for t in range(image.shape[0]):
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
    # Each trace stores mapping frame_idx -> label
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
        _process_frame(state=state, regions_all=regions_all, min_iou=min_iou, frame_idx=t)
        # progress reporting is the caller's responsibility; always report generic tracking
        if progress_callback is not None:
            progress_callback(t, image.shape[0], "Tracking")

    out[...] = 0
    for cell_id, trace in enumerate(state.traces, start=1):
        for frame_idx, lbl in trace.items():
            frame_props = regions_all[frame_idx]
            region = frame_props.get(lbl)
            if region is None:
                continue
            coords = region.coords
            ys, xs = coords[:, 0], coords[:, 1]
            out[frame_idx, ys, xs] = cell_id