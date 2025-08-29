import scipy.ndimage as smg
import numpy as np
import numba as nb

STRUCT3 = np.ones((3,3), dtype=bool)
STRUCT5 = np.ones((5,5), dtype=bool)
STRUCT5[[0,0,-1,-1], [0,-1,0,-1]] = False

@nb.njit
def window_std(img):
    """Calculate unnormed variance of 'img'"""
    return np.sum((img - np.mean(img))**2)


@nb.njit
def generic_filter(img, fun, size=3, reflect=False):
    """Apply filter to image.

    img -- the image to be filtered
    fun -- the filter function to be applied, must accept subimage of 'img' as only argument and return a scalar
    size -- the size (side length) of the mask; must be an odd integer
    reflect -- switch for border mode: True for 'reflect', False for 'mirror'

    Returns a np.float64 array with same shape as 'img'.

    This function is intended to be a numba-capable replacement of scipy.ndimage.generic_filter.
    """
    if size % 2 != 1:
        raise ValueError("'size' must be an odd integer")
    height, width = img.shape
    s2 = size // 2

    # Set up temporary image for correct border handling
    img_temp = np.empty((height+2*s2, width+2*s2), dtype=np.float64)
    img_temp[s2:-s2, s2:-s2] = img
    if reflect:
        img_temp[:s2, s2:-s2] = img[s2-1::-1, :]
        img_temp[-s2:, s2:-s2] = img[:-s2-1:-1, :]
        img_temp[:, :s2] = img_temp[:, 2*s2-1:s2-1:-1]
        img_temp[:, -s2:] = img_temp[:, -s2-1:-2*s2-1:-1]
    else:
        img_temp[:s2, s2:-s2] = img[s2:0:-1, :]
        img_temp[-s2:, s2:-s2] = img[-2:-s2-2:-1, :]
        img_temp[:, :s2] = img_temp[:, 2*s2:s2:-1]
        img_temp[:, -s2:] = img_temp[:, -s2-2:-2*s2-2:-1]

    # Create and populate result image
    filtered_img = np.empty_like(img, dtype=np.float64)
    for y in range(height):
        for x in range(width):
            filtered_img[y, x] = fun(img_temp[y:y+2*s2+1, x:x+2*s2+1])

    return filtered_img


def binarize_frame(img, mask_size=3):
    """Coarse segmentation of phase-contrast image frame

    Returns binarized image of frame
    """
    # Get logarithmic standard deviation at each pixel
    std_log = generic_filter(img, window_std, size=mask_size)
    std_log[std_log>0] = (np.log(std_log[std_log>0]) - np.log(mask_size**2 - 1)) / 2

    # Get width of histogram modulus
    counts, edges = np.histogram(std_log, bins=200)
    bins = (edges[:-1] + edges[1:]) / 2
    hist_max = bins[np.argmax(counts)]
    sigma = np.std(std_log[std_log <= hist_max])

    # Apply histogram-based threshold
    img_bin = std_log >= hist_max + 3 * sigma

    # Remove noise
    img_bin = smg.binary_dilation(img_bin, structure=STRUCT3)
    img_bin = smg.binary_fill_holes(img_bin)
    img_bin &= smg.binary_opening(img_bin, iterations=2, structure=STRUCT5)
    img_bin = smg.binary_erosion(img_bin, border_value=1)

    return img_bin
