from collections import defaultdict
from threading import RLock
import weakref

from ..stack import const as stconst
from ..util import make_uid

class BaseRoi:
    """Base class for representing a region-of-interest (ROI).

'group' is None or a group. Will be stored as weakref.
'color' is None or a string of a hex RGB color ('#rrggbb')
'visible' is a boolean flag whether to display the ROI.

If the 'color' or 'visible' properties are None, their values
are inherited from the 'group'.
    """
    __slots__ = ('__lock', '__id', '__weakref__', '__name', '__group_ref', '__visible', '__color')

    def __init__(self, name=None, group=None, color=None, visible=None):
        self.__lock = RLock()
        self.__id = make_uid(self)
        self.group = group
        self.__name = name
        self.__color = color
        self.__visible = visible

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
    def group(self):
        with self.__lock:
            return self.__group_ref()

    @group.setter
    def group(self, new):
        with self.__lock:
            if not new:
                self.__group_ref = None
            else:
                self.__group_ref = weakref.ref(new, self.__delete_group_ref)

    @property
    def color(self):
        with self.__lock:
            if self.__color is None:
                try:
                    return self.group.color
                except Exception:
                    return None
            else:
                return self.__color

    @color.setter
    def color(self, col):
        with self.__lock:
            self.__color = col

    @property
    def visible(self):
        with self.__lock:
            if self.__visible is None:
                try:
                    return self.group.visible
                except Exception:
                    return None
            else:
                return self.__visible

    @visible.setter
    def visible(self, is_visible):
        with self.__lock:
            self.__visible = is_visible

    def __delete_group_ref(self, ref):
        with self.__lock:
            if ref is self.__group_ref:
                self.__group_ref = None


class Roi(BaseRoi):
    """Representation of a region-of-interest (ROI).

'params' is a RoiParameters object.
'par_ind' is a dict with individual parameters.

'props' is a RoiProperties instance corresponding to the
individual parameters and the RoiParameters. It is created
just-in-time and will be cached.
    """
    __slots__ = ('__params', '__par_ind', '__props')

    def __init__(self, params, par_ind, **base_args):
        super().__init__(**base_args)
        self.__params = params
        self.__props = None
        self.__par_ind = par_ind

    @property
    def params(self):
        return self.__params

    @property
    def par_ind(self):
        with self.__lock:
            return self.__par_ind.copy()

    @property
    def props(self):
        with self.__lock:
            if self.__props is None:
                self.__props = self.__params.props(**self.par_ind)
            return self.__props


class RoiGroup(BaseRoi):
    """Class for grouping related Roi instances.

    """
    __slots__ = ('__parent_ref', '__dimensions', '__rois', '__subgroups', '__tacking_class')

    def __init__(self, parent=None, dimensions=None, rois=None, subgroups=None, tracking_class=None, **kwargs):
        super().__init__(**kwargs)
        self.parent = parent
        self.__subgroups = set()
        if subgroups:
            self.add_subgroups(*subgroups)

    @property
    def parent(self):
        with self.__lock:
            return self.__parent_ref()

    @parent.setter
    def parent(self, new):
        with self.__lock:
            if new is None:
                self.__parent_ref = None
            else:
                self.__parent_ref = weakref.ref(parent, self.__delete_parent_ref)

    def __delete_parent_ref(self, ref):
        with self.__lock:
            if ref is self.__parent_ref:
                self.__parent_ref = None

    @property
    def subgroups(self):
        with self.__lock:
            return self.__subgroups.copy()

    def add_subgroups(self, **new):
        with self.__lock:
            self.__subgroups |= new

    def remove_subgroups(self, **old):
        with self.__lock:
            self.__subgroups -= old




## OLD STUFF:


# class Roi(BaseRoi):
    # __slots__ = ('_dimensions', '_rois')

    # def __init__(self, dimensions, rois=None, **kwargs):
        # super().__init__(**kwargs)
        # self._dimensions = {d for d in dimensions if d in stconst.STACK_DIM}
        # self._rois = {d: defaultdict(set) for d in self._dimensions}

    # def at(self, t=None, z=None, c=None):
        # """Get ROI at given stack position"""
        # raise NotImplementedError #TODO
        # res = None
        # with self.lock:
            # for dim in self._dimensions:
                # r = self._rois[dim][None]
                # if dim == stconst.T:
                    # d = t
                # elif dim == stconst.C:
                    # d = c
                # elif dim == stconst.Z:
                    # d = z

                # if d is not None:
                    # r |= self._rois[dim][d]

                # if res is None:
                    # res = r
                # else:
                    # res &= r

        # assert len(res) == 1 #TODO: More advanced processing?

        # reutrn res.pop()





    # def add(self, *rois):
        # with self._lock:
            # for roi in rois:
                # for d in self._dimensions:
                    # try:
                        # self._dimensions[d][roi.position[d]].add(roi)
                    # except:
                        # self._dimensions[d][None].add(roi)
