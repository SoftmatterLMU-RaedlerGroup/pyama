from threading import RLock

import numpy as np

from ..util import make_uid


class RoiParameters:
    __slots__ = ('__lock', '__id', '__name')
    def __init__(self, name=None):
        self.__lock = RLock()
        self.__id = make_uid(self)
        self.__name = name

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

    def props(self, **par_individual):
        """Get the (technical) properties of the ROI.

Override this when subclassing RoiParameters.
`par_individual` holds the individual parameters of the given ROI.
This method should return an instance of a subclass of
RoiProperties.
        """
        raise NotImplementedError


class RoiProperties:
    """Provider of (techincal) ROI properties.

The properties are calculated based on the coordinates
just-in-time. Since many RoiProperties instances may consume
a significant amount of memory, this class is intended to
be used as throw-away class.

Once calculated, the properties should not be changed any more.
ROI properties should only be accessed through the
properties definded by this class (or its subclasses) to ensure
that just-in-time calculation is invoked, if necessary.

This class is intended to be sub-classed.
    """
    __slots__ = ()
    def __init__(self):
        self._coords = None
        self._area = None


    @property
    def coords(self):
        return self._coords





