"""IoU-based cell tracking with Hungarian assignment (functional API).

Pipeline (per frame pair):
- extract_regions(frame) -> RegionInfo objects with bbox and coordinates
- bbox_overlap(a, b) -> fast gating for candidate region pairs
- iou_from_indices(a, b) -> precise IoU computation using coordinate sets
- linear_sum_assignment(cost_matrix) -> optimal one-to-one matching
- create_labeled_stack(traces) -> final output with consistent cell IDs

This implementation uses vectorized operations and efficient data structures
for fast processing of large time-series datasets. Traces may be incomplete;
final labeling includes whatever frames are present in each trace.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np
from skimage.measure import label, regionprops
from scipy.optimize import linear_sum_assignment


@dataclass
class RegionInfo:
    label: int
    area: int
    bbox: tuple[int, int, int, int]  # (y_min, x_min, y_max, x_max)
    coords_1d_sorted: np.ndarray  # sorted 1D indices for fast intersections


def _coords_to_1d(coords: np.ndarray, width: int) -> np.ndarray:
    """Convert (y, x) coordinates to sorted 1D indices for fast intersections."""
    return np.sort(coords[:, 0] * width + coords[:, 1])


def _extract_regions(frame: np.ndarray, width: int) -> dict[int, RegionInfo]:
    """Extract connected components and compute region properties for tracking."""
    if frame.ndim != 2:
        raise ValueError("frame must be a 2D array")

    labeled = label(frame, connectivity=1)
    regions = {}
    for p in regionprops(labeled):
        y_min, x_min, y_max, x_max = p.bbox
        regions[p.label] = RegionInfo(
            label=p.label,
            area=int(p.area),
            bbox=(int(y_min), int(x_min), int(y_max), int(x_max)),
            coords_1d_sorted=_coords_to_1d(p.coords, width),
        )
    return regions


def _bbox_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    """Check if two bounding boxes overlap (fast gating for IoU computation)."""
    ay0, ax0, ay1, ax1 = a
    by0, bx0, by1, bx1 = b
    return (ay0 < by1) and (ay1 > by0) and (ax0 < bx1) and (ax1 > bx0)


def _intersection_size(a_idx: np.ndarray, b_idx: np.ndarray) -> int:
    """Compute intersection size from sorted 1D coordinate indices."""
    inter = np.intersect1d(a_idx, b_idx, assume_unique=True)
    return int(inter.size)


def _iou_from_indices(
    a_idx: np.ndarray, b_idx: np.ndarray, a_area: int, b_area: int
) -> float:
    """Compute IoU (intersection over union) from coordinate indices and areas."""
    inter = _intersection_size(a_idx, b_idx)
    if inter == 0:
        return 0.0
    union = a_area + b_area - inter
    if union <= 0:
        return 0.0
    return float(inter) / float(union)


def _build_cost_matrix(
    prev_regions: list[RegionInfo],
    curr_regions: list[RegionInfo],
    min_iou: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Build cost matrix (1 - IoU) for candidate pairs, and a mask for valid pairs.

    Returns a tuple (cost, valid_mask) of shape (N_prev, N_curr).
    Invalid pairs have cost set to a large number (1.0) and valid_mask=False.
    """
    n_prev = len(prev_regions)
    n_curr = len(curr_regions)
    if n_prev == 0 or n_curr == 0:
        return np.ones((n_prev, n_curr), dtype=float), np.zeros(
            (n_prev, n_curr), dtype=bool
        )

    cost = np.ones((n_prev, n_curr), dtype=float)  # default high cost
    valid = np.zeros((n_prev, n_curr), dtype=bool)

    # Gate by bbox overlap first to prune pairs drastically
    for i, pr in enumerate(prev_regions):
        for j, cr in enumerate(curr_regions):
            if not _bbox_overlap(pr.bbox, cr.bbox):
                continue
            iou = _iou_from_indices(
                pr.coords_1d_sorted, cr.coords_1d_sorted, pr.area, cr.area
            )
            if iou >= min_iou:
                cost[i, j] = 1.0 - iou
                valid[i, j] = True

    return cost, valid


def _filter_regions_by_size(
    regions: dict[int, RegionInfo], min_size: int | None, max_size: int | None
) -> dict[int, RegionInfo]:
    """Filter regions by size constraints to remove noise and overly large objects.

    This enforces `min_size` as a hard cutoff: any region with `area < min_size`
    will be removed. Regions with `area > max_size` are also removed.
    """
    out = {}
    for lbl, r in regions.items():
        if max_size and r.area > max_size:
            continue
        if min_size and r.area < min_size:
            continue
        out[lbl] = r
    return out


