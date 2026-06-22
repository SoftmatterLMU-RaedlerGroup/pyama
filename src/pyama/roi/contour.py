import numpy as np
import skimage.measure as skmeas
#import skimage.segmentation as skseg

from .base import Roi


class ContourRoi(Roi):
    @classmethod
    def key(cls):
        return ("raw", "0.1")

    def __init__(self, mask=None, label=None, coords=None, regionprop=None, lazy=True, **kwargs):
        super().__init__(**kwargs)
        self.label = None
        self._contour = None
        if regionprop is None and label is not None:
            self.label = label
            if mask is not None:
                self.coords = np.array((mask == label).nonzero()).T
            elif coords is not None:
                self.coords = coords
            else:
                raise ValueError("Illegal arguments")

        elif regionprop is not None:
            if label is not None:
                self.label = label
            else:
                self.label = regionprop.label
            self.area = regionprop.area
            self.coords = regionprop.coords

        else:
            raise ValueError("Illegal arguments")

        #self.bbox = np.array((self.rows.min(), self.cols.min(), self.rows.max(), self.cols.max()),
        #        dtype=[(x, np.int16) for x in ('y_min', 'x_min', 'y_max', 'x_max')])

        if not lazy:
            self.perimeter
            self.corners
            self.contour
            self.centroid

    @classmethod
    def from_regionprops(cls, regionprops, lazy=True):
        return [cls(regionprop=rp, lazy=lazy) for rp in regionprops]

    def _find_contour(self):
        img = np.zeros((self.y_max - self.y_min + 3, self.x_max - self.x_min + 3), dtype=np.uint8)
        img[self.rows - self.y_min + 1, self.cols - self.x_min + 1] = 1
        contours = skmeas.find_contours(img, .5, fully_connected='high')
        self._contour = max(contours, key=lambda c: c.size) + np.array(((self.y_min - 1, self.x_min - 1)))

    @property
    def contour(self):
        """Return the coordinates of the ROI contour polygon corners.

        The returned coordinates should only be used for illustrating the ROI outline.
        The coordinates are multiples of 0.5, indicating spaces between pixels.

        For exact contours, see: Roi.perimeter, Roi.corners
        """
        with self.lock:
            if self._contour is None:
                self._find_contour()
            return self._contour.copy()
