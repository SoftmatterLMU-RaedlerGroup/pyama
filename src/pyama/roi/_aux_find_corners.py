import numpy as np

def find_corners(img):
    """Find corners of a polygon.

Note: This function finds the corner pixels. To find the
inter-pixel spaces, +1 must be added to each right and
lower coordinate (and additional corners may be necessary).

Arguments:
img -- 2d binary image of (filled) polygon

Returns:
n-by-2 array of n corner coordinates
column 0: y-value
column 1: x-value
    """
    LEFT_BORDER = 1
    UPPER_BORDER = 2
    RIGHT_BORDER = 4
    LOWER_BORDER = 8

    UPPER_LEFT_KNEE = 16
    UPPER_RIGHT_KNEE = 32
    LOWER_RIGHT_KNEE = 64
    LOWER_LEFT_KNEE = 128

    # Check borders
    borders = np.zeros_like(img, dtype=np.uint8)
    n_rows, n_cols = borders.shape
    max_row = n_rows - 1
    max_col = n_cols - 1
    for i in range(n_rows):
        for j in range(n_cols):
            val = 0
            if img[i,j] == 0:
                continue
            if i == 0 or img[i-1,j] == 0:
                val += UPPER_BORDER
            if i == max_row or img[i+1,j] == 0:
                val += LOWER_BORDER
            if j == 0 or img[i,j-1] == 0:
                val += LEFT_BORDER
            if j == max_col or img[i,j+1] == 0:
                val += RIGHT_BORDER
            if i > 0 and j > 0 and img[i-1,j] and img[i,j-1] and img[i-1,j-1] == 0:
                val += UPPER_LEFT_KNEE
            if i > 0 and j < max_col and img[i-1,j] and img[i,j+1] and img[i-1,j+1] == 0:
                val += UPPER_RIGHT_KNEE
            if i < max_row and j < max_col and img[i+1,j] and img[i,j+1] and img[i+1,j+1] == 0:
                val += LOWER_RIGHT_KNEE
            if i < max_row and j > 0 and img[i+1,j] and img[i,j-1] and img[i+1,j-1] == 0:
                val += LOWER_LEFT_KNEE
            if val:
                borders[i, j] = val

    # Find corners
    # `i` is row index, `j` is column index
    # Find a startpoint and walk clock-wise along the border:
    # Along the upper border, walk right (increase j).
    # Along the right border, walk down (increase i).
    # Along the lower border, walk left (decrease j).
    # Along the left  border, walk up (decrease i).
    # The startpoint is always an upper left corner.
    borderpoints = np.flatnonzero(borders)
    if not borderpoints.size:
        return np.empty((0, 2), dtype=np.uint16)
    startpoint = borderpoints[0]
    i = startpoint // n_cols
    j = startpoint % n_cols
    corners = [(i, j)]
    direction = UPPER_BORDER
    borders[i, j] -= UPPER_BORDER
    while True:
        if direction == UPPER_BORDER:
            if borders[i,j] & UPPER_LEFT_KNEE:
                corners.append((i, j))
                borders[i, j] -= UPPER_LEFT_KNEE
                direction = LEFT_BORDER
                i -= 1
            elif borders[i,j] & RIGHT_BORDER:
                corners.append((i, j))
                borders[i, j] -= RIGHT_BORDER
                if borders[i,j] & LOWER_BORDER:
                    borders[i, j] -= LOWER_BORDER
                    direction = LOWER_BORDER
                    j -= 1
                else:
                    direction = RIGHT_BORDER
                    i += 1
            else:
                j += 1
        elif direction == RIGHT_BORDER:
            if borders[i,j] & UPPER_RIGHT_KNEE:
                corners.append((i, j))
                borders[i, j] -= UPPER_RIGHT_KNEE
                direction = UPPER_BORDER
                j += 1
            elif borders[i,j] & LOWER_BORDER:
                corners.append((i, j))
                borders[i, j] -= LOWER_BORDER
                if borders[i,j] & LEFT_BORDER:
                    borders[i, j] -= LEFT_BORDER
                    direction = LEFT_BORDER
                    i -= 1
                else:
                    direction = LOWER_BORDER
                    j -= 1
            else:
                i += 1
        elif direction == LOWER_BORDER:
            if borders[i,j] & LOWER_RIGHT_KNEE:
                corners.append((i, j))
                borders[i, j] -= LOWER_RIGHT_KNEE
                direction = RIGHT_BORDER
                i += 1
            elif borders[i,j] & LEFT_BORDER:
                corners.append((i, j))
                borders[i, j] -= LEFT_BORDER
                if borders[i,j] & UPPER_BORDER:
                    borders[i, j] -= UPPER_BORDER
                    direction = UPPER_BORDER
                    j += 1
                else:
                    direction = LEFT_BORDER
                    i -= 1
            else:
                j -= 1
        elif direction == LEFT_BORDER:
            if borders[i,j] & LOWER_LEFT_KNEE:
                corners.append((i, j))
                borders[i, j] -= LOWER_LEFT_KNEE
                direction = LOWER_BORDER
                j -= 1
            elif borders[i,j] & UPPER_BORDER:
                corners.append((i, j))
                borders[i, j] -= UPPER_BORDER
                if borders[i,j] & RIGHT_BORDER:
                    borders[i, j] -= RIGHT_BORDER
                    direction = RIGHT_BORDER
                    i += 1
                else:
                    direction = UPPER_BORDER
                    j += 1
            else:
                i -= 1
        else:
            raise ValueError(f"Undefined direction {direction}")

        if i < 0 or j < 0 or i > max_row or j > max_col:
            break
        elif borders[i,j] & direction:
            borders[i, j] -= direction
            continue
        elif borders[i,j] == 0:
            break

    return np.array(corners, dtype=np.uint16)


def find_roi_corners(roi):
    img = np.zeros((roi.y_max - roi.y_min + 1, roi.x_max - roi.x_min + 1), dtype=np.bool_)
    img[roi.rows - roi.y_min, roi.cols - roi.x_min] = True
    return find_corners(img) + np.array(((roi.y_min, roi.x_min)))
