#! /usr/bin/env python3
"""Read and write ImageJ Roi files.
For file syntax, see:
https://github.com/imagej/imagej1/blob/master/ij/io/RoiDecoder.java
"""
import codecs
from contextlib import ExitStack
from collections import OrderedDict
import os
import struct
import zipfile as zf
import numpy as np

# Constants
TARGET_VERSION = 227
HEADER1_SIZE = 64
HEADER2_SIZE = 64

# Offsets
# Header 1
IOUT = 0
VERSION = 4
TYPE = 6
TOP = 8
LEFT = 10
BOTTOM = 12
RIGHT = 14
N_COORDINATES = 16
COORDINATES = 64
HEADER2_OFFSET = 60

# Header 2
T_POSITION = 12
NAME_OFFSET = 16
NAME_LENGTH = 20

# Roi types
TYPE_POLYGON = 0
TYPE_RECT = 1
TYPE_FREEHAND = 7

def to_int(b):
    return int.from_bytes(b, byteorder='big', signed=True)

def read_int(b, i, size=2):
    """Read an integer from bytearray.

b -- bytearray
i -- starting index
size -- number of bytes to read
    """
    return int.from_bytes(b[i:i+size], byteorder='big', signed=True)

def write_int(b, pos, i, size=2):
    """Write an integer into bytearray.

b -- bytearray
pos -- position (starting index) of writing
i -- integer to be written
size -- number of bytes of converted integer

The bytearray is changed inplace.
Nothing is returned.
    """
    x = i.to_bytes(size, byteorder='big', signed=True)
    b[pos:pos+len(x)] = x

def write_val(b, off, *arr, dtype='h', size=None):
    """Write a numpy array into a buffer

b -- buffer (e.g. bytearray, memoryview)
off -- offset in buffer
arr -- values to be written
dtype -- format to write as defined by `struct` module
size -- bit-width for signed integer

Formats for typical (signed) integer bitwidths are:
b -- 1 byte
h -- 2 bytes
i -- 4 bytes
q -- 8 bytes
Use a capital letter for the corresponding unsigned data type.
Formats for floating point data types:
f -- 4 bytes
d -- 8 bytes
If `size` is given, the value of `dtype` is ignored and an
signed integer data type with `size` bytes is used.
    """
    if size is not None:
        if size == 1:
            dtype = 'b'
        elif size == 2:
            dtype = 'h'
        elif size == 4:
            dtype = 'i'
        elif size == 8:
            dtype = 'q'
        else:
            raise ValueError(f"Invalid value for 'size': {size.__repr__()}")
    struct.pack_into(f'>{len(arr)}{dtype}', b, off, *arr)

def iter_bytes(b):
    """Iterator over bytes in bytes-like `b`"""
    for x in b:
        yield x.to_bytes(1, 'big')

def decode_str(data, length):
    """Extract a string of given length from bytearray

Arguments:
data -- bytes-like object starting with a UTF-16-BE encoded string
length -- the number of code points in the string

Returns:
the extracted string
    """
    res = []
    it = codecs.iterdecode(iter_bytes(data), encoding='utf_16_be')
    while length > 0:
        res.append(next(it))
        length -= 1
    return ''.join(res)


