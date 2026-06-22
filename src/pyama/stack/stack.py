#! /usr/bin/env python3
import json
import os
import re
import tempfile
import threading

import h5py
import nd2reader
import numpy as np
import tifffile
import PIL.Image as pilimg
import PIL.ImageTk as piltk

from ._parse_ome import parse_ome
from ..roi import RoiCollection
from ..listener import Listeners
from ..session.status import DummyStatus

SUPPORTED_DTYPES = ('bool', 'uint8', 'uint16', 'uint32', 'uint64', 'float16', 'float32', 'float64')

class Stack:
    """Represents an image stack.

    :param path: (optional) path to a file holding a TIFF stack
    :type path: str
    """

    def __init__(self, path=None, arr=None, width=None, height=None, n_frames=None, n_channels=None, dtype=None, status=None, channels=None, view=None):
        """Initialize a stack."""
        self.image_lock = threading.RLock()
        self.info_lock = threading.RLock()
        self.roi_lock = threading.RLock()
        self._listeners = Listeners(kinds={"roi", "image"})
        self._clear_state()
        if status is None:
            status = DummyStatus()

        # Initialize stack
        if path is not None:
            # Load from file (TIFF or numpy array)
            if view is not None:
                self.load(path, status=status, channels=channels, view=view)
            else:
                self.load(path, status=status, channels=channels)
        elif arr is not None:
            # Use array
            self._path = None
            self.img = arr
            self._n_channels, self._n_frames, self._height, self._width = arr.shape
            self._n_images = self._n_channels * self._n_frames
            self._mode = self.dtype_str(arr.dtype)
            self._listeners.notify("image")
        elif None not in (width, height, n_frames, n_channels, dtype):
            # Create empty array
            self._path = None
            self._width = width
            self._height = height
            self._n_frames = n_frames
            self._n_channels = n_channels
            self._mode = self.dtype_str(dtype)
            self.img = np.zeros(dtype=dtype,
                                shape=(self._n_channels,
                                       self._n_frames,
                                       self._height,
                                       self._width
                                      )
                               )
            self._listeners.notify("image")

    def _clear_state(self):
        """Clear the internal state"""
        with self.image_lock:
            # The stack path and object
            self._path = None
            self.img = None # This will now free the in-memory numpy array
            self._stacktype = None

            # The stack properties
            self._mode = None
            self._order = None
            self._width = 0
            self._height = 0
            self._n_images = 0
            self._n_frames = 0
            self._n_channels = 0
            self._channel_labels = None

        # ROI list
        with self.roi_lock:
            self.__rois = {}

        # Clear image information
        self.clear_info()

        # Notify listeners
        self._listeners.notify(kind=None)

    @staticmethod
    def dtype_str(dt):
        """String representation of supported data type"""
        dt = str(np.dtype(dt))
        if dt not in SUPPORTED_DTYPES:
            raise TypeError(f"Data type '{dt}' not supported.")
        return dt


    def load(self, path, loader=None, status=None, channels=None, h5_key=None, view=0):
        """Load a stack from a path.

        `path` -- path to a stack file
        `loader` -- str, name of a stack loader.
                    Currently supported loaders: tiff, npy, hdf5
                    If not given, loader is determined from file extension.
        `status` -- Status instance for displaying progress
        `channels` -- index of channels to be loaded. Default is to load all channels.
                      Any value for indexing into a dimension of a numpy array
                      may be given.
        `h5_key` -- str, key of the dataset in a HDF5 file.
                    Currently, only HDF5 files created by Ilastik are supported.
                    May be omitted if file contains only one dataset.
        """
        self._path = path
        if loader is None:
            ext = os.path.splitext(self._path)[-1]
            if ext.casefold().startswith('.tif'):
                loader = 'tiff'
            elif ext.casefold().startswith('.np'):
                loader = 'npy'
            elif ext.casefold() in ('.h5', '.hdf5'):
                loader = 'hdf5'
            elif ext.casefold().startswith('.nd2'):
                loader = 'nd2'
            else:
                loader = '' # to prevent error in string comparison
        if loader == 'tiff':
            self._load_tiff(status=status, channels=channels)
        elif loader == 'npy':
            self._load_npy(status=status, channels=channels)
        elif loader == 'hdf5':
            self._load_hdf5(status=status, channels=channels, h5_key=h5_key)
        elif loader == 'nd2':
            self._load_nd2(status=status, channels=channels, view=view)
        else:
            self._clear_state()
            raise TypeError("Unknown type: {}".format(loader))

    def _load_npy(self, ext=None, channels=None, status=None):
        if channels is not None:
            #TODO implement channel selection
            raise NotImplementedError("Channel selection for TIFF is not implemented yet")
        if status is None:
            status = DummyStatus()
        if ext is None:
            ext = os.path.splitext(self._path)[-1]
        with self.image_lock, status("Reading stack"):
            if ext == '.npy':
                arr = np.load(self._path, mmap_mode='r', allow_pickle=False)
            elif ext == '.npz':
                with np.load(self._path, mmap_mode='r', allow_pickle=False) as arr_file:
                    arr = next(iter(arr_file.values()))
            else:
                raise TypeError("Unknown file extension: {}".format(ext))
            self._stacktype = 'numpy'
            self._mode = self.dtype_str(arr.dtype)
            #TODO: check dimensions (swap height/width?)
            if arr.ndim == 2:
                self._n_channels = 1
                self._n_frames = 1
                self._height, self._width = arr.shape
                arr = np.reshape(arr, (1, 1, self._height, self._width))
            elif arr.ndim == 3:
                self._n_channels = 1
                self._n_frames, self._height, self._width = arr.shape
                arr = np.reshape(arr, (1, self._n_frames, self._height, self._width))
            elif arr.ndim == 4:
                self._n_frames, self._height, self._width, self._n_channels = arr.shape
                arr = np.moveaxis(arr, 3, 0)
            else:
                raise ValueError("Bad array shape: {}".format(arr.ndim))
            self._n_images = self._n_channels * self._n_frames
            try:
                self.img = np.zeros(dtype=arr.dtype,
                                    shape=(self._n_channels,
                                           self._n_frames,
                                           self._height,
                                           self._width
                                          )
                                   )
                self.img[...] = arr[...]
            except Exception:
                self._clear_state()
                raise
            finally:
                del arr
                self._listeners.notify("image")

    def _load_nd2(self, status=None, channels=None, view=0):
        if channels is not None:
            #TODO implement channel selection
            raise NotImplementedError("Channel selection for ND2 is not implemented yet")
        if status is None:
            status = DummyStatus()
            print("Stack._load_nd2: use DummyStatus") #DEBUG
        try:
            with self.image_lock, nd2reader.ND2Reader(self._path) as nd2, status("Reading stack …") as current_status:
                self._stacktype = 'nd2'
                self._n_channels = nd2.sizes.get('c', 1)
                self._n_frames = nd2.sizes.get('t', 1)
                self._n_views = nd2.sizes.get('v', 1)
                self._height = nd2.sizes.get('y', 1)
                self._width = nd2.sizes.get('x', 1)
                self._mode = self.dtype_str(nd2.pixel_type)
                self._n_images = self._n_channels * self._n_frames
                self._order = 'tc'

                if view >= self._n_views or view < 0:
                    raise ValueError(f"View index {view} is out of range for {self._path}")

                self.img = np.zeros(dtype=self._mode, # self._mode is already a dtype string
                                    shape=(self._n_channels,
                                           self._n_frames,
                                           self._height,
                                           self._width))
                for i in range(self._n_images):
                    current_status.reset("Reading image", current=i+1, total=self._n_images)
                    ch, fr = self.convert_position(image=i)
                    self.img[ch, fr, :, :] = nd2.get_frame_2D(c=ch, t=fr, v=view)

        except Exception as e:
            self._clear_state()
            print(str(e))
            raise

        finally:
            self._listeners.notify("image")
            
    def _load_tiff(self, status=None, channels=None):
        if channels is not None:
            #TODO implement channel selection
            raise NotImplementedError("Channel selection for TIFF is not implemented yet")
        if status is None:
            status = DummyStatus()
            print("Stack._load_tiff: use DummyStatus") #DEBUG
        try:
            with self.image_lock, tifffile.TiffFile(self._path) as tiff, status("Reading image …") as current_status:
                self._stacktype = 'tiff'
                pages = tiff.pages
                if not pages:
                    raise ValueError(f"Cannot open file '{self._path}': No pages found in TIFF.")

                # Get basic information
                self._n_images = len(pages)
                page0 = pages[0]
                self._width = page0.imagewidth
                self._height = page0.imagelength
                self._mode = self.dtype_str(page0.dtype)

                # Get software-specific information
                description = page0.description
                if page0.is_imagej:
                    self._parse_imagej_tags(description)
                elif tiff.is_ome:
                    self._parse_ome(tiff.ome_metadata)
                else:
                    # If TIFF type is not known, show as 1D stack
                    print("Unknown image type.")
                    self._n_channels = 1
                    self._n_frames = self._n_images

                self.img = np.zeros(dtype=page0.dtype,
                                    shape=(self._n_channels,
                                           self._n_frames,
                                           self._height,
                                           self._width))
                for i in range(self._n_images):
                    current_status.reset("Reading image", current=i+1, total=self._n_images)
                    ch, fr = self.convert_position(image=i)
                    self.img[ch, fr, :, :] = pages[i].asarray()

        except Exception as e:
            self._clear_state()
            print(str(e))
            raise

        finally:
            self._listeners.notify("image")

    def _load_hdf5(self, status=None, h5_key=None, channels=None):
        """Note: Currently only ilastik HDF5 is supported"""
        if status is None:
            status = DummyStatus()
        try:
            with self.image_lock, h5py.File(self._path, 'r') as h5, status("Reading stack …") as current_status:
                self._stacktype = 'hdf5'
                if h5_key is not None:
                    key = h5_key
                else:
                    keys = list(h5.keys())
                    if len(keys) != 1:
                        raise ValueError("Cannot infer HDF5 key of dataset")
                    else:
                        key = next(iter(keys))
                data5 = h5[key]

                try:
                    ax5 = json.loads(h5.attrs['axistags'])['axes']
                    idx = {item['key']: pos for pos, item in enumerate(ax5)}
                except KeyError:
                    # Assume order 'tyxc'
                    idx = dict(t=0, y=1, x=2, c=3)
                    if data5.ndim < 4:
                        del idx['c']
                    if data5.ndim < 3:
                        del idx['t']
                        for k in idx.keys():
                            idx[k] -= 1
                self._height = data5.shape[idx['y']]
                self._width = data5.shape[idx['x']]
                self._mode = self.dtype_str(data5.dtype)
                if idx.get('t') is None:
                    self._n_frames = 1
                else:
                    self._n_frames = data5.shape[idx['t']]
                try:
                    self._n_channels = data5.shape[idx['c']]
                except KeyError:
                    self._n_channels = 1
                    channels = (None,)
                else:
                    if channels is None:
                        channels = range(self._n_channels)
                    elif isinstance(channels, slice):
                        channels = range(*channels.indices(self._n_channels))
                        self._n_channels = len(channels)
                    elif isinstance(channels, range):
                        self._n_channels = len(channels)
                    else:
                        channels = np.ravel(channels)
                        self._n_channels = channels.size
                self._n_images = self._n_frames * self._n_channels

                self.img = np.zeros(dtype=data5.dtype,
                                    shape=(self._n_channels,
                                           self._n_frames,
                                           self._height,
                                           self._width))
                i = np.zeros(len(idx), dtype=object)
                for dim in 'xy':
                    i[idx[dim]] = slice(None)
                for fr in range(self._n_frames):
                    if 't' in idx:
                        i[idx['t']] = fr
                    for ch, orig_ch in enumerate(channels):
                        if 'c' in idx:
                            i[idx['c']] = orig_ch
                        current_status.reset("Reading image",
                                current=1 + ch + fr * self._n_channels,
                                total=self._n_images)
                        self.img[ch, fr, :, :] = data5[tuple(i)]

        except Exception as e:
            self._clear_state()
            print(str(e))
            raise

        finally:
            self._listeners.notify("image")

    def close(self):
        """Close the stack and release associated resources (the in-memory array)."""
        # _clear_state() handles setting self.img to None.
        self._clear_state()

    def __del__(self):
        self.close()

    def crop(self, *, top=0, bottom=0, left=0, right=0):
        """Crop image with specified margins"""
        new_height = self._height - (top + bottom)
        new_width = self._width - (left + right)
        if new_height < 0 or new_width < 0:
            raise ValueError("Margins are larger than image")
        if bottom == 0:
            bottom = self._height
        else:
            bottom = -bottom
        if right == 0:
            right = self._width
        else:
            right = -right
        with self.image_lock:
            try:
                new_img = np.zeros(dtype=self.img.dtype,
                                   shape=(self._n_channels,
                                          self._n_frames,
                                          new_height,
                                          new_width))
                new_img[:, :, :, :] = self.img[:, :, top:bottom, left:right]
            except Exception:
                # new_tempfile.close() # No longer needed
                raise
            
            # self.img is already an in-memory array, direct assignment is fine.
            # Old memmap-specific cleanup is not needed.
            self.img = new_img
            self._width = new_width
            self._height = new_height
            # try: # Remove old tempfile logic
            #     self._tmpfile.close()
            # except Exception:
            #     pass
            # self._tmpfile = new_tempfile # Remove old tempfile logic
        self._listeners.notify("image")


    def _parse_imagej_tags(self, desc):
        """Read stack dimensions from ImageJ's TIFF description tag."""
        #TODO: use tiff.imagej_metadata instead of page0.description
        # Set dimension order
        self._order = "tc"

        # Get number of frames in stack
        m = re.search(r"frames=(\d+)", desc)
        if m:
            self._n_frames = int(m.group(1))
        else:
            self._n_frames = 1

        # Get number of slices in stack
        m = re.search(r"slices=(\d+)", desc)
        if m:
            n_slices = int(m.group(1))
            if self._n_frames == 1 and n_slices > 1:
                self._n_frames = n_slices
            elif self._n_frames > 1:
                raise ValueError("Bad image format: multiple slices and frames detected.")

        # Get number of channels in stack
        m = re.search(r"channels=(\d+)", desc)
        if m:
            self._n_channels = int(m.group(1))
        else:
            self._n_channels = 1


    def _parse_ome(self, ome):
        n_frames, n_channels, dim_order = parse_ome(ome, self._n_images)

        # Write image size
        self._n_frames = n_frames
        self._n_channels = n_channels

        idx_C = dim_order.find('C')
        idx_T = dim_order.find('T')
        if idx_C == -1 or idx_T == -1:
            raise ValueError("Bad 'DimensionOrder' value in OME description.")
        if idx_C < idx_T:
            self._order = 'tc'
        else:
            self._order = 'ct'


    def convert_position(self, channel=None, frame=None, image=None):
        """
        Convert stack position between (channel, frame) and image.

        Either give "channel" and "frame" to obtain the corresponding
        image index, or give "image" to obtain the corresponding indices
        of channel and frame as tuple.
        All other combinations will return None.
        """
        # Check arguments
        if channel is None and frame is None:
            to2 = True
        elif channel is None or frame is None:
            return None
        else:
            to2 = False
        if image is None and to2:
            return None

        # Convert
        with self.image_lock:
            if self._order is None:
                return None

            elif self._order == "tc": # 11,12,13,21,22,23,31,32,33,41,42,43 (t=4, c=3)
                if to2:
                    channel = image % self._n_channels # 0,1,2,0,1,2,0,1,2,0,1,2
                    frame = image // self._n_channels # 0,0,0,1,1,1,2,2,2,3,3,3
                    return (channel, frame)
                else:
                    image = frame * self._n_channels + channel
                    return image

            elif self._order == "ct": # 11,21,31,41,12,22,32,42,13,23,33,43 (t=4, c=3)
                if to2:
                    channel = image // self._n_frames # 0,1,2,3,0,1,2,3,0,1,2,3
                    frame = image % self._n_frames # 0,0,0,0,1,1,1,1,2,2,2,2
                    return (channel, frame)
                else:
                    image = channel * self._n_frames + frame
                    return image

            else:
                raise NotImplementedError(f"Dimension order '{self._order}' not implemented yet.")

    def get_image(self, channel, frame):
        """Get a numpy array of a stack position."""
        with self.image_lock:
            return self.img[channel, frame, :, :]

    def get_image_copy(self, channel, frame):
        """Get a copy of a numpy array of a stack position."""
        with self.image_lock:
            return self.img[channel, frame, :, :].copy()

    def get_frame_tk(self, channel, frame, convert_fcn=None):
        """
        Get a frame of the stack as :py:class:`tkinter.PhotoImage`.

        :param channel: The channel of the requested stack position
        :type channel: int
        :param frame: The frame of the requested stack position
        :type frame: int
        :param convert_fcn: Custom conversion function
        :type convert_fcn: None or function

        If a custom conversion function is given, the function must take
        one argument, which is a (n_rows, n_columns)-shaped numpy array
        of the current stack position with the bit-depth of the original
        image (typically 8 or 16 bit per pixel), and must return
        a (n_rows, n_columns)-shaped numpy array of ``uint8`` type.

        :return: the image at the requested stack position
        :rtype: :py:class:`tkinter.PhotoImage`
        """
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

    def clear_info(self):
        """Clear the image information"""
        with self.info_lock:
            self._info = {}

    def update_info(self, name, value):
        with self.info_lock:
            self._info[name] = value

    def get_info(self, name):
        with self.info_lock:
            return self._info.get(name)

    def stack_info(self):
        """Print stack info for DEBUGging."""
        with self.image_lock:
            print("Path: " + str(self._path))
            print("width: " + str(self._width))
            print("height: " + str(self._height))
            print("n_images: " + str(self._n_images))
            print("n_channels: " + str(self._n_channels))
            print("n_frames: " + str(self._n_frames))

    def add_listener(self, fun, kind=None):
        """Register a listener to stack changes."""
        return self._listeners.register(fun, kind)

    def delete_listener(self, lid):
        """Un-register a listener."""
        self._listeners.delete(lid)

    def _notify_roi_listeners(self, *_, **__):
        """Convenience function for propagation of ROI changes"""
        self._listeners.notify("roi")

    def new_roi_collection(self, roi):
        """Create a new RoiCollection"""
        if isinstance(roi, RoiCollection):
            with self.roi_lock:
                roi.register_listener(self._notify_roi_listeners)
                self.__rois[roi.key] = roi
        else:
            raise TypeError(f"Expected 'RoiCollection', got '{type(roi)}'")

    def set_rois(self, rois, key=None, frame=Ellipsis, replace=False):
        """Set the ROI set of the stack.

        :param rois: The ROIs to be set
        :type rois: iterable of Roi
        :param frame: index of the frame to which the ROI belongs.
            Use ``Ellipsis`` to specify ROIs valid in all frames.
        :type frame: int or Ellipsis

        For details, see :py:class:`RoiCollection`.
        """
        # Infer ROI type key
        if key is None:
            for r in rois:
                key = r.key()
                break

        with self.roi_lock:
            if key not in self.__rois:
                self.__rois[key] = RoiCollection(key)
                self.__rois[key].register_listener(self._notify_roi_listeners)
            if replace:
                self.__rois[key][frame] = rois
            else:
                self.__rois[key].add(frame, rois)

    def print_rois(self):
        """Nice printout of ROIs. Only for DEBUGging."""
        prefix = "[Stack.print_rois]"
        for k, v in self.__rois.items():
            print(f"{prefix} ROI type '{k}' has {len(v)} frame(s)")
            for frame, rois in v.items():
                print(f"{prefix}\t frame '{frame}' has {len(rois)} ROIs")
                # print(rois) # DEBUG

    @property
    def rois(self):
        with self.roi_lock:
            return self.__rois

    def get_rois(self, key=None, frame=None):
        """Get ROIs, optionally at a specified position.

        :param key: ROI type identifier
        :type key: tuple (len 2) of str
        :param frame: frame identifier
        :return: ROI set
        """
        with self.roi_lock:
            rois = self.__rois.get(key)
            if rois is not None and frame is not None:
                return rois[frame]
            return rois

    def clear_rois(self, key=None, frame=None):
        """Delete the current ROI set"""
        with self.roi_lock:
            if key is None:
                self.__rois = {}
            elif frame is None:
                del self.__rois[key]
            else:
                del self.__rois[key][frame]
            self._notify_roi_listeners()

    @property
    def path(self):
        with self.image_lock:
            return self._path

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
