import time

import numpy as np


from .binarize import binarize_phasecontrast_stack
from ..img_op import background_correction as bgcorr
from ..session.status import DummyStatus

def perform_background_correction(chan_fl, chan_bin, outfile, status=None):
    if status is None:
        status = DummyStatus()

    with status("Performing background correction …"):
        chan_corr = bgcorr.background_schwarzfischer(chan_fl, chan_bin)
        n_frames, height, width = chan_corr.shape
        tiff_shape = (n_frames, 1, 1, height, width, 1)
        np.savez_compressed(outfile, chan_corr)
        print(f"Background correction written to {outfile}")

    with status("Finished background correction"):
        time.sleep(2)
