import time

import numpy as np
import skimage.measure as skmeas

from .stack import Stack
from .session.status import DummyStatus

IGNORE_SIZE = 300
MIN_SIZE = 1000
MAX_SIZE = 10000

def intercalation_iterator(n):
    """Generator function for iterating from both ends in `n` steps"""
    n = int(n)
    if n <= 0:
        return
    elif n % 2:
        yield 0
        i1 = n - 1
        step1 = -2
        stop1 = 0
        i2 = 1
        step2 = 2
    else:
        i1 = 0
        step1 = 2
        stop1 = n
        i2 = n - 1
        step2 = -2
    while i1 != stop1:
        yield i1
        yield i2
        i1 += step1
        i2 += step2

def check_coordinate_overlap(coords1, coords2):
    """Performantly check two coordinate sets for overlap

    Arguments:
        Both `coords1` and `coords2` are n-by-2 numpy arrrays.
        Each line cooresponds to one pixel.
        The first column is the vertical coordinate, and
        the second column is the horizontal coordinate.

    Returns:
        True if the coordinate sets overlap, else False.
    """
    uy = np.intersect1d(coords1[:, 0], coords2[:, 0])
    for iy in intercalation_iterator(uy.size):
        y = uy[iy]
        if np.intersect1d(coords1[coords1[:, 0] == y, 1], coords2[coords2[:, 0] == y, 1]).size:
            return True
    return False


