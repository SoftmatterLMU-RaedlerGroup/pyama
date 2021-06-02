import tempfile
import threading
import time

import numpy as np

from ..util.listener import Listeners

class BaseStack:
    is_composite = None

    def __init__(self):
        self.id = self._generate_id()
        self.image_lock = threading.RLock()
        self._listeners = Listeners(kinds={"image"})
        self._init_attributes()

    def _init_attributes(self):
        """Initialize attributes into a defined state.

This method is intended to be called only once during initialization.
        """
        # The stack path and object
        self._path = None
        self._i_channel = None
        self.img = None
        self._tmpfile = None
        self._stacktype = None

        # The stack properties
        self._mode = None
        self._width = 0
        self._height = 0
        self._n_images = 0
        self._n_frames = 0
        self._n_channels = 0
        if self.is_composite:
            self._channel_order = []
            self._channel_lut = {}
        else:
            self._channel_order = None
            self._channel_lut = None
        self._channel_labels = None

    def _generate_id(self):
        """Generate an unique string ID of this instance"""
        return f"{id(self) :x}_{time.perf_counter_ns() :x}"

    def add_channel(self, chan, index=-1, force=False):
        if not self.is_composite:
            raise RuntimeError("Adding channels is forbidden for non-composite stacks")
        with self.img_lock:
            if chan.id in self._channel_lut:
                if not force:
                    raise RuntimeError("Attempting to add channel twice")
            else:
                self._channel_lut[chan.id] = chan
            if index < 0:
                index = len(self._channel_order) + 1 - index
            self._channel_order.insert(index, chan)
            self._listeners.notify("image")

    def remove_channel(self, *indices, close=False):
        with self.img_lock:
            #TODO check if i is integer or string
            self._channel_order[:] = (i for i in self._channel_order if i not in indices)
            for i in indices:
                try:
                    del self._channel_lut[i]
                except KeyError:
                    print(f"Cannot remove channel '{i}': not found")
                else:
                    #TODO close channel if `close`



            self._listeners.notify("image")




    def _make_memmap(self, dtype=None, single_chan=False):
        if self.is_composite:
            raise RuntimeError("Creating memmap is forbidden for composite stacks")
        if dtype is None:
            if self._mode == 16:
                dtype = np.unit16
            elif self._mode == 8:
                dtype = np.uint8
            elif self._mode == 1:
                dtype = np.bool_
            else:
                raise ValueError("Cannot create memmap: no valid dtype found")
        with self.image_lock:
            if single_chan and self._n_channels == 1:
                 shape = (self._n_frames, self._height, self._width)
            else:
                 shape = (self._n_channels, self._n_frames, self._height, self._width)
            if self._tmpfile is not None:
                self._tmpfile.close()
            self._tmpfile = tempfile.TemporaryFile()
            self.img = np.memmap(filename=self._tmpfile,
                                 dtype=dtype,
                                 shape=shape,
                                )

    def close(self):
        """Close the TIFF file."""
        with self.image_lock:
            if self.is_composite:
                for c in self._channels:
                    c.close()
            else:
                self.img = None
                try:
                    self._tmpfile.close()
                except Exception:
                    pass
                self._tmpfile = None


    def __del__(self):
        if self._tmpfile is not None:
            self._tmpfile.close()

    def get_image(self, *, channel=None, frame):
        """Get a numpy array of a stack position."""
        with self.image_lock:
            if channel is None and self._n_channels == 1:
                channel = ...
            return self.img[channel, frame, :, :].copy()

    def get_image_copy(self, *, frame, channel=None):
        """Get a copy of a numpy array of a stack position.

DEPRECATED: Use `get_image` instead.
        """
        #DEBUG
        import traceback
        print("\n*** [get_image_copy] DEPRECATED ***")
        traceback.print_stack(limit=-3)
        self.get_image(channel=channel, frame=frame)


    @property
    def path(self):
        with self.image_lock:
            return self._path

    @property
    def i_channel(self):
        with self.image_lock:
            return self._i_channel

    @property
    def mode(self):
        with self.image_lock:
            return self._mode

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
            return self._n_images

    @property
    def n_channels(self):
        with self.image_lock:
            return self._n_channels

    @property
    def n_frames(self):
        with self.image_lock:
            return self._n_frames

    @property
    def stacktype(self):
        return self._stacktype

    def add_listener(self, fun, kind=None):
        """Register a listener to stack changes."""
        return self._listeners.register(fun, kind)

    def delete_listener(self, lid):
        """Un-register a listener."""
        self._listeners.delete(lid)

