from threading import RLock
from .base import Roi
from ..util import make_uid
from ..util.listener import Listeners


class RoiCollection:
    IDX_TYPE = 0
    IDX_VERSION = 1

    def __init__(self, type_=None, parameters=None, name=None, color=None, stroke_width=None):
        self.__uid = make_uid(self)
        self.__type = type_
        self.__parameters = parameters
        self.__name = name
        self.__color = color
        self.__stroke_width = stroke_width
        self.__rois = {}
        self.__listeners = Listeners()
        self.__lock = RLock()

    #@property
    #def key(self):
    #    return self.__key

    @property
    def type(self):
        return self.__type
    #    return self.__key[RoiCollection.IDX_TYPE]

    #@property
    #def version(self):
    #    return self.__key[RoiCollection.IDX_VERSION]

    @property
    def uid(self):
        return self.__uid

    def __len__(self):
        with self.__lock:
            return self.__rois.__len__()

    def __contains__(self, frame):
        with self.__lock:
            return self.__rois.__contains__(frame)

    def _assert_roi_compatibility(self, roi):
        """Perpare ROI or list of ROIs for further processing.

`roi` is a Roi instance or an iterable of Roi instances with the same
value for the `type` property. Else, an exception is raised.

A tuple is returned with a list of the roi elements in `roi` as first tuple element,
and the value of the `type` property as second tuple element.
        """
        if isinstance(roi, Roi):
            checked_type = roi.type
            rois = [roi]
        else:
            checked_type = None
            rois = []
            for r in roi:
                if not isinstance(r, Roi):
                    raise TypeError(f"incompatible ROI type: expected 'Roi', got '{type(r)}'")
                elif r.type != checked_type:
                    if checked_type is None:
                        checked_type = r.type
                    else:
                        raise TypeError(f"incomaptible ROI type: expected '{checked_type}', got '{r.type}'")
                rois.append(r)
        return rois, checked_type

    def set(self, frame, roi):
        print("[RoiCollection.set] DEPRECATED, use __setitem__ instead") #DEBUG
        self[frame] = roi

    def add(self, frame, rois):
        #TODO use frame attribute of Roi objects
        if frame not in self:
            self[frame] = rois
            return
        rois, rtype = self._assert_roi_compatibility(roi)
        with self.__lock:
            if self.__type != rtype:
                if self.__type is None:
                    self.__type is rtype
                else:
                    raise TypeError(f"incomaptible ROI type: expected '{self.__type}', got '{rtype}'")
            self.__rois[frame].extend(rois)
        self.__listeners.notify()

    def __getitem__(self, frame):
        with self.__lock:
            return self.__rois.get(frame)

    def __setitem__(self, frame, rois):
        rois, rtype = self._assert_roi_compatibility(rois)
        with self.__lock:
            if self.__type != rtype:
                if self.__type is None:
                    self.__type = rtype
                else:
                    raise TypeError(f"incomaptible ROI type: expected '{self.__type}', got '{rtype}'")
            self.__rois[frame] = rois
        self.__listeners.notify()

    def __delitem__(self, frame):
        if isinstance(frame, tuple):
            frame, rois = frame
            if isinstance(rois, Roi):
                rois = [rois]
            with self.__lock:
                for r in rois:
                    self.__rois[frame].remove(r)
        else:
            with self.__lock:
                del self.__rois[frame]

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
