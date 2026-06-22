#! /usr/bin/env python3
import numpy as np
import tkinter as tk

def coords2xbm(coords, returnOffset=False, joinstr=', '):
    """
    Draw an XBM-formatted image from coordinates.

    :param coords: The coordinates to be set as image foreground
    :type coords: (N,2)-shaped numpy array with x-values in first and y-values in second column
    :param returnOffset: Flag whether to return the offset or not
    :type returnOffset: bool
    :param joinstr: The string to be used for joining the byte values; defaults to ", "
    :type joinstr: str
    :return: if ``returnOffset``, a tuple of a tuple of the x- and y-offset and the image string, else only the image string
    """
    # Assess coordinate range
    x_min = coords[:,0].min()
    x_max = coords[:,0].max()
    y_min = coords[:,1].min()
    y_max = coords[:,1].max()

    n_cols = np.ceil(x_max - x_min + 1).astype(np.uint)
    n_bytes = np.ceil(n_cols / 8).astype(np.uint)
    n_rows = np.ceil(y_max - y_min + 1).astype(np.uint)

    # Normalize coordinates (eliminate offset)
    coords = np.round(coords - np.array([[x_min, y_min]])).astype(np.uint)

    # Write pixel data
    bm = np.zeros([n_rows, n_bytes], dtype=np.uint8)
    for x, y in coords:
        byte = np.floor(x / 8).astype(np.uint)
        bit = (x % 8).astype(np.uint8)
        bm[y,byte] |= 1 << bit

    # Convert pixel data to XBM format
    bmx = joinstr.join("{:#x}".format(b) for b in bm.flat)
    xbm = "#define im_width {:d}\n#define im_height {:d}\nstatic char im_bits[] = {{\n{}\n}};".format(n_cols, n_rows, bmx)

    if returnOffset:
        return (x_min, y_min), xbm
    return xbm


if __name__ == "__main__":
    coords = np.array([[0,0], [2,0], [4,0], [6,0], [1,2], [2,2], [4,2], [5,2], [1,3], [2,3], [4,3], [5,3], [3,5], [3,6], [1,7], [5,7], [2,8], [4,8], [3,8]], dtype=np.uint)
    xbm = coords2xbm(coords)
    print(xbm)

    with open("out.xbm", "w") as f:
        f.write(xbm)

    root = tk.Tk()
    canvas = tk.Canvas(root, highlightthickness=0)
    canvas.pack()
    bitmap = tk.BitmapImage(data=xbm, master=root)
    canvas.bm = bitmap
    canvas.create_image(0, 0, image=bitmap, anchor=tk.NW)
    root.mainloop()

