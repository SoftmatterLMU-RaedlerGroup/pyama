import numpy as np
import skimage.draw as skid
from .base import Roi

__version__ = "0.1"

class RectRoi(Roi):
    """Holds information of a ROI.

    :param polygon: corner coordinates (in pixels) of the ROI
    :type polygon: 4-by-2 :py:class:`numpy.array`, where ``coords[i,0]`` is the x-coordinate and ``coords[i,1]`` the y-coordinate of corner ``i``
    :param props: parameters for spanning the grid
    :type props: dict
    :param inverted: flag whether the columns of ``polygon`` are interchanged, so that ``coords[i,0]`` is the y-coordinate and ``coords[i,1]`` the x-coordinate of corner ``i``
    :type inverted: bool

    The following properties are exposed:

    ``corners``
        The corners of the ROI, given as a 4-by-2 :py:class:`numpy.array`,
        where ``coords[i,0]`` is the y-coordinate and ``coords[i,1]`` the
        x-coordinate of corner ``i`` (note the different ordering than for
        the constructor argument).

    ``props``
        A dictionary of grid parameters; can be used to reproduce the grid.
        The underlying object may be shared by multiple instances of
        ``RectRoi`` and should not be changed.

    ``coords``
        The coordinates of all pixels within the ROI, represented as a
        N-by-2 :py:class:`numpy.array` with row indices at ``[:,0]`` and
        column indices at ``[:,0]``.
        The coordinates are calculated in a lazy manner since this may
        take comparably long. Results are cached.

    ``area``
        The number of pixels in the ROI. Querying this value involves
        calculating the ``coords``.

    ``perimeter``
        The coordinates of the pixels at the edge of the ROI, represented
        as a N-by-2 :py:class:`numpy.array` with row indices at ``[:,0]``
        and column indices at ``[:,0]``.
        The coordinates are calculated in a lazy manner since this may
        take comparably long. Results are cached.

    ``rows``
        A one-dimensional :py:class:`numpy.array` of the row indices of
        the ``coords``. Querying this value involves calculating
        the ``coords``.

    ``columns``
        A one-dimensional :py:class:`numpy.array` of the colulmn indices
        of the ``coords``. Querying this value involves calculating
        the ``coords``.
    """
    #TODO: adapt new API (cf. ContourRoi)
    type_id = "rect"
    version = "0.1"

    @classmethod
    def key(cls):
        return (cls.type_id, cls.version)

    def __init__(self, polygon, props=None, inverted=False, **kwargs):
        super().__init__(**kwargs)
        if inverted:
            self._corners = np.asarray(polygon).copy()
        else:
            self._corners = np.asarray(polygon[:,::-1]).copy()

        self.props = props
        if self.props is not None:
            self._area = self.props['width'] * self.props['height']

    @property
    def corners(self):
        with self.lock:
            return self._corners.copy()

    @corners.setter
    def corners(self, val):
        with self.lock:
            self._coords = None
            self._corners = val

    @property
    def coords(self):
        with self.lock:
            if self._coords is None:
                pc = skid.polygon(self._corners[:, self.Y], self._corners[:, self.X])
                self._coords = np.stack([pc[self.Y], pc[self.X]], axis=1)
            return self._coords

    @coords.setter
    def coords(self, val):
        raise NotImplementedError("Set the coordinates of a RectRoi by the argument 'polygon' of __init__")


