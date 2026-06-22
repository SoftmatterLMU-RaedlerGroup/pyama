"""Perform a background correction on a fluorescence channel.

The background correction is based on Schwarzfischer et al.:
“Efficient fluorescence image normalization for time lapse movies”
https://push-zb.helmholtz-muenchen.de/frontdoor.php?source_opus=6773
"""
# Based on "background_correction.py"
# of commit f46236d89b18ec8833e54bbdfe748f3e5bce6924
# in repository https://gitlab.physik.uni-muenchen.de/lsr-pyama/schwarzfischer
import numpy as np
import numpy.ma as ma
import scipy.interpolate as scint
import scipy.stats as scst

from .. import util


def _make_tiles(n, div, name='center'):
    borders = np.rint(np.linspace(0, n, 2*div-1)).astype(np.uint16)
    tiles = np.empty(len(borders)-2, dtype=[(name, float), ('slice', object)])
    for i, (b1, b2) in enumerate(zip(borders[:-2], borders[2:])):
        tiles[i] = (b1 + b2) / 2, slice(b1, b2)
    return tiles


def _get_arr(shape, dtype, mem_lim, memmap_dir):
    """Create channel arrays.

    Since the arrays may become very large, they can be created as
    memory-mapped file.

    Arguments:
        shape -- shape of the channel array (frames, height, width)
        dtype -- dtype of the output array
        mem_lim, memmap_dir -- like `background_schwarzfischer`

    Returns a tuple of:
        array guaranteed to have full channel size to store interpolated
                background and corrected image, may be in memory or on disk
        array for temporary values, residing in memory (if possible),
                may be smaller than the full channel size
        iterator for iterating through the middle (height) dimension
                of the channel, yielding a tuple
                    (number of elements, slice)
    """
    force_mem = False
    if mem_lim is None:
        mem_lim = util.mem_avail() * .95
    elif mem_lim > 0 and mem_lim <= 1:
        mem_lim = util.mem_avail() * mem_lim
    elif mem_lim <= 0:
        force_mem = True

    n_req = np.prod((dtype.itemsize, *shape), dtype=np.intp)

    if n_req < mem_lim or force_mem:
        arr_interp = np.empty(shape=shape, dtype=dtype)
        mem_lim = max(mem_lim - arr_interp.nbytes, 0)
    else:
        if not memmap_dir:
            memmap_dir = ()
        f = util.open_tempfile(memmap_dir)
        arr_interp = np.zeros(shape=shape, dtype=dtype)

    if n_req < mem_lim or force_mem:
        arr_temp = np.empty(shape=shape, dtype=dtype)
        def iter_temp():
            yield (shape[1], slice(None, None))
    else:
        n_wt = shape[0] * shape[2]
        n_h = int(mem_lim // n_wt)
        if n_h < 1:
            # Not enough memory left; continue with swapping
            n_h = 1
        arr_temp = np.empty(shape=(shape[0], n_h, shape[2]), dtype=dtype)
        def iter_temp():
            h = shape[1]
            n = int(h // n_h)
            for i in range(n):
                yield (n_h, slice(i * n_h, (i+1) * n_h))
            if rem := h % n_h:
                yield (rem, slice(n * n_h, n * n_h + rem))

    return arr_interp, arr_temp, iter_temp()


def background_schwarzfischer(fluor_chan, bin_chan, div_horiz=7, div_vert=5, mem_lim=None, memmap_dir=None):
    """Perform background correction according to Schwarzfischer et al.

    Arguments:
        fluor_chan -- (frames x height x width) numpy array; the fluorescence channel to be corrected
        bin_chan -- boolean numpy array of same shape as `fluor_chan`; segmentation map (background=False, cell=True)
        div_horiz -- int; number of (non-overlapping) tiles in horizontal direction
        div_vert -- int; number of (non-overlapping) tiles in vertical direction
        mem_lim -- max number of bytes for temporary data before switching to memmap;
                if in (0,1], max percentage of free memory to be used;
                if non-positive, always use memory; if None, decide automatically
        memmap_dir -- str; directory for creating memmap

    Returns:
        Background-corrected fluorescence channel as numpy array (dtype single) of same shape as `fluor_chan`
    """
    n_frames, height, width = fluor_chan.shape

    # Allocate arrays
    if np.can_cast(fluor_chan, np.float16):
        dtype_interp = np.float16
    elif np.can_cast(fluor_chan, np.float32):
        dtype_interp = np.float32
    else:
        dtype_interp = np.float64
    dtype_interp = np.dtype(dtype_interp)
    bg_mean = np.empty((n_frames, 1, 1), dtype=dtype_interp)

    # Create large arrays in memory or as memmap
    if mem_lim is None or mem_lim > 0:
        bg_interp, arr_temp, iter_temp = _get_arr(fluor_chan.shape, dtype_interp, mem_lim, memmap_dir)
    else:
        bg_interp, arr_temp, iter_temp = np.empty(shape=fluor_chan.shape, dtype=dtype_interp)

    # Construct tiles for background interpolation
    # Each pair of neighboring tiles is overlapped by a third tile, resulting in a total tile number
    # of `2 * div_i - 1` tiles for each direction `i` in {`horiz`, `vert`}.
    # Due to integer rounding, the sizes may slightly vary between tiles.
    tiles_vert = _make_tiles(height, div_vert)
    tiles_horiz = _make_tiles(width, div_horiz)
    supp = np.empty((tiles_horiz.size, tiles_vert.size))

    # Interpolate background as cubic spline with each tile’s median as support point at the tile center
    for t in range(n_frames):
        print(f"Interpolating background in frame {t:3d} …")
        masked_frame = ma.masked_array(fluor_chan[t, ...], mask=bin_chan[t, ...])
        for iy, (y, sy) in enumerate(tiles_vert):
            for ix, (x, sx) in enumerate(tiles_horiz):
                supp[ix, iy] = ma.median(masked_frame[sy, sx])
        bg_spline = scint.RectBivariateSpline(x=tiles_horiz['center'], y=tiles_vert['center'], z=supp)
        patch = bg_spline(x=range(width), y=range(height)).T
        bg_interp[t, ...] = patch
        bg_mean[t, ...] = patch.mean()

    # Correct for background using Schwarzfischer’s formula:
    #   corrected_image = (raw_image - interpolated_background) / gain
    # wherein, in opposite to Schwarzfischer, the gain is approximated as
    #   median(interpolated_background / mean_background)
    # This “simple” calculation may consume more memory than available.
    # Therefore, a less readable but more memory-efficient command flow is used.
    for st, sl in iter_temp:
        np.divide(bg_interp[:, sl, :], bg_mean, out=arr_temp[:, :st, :])
        np.subtract(fluor_chan[:, sl, :], bg_interp[:, sl, :], out=bg_interp[:, sl, :])
        np.divide(bg_interp[:, sl, :], np.median(arr_temp[:, :st, :], axis=0, keepdims=True), out=bg_interp[:, sl, :])

    # `bg_interp` now holds the corrected image
    return bg_interp
