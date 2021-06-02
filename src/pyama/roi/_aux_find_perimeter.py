import numpy as np

def find_perimeter(img):
    """Find perimeter of a polygon.

Note: This function finds the polygon-shaped line that
surrounds the pixels. The returned coordinates do not
refer to the pixel centers, but to the edges between
the pixels.

Arguments:
img -- 2d binary image of (filled) polygon

Returns:
n-by-2 array of n corner coordinates
column 0: y-value
column 1: x-value
    """
    RIGHT = 1
    DOWN = 2
    LEFT = 3
    UP = 4

    if img.ndim != 2:
        raise ValueError("2-dimensional image required")
    n_rows, n_cols = img.shape
    max_row, max_col = n_rows-1, n_cols-1

    # Find corners
    # `i` is row index, `j` is column index
    # Find a startpoint and walk clock-wise along the border:
    # Along the upper border, walk right (increase j).
    # Along the right border, walk down (increase i).
    # Along the lower border, walk left (decrease j).
    # Along the left  border, walk up (decrease i).
    # The startpoint is always at an upper left corner.
    startpoint = np.flatnonzero(img)
    if not startpoint.size:
        return np.empty((0, 2), dtype=np.uint16)
    startpoint = startpoint[0]
    i = startpoint // n_cols
    j = startpoint % n_cols
    startpoint = (i, j)
    corners = [(startpoint)]
    direction = RIGHT
    while True:
        append = None
        if direction == RIGHT:
            j += 1
            if i > 0 and j <= max_col and img[i-1,j]:
                direction = UP
            elif j <= max_col and img[i,j]:
                continue
            else:
                direction = DOWN
            append = (i, j)
        elif direction == DOWN:
            i += 1
            if i <= max_row and j <= max_col and img[i,j]:
                direction = RIGHT
            elif i <= max_row and img[i,j-1]:
                continue
            else:
                direction = LEFT
            append = (i, j)
        elif direction == LEFT:
            j -= 1
            if i <= max_row and j > 0 and img[i,j-1]:
                direction = DOWN
            elif j > 0 and img[i-1,j-1]:
                continue
            else:
                direction = UP
            append = (i, j)
        elif direction == UP:
            i -= 1
            if i > 0 and j > 0 and img[i-1,j-1]:
                direction = LEFT
            elif i > 0 and img[i-1,j]:
                continue
            else:
                direction = RIGHT
            append = (i, j)

        if append is None:
            raise ValueError("Undefined state")
        elif append == startpoint:
            break
        else:
            corners.append(append)

    return np.array(corners, dtype=np.uint16)


def find_roi_perimeter(roi):
    img = np.zeros((roi.y_max - roi.y_min + 1, roi.x_max - roi.x_min + 1), dtype=np.bool_)
    img[roi.rows - roi.y_min, roi.cols - roi.x_min] = True
    return find_perimeter(img) + np.array(((roi.y_min, roi.x_min)))
