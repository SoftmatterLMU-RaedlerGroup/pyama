from collections import namedtuple, OrderedDict
import threading

from . import const
from ..util import make_uid
from ..util.listener import Listeners


class BaseStack:
    """Base class for stacks.

This class provides basic stack functionality that may be used by subclasses.
This class not intended for direct instantiation, but only for subclassing.

Implementing classes should provide this API:
* A numpy array of one frame can be obtained by the `get_image` method.
* If the shape of the stack may be changed, the `reshape` method should
be used. Upon reshape, the listeners should be notified.
Else, `reshape` should throw a NotImplementedError.
* If the stack corresponds to a file, the path should be accessible
under `_path`.
* If the stack is a virtual stack (frames are calculated just in time
when `get_image` is called), the constructor of this class should be
called with `virtual=True`.
* If an implementing class has special requirements for listeners
(e.g. require queue, enforce other Listeners implementaiton), an existing
Listeners instance should be passed via the `listeners` keyword or Listeners
options should be passed via the `listeners_opt` keyword of the constructor.
The Listeners must at least have the kinds `reshape` and `close`.
If only more listener kinds are required, the additional kinds can be
passed via the `listeners_kinds` keyword argument.

This class fires these event kinds with a dict as keyword argument `message`:
* Event `const.EVT_RESHAPE` with `message` containing these fields:
- `event`: const.EVT_RESHAPE
- `id`: ID of the calling stack
- `old`: an OrderedDict of the previous shape
- `new`: an OrderedDict of the newly established shape
* Event `const.EVT_CLOSE` with `message` containing these fields:
- `event`: const.EVT_CLOSE
- `id`: ID of the calling stack
A stack emitting this event is being closed and should not send any
events after this event has been sent.
Listeners may/should clean up references to the stack upon this event.
Additionally, all events contain the keyword argument `stack_id` holding the
ID of this stack, which can also be retrieved with the `id` property.
    """

    def __init__(self, *, virtual=False, listeners=None, listeners_kinds=None, listeners_opt=None):
        self.lock = threading.RLock()
        self._listeners_kinds = [const.EVT_RESHAPE, const.EVT_CLOSE]
        if listeners_kinds:
            if isinstance(listeners_kinds, str):
                listeners_kinds = (listenres_kinds,)
            self._listeners_kinds.extend(listeners_kinds)
        if listeners:
            self.listeners = listeners
        else:
            if not listeners_opt:
                listeners_opt = dict()
            if 'kinds' not in listeners_opt:
                listeners_opt['kinds'] = self._listeners_kinds
            self.listeners = Listeners(**listeners_opt)
        assert all(k in self.listeners.kinds for k in (const.EVT_RESHAPE, const.EVT_CLOSE))
        self.__virtual = virtual

        self._id = make_uid(self)
        self._path = None
        self._dtype = None
        self._n_images = None
        self._shape = None
        self._min_val = None
        self._max_val = None


    def close(self):
        """Close the TIFF file.

This method may be implemented/overwritten by a subclass.
Closing a stack should always fire a `const.EVT_CLOSE` event
to its listeners to allow for cleanup.
        """
        msg = dict(event=const.EVT_CLOSE, id=self._id)
        self.listeners.notify(const.EVT_CLOSE, message=msg)


    def get_image(self, *, frame=None, z=None, channel=None):
        """Get a numpy array of a stack position."""
        raise NotImplementedError("This method must be implemented by a subclass.")


    def get_linear_index(self, *, frame=None, z=None, channel=None):
        """Get index of an image in a linear sequence of images.

Indices are zero-based.
All indices of existing dimensions are required.
Slicing is not supported.
        """
        i_request = {const.T:frame, const.Z:z, const.C:channel}
        i = 0
        with self.lock:
            for dim, n in self._shape:
                if dim not in const.STACK_DIM:
                    break
                m = i_request.pop(dim)
                if all(x is None for x in (n, m)):
                    continue
                elif any(x is None for x in (n, m)):
                    raise IndexError(f"Dimension '{dim}' with size '{n}' has no index '{m}'")
                i = i * n + m
                if not i_request:
                    break
            if i_request and any(x is not None for x in i_request.keys()):
                dim = ", ".join(dim for dim, n in i_request.items() if n is not None)
                raise IndexError(f"Index requested for non-existing dimension(s): {dim}")
            return i


    def reshape(self, shape):
        """Reshape the stack.

The new shape must be passed as a dict-like object with preserved order.

When reshaping is finished, listeners of the event const.EVT_RESHAPE are
notified with the keyword argument `message` holding a namedtuple with fields:

`event`: const.EVT_RESHAPE

`old`: OrderedDict of shape before reshape

`new`: OrderedDict of shape after reshape
        """
        new_shape = OrderedDict()
        n_img = 1
        is_stack_dim = True
        for dim, n in shape.items():
            if dim in const.STACK_DIM:
                if not is_stack_dim:
                    raise ValueError("Dimensions 'TZC' must not be set after 'YXS'")
                n_img *= n
            elif dim in const.IMG_DIM:
                if is_stack_dim:
                    is_stack_dim = False
            else:
                raise ValueError(f"Unknown dimension '{dim}'")
            new_shape[dim] = n
        assert self._n_images == n_img

        with self.lock:
            old_shape, self._shape = self._shape, new_shape
            msg = dict(event=const.EVT_RESHAPE,
                       id=self._id,
                       old=old_shape.copy(),
                       new=new_shape.copy())
            self.listeners.notify(const.EVT_RESHAPE, message=msg)


    def add_listener(self, fun, queue):
        """Register a listener to stack changes."""
        return self.listeners.register(fun, queue=queue)


    def delete_listener(self, lid):
        """Un-register a listener."""
        self.listeners.delete(lid)


    @property
    def id(self):
        return self._id

    @property
    def is_virtual(self):
        return self.__virtual

    @property
    def path(self):
        with self.lock:
            return self._path

    @property
    def dtype(self):
        with self.lock:
            return self._dtype

    @property
    def n_images(self):
        with self.lock:
            return self._n_images

    @property
    def shape(self):
        with self.lock:
            sh = self._shape
        if sh is None:
            return None
        return namedtuple('ShapeTuple', sh.keys())(**sh)

    @property
    def shape_dict(self):
        with self.lock:
            try:
                return self._shape.copy()
            except AttributeError:
                return None

    @property
    def n_frames(self):
        try:
            with self.lock:
                return self._shape[const.T]
        except KeyError:
            return None

    @property
    def n_slices(self):
        try:
            with self.lock:
                return self._shape[const.Z]
        except KeyError:
            return None

    @property
    def n_channels(self):
        try:
            with self.lock:
                return self._shape[const.C]
        except KeyError:
            return None

    @property
    def height(self):
        try:
            with self.lock:
                return self._shape[const.Y]
        except KeyError:
            return None

    @property
    def width(self):
        try:
            with self.lock:
                return self._shape[const.X]
        except KeyError:
            return None

    @property
    def n_samples(self):
        try:
            with self.lock:
                return self._shape[const.S]
        except KeyError:
            return None

