from dataclasses import dataclass
import threading

import numpy as np
import PIL.Image as pilimg
import PIL.ImageTk as piltk
import skimage.transform as sktrans

from .stack import Stack
from .roistack import RoiStack
from ..util.listener import Listeners


@dataclass
class ChannelSpec:
    isVirtual = None
    name = None
    channel = None
    fun = None
    label = None
    type_ = None
    scales = None

    def __init__(self, name=None, channel=None, fun=None, label=None, type_=None, scales=False):
        if name is not None and channel is not None:
            self.isVirtual = False
            self.name = name
            self.channel = channel
            self.scales = False
            self.label = label
            self.type = type_
        elif fun is not None:
            self.isVirtual = True
            self.fun = fun
            self.scales = scales
            self.label = label
            self.type = type_


class MetaStack(RoiStack):
    def __init__(self):
        super().__init__()
        self.image_lock = threading.RLock()
        self._listeners = Listeners(kinds={'roi', 'image', 'load'})
        self._stacks = {}
        self._channels = []
        self._n_frames = None
        self._width = None
        self._height = None
        self._mode = None

        self.close = self.clear

    def clear(self):
        with self.image_lock:
            for s in self.stacks.keys():
                s.close()
            self._stacks = {}
            self._channels = []
            self._n_frames = None
            self._width = None
            self._height = None
            self._mode = None

        with self.roi_lock:
            self.clear_rois()

        # Notify listeners
        self._listeners.notify(kind=None)

    def set_properties(self, n_frames=None, width=None, height=None, mode=None):
        """Set image properties, overwriting current properties"""
        with self.image_lock:
            if n_frames is not None:
                self._n_frames = n_frames
            if width is not None:
                self._width = width
            if height is not None:
                self._height = height
            if mode is not None:
                self._mode = Stack.dtype_str(mode)
        self._listeners.notify('image')

    def check_properties(self):
        """Check whether properties are set"""
        return None not in (self._n_frames, self._width, self._height)

    def add_stack(self, new_stack, name=None, overwrite=False):
        """Insert a new stack

`new_stack` is either a string of the path of a TIFF stack
or a `Stack` object.
If `overwrite` is False, the method silently returns when
a stack with `name` is already registered.
        """
        # Load stack, if path is given
        if isinstance(new_stack, str):
            name = new_stack
        elif name is None:
            name = new_stack.path
        if not overwrite and name in self._stacks:
            # Avoid overwriting existing stack
            return
        if isinstance(new_stack, str):
            new_stack = self.load_stack(new_stack)

        with self.image_lock:
            # First, check if stack is compatible
            if self._n_frames is None:
                self._n_frames = new_stack.n_frames
            elif self._n_frames != new_stack.n_frames:
                raise ValueError("Incompatible stack: expected {} frames, but found {} frames in '{}'.".format(self._n_frames, new_stack.n_frames, name))
            if self._width is None:
                self._width = new_stack.width
            elif self._width != new_stack.width:
                raise ValueError("Incompatible stack: expected width {}, but found width {} in '{}'.".format(self._width, new_stack.width, name))
            if self._height is None:
                self._height = new_stack.height
            elif self._height != new_stack.height:
                raise ValueError("Incompatible stack: expected height {}, but found height {} in '{}'.".format(self._height, new_stack.height, name))

            if self._mode is None:
                self._mode = new_stack.mode
            else:
                self_dtype = Stack.dtype_str(self._mode)
                new_dtype = Stack.dtype_str(new_stack.mode)
                if np.can_cast(new_dtype, self_dtype):
                    pass
                elif np.can_cast(self_dtype, new_dtype):
                    self._mode = new_stack.mode
                else:
                    raise TypeError(f"Stack types '{self_dtype}'  and '{new_dtype}' not castable")

            # Secondly, register the stack
            self._stacks[name] = new_stack

    def add_channel(self, name=None, channel=None, fun=None, label=None, type_=None, scales=None):
        with self.image_lock:
            if name is not None and channel is not None:
                if name not in self._stacks:
                    raise KeyError("Unknown stack: {}".format(name))
                if channel >= self._stacks[name].n_channels:
                    nc = self._stacks[name].n_channels
                    raise IndexError("Index {} out of range: found {} channels in stack '{}'.".format(idx, nc, name))
                spec = ChannelSpec(name=name, channel=channel, label=label, type_=type_)
            elif fun is not None:
                if not callable(fun):
                    raise ValueError("Expected callable for virtual channel, but found {}.".format(type(fun)))
                spec = ChannelSpec(fun=fun, label=label, scales=scales, type_=type_)
            else:
                raise ValueError("Stack name and channel or function required.")
            self._channels.append(spec)
        self._listeners.notify('image')


    def arrange_channels(self, order):
        """Specify the channel arrangement.

`order` is an iterable of tuples. The first element
of the tuple is the name of a stack, and the second
element of the tuple is a channel index.
        """
        with self.image_lock:
            self._channels = []
            for o in order:
                if isinstance(o, ChannelSpec):
                    self._channels.append(o)
                else:
                    raise TypeError("Require sequence of ChannelSpec")
        self._listeners.notify('image')

    def load_stack(self, path, block=True):
        """Load the stack in TIFF file `path`."""
        #TODO implement progress indicator
        stack = Stack(path)
        return stack

    def get_image(self, *, channel, frame):
        """Get a numpy array of a stack position."""
        with self.image_lock:
            spec = self._channels[channel]
            if spec.isVirtual:
                img = spec.fun(self, frame=frame)
            else:
                name = spec.name
                ch = spec.channel
                img = self._stacks[name].get_image(channel=ch, frame=frame)
            return img

    @staticmethod
    def scale_img(img, scale, anti_aliasing=True, anti_aliasing_sigma=None):
        """Scales an image.

`img` -- the image (ndarray) to be scaled
`scale` -- if scalar, a scaling factor passed to `skimage.resize`,
if multiple values, a shape passed to `skimage.rescale`
`anti_aliasing`, `anti_aliasing_sigma` -- anit-aliasing settings,
see `skimage.rescale` and `skimage.resize`
        """
        if scale is None:
            return img
        scale = np.array(scale)
        if scale.size == 1:
            return sktrans.rescale(img,
                                   scale,
                                   multichannel=False,
                                   mode='constant',
                                   preserve_range=True,
                                   anti_aliasing=True,
                                   anti_aliasing_sigma=anti_aliasing_sigma,
                                  )
        else:
            return sktrans.resize(img,
                                  scale,
                                  mode='constant',
                                  preserve_range=True,
                                  anti_aliasing=True,
                                  anti_aliasing_sigma=anti_aliasing_sigma,
                                 )


    def get_image_copy(self, *, channel, frame):
        """Get a copy of a numpy array of a stack position."""
        return self.get_image(channel=channel, frame=frame).copy()


    def get_frame_tk(self, *, channel, frame, convert_fcn=None):
        """
Get a frame of the stack as <!-- :py:class: -->`tkinter.PhotoImage`.

@param channel The channel of the requested stack position
<!-- :type channel: --> int
@param frame The frame of the requested stack position
<!-- :type frame: --> int
@param convert_fcn Custom conversion function
<!-- :type convert_fcn: --> None or function

If a custom conversion function is given, the function must take
one argument, which is a (n_rows, n_columns)-shaped numpy array
of the current stack position with the bit-depth of the original
image (typically 8 or 16 bit per pixel), and must return
a (n_rows, n_columns)-shaped numpy array of ``uint8`` type.

@return  the image at the requested stack position
<!-- :rtype: --> <!-- :py:class: -->`tkinter.PhotoImage`
        """
        #TODO
        with self.image_lock:
            a0 = self.get_image(channel=channel, frame=frame)
            if convert_fcn:
                a8 = convert_fcn(a0)
            elif self._mode == 'uint8':
                a8 = a0
            elif self._mode == 'bool':
                a8 = np.zeros(a0.shape, dtype=np.uint8)
                a8[a0] = 255
            elif self._mode.startswith('uint'):
                a8 = a0 >> ((a0.itemsize - 1) * 8)
            elif self._mode.startswith('float'):
                #TODO: normalize to global maximum
                a0_min = a0.min()
                a0_max = a0.max()
                if a0_min >= 0. and a0_max <= 1.:
                    # Assume values in [0,1]
                    a0_min = 0.
                    a0_max = 1.
                a8 = (256 / (a0_max - a0_min) * (a0 - a0_min)).astype(np.uint8)
            else:
                raise ValueError(f"Illegal image mode: {self._mode}")
            return piltk.PhotoImage(pilimg.fromarray(a8, mode='L'))

    def add_listener(self, fun, kind=None):
        """Register a listener to stack changes."""
        return self._listeners.register(fun, kind)

    def delete_listener(self, lid):
        """Un-register a listener."""
        self._listeners.delete(lid)

    @property
    def path(self):
        return None

    @property
    def mode(self):
        with self.image_lock:
            return self._mode

    @property
    def order(self):
        with self.image_lock:
            return self._order

    @property
    def width(self):
        with self.image_lock:
            return self._width

    @property
    def height(self):
        with self.image_lock:
            return self._height

    @property
    def n_images(self):
        with self.image_lock:
            if not self._channels:
                return None
            else:
                return len(self._channels) * self._n_frames

    @property
    def n_channels(self):
        with self.image_lock:
            if not self._channels:
                return None
            else:
                return len(self._channels)

    @property
    def n_frames(self):
        with self.image_lock:
            return self._n_frames

    @property
    def stacks(self):
        with self.image_lock:
            return {name: stack.n_channels
                for name, stack in self._stacks.items()}

    def stack(self, name):
        with self.image_lock:
            return self._stacks[name]

    @property
    def channels(self):
        with self.image_lock:
            return self._channels.copy()

    def spec(self, i):
        with self.image_lock:
            return self._channels[i]

    @property
    def stacktype(self):
        return 'meta'