class Roi:
    def __init__(self, coords=None, type_=None, name=None, frame=None):
        self._coords = None
        if coords is not None:
            self.coords = coords
        self._type = None
        if type_ is not None:
            self.type = type_
        self.name = name
        self.frame = frame

    @property
    def coords(self):
        return self._coords

    @coords.setter
    def coords(self, coords):
        if coords is None:
            self._coords = None
        elif coords.ndim != 2 or coords.shape[1] != 2:
            raise ValueError(f"'coords' must have shape (n, 2), found shape {tuple(coords.shape)}")
        self._coords = coords

    @property
    def n_coords(self):
        if self.coords is None:
            return None
        else:
            return self.coords.shape[0]

    @property
    def rows(self):
        if self.coords is None:
            return None
        return self.coords[:,0]

    @property
    def cols(self):
        if self.coords is None:
            return None
        return self.coords[:,1]

    @property
    def bbox(self):
        if self.coords is None:
            return None
        bb = OrderedDict()
        bb['top'] = self.coords[:,0].min()
        bb['bottom'] = self.coords[:,0].max()
        bb['left'] = self.coords[:,1].min()
        bb['right'] = self.coords[:,1].max()
        return bb

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, t):
        if t in (TYPE_RECT, TYPE_POLYGON, TYPE_FREEHAND):
            self._type = t
        elif t == 'rect':
            self._type = TYPE_RECT
        elif t == 'polygon':
            self._type = TYPE_POLYGON
        elif t == 'freehand':
            self._type = TYPE_FREEHAND
        else:
            raise ValueError(f"Unknown ROI type '{t}'")

    @classmethod
    def read(cls, f):
        """Create a new Roi object.

`f` must either be the path of a .roi file as string
or its content as a bytes object.

The created Roi object is returned.
        """
        # Read .roi file
        if isinstance(f, str):
            with open(f, 'rb') as f_:
                f = f_.read()

        # Check for file type and version
        if f[:4].decode('ascii') != 'Iout':
            raise ValueError("Bad file format")
        version = read_int(f, VERSION)
        if version != TARGET_VERSION:
            print(f"Expected version {TARGET_VERSION}, found {version}. "
                    "Import may fail.")

        # Read metadata
        type_ = read_int(f, TYPE, size=1)
        top = read_int(f, TOP)
        left = read_int(f, LEFT)
        bottom = read_int(f, BOTTOM)
        right = read_int(f, RIGHT)
        n_coords = read_int(f, N_COORDINATES)
        offset_header2 = read_int(f, HEADER2_OFFSET, size=4)

        # Read coordinates (depending on Roi type)
        if type_ == TYPE_RECT:
            n_coords = 4
            coords = np.empty((4, 2), dtype=np.int16)
            coords[(0, -1),0] = left
            coords[1:3,0] = right
            coords[:2,1] = top
            coords[-2:,1] = bottom

        elif n_coords == 0:
            raise NotImplementedError(f"ROI type {type_} not supported")

        else:
            coords = np.empty((n_coords, 2), dtype=np.int16)
            for i in range(0, n_coords):
                ix = COORDINATES + 2 * i
                iy = ix + 2 * n_coords
                coords[i, 1] = read_int(f, ix)
                coords[i, 0] = read_int(f, iy)
            coords += np.array([[top, left]], dtype=np.int16)

        # Read header 2
        with memoryview(f) as vf, vf[offset_header2:] as hdr2:
            frame = read_int(hdr2, T_POSITION, size=4)
            if frame:
                frame -= 1
            else:
                frame = None
            name_off = read_int(hdr2, NAME_OFFSET, size=4)
            name_len = read_int(hdr2, NAME_LENGTH, size=4)

        # Get Roi name
        if name_len:
            with memoryview(f) as v:
                name = decode_str(v[name_off:], name_len)
        else:
            name = None

        # Create and return Roi object
        return cls(type_=type_,
                   coords=coords,
                   name=name,
                   frame=frame,
                  )

    @classmethod
    def read_multi(cls, fn, as_dict=True):
        """Load multiple Roi objects.

`fn` is a path name of a file holding Roi information.
'.roi' and '.zip' files are allowed.
If `fn` is a file-like object, only opened ZIP files are allowed.
If `as_dict` is false (default), a list of the
loaded Roi objects is returned.
If `as_dict` is true, the Roi objects are returned as
dictionary with the Roi names as keys.
        """
        rois = []
        with ExitStack() as es:
            if isinstance(fn, str):
                ext = os.path.splitext(fn)[-1]
                if ext == '.roi':
                    rois.append(cls.read(fn))
                    z is None
                elif ext == '.zip':
                    z = es.enter_context(zf.ZipFile(fn, 'r'))
                else:
                    raise ValueError("Invalid file type '{}'".format(ext))
            else:
                z = fn
            if z is not None:
                names = z.namelist()
                for name in names:
                    if os.path.splitext(name)[-1] != '.roi':
                        continue
                    rois.append(cls.read(z.read(name)))
        if as_dict:
            return {r.name: r for r in rois}
        else:
            return rois

    def write(self, out=None):
        """Write the ROI in ImageJ format

Arguments:
out -- buffer or string of file path

The ROI is written to `out`, if given.
Else, a bytearray with the ROI is returned.
        """
        # Check data for validity
        if self.coords is None:
            raise ValueError("No coordinates assigned")
        if self._type is None:
            raise ValueError("No Roi type specified")

        # Check ROI properties with influence on file size
        if self._type == TYPE_RECT:
            n_coordinates = 0
        else:
            n_coordinates = self._coords.shape[0]

        if self.name is not None:
            name_len = len(self.name)
            name = self.name.encode(encoding='utf_16_be')
            name_bin_len = len(name)
        else:
            name_len = 0
            name_bin_len = 0

        # Allocate memory for ROI
        roi = bytearray(HEADER1_SIZE + 4 * n_coordinates + HEADER2_SIZE + name_bin_len)

        # Populate header 1
        roi[IOUT:4] = b'Iout'
        write_int(roi, VERSION, TARGET_VERSION)
        write_int(roi, TYPE, self._type, size=1)

        write_val(roi, TOP, self.coords[:,0].min())
        write_val(roi, LEFT, self.coords[:,1].min())
        write_val(roi, BOTTOM, self.coords[:,0].max())
        write_val(roi, RIGHT, self.coords[:,1].max())

        hdr2_off = HEADER1_SIZE + 4 * n_coordinates
        write_int(roi, HEADER2_OFFSET, hdr2_off, size=4)

        # Write coordinates
        if n_coordinates:
            write_int(roi, N_COORDINATES, n_coordinates)
            write_val(roi, HEADER1_SIZE,
                      *self._coords[:, 1] - self._coords[:, 1].min(),
                      *self._coords[:, 0] - self._coords[:, 0].min())

        # Populate header 2
        with memoryview(roi) as vroi, vroi[hdr2_off:hdr2_off+HEADER2_SIZE] as hdr2:
            if self.frame is not None:
                write_int(hdr2, T_POSITION, self.frame + 1, size=4)
            if name_len:
                name_off = hdr2_off + HEADER2_SIZE
                write_int(hdr2, NAME_OFFSET, name_off, size=4)
                write_int(hdr2, NAME_LENGTH, name_len, size=4)

        # Write name
        if name_len:
            roi[name_off:name_off+name_bin_len] = name

        # Write to file/buffer
        if out is None:
            return roi
        with ExitStack() as stack:
            if isinstance(out, str):
                f = stack.enter_context(open(out, 'bw'))
            f.write(roi)

    @classmethod
    def write_multi(cls, out=None, rois=()):
        """Write multiple ROIs

Arguments:
out -- target to write the targets. Either str giving the
file path or a binary buffer of a ZIP file

Arguments:
out -- target to write the targets. Either str giving the
file path or a writable binary buffer of a ZIP file.
If None, return a list of ROIs.
rois -- Iterable of Roi instances to write.
Returns:
If out is None, return dict of formatted ROIs.
        """
        if out is None:
            return {roi.name: roi.write() for roi in rois}

        with ExitStack() as stack:
            if isinstance(out, str):
                zipped = stack.enter_context(zf.ZipFile(out, mode='w', compression=zf.ZIP_DEFLATED))
            else:
                zipped = out
            for roi in rois:
                zipped.writestr(f"{roi.name}.roi", roi.write())

    def __str__(self):
        s = []
        p = "    "
        s.append("ROI '{}'".format(self.name))
        if self._type == TYPE_POLYGON:
            type_ = "polygon"
        elif self._type == TYPE_RECT:
            type_ = "rect"
        elif self._type == TYPE_FREEHAND:
            type_ = "freehand"
        else:
            type_ = "{} (not implemented)".format(self._type)
        s.append("{}{:13s} {}".format(p, "Type:", type_))
        s.append("{}{:13s} {}".format(p, "Frame:", self.frame))
        s.append("{}{:13s} {}".format(p, "#Points:", self.n_coords))
        s.append("{}{:13s}".format(p, "Bounding box:"))
        bbox = self.bbox
        s.append("{}{}{:7s} {:4d}".format(p, p, "Top:", bbox['top']))
        s.append("{}{}{:7s} {:4d}".format(p, p, "Left:", bbox['left']))
        s.append("{}{}{:7s} {:4d}".format(p, p, "Bottom:", bbox['bottom']))
        s.append("{}{}{:7s} {:4d}".format(p, p, "Right:", bbox['right']))
        s.append("{}{:13s}".format(p, "Coordinates:"))
        if self.coords is None:
            s.append("{}{}<None>".format(p, p))
        else:
            s.append("{}{}{:>5s} {:>5s}".format(p, p, "x", "y"))
            for coord in self.coords:
                s.append("{}{}{:5d} {:5d}".format(p, p, *coord))
        s.append("")
        return "\n".join(s)

    def asarray(self, dtype=None, val=1, shape=None):
        """Return the Roi as a binary array.

Arguments:
dtype -- the desired dtype of the returned array (default: np.bool_)
val -- the value of pixels indicating the Roi (default: 1)
shape -- the desired shape of the returned array (default: largest coordinates + 1)
        """
        import skimage.draw as skd
        if self.coords is None:
            return None
        if dtype is None:
            dtype = np.bool_
        if shape is None:
            shape = (bbox['bottom'] + 1, bbox['right'] + 1)
        bbox = self.bbox
        arr = np.zeros(shape, dtype=dtype)
        if self._type == TYPE_RECT:
            rr, cc = skd.rectangle(start=(bbox['top'], bbox['left']), end=(bbox['bottom'], bbox['right']), shape=shape)
        elif self._type in (TYPE_POLYGON, TYPE_FREEHAND):
            rr, cc = skd.polygon(self.rows, self.cols, shape=shape)
        else:
            raise NotImplementedError(f"Array conversion for ROI type '{self._type}' is not implemented.")
        arr[rr, cc] = val
        return arr

    def astiff(self, fn=None, shape=None):
        """Return a TIFF file illustrating the Roi.

Arguments:
fn -- a file name (default: <Roi.name>.tiff)
shape -- shape of the TIFF file (default: see Roi.asarray)
Returns:
file name of the TIFF file as str
        """
        import tifffile
        if fn is None:
            fn = '.'.join((self.name, 'tiff'))
        arr = self.asarray(dtype=np.uint8, val=255, shape=shape)
        tifffile.imwrite(fn, arr)
        return fn


if __name__ == '__main__':
    import sys
    fn = sys.argv[1]
    rois = Roi.read_multi(fn)
    for roi in rois:
        print(roi)
