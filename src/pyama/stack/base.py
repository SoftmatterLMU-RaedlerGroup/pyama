from collections import namedtuple, OrderedDict
import threading

from . import const
from .shape import Shape
from ..util import make_uid
from ..util.listener import Listeners


class BaseStack:
    """Base class for stacks.

    This class provides basic stack functionality that may be used by subclasses.
    This class not intended for direct instantiation, but only for subclassing.

    Implementing classes should provide this API:
        * A numpy array of one frame can be obtained by the `get_image` method.
        * If the shape of the stack can be changed, the `reshape` method should
          be used. Upon reshape, the listeners should be notified.
          An example for reshaping a stack is when a channel is added.
          Else, `reshape` should throw a NotImplementedError.
        * The stack should be given a name, which is saved under
          `_name` for display in the user interface.
          The default name may be created based on the file path.
        * If an implementing class has special requirements for listeners
          (e.g. require queue, enforce other Listeners implementaiton), an existing
          Listeners instance should be passed via the `listeners` keyword or Listeners
          options should be passed via the `listeners_opt` keyword of the constructor.
          The Listeners must at least have the kinds 'reshape' and 'close'.
          If only more listener kinds are required, the additional kinds can be
          passed via the `listeners_kinds` keyword argument.

    This class fires these event kinds with a dict as keyword argument 'message':
        * Event 'const.EVT_RESHAPE' with 'message' containing these fields:
            - 'event': const.EVT_RESHAPE
            - 'id': ID of the calling stack
            - 'old': an OrderedDict of the previous shape
            - 'new': an OrderedDict of the newly established shape
        * Event 'const.EVT_CLOSE' with 'message' containing these fields:
            - 'event': const.EVT_CLOSE
            - 'id': ID of the calling stack
          A stack emitting this event is being closed and should not send any
          events after this event has been sent.
          Listeners should clean up references to the stack upon this event.
    """

    def __init__(self, name=None, *, listeners=None, listeners_kinds=None, listeners_opt=None):
        self.lock = threading.RLock()
        self._listeners_kinds = [const.EVT_RESHAPE, const.EVT_CLOSE, const.EVT_STACK_RENAME]
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

        self._id = make_uid(self)
        self._name = name
        self._shape = None
        self._channels = {}
        self._channel_order = []


    def init_shape(self, *, T, Z=None, Y, X, order='TZC'):
        """Initialize the shape of the stack instance.

        The stack is initialized with zero channels.
        The other dimensions can be adjusted with the keyword arguments
        `T` (frames), `Z` (slices, optional), `Y` (rows) and `X` (columns).

        The order of the stack dimensions can be adjusted by setting
        the `order` argument to any permutation of 'TZC'; Z may be omitted.
        """
        sd = OrderedDict()
        for dim in order:
            if dim == const.T:
                sd[const.T] = T
            elif dim == const.C:
                sd[const.C] = C
            elif dim = const.Z:
                sd[const.Z] = Z
            else:
                raise ValueError(f"Invalid dimension '{dim}'")
        sd[const.Y] = Y
        sd[const.X] = X
        shape = Shape(sd)
        with self._lock:
            if self._shape is not None:
                raise RuntimeError("The shape is already set.")
            self._shape = shape


    def close(self):
        """Close the TIFF file.

        This method should be called using 'super()' when a subclass instance is closed.
        Closing a stack should always fire a 'const.EVT_CLOSE' event
        to its listeners to allow for cleanup.
        """
        msg = dict(event=const.EVT_CLOSE, id=self._id)
        self.listeners.notify(const.EVT_CLOSE, message=msg)


    def get_image(self, *, frame=None, z=None, channel=None):
        """Get a numpy array of a stack position."""
        with self.lock:
            if channel is None and len(self._channels) == 1:
                channel = next(iter(self._channels.values()))
            else:
                channel = self._channels[self._identify_channel(channel)[1]]
            return channel.get_image(frame=frame, z=z)


    def add_channel(self, channel, index=None):
        """Insert a new channel into the stack.

        Arguments:
            channel -- the channel instance to add
            index -- the position at which to insert the new channel
                    into the channel list, given as zero-based integer.
                    By default, the new channel is appended at the end.
        """
        chid = channel.id
        with self.lock:
            self._channels[chid] = channel
            if index is None:
                self._channel_order.append(chid)
            else:
                self._channel_order.insert(index, chid)
            self._shape['C'] += 1


    def _identify_channel(self, channel):
        """Identify a channel from its ID or index.

        `channel` is the ID of a channel, the index of a channel in
        the channel order of the stack or the channel object itself.

        Returns the tuple (channel ID, channel index).

        Raises `ValueError` if no corresponding channel is found.
        """
        with self.lock:
            try:
                chid = self._channel_order[channel]
                index = channel
            except Exception:
                try:
                    index = self._channel_order.index(channel)
                    chid = channel
                except Exception:
                    try:
                        chid = channel.id
                        index = self._channel_order.index(chid)
                    except Exception:
                        raise ValueError(f"No corresonding channel found for '{channel}'.") from None
            return chid, index


    def drop_channel(self, channel):
        """Drop a channel from the stack.

         Arguments:
            channel -- the zero-based integer index or the ID
                       of the channel to be dropped.

        Raises `ValueError` if channel is not found.
        """
        with self.lock:
            chid, index = self._identify_channel(channel)
            self._channel_order.pop(index)
            self._channels.pop(chid)
            self._shape['C'] -= 1


    def get_channel(self, channel):
        """Get a channel instance"""
        with self.lock:
            chid, _ = self._identify_channel(channel)
            return self._channels[chid]


    def get_linear_index(self, *, frame=None, z=None, channel=None):
        """Get index of an image in a linear sequence of images.

        Indices are zero-based.
        All indices of existing dimensions are required.
        Slicing is not supported.

        @attention This method is deprecated and will be removed from this class
        since getting the linear index is specific to the implementing class.
        """
        i_request = {const.T: frame, const.Z: z, const.C: channel}
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
        notified with the keyword argument 'message' holding a namedtuple with fields:
            'event': const.EVT_RESHAPE
            'old': OrderedDict of shape before reshape
            'new': OrderedDict of shape after reshape

        @attention This method is deprecated and will be removed from this class
        since reshaping is specific to the implementing class.
        """
        new_shape = OrderedDict()
        n_img = 1
        is_stack_dim = True
        for dim, n in shape.items():
            if dim in const.STACK_DIM:
                if not is_stack_dim:
                    raise ValueError("Dimensions 'TZC' must not be set after 'YX'")
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
    def name(self):
        with self.lock:
            return self._name

    @name.setter
    def name(self, new_name):
        with self.lock:
            self._name = new_name
            msg = dict(event=const.EVT_STACK_RENAME,
                       id=self._id,
                       name=self._name)
            self.listeners.notify(const.EVT_STACK_RENAME, msg)

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


class BaseChannel:
    """Base class for channels.

    This class is not intended to be directly instantiated.
    Instead, classes that implement specific channel types should inherit
    from this class.

    Initializer arguments:
        `shape` -- (mutable) dict-like holding the shape of the channel or its
        containing stack.

    The fields `_min` and `_max` give the minimum and maximum value in the whole
    channel; the field `_dtype` gives the dtype that is returned by the `get_image`
    method.
    These fields should be filled when initializing an implementing class.
    They can be retrieved by the properties `min`, `max` and `dtype`, respectively.
    """
    def __init__(self, shape):
        self._lock = threading.RLock()
        self._id = make_uid(self)
        self._min = None
        self._max = None
        self._dtype = None

        shape[const.C] = 1
        self._shape = Shape(shape, reshapable_dims=None)


    def get_image(self, *, frame, z=None):
        """Get an image frame as numpy array.

        This method must be provided by an inheriting class.
        """
        raise NotImplementedError


    @property
    def id(self):
        return self._id


    @property
    def min(self):
        with self._lock:
            return self._min


    @property
    def max(self):
        with self._lock:
            return self._max


    @property
    def dtype(self):
        with self._lock:
            return self._dtype


    @property
    def shape(self):
        with self._lock:
            sh = self._shape
        if sh is None:
            return None
        return namedtuple('ShapeTuple', sh.keys())(**sh)


    @property
    def shape_dict(self):
        with self._lock:
            try:
                return self._shape.copy()
            except AttributeError:
                return None

    @property
    def n_frames(self):
        try:
            with self._lock:
                return self._shape[const.T]
        except KeyError:
            return None

    @property
    def n_slices(self):
        try:
            with self._lock:
                return self._shape[const.Z]
        except KeyError:
            return None

    @property
    def height(self):
        try:
            with self._lock:
                return self._shape[const.Y]
        except KeyError:
            return None

    @property
    def width(self):
        try:
            with self._lock:
                return self._shape[const.X]
        except KeyError:
            return None