class Tracker:
    """Performs tracking in multithreaded fashion.
    
    Constructor arguments:
        segmented_stack -- a Stack with segmented cells
        labeled_stack -- a Stack with each cell having a unique label (per frame)
    In both cases, background is 0.
    Only one of both arguments needs be given.
    The labeled stack can be created using `Tracker.label`.
    """

    def __init__(self, segmented_stack=None, labeled_stack=None, make_labeled_stack=False, ignore_size=IGNORE_SIZE,
            min_size=MIN_SIZE, max_size=MAX_SIZE, preprocessing=None, segmented_chan=None, labeled_chan=None, status=None):
        self.stack_seg = segmented_stack
        if segmented_chan is None:
            self.segmented_chan = 0
        else:
            self.segmented_chan = segmented_chan
        self.stack_lbl = labeled_stack
        if self.stack_lbl is None or labeled_chan is None:
            self.labeled_chan = 0
        else:
            self.labeled_chan = labeled_chan
        if status is None:
            self.status = DummyStatus()
        else:
            self.status = status
        self.min_size = min_size
        self.max_size = max_size
        self.ignore_size = ignore_size
        self.props = None
        self.traces = None
        self.traces_selection = None
        self.make_labeled_stack = make_labeled_stack
        self.preprocessing = preprocessing

        if self.stack_seg is not None:
            self.n_frames = self.stack_seg.n_frames
            self.width = self.stack_seg.width
            self.height = self.stack_seg.height
        elif self.stack_lbl is not None:
            self.n_frames = self.stack_lbl.n_frames
            self.width = self.stack_lbl.width
            self.height = self.stack_lbl.height
        else:
            raise ValueError("At least `segmented_stack` or `labeled_stack` must be given.")

    def label_stack(self):
        if self.stack_lbl is not None:
            return
        self.stack_lbl = Stack(width=self.width,
                               height=self.height,
                               n_frames=self.n_frames,
                               n_channels=1,
                               dtype=np.uint16,
                              )
        for fr in range(self.n_frames):
            with self.status(msg="Labeling frames", current=fr+1, total=self.n_frames):
                self.stack_lbl.img[self.labeled_chan, fr, :, :] = self.label(
                        self.stack_seg.get_image(channel=self.segmented_chan, frame=fr))

    def label(self, img):
        if self.preprocessing is not None:
            img = self.preprocessing(img)
        return skmeas.label(img, connectivity=1)

    def read_regionprops(self):
        self.props = {}
        for fr in range(self.n_frames):
            with self.status(msg="Reading region props", current=fr+1, total=self.n_frames):
                if self.stack_lbl is None:
                    img = self.label(self.stack_seg.get_image(channel=self.segmented_chan, frame=fr))
                else:
                    img = self.stack_lbl.get_image(channel=self.labeled_chan, frame=fr)
                props = skmeas.regionprops(img)
                this_props = {}
                for p in props:
                    this_props[p.label] = p
                self.props[fr] = this_props

    def get_bboxes(self, fr):
        """Build a dictionary with bounding boxes of ROIs in frame `fr`"""
        this_props = self.props[fr]
        n = len(this_props)
        i = 0
        labels = np.empty(n, dtype=object)
        props = np.empty(n, dtype=object)
        y_min = np.empty(n, dtype=np.int32)
        x_min = np.empty(n, dtype=np.int32)
        y_max = np.empty(n, dtype=np.int32)
        x_max = np.empty(n, dtype=np.int32)
        for lbl, p in this_props.items():
            labels[i] = lbl
            props[i] = p
            y_min[i], x_min[i], y_max[i], x_max[i] = p.bbox
            i += 1
        return {
                'n': n,
                'labels': labels,
                'props': props,
                'y_min': y_min,
                'x_min': x_min,
                'y_max': y_max,
                'x_max': x_max,
               }

    def update_bboxes(self, bb, keys):
        """Remove all entries from bboxes instance `bb` that are not in `keys`"""
        idx = np.isin(bb['labels'], keys)
        if np.all(idx):
            return bb
        bb['n'] = np.sum(idx)
        bb['labels'] = bb['labels'][idx]
        bb['props'] = bb['props'][idx]
        bb['y_min'] = bb['y_min'][idx]
        bb['x_min'] = bb['x_min'][idx]
        bb['y_max'] = bb['y_max'][idx]
        bb['x_max'] = bb['x_max'][idx]
        return bb

    def track(self):
        """Track the cells through the stack."""
        # `traces` holds for each cell a list with the labels for each frame.
        # `traces_selection` holds a size-based selection for the elements of `traces` with same indices.
        # `prev_idx` maps the labels of the cells in the last iteration to an index in `traces`.
        traces = []
        traces_selection = []
        prev_checks = {}
        prev_idx = {}

        # Initialization for first frame
        tic0 = time.time() #DEBUG
        with self.status(msg="Tracking cells", current=1, total=self.n_frames):
            tic = time.time() #DEBUG
            new_bbox = self.get_bboxes(0)
            for i in range(new_bbox['n']):
                ck = self._get_trace_checks(new_bbox['props'][i])
                if ck['ignore']:
                    continue
                elif ck['edge']:
                    is_select = None
                elif ck['good']:
                    is_select = True
                else:
                    is_select = False
                lbl = new_bbox['labels'][i]
                prev_checks[lbl] = ck
                prev_idx[lbl] = len(traces)
                traces.append([lbl])
                traces_selection.append(is_select)
        print("Frame 001: {:.4f}s".format(time.time() - tic)) #DEBUG

        # Track further frames
        for fr in range(1, self.n_frames):
            new_checks = {}
            new_idx = {}
            with self.status(msg="Tracking cells", current=fr + 1, total=self.n_frames):
                tic = time.time() #DEBUG

                # Compare bounding boxes
                prev_bbox = self.update_bboxes(new_bbox, (*prev_idx.keys(),))
                new_bbox = self.get_bboxes(fr)
                overlaps = np.logical_and(
                    np.logical_and(
                        new_bbox['y_min'].reshape((-1, 1)) < prev_bbox['y_max'].reshape((1, -1)),
                        new_bbox['y_max'].reshape((-1, 1)) > prev_bbox['y_min'].reshape((1, -1))),
                    np.logical_and(
                        new_bbox['x_min'].reshape((-1, 1)) < prev_bbox['x_max'].reshape((1, -1)),
                        new_bbox['x_max'].reshape((-1, 1)) > prev_bbox['x_min'].reshape((1, -1))))

                for i in range(overlaps.shape[0]):
                    js = np.flatnonzero(overlaps[i,:])

                    # Continue if ROI has no parent
                    if js.size == 0:
                        continue

                    li = new_bbox['labels'][i]
                    pi = new_bbox['props'][i]
                    ci = pi.coords

                    cki = self._get_trace_checks(pi)
                    if cki['ignore']:
                        continue
                    elif cki['edge']:
                        is_select = None
                    elif cki['good']:
                        is_select = True
                    else:
                        is_select = False
                    new_checks[li] = cki

                    # Compare with regions of previous frame
                    # Check if parent is valid (area, edge)
                    parents = []
                    for j in js:
                        pj = prev_bbox['props'][j]
                        lj = pj.label
                        cj = pj.coords
                        if not check_coordinate_overlap(ci, cj):
                            continue
                        try:
                            ckj = prev_checks[lj]
                        except KeyError:
                            continue

                        if ckj['edge']:
                            is_select = None
                            break

                        parents.append(dict(ckj))

                    # Check for parents
                    parents.sort(key=lambda p: p['area'])
                    if is_select is None:
                        pass
                    elif not parents:
                        continue
                    elif parents[0]['ignore']:
                        is_select = None
                    elif len(parents) > 1 and not parents[1]['ignore']:
                        is_select = None
                    else:
                        parent = 0

                    # Mark untrackable cells
                    if is_select is None:
                        for p in parents:
                            try:
                                invalid_idx = prev_idx[p['label']]
                            except KeyError:
                                continue
                            traces_selection[invalid_idx] = None
                        continue

                    # Final checks
                    parent = parents[parent]
                    try:
                        trace_idx = prev_idx[parent['label']]
                    except KeyError:
                        continue

                    if traces_selection[trace_idx] is None:
                        # Ignore traces with "bad ancestors"
                        continue
                    elif any(not new_checks[l]['ignore'] for l, x in new_idx.items() if x == trace_idx):
                        # Eliminate siblings
                        traces_selection[trace_idx] = None
                    elif not is_select and traces_selection[trace_idx]:
                        # Propagate deselect
                        traces_selection[trace_idx] = False
                    # Register this region as child of parent
                    new_idx[li] = trace_idx
                    traces[trace_idx].append(li)

                prev_idx = new_idx
                prev_checks = new_checks
                print("Frame {:03d}: {:.4f}s".format(fr + 1, time.time() - tic)) #DEBUG

        # Clean up cells
        self.traces = []
        self.traces_selection = []
        for tr, sel in zip(traces, traces_selection):
            if len(tr) == self.n_frames and sel is not None:
                self.traces.append(tr)
                self.traces_selection.append(sel)
        print(f"Total tracking time: {time.time() - tic0 :.2f}s") #DEBUG

    def _get_trace_checks(self, props, edges=True):
        is_good = True
        is_edge = False
        is_small = False
        is_large = False
        is_ignore = False
        if edges:
            coords = props.coords
            if (np.any(coords.flat == 0) or np.any(coords[:,0] == self.height-1) or \
                    np.any(coords[:,1] == self.width-1)):
                is_edge = True
                is_good = False
        if self.max_size and props.area > self.max_size:
            is_large = True
            is_good = False
        if self.min_size and props.area < self.min_size:
            is_small = True
            is_good = False
            if self.ignore_size and props.area <= self.ignore_size:
                is_ignore=True
        return dict(label=props.label,
                    area=props.area,
                    good=is_good,
                    edge=is_edge,
                    ignore=is_ignore,
                    small=is_small,
                    large=is_large)

    def get_traces(self):
        """Label and track cells.

        This method is intended to be called externally."""
        if self.make_labeled_stack and self.stack_lbl is None:
            self.label_stack()
        if self.props is None:
            self.read_regionprops()
        self.track()
