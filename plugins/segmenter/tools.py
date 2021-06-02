from ...roi import ContourRoi
import numpy as np
import scipy.interpolate as si
import skimage.measure as meas
import skimage.morphology as morph


# Get number of tiles in both directions
N_TILES_HORIZ = 10
N_TILES_VERT = 8

# Set histgram requirements
HIST_N_BINS = 15
HIST_BREAK_WIDTH = 30
HIST_THRESH = .5


def interpolate_background(frame,
                           n_tiles_horiz=N_TILES_HORIZ,
                           n_tiles_vert=N_TILES_VERT,
                           hist_n_bins=HIST_N_BINS,
                           hist_break_width=HIST_BREAK_WIDTH,
                           hist_thresh=HIST_THRESH,
                           debug=False):
    """
Calculate an interpolated background by histogram.

@param frame the image whose background is to be estimated
<!-- :type frame: --> 2D numpy array
@param n_tiles_horiz number of tiles in horizontal direction
<!-- :type n_tiles_horiz: --> int >0
@param n_tiles_vert number of tiles in vertical direction
<!-- :type n_tiles_vert: --> int >0
@param hist_n_bins Number of bins to use in histogram
<!-- :type hist_n_bins: --> int >0
@param hist_break_width Histogram bin width threshold for acceptance
<!-- :type hist_break_width: --> int >0
@param hist_thresh Relative threshold of histogram bins for acceptance
<!-- :type hist_thresh: --> int >0
@param debug if ``True``, return dict of internal variables
<!-- :type degub: --> bool

@return  interpolated background
<!-- :rtype: --> same as ``frame``
    """
    # Get frame shape
    n_px_rows, n_px_cols = frame.shape

    # Calculate tile size
    s_tiles_horiz = np.floor(n_px_cols / n_tiles_horiz).astype(np.uint16)
    s_tiles_vert = np.floor(n_px_rows / n_tiles_vert).astype(np.uint16)

    # Calculate tile edges
    tile_edges_horiz = np.array(range(n_tiles_horiz + 1), dtype=np.uint16)
    tile_edges_horiz[:-1] *= s_tiles_horiz
    tile_edges_horiz[-1] = n_px_cols

    tile_edges_vert = np.array(range(n_tiles_vert + 1), dtype=np.uint16)
    tile_edges_vert[:-1] *= s_tiles_vert
    tile_edges_vert[-1] = n_px_rows

    # Calculate tile centers
    tile_centers_horiz = (tile_edges_horiz[:-1] + tile_edges_horiz[1:]) / 2
    tile_centers_vert = (tile_edges_vert[:-1] + tile_edges_vert[1:]) / 2

    if debug:
        print(tile_edges_horiz)
        print(tile_centers_horiz)
        print(tile_edges_vert)
        print(tile_centers_vert)

    # Build array of tile mean values
    tile_values = np.empty((n_tiles_vert, n_tiles_horiz), dtype=np.float_)
    if debug:
        tile_median = np.empty_like(tile_values)

    for iRow in range(n_tiles_vert):
        for iCol in range(n_tiles_horiz):
            # The values of the current tile
            px_vals = frame[tile_edges_vert[iRow]:tile_edges_vert[iRow+1],
                            tile_edges_horiz[iCol]:tile_edges_horiz[iCol+1]]
            if debug:
                tile_median[iRow, iCol] = np.median(px_vals)

            while True:
                # Find highest bin in histogram of tile values
                hist, bin_edges = np.histogram(px_vals, bins=hist_n_bins)
                iMax = hist.argmax()

                if debug:
                    print("[{:1d},{:1d}] iMax={:2d}, hist_width={:.3f}".format(
                            iRow, iCol, iMax,
                            bin_edges[iMax+1] - bin_edges[iMax]))

                if bin_edges[iMax+1] - bin_edges[iMax] <= hist_break_width:
                    # Bins are small enough
                    break
                elif iMax > 0 and iMax < bin_edges.size-1 and \
                        hist[iMax-1] > hist[iMax] * hist_thresh and \
                        hist[iMax+1] > hist[iMax] * hist_thresh:
                    # Highest bin is not "suspicious"
                    break
                else:
                    # Histogram is much wider than relevant range;
                    # most frequent values are concentrated in single bin.
                    # Reduce tile values to those in current bin
                    # and recalculate histogram
                    px_vals = px_vals[(px_vals >= bin_edges[iMax]) &
                                      (px_vals < bin_edges[iMax+1])]

            #tile_values[iRow,iCol] = (bin_edges[iMax] + bin_edges[iMax+1]) / 2
            tile_values[iRow, iCol] = np.median(px_vals)

    # Reconstruct background by 2D splines
    x_interp = np.array(range(n_px_cols))
    y_interp = np.array(range(n_px_rows))
    bg = si.RectBivariateSpline(tile_centers_horiz,
                                tile_centers_vert, tile_values.T, kx=3, ky=3) \
                                (x_interp, y_interp, grid=True).T

    if debug:
        ret = {}
        ret['bg'] = bg
        ret['tile_values'] = tile_values
        ret['tile_median'] = tile_median
        ret['tile_centers_horiz'] = tile_centers_horiz
        ret['tile_centers_vert'] = tile_centers_vert
        ret['tile_edges_horiz'] = tile_edges_horiz
        ret['tile_edges_vert'] = tile_edges_vert
        ret['n_tiles_horiz'] = n_tiles_horiz
        ret['n_tiles_vert'] = n_tiles_vert
        ret['x_interp'] = x_interp
        ret['y_interp'] = y_interp
        return ret

    return bg


def segment_frame(frame, bg, conn=2, cell_threshold=1.1):
    if conn == 1 or conn == 2:
        pass
    elif conn == 4:
        conn = 1
    elif conn == 8:
        conn = 2
    else:
        conn = 2

    # Make mask
    mask = frame / bg >= cell_threshold

    # Smoothen mask (first erode, then dilate with circle)
    mask = morph.binary_erosion(mask)
    selem_dil = np.ones((5, 5), dtype=np.bool)
    selem_dil[0, 0] = 0
    selem_dil[0, -1] = 0
    selem_dil[-1, 0] = 0
    selem_dil[-1, -1] = 0
    mask = morph.binary_dilation(mask, selem=selem_dil)

    # Find clusters
    mask = meas.label(mask, connectivity=conn, return_num=False)
    regions = ContourRoi.from_regionprops(meas.regionprops(mask), lazy=False)
    return regions


def get_regions(frame):
    """Get regions with cells.

@param frame the grayscale frame in which to find regions
:type: 2D numpy array
@return  regions found
<!-- :rtype: --> list of ContourRoi
    """
    bg = interpolate_background(frame)
    regions = segment_frame(frame, bg)
    return regions
