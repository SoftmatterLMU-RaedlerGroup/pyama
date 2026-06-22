import base64
from contextlib import ExitStack
import io
import json
import math
import os
import re
import struct
import zipfile

import numpy as np
import skimage.draw as skd

from .roi import Roi
from ..roi import ContourRoi
from ..session.status import DummyStatus

ZIP_JSON_NAME = 'session.json'

def get_format(fmt):
    """Get format properties for binary data.

    `fmt` is a format character of the package `struct`.
    Note that the following characters are not allowed:
    x, ?, n, N, s, p, P

    The corresponding numpy dtype is returned.
    The number of bytes required per value can be
    accessed with the attribute `itemsize`.
    """
    if fmt in 'cb':
        return np.int8, 1
    elif fmt == 'B':
        return np.uint8, 1
    elif fmt == 'h':
        return np.int16, 2
    elif fmt == 'H':
        return np.uint16, 2
    elif fmt in 'il':
        return np.int32, 4
    elif fmt in 'IL':
        return np.uint32, 4
    elif fmt == 'q':
        return np.int64, 8
    elif fmt == 'Q':
        return np.uint64, 8
    elif fmt == 'e':
        return np.float16, 2
    elif fmt == 'f':
        return np.float32, 4
    elif fmt == 'd':
        return np.float64, 8
    else:
        raise ValueError(f"Undefined format character '{fmt}'")


