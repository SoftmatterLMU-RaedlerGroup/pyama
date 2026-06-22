import tifffile

from .binarize import binarize_phasecontrast_stack
from ..img_op import background_correction as bgcorr
from ..session.status import DummyStatus

def perform_background_correction(chan_fl, chan_bin, outfile, status=None):
    if status is None:
        status = DummyStatus()

    with status("Performing background correction …"):
        chan_corr = bgcorr.background_schwarzfischer(chan_fl, chan_bin)
        chan_corr = bgcorr.corr_gauss(chan_corr)

        n_frames, height, width = chan_corr.shape
        tiff_shape = (n_frames, 1, 1, height, width, 1)
        tifffile.imwrite(outfile, chan_corr.reshape(tiff_shape), shape=tiff_shape, imagej=True)
