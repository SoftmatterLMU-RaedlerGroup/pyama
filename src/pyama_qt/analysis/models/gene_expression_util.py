import numpy as np
from scipy.interpolate import interp1d


def guess_t0(t, d):
    """Returns a guess for onset time t0"""

    # Allocate interpolation mask
    int_mask = np.ones(d.size, dtype=np.bool_)

    # Exclude values outside of extrema
    idx_max = d.argmax()
    if idx_max < d.size - 1:
        int_mask[idx_max + 1 :] = False

    idx_min = d[int_mask].argmin()
    if idx_min > 0:
        int_mask[:idx_min] = False

    # Eliminate values that violate monotonicity
    current_min = d[idx_max]
    for i in range(idx_max - 1, idx_min - 1, -1):
        if d[i] < current_min:
            current_min = d[i]
        elif d[i] > current_min:
            int_mask[i] = False

    if np.sum(int_mask) == 1:
        return t[int_mask]
    elif not np.any(int_mask):
        return 0.0
    return interp1d(d[int_mask], t[int_mask], assume_sorted=True)(
        d[idx_min] + 0.1 * (d[idx_max] - d[idx_min])
    )


def shape_onset(t, d):
    """Prepend data points to model an onset if needed.

    Arguments:
        t -- time vector (in hours)
        d -- data vector

    Returns:
        None if onset is in present data,
        else (t, d) with modelled onset prepended.
    """
    # Check if onset is present
    # (average slope in first 10 frames smaller than 1% of amplitude)
    slope10 = (d[1:11] - d[:10]) / (t[1:11] - t[:10])
    slope10_avg = np.mean(slope10)
    delta10 = slope10_avg * (t[10] - t[0])
    delta10_relative = delta10 / (d.max() - d.min())
    print(f"Relative slope in first 10 frames: {delta10_relative:.2%}")  # DEBUG
    if delta10_relative <= 0.01:
        return None

    # Get parameters for artificial onset
    t0 = t[0] - 2 * d[0] / slope10_avg
    art_slope = slope10_avg / 2 / (t[0] - t0)

    delta_t = np.median(t[1:] - t[:-1])
    t_start = t0 - 2
    n_points = np.ceil((t[0] - t_start) / delta_t).astype(np.int_)

    # Construct artificial onset
    t_new = np.concatenate((np.linspace(t_start, t[0], n_points, endpoint=False), t))
    idx_on_art = np.logical_and(t_new < t[0], t_new > t0)
    d_new = np.zeros_like(t_new)
    d_new[idx_on_art] = art_slope * (t_new[idx_on_art] - t0) ** 2
    d_new[n_points:] = d
    return t_new, d_new
