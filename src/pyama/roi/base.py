import abc
from collections import namedtuple
from threading import RLock

from matplotlib.colors import to_hex
import numpy as np

from ._aux_find_corners import find_roi_corners
from ._aux_find_perimeter import find_roi_perimeter

from ..util import make_uid


class Roi(abc.ABC):
    """Base class for ROIs

ROI types must inherit from this class and implement at least `key`.
    """
    Y = 0
    X = 1
    Roi_BBox = namedtuple('Roi_BBox', ('y_min', 'x_min', 'y_max', 'x_max'))
    TYPE = None

    def __init__(self, category=None, visible=True, name=None, name_visible=True, color=None, stroke_width=None,
            frame=Ellipsis, coords=None):
        self.__uid = make_uid(self)
        self.lock = RLock()

        self._category = category
        self._visible = visible
        self._name = name
        self._name_visible = name_visible
        self._color = color
        self._stroke_width = stroke_width
        self._frame = frame
        self._coords = coords
        self._bbox = None
        self._size = None
        self._area = None
        self._perimeter = None
        self._corners = None


    #@classmethod
    #@abc.abstractmethod
    #def key(cls):
    #    """Return a tuple of two strings: (type, version)"""
    #    raise NotImplementedError

    @property
    def type(self):
        return self.TYPE

    def serialize(self, *_, **__):
        raise NotImplementedError

    def deserialize(self, *_, **__):
        raise NotImplementedError

    @property
    def uid(self):
        return self.__uid

    @property
    def category(self):
        with self.lock:
            return self._category

    @category.setter
    def category(self, val):
        with self.lock:
            self._category = val

    @property
    def visible(self):
        with self.lock:
            return self._visible

    @visible.setter
    def visible(self, val):
        with self.lock:
            self._visible = bool(val)

    @property
    def name(self):
        with self.lock:
            return self._name

    @name.setter
    def name(self, val):
        with self.lock:
            self._name = val

    @property
    def name_visible(self):
        with self.lock:
            return self._name_visible

    @name_visible.setter
    def name_visible(self, val):
        with self.lock:
            self._name_visible = bool(val)

    @property
    def color(self):
        with self.lock:
            return self._color

    @property
    def color_hex(self):
        """Guaranteed to return color as #rrggbb hex string (or None)"""
        try:
            with self.lock:
                return to_hex(self._color)
        except ValueError:
            return None

    @color.setter
    def color(self, val):
        with self.lock:
            self._color = val

    @property
    def stroke_width(self):
        with self.lock:
            return self._stroke_width

    @stroke_width.setter
    def stroke_width(self, val):
        with self.lock:
            self._stroke_width = val

    @property
    def frame(self):
        with self.lock:
            return self._frame

    @frame.setter
    def frame(self, val):
        with self.lock:
            self._frame = val

    @property
    def coords(self):
        with self.lock:
            return self._coords

    @coords.setter
    def coords(self, val):
        with self.lock:
            if val is None or not len(val) or not val.size:
                self._coords = None
                self._bbox = None
                self._size = None
                self._area = None
            else:
                self._coords = val
                self._size = self._coords.shape[0]
                if self._area is None:
                    self._area = self._size
                #self._bbox = np.array((self.rows.min(), self.cols.min(), self.rows.max(), self.cols.max()),
                #        dtype=[(x, np.int16) for x in ('y_min', 'x_min', 'y_max', 'x_max')])
                self._bbox = self.Roi_BBox(y_min=self._coords[:, self.Y].min(),
                                           y_max=self._coords[:, self.Y].max(),
                                           x_min=self._coords[:, self.X].min(),
                                           x_max=self._coords[:, self.X].max())
            self._perimeter = None
            self._corners = None

    @property
    def size(self):
        """Guaranteed to be the integer number of points in coords (or None)"""
        with self.lock:
            return self._size

    @property
    def area(self):
        """Arbitrary number corresponding to area; defaults to `Roi.size`"""
        with self.lock:
            return self._area

    @area.setter
    def area(self, val):
        with self.lock:
            self._area = val

    @property
    def bbox(self):
        with self.lock:
            return self._bbox

    @property
    def y_min(self):
        try:
            return self.bbox.y_min
        except AttributeError:
            return None

    @property
    def y_max(self):
        try:
            return self.bbox.y_max
        except AttributeError:
            return None

    @property
    def x_min(self):
        try:
            return self.bbox.x_min
        except AttributeError:
            return None

    @property
    def x_max(self):
        try:
            return self.bbox.x_max
        except AttributeError:
            return None

    @property
    def rows(self):
        try:
            return self.coords[:, self.Y]
        except TypeError:
            return None

    @property
    def cols(self):
        try:
            return self.coords[:, self.X]
        except TypeError:
            return None

    def overlap(self, other):
        overlap = np.empty(self.size, dtype=np.bool)
        for i, row in enumerate(self.coords):
            overlap[i] = np.any(np.all(row == other.coords, axis=1))
        return self.coords[overlap, :]

    @property
    def centroid(self):
        """Return centroid of the ROI"""
        return np.array([self.rows.mean(), self.cols.mean()])

    @property
    def perimeter(self):
        """Return the surrounding polygon.

The returned coordinates correspond to the vertices of a polygon
surrounding the ROI like a rubberband, i.e. the coordinates do
not correspond to pixel centers, but to the edges between pixels.

These values can be used to reconstruct the ROI coordinates with
the function skimage.draw.polygon, and to export the ROI in the
format required by ImageJ.

See also: Roi.corners
        """
        with self.lock:
            if self._perimeter is None:
                self._perimeter = find_roi_perimeter(self)
            return self._perimeter.copy()

    @property
    def corners(self):
        """Return the coordinates of the ROI corners.

The returned coordinates correspond to the pixel centers
of the corner pixels of the ROI. Connecting the coordinates
in the returned order with straight lines gives the
outermost pixels of the ROI.

See also: Roi.perimeter
        """
        with self.lock:
            if self._corners is None:
                self._corners = find_roi_corners(self)
            return self._corners.copy()
