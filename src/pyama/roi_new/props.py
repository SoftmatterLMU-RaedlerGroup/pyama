# TO BE DELETED
from threading import RLock
from weakref import WeakSet

from ..util import make_uid

class RoiLabel:
    """Label class for ROIs.

name -- str, human-readable description
color -- default color for visual representation
rois -- WeakSet of ROIs having this label
groups -- WeakSet of RoiGroups having this label
    """
    __slots__ = ('__lock', '__id', '__name', '__color', '__rois', '__groups')
    def __init__(self, name=None, color=None, rois=None, groups=None):
        self.__lock = RLock()
        self.__id = make_uid(self)
        self.__name = name
        self.__color = color
        self.__rois = WeakSet()
        self.__groups = WeakSet()

    @property
    def lock(self):
        return self.__lock

    @property
    def id(self):
        return self.__id

    @property
    def name(self):
        with self.__lock:
            return self.__name

    @name.setter
    def name(self, new):
        with self.__lock:
            if new:
                self.__name = new
            else:
                self.__name = None

    @property
    def color(self):
        with self.__lock:
            return self.__color

    @color.setter
    def color(self, new):
        if not new:
            new = None
        with self.__lock:
            self.__color = new

    @property
    def rois(self):
        with self.__lock:
            return self.__rois.copy()

    def add_rois(self, *rois):
        with self.__lock:
            self.__rois.update(rois)

    def drop_rois(self, *rois):
        with self.__lock:
            self.__rois.difference_update(rois)

    @property
    def groups(self):
        with self.__lock:
            return self.__groups.copy()

    def add_groups(self, *groups):
        with self.__lock:
            self.__groups.update(groups)

    def drop_groups(self, *groups):
        with self.__lock:
            self.__groups.difference_update(groups)