class StackdataIO:
    """Provides an interface for standardized export and import of stack data.

    Arguments:
        traces -- traces such as Main_Tk.traces
        rois -- ROIs such as Main_Tk.rois
        status -- status instance for displaying loading progress

    In addition to traces and ROIs, which may be inserted using the constructor or
    the methods `load_traces` (all traces) / `insert_trace` (one trace) and `load_rois`
    (all ROIs) / `insert_roi` (single ROI), also the following fields should be filled:
        `n_frames`: number of frames in the stack
        `channels`: information about channels, to be added with the method `add_channel`
        `microscope_name`: display name of the used microscope
        `microscope_resolution`: resolution of the microscope, float value in [µm/px]

    When all fields are filled, the data can be written with the method `dump`.
    """
    def __init__(self, traces=None, rois=None, status=None):
        self.version = '1.0'
        self.microscope_name = None
        self.microscope_resolution = None
        self.n_frames = None
        self.rois = None
        self.channels = []
        self.traces = None
        if status is None:
            self.status = DummyStatus()
        else:
            self.status = status

        if traces is not None:
            self.load_traces(traces)
        if rois is not None:
            self.load_rois(rois)

    def add_channel(self, path, type_, i_channel=0, name=None, label=None):
        """Insert information about a new channel.

        Arguments:
            path -- str, path of the stack containing the channel, may be used for re-opening the stack
            type_ -- str, type of the channel, one of MetaStack.TYPE_{FLUORESCENCE,PHASECONTRAST,SEGMENTATION}
            i_channel -- int, index of the channel in the MetaStack
            name -- str, name of the stack containing the channel
            label -- str, additional label describing the channel
        """
        if path is None:
            file_directory = None
            file_name = None
        else:
            file_directory, file_name = os.path.split(path)
        self.channels.append({
                              'file_name': file_name,
                              'file_directory': file_directory,
                              'i_channel': i_channel,
                              'type': type_,
                              'name': name,
                              'label': label,
                             })

    def load_rois(self, rois):
        """Loads the given ROIS"""
        for fr, rois_frame in enumerate(rois):
            for label, roi in rois_frame.items():
                self.insert_roi(roi, frame=fr, label=label)
                
    def insert_roi(self, roi, frame=None, label=None):
        """Inserts a ROI.

        Arguments:
            roi -- the ContourRoi instance
            frame -- int, the 0-based index of the frame the ROI belongs to
            label -- int, the label of the ROI
        """
        if self.rois is None:
            self.rois = []
        while frame >= len(self.rois):
            self.rois.append({})
        if frame is None:
            frame = roi.frame
        if label is None:
            label = roi.label
        self.rois[frame][label] = roi

    def load_traces(self, traces):
        """Loads the given traces"""
        for name, tr in traces.items():
            self.insert_trace(name, tr['roi'], tr['select'])

    def insert_trace(self, name, rois, is_selected=True):
        """Inserts a trace/cell.

        Arguments:
            name -- str, name of the trace/cell, e.g. based on its position in the image
            rois -- list of str, indicating the ROIs of the cell in all frames
            is_selected -- bool, indicating whether the trace/cell is selected
        """
        if self.traces is None:
            self.traces = []
        self.traces.append({
                            'name': name,
                            'select': is_selected,
                            'rois': rois, # list of `n_frames` roi labels
                           })

    def dump(self, *out):
        """Write the stack data to JSON.

        If `out` is a str or file-like object, the session data and ROIs are written there.
        If `out` is None, a tuple (session data, ROIs) is returned.

        The session data is JSON formatted, the ROIs are in ImageJ ROI format.
        """
        if self.n_frames is None:
            raise ValueError("Number of frames is not given.")
        elif self.rois is None:
            raise ValueError("ROIs are not defined.")
        elif not self.channels:
            raise ValueError("No channels are given.")
        elif len(self.rois) != self.n_frames:
            raise ValueError("Number of frames with ROIs is inconsistent")

        # Convert ROI names to avoid duplicates and create ROI dict
        roi_dict = {}
        roi_name_conversion = []
        for rois in self.rois:
            conv = {}
            for label, roi in rois.items():
                new_name =  self._unique_roi_name(roi)
                conv[label] = new_name
                roi_dict[new_name] = Roi(
                                         coords=roi.perimeter,
                                         type_='polygon',
                                         name=new_name,
                                         frame=roi.frame,
                                        )
            roi_name_conversion.append(conv)
        for trace in self.traces:
            trace['rois'] = [roi_name_conversion[fr][roi] for fr, roi in enumerate(trace['rois'])]

        # Create metadata content (will be written in JSON format)
        data = {'version': self.version,
                'n_frames': self.n_frames,
                'channels': self.channels,
                'microscope': {'name': self.microscope_name,
                               'resolution': self.microscope_resolution,
                              },
                'cells': self.traces,
               }
        json_args = {'indent': '\t'}

        # Write data to ZIP file
        if not out:
            return roi_dict, json.dumps(data, **json_args)
        with ExitStack() as es:
            if len(out) > 1 or isinstance(out[0], str):
                zf = es.enter_context(zipfile.ZipFile(os.path.join(*out), 'w', compression=zipfile.ZIP_DEFLATED))
            else:
                zf = out.pop()
            Roi.write_multi(zf, roi_dict.values())
            with io.TextIOWrapper(
                    es.enter_context(zf.open(ZIP_JSON_NAME, 'w')),
                    encoding='utf8', newline='\n', write_through=True) as jf:
                json.dump(data, jf, **json_args)

    def load(self, fin=None, s=None, rois=None):
        """Loads stack information and ROI information from JSON

        Arguments:
            fin -- file-like or str holding a filename of ZIP file to be read
            s -- string holding JSON data
            rois -- list of dicts, holding ContourRoi instances

        If `fin` is given, `s` and `rois` are ignored.
        `fin` should be a ZIP file containing a file named 'session.json' that holds
        the session information, and '*.roi' files that hold the ROI information
        in ImageJ ROI format.
        Note that if `rois` is given, the ROI labels must comply with the
        cell-to-ROI assignment in `s`.

        The content of the ZIP file is loaded and can be accessed
        via the fields of this object.
        """
        if fin is not None:
            with ExitStack() as es, self.status("Loading session information"):
                if isinstance(fin, str):
                    zf = es.enter_context(zipfile.ZipFile(fin))
                else:
                    zf = fin
                with zf.open(ZIP_JSON_NAME) as f:
                    data = json.loads(io.TextIOWrapper(f, encoding='utf8').read())
                rois_raw = Roi.read_multi(zf)
                self.rois = None
        elif s is not None:
            data = json.loads(s)
            if rois is not None:
                self.rois = rois
        else:
            raise ValueError("Either file or string must be given.")

        with self.status("Importing session …") as current_status:
            self.version = data['version']
            self.n_frames = data['n_frames']
            self.channels = data['channels']
            self.microscope_name = data['microscope']['name']
            self.microscope_resolution = data['microscope']['resolution']
            self.traces = data['cells']
            if self.rois is None:
                self.rois = []
                label_conversion = []
                n_rois = len(rois_raw)
                i_rr = 1
                for rr in rois_raw.values():
                    current_status.reset("Importing ROIs", current=i_rr, total=n_rois)
                    i_rr += 1
                    info = self.parse_roi_name(rr.name)
                    fr = rr.frame
                    if not fr:
                        fr = info['frame']
                    label = info['label']
                    if label is None:
                        label = rr.name
                    if label is None:
                        label = i_rr
                    poly_rr, poly_cc = skd.polygon(rr.rows, rr.cols)
                    coords = np.empty((len(poly_rr), 2), dtype=np.uint16)
                    coords[:,0] = poly_rr
                    coords[:,1] = poly_cc
                    roi = ContourRoi(label=label, coords=coords, name=info['cell'], frame=fr)

                    while fr >= len(self.rois):
                        self.rois.append({})
                    self.rois[fr][label] = roi
                    while fr >= len(label_conversion):
                        label_conversion.append({})
                    label_conversion[fr][rr.name] = label

            current_status.reset("Assigning ROIs to traces …")
            for cell in self.traces:
                name = cell['name']
                roi_list = cell['rois']
                for fr, roi_ref in enumerate(roi_list):
                    nl = label_conversion[fr][roi_ref]
                    roi_list[fr] = nl
                    self.rois[fr][nl].name = name

    def _unique_roi_name(self, roi):
        """Build a ROI name unique throughout the whole stack.

        The name has the format:
            cNAME_tFRAME_lLABEL
        wherein NAME is the name of the cell the ROI belongs to,
        FRAME is the frame number of the ROI (one-based, possibly with leading '0's),
        and LABEL is the numerical label assigned to this ROI
        by skimage.measure.label.
        If the ROI does not belong to a cell, the part 'cNAME' is
        left away, and the returned ROI name starts with an underscore.
        """
        if isinstance(roi.label, str):
            return roi.label
        len_fr = math.floor(math.log10(self.n_frames)) + 1
        if roi.name:
            namestr = f"c{roi.name}"
        else:
            namestr = ""
        return f"{namestr}_t{roi.frame+1 :0{len_fr}d}_l{roi.label}"

    @staticmethod
    def parse_roi_name(name):
        """Parse the ROI name generated wth _unique_roi_name

        Returns a dict with the fields 'cell', 'frame', 'label',
        any of which may point to None.
        """
        info = dict(cell=None, frame=None, label=None)
        m = re.fullmatch(r"(?:c(?P<cell>.+))?_t(?P<frame>\d+)_l(?P<label>\d+)", name)
        if m is not None:
            if m.group('cell'):
                info['cell'] = m.group('cell')
            if m.group('frame'):
                info['frame'] = int(m.group('frame')) - 1
            if m.group('label'):
                info['label'] = int(m.group('label'))
        return info

    @staticmethod
    def to_list64(arr, fmt='<H'):
        """Write array content to base64.

        Arguments:
            arr -- the numpy-array to encode
            fmt -- the format for byte conversion

        The flattened `arr` is converted to a bytes holding a sequence of numbers
        encoded according to `fmt`. `fmt` must be a two-element str, wherein the
        first element indicates the endianness and the second element indicates
        a byte length and sign. See the `struct` package for possible options.

        The resulting bytes object is prepended with fmt and returned as string.
        """
        data = b''.join((fmt.encode(), *(struct.pack(fmt, x) for x in arr.flat)))
        return base64.b64encode(data).decode()

    @staticmethod
    def from_list64(data):
        """Read base64-encoded array.

        `data` must be a base64-encoded array in the format described for `to_list64`.
        It is returned as 1-dim numpy array.
        """
        data = base64.b64decode(data)
        fmt = data[:2].decode()
        data = data[2:]
        dtype, itemsize = get_format(fmt[1])
        numel = len(data) // itemsize
        arr = np.empty(numel, dtype=dtype)
        for i in range(numel):
            arr[i] = struct.unpack(fmt, data[i*itemsize:(i+1)*itemsize])[0]
        return arr
