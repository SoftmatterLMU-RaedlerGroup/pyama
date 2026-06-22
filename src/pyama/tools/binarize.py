import os.path as op
import time

import numpy as np
import tifffile as tiff

from ..session.status import DummyStatus
from ..img_op.coarse_binarize_phc import binarize_frame

def binarize_phasecontrast_stack(stack, i_channel, outfile=None, status=None, return_result=False):
    if status is None:
        status = DummyStatus()

    stack_bin = np.empty((stack.n_frames, stack.height, stack.width), dtype=np.uint8)
    with status("Binarizing …") as current_status:
        for i_frame in range(stack.n_frames):
            current_status.reset(msg="Binarizing frame", current=i_frame+1, total=stack.n_frames)
            stack_bin[i_frame, ...] = binarize_frame(stack.get_image(frame=i_frame, channel=i_channel))

        if outfile:
            current_status.reset(f"Saving binarized stack to '{outfile}' …")

            ext = op.splitext(outfile)[-1].casefold()
            if ext in ('.tif', '.tiff'):
                tiff.imwrite(outfile, stack_bin[:, None, None, ...], imagej=True) # match imagej shape (t, c, z, y, x)
            elif ext == '.npy':
                np.save(outfile, stack_bin)
            elif ext == '.npz':
                np.savez_compressed(outfile, stack_bin)
            else:
                raise ValueError(f"Unknown file extension '{ext}'")

            current_status.reset(f"Saved binarized stack to '{outfile}'.")

        if return_result:
            return stack_bin

        time.sleep(2)

