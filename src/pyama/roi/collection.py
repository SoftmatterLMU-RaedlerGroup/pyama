from threading import RLock
from .base import Roi
from ..listener import Listeners


class RoiCollection:
    IDX_TYPE = 0
    IDX_VERSION = 1

    def __init__(self, key=None, type_=None, version=None,
                 parameters=None, name=None, color=None, stroke_width=None):
        if key is None and isinstance(type_, str) and isinstance(version, str):
            self.__key = (type_, version)
        elif isinstance(key, tuple) and len(key) == 2 and \
                isinstance(key[RoiCollection.IDX_TYPE], str) and \
                isinstance(key[RoiCollection.IDX_VERSION], str):
            self.__key = key
        else:
            raise TypeError(f"Invalid ROI type identifier given: {key}")

        self.__parameters = parameters
        self.__name = name
        self.__color = color
        self.__stroke_width = stroke_width
        self.__rois = {}
        self.__listeners = Listeners()
        self.__lock = RLock()

    @property
    def key(self):
        return self.__key

    @property
    def type(self):
        return self.__key[RoiCollection.IDX_TYPE]

    @property
    def version(self):
        return self.__key[RoiCollection.IDX_VERSION]

    def __len__(self):
        with self.__lock:
            return self.__rois.__len__()

    def __contains__(self, frame):
        with self.__lock:
            return self.__rois.__contains__(frame)

    def set(self, frame, roi):
        print("[RoiCollection.set] DEPRECATED, use __setitem__ instead")
        self[frame] = roi

    def add(self, frame, roi):
        if frame not in self:
            self[frame] = roi
            return
        if isinstance(roi, list) and all(isinstance(r, Roi) for r in roi):
            if any(r.key() != self.__key for r in roi):
                raise TypeError("incomaptible ROI type")
            with self.__lock:
                self.__rois[frame].extend(roi)
        elif isinstance(roi, Roi):
            if roi.key() != self.__key:
                raise TypeError(f"incomaptible ROI type: expected '{self.__key}', got '{roi.key()}'")
            with self.__lock:
                self.__rois[frame].append(roi)
        else:
            raise TypeError(f"expected type 'Roi', got '{type(roi)}')")
        self.__listeners.notify()

    def __getitem__(self, frame):
        with self.__lock:
            return self.__rois.get(frame)

    def __setitem__(self, frame, rois):
        if isinstance(rois, list) and all(isinstance(r, Roi) for r in rois):
            if any(r.key() != self.__key for r in rois):
                raise TypeError("incomaptible ROI type")
            with self.__lock:
                self.__rois[frame] = rois
        elif isinstance(rois, Roi):
            if rois.key() != self.__key:
                raise TypeError(f"incomaptible ROI type: expected '{self.__key}', got '{rois.key()}'")
            with self.__lock:
                self.__rois[frame] = [rois]
        else:
            raise TypeError(f"expected type 'Roi', got '{type(rois)}'")
        self.__listeners.notify()

    def __delitem__(self, frame):
        with self.__lock:
            self.__rois.__delitem__(frame)

    def __iter__(self):
        return self.__rois.__iter__()

    def items(self):
        with self.__lock:
            return self.__rois.items()

    def frames(self):
        with self.__lock:
            return self.__rois.keys()

    def rois(self):
        with self.__lock:
            return self.__rois.values()

    @property
    def parameters(self):
        with self.__lock:
            return self.__parameters

    @parameters.setter
    def parameters(self, params):
        with self.__lock:
            self.__parameters = params

    @property
    def name(self):
        with self.__lock:
            return self.__name

    @name.setter
    def name(self, n):
        with self.__lock:
            self.__name = n

    @property
    def color(self):
        with self.__lock:
            return self.__color

    @color.setter
    def color(self, c):
        with self.__lock:
            self.__color = c

    @property
    def stroke_width(self):
        with self.__lock:
            return self.__stroke_width

    @stroke_width.setter
    def stroke_width(self, sw):
        with self.__lock:
            self.__stroke_width = sw

    def register_listener(self, fun):
        return self.__listeners.register(fun)

    def delete_listener(self, lid):
        self.__listeners.delete(lid)
