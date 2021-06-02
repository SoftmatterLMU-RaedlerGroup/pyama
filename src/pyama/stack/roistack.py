import threading

from ..roi import RoiCollection

class RoiStack:
    """This class provides capability of a stack to hold
RoiCollections and is not intended to be directly instantiated.

Inheriting classes must provide:
* a call to super().__init__()
* `_listeners`: a Listeners instance with at least the kind `roi`
    """
    def __init__(self):
        self.roi_lock = threading.RLock()
        self.__rois = {}

    def _notify_roi_listeners(self, *_, **__):
        """Convenience function for propagation of ROI changes"""
        self._listeners.notify('roi')

    def new_roi_collection(self, rc):
        """Create a new RoiCollection"""
        if isinstance(rc, RoiCollection):
            with self.roi_lock:
                rc.register_listener(self._notify_roi_listeners)
                self.__rois[rc.name] = rc
        else:
            raise TypeError(f"Expected 'RoiCollection', got '{type(rc)}'")

    def set_rois(self, rois, name=Ellipsis, frame=Ellipsis, replace=False):
        """Set the ROI set of the stack.

@param rois The ROIs to be set
<!-- :type rois: --> iterable of Roi
@param name The name of the RoiCollection as displayed (use Ellipsis as default)
<!-- :type name: --> str
@param frame index of the frame to which the ROI belongs.
Use ``Ellipsis`` to specify ROIs valid in all frames.
<!-- :type frame: --> int or Ellipsis

For details, see <!-- :py:class: -->`RoiCollection`.
        """
        with self.roi_lock:
            if name not in self.__rois:
                self.new_roi_collection(RoiCollection(name=name))
            if replace:
                self.__rois[name][frame] = rois
            else:
                self.__rois[name].add(frame, rois)

    def print_rois(self):
        """Nice printout of ROIs. Only for DEBUGging."""
        prefix = "[Stack.print_rois]"
        for k, v in self.__rois.items():
            print(f"{prefix} Roi '{k}' has {len(v)} frame(s)")
            for frame, rois in v.items():
                print(f"{prefix}\t frame '{frame}' has {len(rois)} ROIs")
                # print(rois) # DEBUG

    @property
    def rois(self):
        with self.roi_lock:
            return self.__rois

    def get_rois(self, name=Ellipsis, frame=None):
        """Get ROIs, optionally at a specified position.

@param name RoiCollection display name
<!-- :type name: --> tuple (len 2) of str
@param frame frame identifier
@return  ROI set
        """
        with self.roi_lock:
            rois = self.__rois.get(name)
            if rois is not None and frame is not None:
                return rois[frame]
            return rois

    def clear_rois(self, name=None, frame=None):
        """Delete the current ROI set"""
        with self.roi_lock:
            if name is None:
                self.__rois = {}
            elif frame is None:
                del self.__rois[name]
            else:
                del self.__rois[name][frame]
            self._notify_roi_listeners()