def _create_labeled_stack(
    traces: list[list[tuple[int, int]]],  # list of [(frame_idx, label), ...]
    frames_props: list[dict[int, RegionInfo]],
    shape: tuple[int, int, int],  # (T, H, W)
) -> np.ndarray:
    """Create final labeled stack from traces.

    Traces may be incomplete; this function labels only the frames present in
    each trace. Each trace is assigned a unique cell ID (starting at 1), and
    pixels for frames missing from a trace remain background (0).
    """
    T, H, W = shape
    labeled_stack = np.zeros((T, H, W), dtype=np.int32)
    for cell_id, trace in enumerate(traces, start=1):
        for frame_idx, lbl in trace:
            coords = frames_props[frame_idx][lbl].coords_1d_sorted
            # Convert 1D back to (y, x)
            ys, xs = divmod(coords, W)
            labeled_stack[frame_idx, ys, xs] = cell_id
    return labeled_stack


def track_cell(
    binary_stack: np.ndarray,
    min_size: int | None = None,
    max_size: int | None = None,
    min_iou: float = 0.1,
    progress_callback: Callable | None = None,
) -> np.ndarray:
    """Track cells across frames using IoU-based Hungarian assignment.

    Extracts regions per frame, builds cost matrix from IoU similarities,
    and solves optimal assignment to maintain consistent cell IDs.

    Parameters
    - binary_stack: 3D (T, H, W) boolean array of segmented frames
    - min_size: minimum region size to track (pixels)
    - max_size: maximum region size to track (pixels)
    - min_iou: minimum IoU threshold for valid matches
    - progress_callback: optional callback function for progress updates

    Returns
    - labeled_stack: (T, H, W) int32 array with consistent cell IDs
    """
    if binary_stack.ndim != 3:
        raise ValueError("binary_stack must be a 3D array with shape (T, H, W)")

    if binary_stack.size == 0:
        raise ValueError("binary_stack cannot be empty")

    if min_iou < 0 or min_iou > 1:
        raise ValueError("min_iou must be between 0 and 1")

    if min_size is not None and min_size < 0:
        raise ValueError("size parameters must be non-negative")

    if max_size is not None and max_size < 0:
        raise ValueError("size parameters must be non-negative")

    T, H, W = binary_stack.shape

    # Extract and prefilter regions for all frames
    frames_props: list[dict[int, RegionInfo]] = []
    for t in range(T):
        regions = _extract_regions(binary_stack[t], width=W)
        regions = _filter_regions_by_size(regions, min_size, max_size)
        frames_props.append(regions)
        if progress_callback is not None:
            progress_callback(t, T, "Labeling/regionprops")                                              

    # Initialize traces with frame 0 regions
    prev_labels = list(frames_props[0].keys())
    prev_regions = [frames_props[0][lbl] for lbl in prev_labels]
    # Each trace stores list of (frame_idx, label)
    traces: list[list[tuple[int, int]]] = [[(0, lbl)] for lbl in prev_labels]

    # Map from label in prev frame to trace index
    prev_map: dict[int, int] = {lbl: i for i, lbl in enumerate(prev_labels)}

    # Process subsequent frames
    for t in range(1, T):
        curr_labels = list(frames_props[t].keys())
        curr_regions = [frames_props[t][lbl] for lbl in curr_labels]

        # Build cost for valid pairs and solve assignment
        cost, valid = _build_cost_matrix(prev_regions, curr_regions, min_iou=min_iou)

        if cost.size == 0:
            # No candidates; all traces will fail to complete
            prev_map = {}
            prev_regions = []
            if progress_callback is not None:
                progress_callback(t, T, "Tracking (no candidates)")
            continue

        row_ind, col_ind = linear_sum_assignment(cost)

        # Accept only matches that are valid and meet IoU gate
        new_prev_map: dict[int, int] = {}
        new_prev_regions: list[RegionInfo] = []

        matched_curr: set[int] = set()

        for r, c in zip(row_ind, col_ind):
            if not valid[r, c]:
                continue
            prev_lbl = prev_labels[r]
            curr_lbl = curr_labels[c]

            trace_idx = prev_map.get(prev_lbl)
            if trace_idx is None:
                continue
            traces[trace_idx].append((t, curr_lbl))

            # Prepare for next iteration
            new_prev_map[curr_lbl] = trace_idx
            new_prev_regions.append(curr_regions[c])
            matched_curr.add(c)

        # Only keep traces that got matched; unmatched traces won't complete
        prev_map = new_prev_map
        prev_regions = new_prev_regions

        if progress_callback is not None:
            progress_callback(t, T, "Tracking")

    # Keep complete traces only (span all frames)
    complete_traces = [tr for tr in traces if len(tr) == T]
    labeled_stack = _create_labeled_stack(complete_traces, frames_props, (T, H, W))
    return labeled_stack
