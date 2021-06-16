import os
import threading

import matplotlib as mpl
mpl.rcParams['pdf.fonttype'] = 42 # Edit plots with Illustrator
from matplotlib.figure import Figure
from matplotlib.ticker import StrMethodFormatter
import numpy as np
import pandas as pd
import skimage.morphology as skmorph

from . import const

from ..util.events import Event
from ..util.status import DummyStatus
from ..io import StackdataIO
from ..roi import ContourRoi
from ..stack import Stack
from ..stack import metastack as ms
from ..tracking import Tracker

class SessionModel:
    #TODO: update this docstring
    """Session info container.

    The following structured fields are present:

    self.channel_selection
        list of dict
        The list items correspond to the channels of
        `self.display_stack` with the same index. The dict
        holds information of the selection widgets:
        'type'      str of the channel type; one of those in:
                    `const.CH_CAT_LIST`
        'val'       boolean; indicates whether this channel is
                    currently displayed (True) or not (False).
        'button'    tk.Button instance for displaying the channel

    self.channel_order
        list of int
        The list values are indices to `self.channel_selection`.
        The order of the values is the order in which to display
        the channel selection buttons.

    self.traces
        dict of dict
        The keys of the outer dict are the trace names (as str),
        each trace corresponding to one tracked cell.
        The inner dict holds information of the trace:
        'roi'       list with frame index as index and corresponding
                    ROI name as value. The ContourRoi instance can
                    be retrieved from `self.rois` using the frame
                    index and the ROI name.
        'select'    boolean; if True, cell trace is read and displayed.
        'highlight' boolean; if True, cell/trace is highlighted in
                    stackviewer and in plot. Only meaningful if
                    the 'select' option is True.
        'val'       dict of values read for the cell. The dict keys are
                    the name of the quantity, the dict values are the
                    corresponding values of the quantity. For most quantities
                    (currently for all), the values are 1-dim numpy arrays
                    with each element being to the value in the
                    corresponding frame. Cell size is automatically present
                    with the key 'Area'. Integrated fluorescence intensities
                    are read for each fluorescence channel.
        'plot'      dict of plot objects (e.g. Line2D instance). The dict keys
                    are the plotted quantities (as in 'val'), the values
                    are the plot objects. Useful for plot manipulations
                    like highlighting traces.

    self.trace_info
        dict of dict
        Holds information about the present data.
        The keys of the outer dict are names of the quantities
        ('Area' predefined), the inner dict contains:
        'label'     (optional) str with additional information
                    about the trace, e.g. 'Fluorescence 1'
        'channel'   int, index of the corresponding channel
                    in `self.stack`. May be None.
        'unit'      str, unit of the quantity. Used for proper
                    axes labels in the plot, in later versions
                    possibly also for unit conversions.
                    Default: 'a.u.'
        'factor'    float, factor to multiply values to yield 'unit'. Default: None
        'type'      str, one of the contents of `const.DT_CAT_LIST`.
                    Indicates the type of quantity of the trace.
        'order'     int, indicates in which order to display the plots.
        'button'    tk.Button, the button instance for controlling 'plot'
        'var'       tk.BooleanVar associated with 'button'
        'plot'      boolean, indicates whether to plot the quantity or not.
        'quantity'  str, name of the value used in plot for y-label
        The outer dict should only be changed using the methods
        `self.add_trace_info` or `self.clear_trace_info`.

    self.rois
        list of dict
        The list indices are the frame indices of the stack,
        the dict keys are the labels (as in the labeled image)
        of the ROIs in the frame (saved as string) and the
        dict values are the corresponding ContourRoi instances.
    """
    def __init__(self, session_id):
        self.id = session_id
        self.lock = threading.RLock()
        self.traces = {}
        self.trace_info = {}
        self.rois = []

        self.init_trace_info() # TODO: abstract this away

        self.display_stack = None
        self.stacks = {}
        self.stack = None

        self.show_contour = True
        self.show_untrackable = False
        self.show_name = True

        self.frames_per_hour = 6 # TODO: let the user change this
        self._microscope_name = None
        self._microscope_resolution = None

    def init_trace_info(self):
        self.trace_info = {const.DT_CAT_AREA: dict(label=None,
                                           channel=None,
                                           unit="px²",
                                           factor=None,
                                           type=const.DT_CAT_AREA,
                                           order=0,
                                           button=None,
                                           var=None,
                                           plot=True,
                                           quantity="Cell area",
                                          )}

    def clear_trace_info(self):
        for k in tuple(self.trace_info.keys()):
            if k != const.DT_CAT_AREA:
                del self.trace_info[k]

    def open_stack(self, fn, status=None):
        """Open a stack and save it in SessionModel.stacks.

        Arguments:
            fn -- str, filename of the stack
            status -- Status instance for progress display

        Returns the stack_id (key to the SessionModel.stacks dictionary).
        """
        if status is None:
            status = DummyStatus()
        stack_props = {}
        if fn.endswith('h5'):
            stack_props['channels'] = 0
        stack_id = Event.now()
        stack = Stack(fn, status=status, **stack_props)
        stack_dir, stack_name = os.path.split(fn)
        n_channels = stack.n_channels
        with self.lock:
            self.stacks[stack_id] = {'id': stack_id,
                                     'name': stack_name,
                                     'dir': stack_dir,
                                     'stack': stack,
                                     'n_channels': n_channels,
                                     }
        return stack_id

    def close_stacks(self, *stack_ids, keep_open=()):
        """Close all stacks held only by this SessionModel"""
        if not stack_ids:
            stack_ids = list(self.stacks.keys())
        for sid in stack_ids:
            try:
                stack = self.stacks[sid]
            except KeyError:
                continue
            if sid not in keep_open:
                stack['stack'].close()
            del self.stacks[sid]

    @property
    def stack_ids(self):
        return set(self.stacks.keys())

    def get_stack_info(self, stack_id=None):
        """Get a stack info dict

        If 'stack_id' is None, return the whole 'stacks' dictionary.
        Else, return the stack info dict for the given stack ID.
        Returns None for non-existent stack ID.

        This method is thread-safe. The returned object must not be altered.
        """
        with self.lock:
            if stack_id is None:
                return self.stacks
            try:
                return self.stacks[stack_id]
            except KeyError:
                return None

    def get_stack(self, stack_id=None):
        """Get a stack

        If 'stack_id' is None, return the whole stack dictionary.
        Else, return the stack info for the given stack ID.
        Returns None for non-existent stack ID.

        This method is thread-safe. The returned object must not be altered.
        """
        with self.lock:
            if stack_id is None:
                return None
            try:
                return self.get_stack_info(stack_id)['stack']
            except KeyError:
                return None

    def config(self, chan_info, render_factory, status=None, do_track=True):
        """Configure the session for display.

        'chan_info' is a list holding dictionaries with these fields, defining the channels to be displayed:
            stack_id -- stack ID, key of `SessionModel.stacks` #DEBUG: Attention, changed behaviour
            name -- str, name of the stack
            dir -- str, directory where the stack file is saved
            i_channel -- int, index of stack to be used
            label -- str, optional user-defined description
            type -- str, stack type (phasecontrast, fluorescence, binary)
        'render_factory' is a factory function for the display_stack rendering function
        'status' is a Status instance for updating the status display.
        'do_track' is a flag whether to perform tracking or not.

        Returns True in case of success, else False.
        """
        # This function corresponds to MainWindow_TK.open_metastack.
        # The argument 'data' is renamed into 'chan_info'
        # (and has slightly different syntax, see docstring)
        if not chan_info:
            return False
        if status is None:
            status = DummyStatus()

        with self.lock, status("Preparing new session"):
            # Check image sizes
            stack_ids_used = set() #TODO: close stacks that are not used
            height_general = None
            width_general = None
            n_frames_general = None
            height_seg = None
            width_seg = None
            n_frames_seg = None
            for ci in chan_info:
                stack = self.get_stack(ci['stack_id'])
                if stack is None:
                    pass
                elif ci['type'] == const.CH_CAT_BIN:
                    height_seg = stack.height
                    width_seg = stack.width
                    n_frames_seg = stack.n_frames
                else:
                    if height_general is None:
                        height_general = stack.height
                    elif stack.height != height_general:
                        raise ValueError(f"Stack '{name}' has height {stack.height}, but height {height_general} is required.")
                    if width_general is None:
                        width_general = stack.width
                    elif stack.width != width_general:
                        raise ValueError(f"Stack '{name}' has width {stack.width}, but width {width_general} is required.")

                    if n_frames_general is None:
                        n_frames_general = stack.n_frames
                    elif stack.n_frames != n_frames_general:
                        raise ValueError(f"Stack '{name}' has {stack.n_frames} frames, but {n_frames_general} frames are required.")

            pad_y = 0
            pad_x = 0
            if None not in (height_general, height_seg):
                if height_seg > height_general:
                    pad_y = height_seg - height_general
                if width_seg > width_general:
                    pad_x = width_seg - width_general

            meta = ms.MetaStack()
            self.clear_trace_info()
            i_channel = 0
            i_channel_fl = 1
            close_stacks = set()
            retain_stacks = set()
            for ci in chan_info:
                stack = self.get_stack(ci['stack_id'])
                if ci['type'] == const.CH_CAT_BIN:
                    if do_track and stack is not None:
                        if pad_y or pad_x:
                            with status("Cropping segmented stack"):
                                stack.crop(right=pad_x, bottom=pad_y)
                        self.track_stack(stack, channel=ci['i_channel'], status=status)
                        close_stacks.add(stack)
                    meta.add_channel(name='segmented_stack',
                                     label=ci['label'],
                                     type_=ci['type'],
                                     fun=self.render_segmentation,
                                     scales=False,
                                    )
                else:
                    name = stack.path
                    meta.add_stack(stack, name=name)
                    meta.add_channel(name=name,
                                     channel=ci['i_channel'],
                                     label=ci['label'],
                                     type_=ci['type'],
                                    )
                    retain_stacks.add(stack)

                if ci['type'] == const.CH_CAT_FL:
                    label = f"Fluorescence {i_channel_fl}"
                    name = ci['label']
                    if not name:
                        name = label
                        label = None
                    self.add_trace_info(name,
                                        label=label,
                                        channel=i_channel,
                                        type_=ci['type'],
                                        order=i_channel_fl,
                                        plot=True,
                                        quantity="Integrated fluorescence",
                                       )
                    i_channel_fl += 1
                i_channel += 1

            # Close stacks that only contain segmentation
            close_stacks -= retain_stacks
            for stack in close_stacks:
                stack.close()

            if not meta.check_properties():
                meta.set_properties(n_frames=n_frames_seg, width=width_seg, height=height_seg)

            # Set meta_stack and display_stack
            self.stack = meta
            self.display_stack = ms.MetaStack()
            self.display_stack.set_properties(n_frames=meta.n_frames,
                                              width=meta.width,
                                              height=meta.height,
                                              mode='uint8',
                                             )
            if self.rois:
                for fr, rois in enumerate(self.rois):
                    self.display_stack.set_rois(list(rois.values()), frame=fr)
            self.display_stack.add_channel(fun=render_factory(self.stack, self.render_segmentation), scales=True)

            # Read traces
            self.read_traces()

    def render_segmentation(self, meta, frame, scale=None, rois=None, binary=False):
        """Dynamically draw segmentation image from ROIs

        This method is to be called by `MetaStack.get_image`.

        Arguments:
            meta -- the calling `MetaStack` instance; ignored
            frame -- the index of the selected frame
            scale -- scaling information; ignored
            rois -- iterable of ROIs to show; if None, show all ROIs in frame
            binary -- if True, returned array is boolean, else uint8
        """
        img = np.zeros((meta.height, meta.width), dtype=(np.bool if binary else np.uint8))
        if rois is None:
            if self.rois is None:
                print("SessionModel.render_segmentation: trying to read non-existent ROIs") #DEBUG
                return img
            rois = self.rois[frame].values()
        elif rois is False:
            rois = self.deselected_rois(frame)
        for roi in rois:
            img[roi.rows, roi.cols] = 255
        return img

    def deselected_rois(self, frame):
        """Get an iterable of all non-selected ROIs in given frame"""
        if not self.rois:
            return ()
        return (roi for roi in self.rois[frame].values()
                if roi.color not in (const.ROI_COLOR_SELECTED, const.ROI_COLOR_HIGHLIGHT))

    def track_stack(self, s, channel=0, status=None):
        """Perform tracking of a given stack"""
        if status is None:
            status = DummyStatus()
        with self.lock, status("Tracking cells"):
            tracker = Tracker(segmented_stack=s, segmented_chan=channel, status=status)
            if s.stacktype == 'hdf5':
                tracker.preprocessing = self.segmentation_preprocessing
            tracker.get_traces()
            self.rois = []
            self.traces = {}
            for fr, props in tracker.props.items():
                self.rois.append({l: ContourRoi(regionprop=p,
                                                label=l,
                                                color=const.ROI_COLOR_UNTRACKABLE,
                                                visible=self.show_untrackable,
                                                name_visible=False,
                                                frame=fr,
                                               ) for l, p in props.items()})
            for i, trace in enumerate(tracker.traces):
                name = str(i + 1)
                is_selected = tracker.traces_selection[i]
                self.traces[name] = {'roi': trace,
                                     'select': is_selected,
                                     'highlight': False,
                                     'val': {},
                                     'plot': {},
                                    }
                for fr, j in enumerate(trace):
                    roi = self.rois[fr][j]
                    roi.name = name
                    roi.color = const.ROI_COLOR_SELECTED if is_selected else const.ROI_COLOR_DESELECTED
                    roi.visible = bool(roi.name) and self.show_contour
                    roi.name_visible = self.show_name

    def segmentation_preprocessing(self, img):
        """Preprocessing function for smoothening segmentation

        Smoothens 2D image `img` using morphological operations.
        `img` must have values from 0 to 1, indicating the probability
        that the corresponding pixel belongs to a cell.
        Returns a binary (boolean) image with same shape as `img`.

        This function is designed for preparing the Probability obtained
        from Ilastik for tracking, using the .label.Tracker.preprocessing attribute.
        """
        img = img >= .5
        img = skmorph.closing(img, selem=skmorph.disk(5))
        img = skmorph.erosion(img, selem=skmorph.disk(1))
        img = skmorph.dilation(img, selem=skmorph.disk(3))
        #img = skmorph.area_closing(img, area_threshold=100)
        #img = skmorph.area_opening(img, area_threshold=100)
        img = skmorph.remove_small_holes(img, area_threshold=150)
        img = skmorph.remove_small_objects(img, min_size=150)
        return img

    def read_traces(self, status=None):
        """Read out cell traces"""
        if not self.traces:
            return
        if status is None:
            status = DummyStatus()

        with self.lock, status("Reading traces"):
            n_frames = self.stack.n_frames

            # Get fluorescence channels
            fl_chans = []
            for name, info in self.trace_info.items():
                if info['type'] == const.CH_CAT_FL:
                    fl_chans.append({'name': name,
                                     'i_channel': info['channel'],
                                     'img': None,
                                    })
            fl_chans.sort(key=lambda ch: self.trace_info[ch['name']]['order'])

            # Get microscope resolution (=area conversion factor)
            area_factor = self.trace_info[const.DT_CAT_AREA]['factor']

            # Read traces
            for tr in self.traces.values():
                tr['val'].clear()

                # Area
                val_area = np.empty(n_frames, dtype=np.float)
                for fr, i in enumerate(tr['roi']):
                    val_area[fr] = self.rois[fr][i].area
                if area_factor is not None:
                    val_area *= area_factor
                tr['val'][const.DT_CAT_AREA] = val_area

                # Fluorescence
                for ch in fl_chans:
                    tr['val'][ch['name']] = np.empty(n_frames, dtype=np.float)

            for fr in range(n_frames):
                images = {}
                for ch in fl_chans:
                    ch['img'] = self.stack.get_image(frame=fr, channel=ch['i_channel'])
                for tr in self.traces.values():
                    roi = self.rois[fr][tr['roi'][fr]]
                    for ch in fl_chans:
                        tr['val'][ch['name']][fr] = np.sum(ch['img'][roi.rows, roi.cols])

    def add_trace_info(self, name, label=None, channel=None, unit="a.u.",
            factor=None, type_=None, order=None, plot=False, quantity=None):
        """Add information about a new category of traces"""
        with self.lock:
            self.trace_info[name] = {'label': label,
                                     'channel': channel,
                                     'unit': unit,
                                     'factor': factor,
                                     'type': type_,
                                     'order': order,
                                     'button': None,
                                     'var': None,
                                     'plot': plot,
                                     'quantity': quantity if quantity is not None else type_,
                                    }

    def traces_sorted(self, fr):
        """Return a list of traces sorted by position

        fr -- the frame number
        """
        with self.lock:
            rois = self.rois[fr]
            traces_pos = {}
            for name, tr in self.traces.items():
                roi = rois[tr['roi'][fr]]
                traces_pos[name] = (roi.y_min, roi.x_min)
        return sorted(traces_pos.keys(), key=lambda name: traces_pos[name])

    def traces_as_dataframes(self):
        """Return a dict of DataFrames of the traces"""
        t = self.to_hours(np.array(range(self.stack.n_frames)))
        time_vec = pd.DataFrame(t, columns=("Time [h]",))
        df_dict = {}
        for name, tr in self.traces.items():
            if not tr['select']:
                continue
            for qty, data in tr['val'].items():
                try:
                    df_dict[qty][name] = data
                except KeyError:
                    df_dict[qty] = time_vec.copy()
                    df_dict[qty][name] = data
        return df_dict

    def plot_traces(self, fig, is_interactive=False, frame_indicator_list=None, status=None):
        """Plots the traces.

        fig -- the Figure instance to plot to
        is_interactive -- special formatting for interactive plot
        frame_indicator_list -- list to which to add frame indicators
        """
        if not self.traces:
            return
        if status is None:
            status = DummyStatus()

        with self.lock, status("Plotting traces …"):
            # Find data to be plotted and plotting order
            plot_list = []
            for name, info in self.trace_info.items():
                if info['plot']:
                    plot_list.append(name)
            plot_list.sort(key=lambda name: self.trace_info[name]['order'])

            t_vec = self.to_hours(np.array(range(self.display_stack.n_frames)))
            axes = fig.subplots(len(plot_list), squeeze=False, sharex=True)[:,0]
            for qty, ax in zip(plot_list, axes):
                ax.set_xmargin(.003)
                ax.yaxis.set_major_formatter(StrMethodFormatter('{x:.4g}'))
                for name, tr in self.traces.items():
                    if not tr['select']:
                        continue
                    if tr['highlight']:
                        lw = const.PLOT_WIDTH_HIGHLIGHT
                        alpha = const.PLOT_ALPHA_HIGHLIGHT
                        color = const.PLOT_COLOR_HIGHLIGHT
                    else:
                        lw = const.PLOT_WIDTH
                        alpha = const.PLOT_ALPHA
                        color = const.PLOT_COLOR
                    l = ax.plot(t_vec, tr['val'][qty],
                            color=color, alpha=alpha, lw=lw, label=name,
                            picker=is_interactive, pickradius=3)
                    if is_interactive:
                        tr['plot'][qty] = l

                xlbl = "Time [h]"
                ax.set_ylabel("{quantity} [{unit}]".format(**self.trace_info[qty]))
                ax.set_title(qty, fontweight='bold')

                if is_interactive:
                    if frame_indicator_list is not None:
                        frame_indicator_list.append(ax.axvline(np.NaN, lw=1.5, color='r'))
                else:
                    ax.xaxis.set_tick_params(labelbottom=True)
                if ax.is_last_row():
                    ax.set_xlabel(xlbl)

    def to_hours(self, x):
        """Convert 0-based frame number to hours"""
        try:
            with self.lock:
                return x / self.frames_per_hour
        except Exception:
            return np.NaN

    @property
    def mic_name(self):
        with self.lock:
            return self._microscope_name

    @property
    def mic_res(self):
        with self.lock:
            return self._microscope_resolution

    def set_microscope(self, name=None, resolution=None, status=None):
        """Set a microscope

        Arguments:
            name -- str, human-readable microscope/objective name
            resolution -- float, image resolution in [µm/px]
            status -- Status, passed on to `SessionModel.read_traces`
        """
        if not resolution:
            name = None
            resolution = None
        elif not name:
            name = None
        elif resolution <= 0:
            raise ValueError(f"Illegal microscope settings: '{name}' with {resolution} µm/px")
        with self.lock:
            self._microscope_name = name
            self._microscope_resolution = resolution

            if resolution is not None:
                self.trace_info[const.DT_CAT_AREA]['unit'] = "µm²"
                self.trace_info[const.DT_CAT_AREA]['factor'] = resolution**2
            else:
                self.trace_info[const.DT_CAT_AREA]['unit'] = "px²"
                self.trace_info[const.DT_CAT_AREA]['factor'] = None
            self.read_traces(status=status)

    def save_session(self, save_dir, status=None):
        """Save the session.

        Arguments:
            save_dir -- str indicating path of directory to which to save
        """
        if status is None:
            status = DummyStatus()

        # Plot the data
        fig = Figure(figsize=(9,7))
        self.plot_traces(fig)
        fig.savefig(os.path.join(save_dir, "Figure.pdf"))

        with self.lock, status("Saving session …"):
            # Save data to Excel file
            df_dict = self.traces_as_dataframes()
            with pd.ExcelWriter(os.path.join(save_dir, "Data.xlsx"), engine='xlsxwriter') as writer:
                for name, df in df_dict.items():
                    df.to_excel(writer, sheet_name=name, index=False)

            # Save data to CSV file
            for name, df in df_dict.items():
                df.to_csv(os.path.join(save_dir, f"{name}.csv"), header=False, index=False, float_format='%.5f')

            # Export ROIs to JSON file
            sd = StackdataIO(traces=self.traces, rois=self.rois)
            sd.n_frames = self.stack.n_frames
            sd.microscope_name = self.mic_name
            sd.microscope_resolution = self.mic_res
            for i, ch in enumerate(self.stack.channels):
                if ch.isVirtual:
                    path = None
                else:
                    path = self.stack.stack(ch.name).path
                i_channel = ch.channel
                type_ = ch.type
                name = ch.name
                label = ch.label
                sd.add_channel(path, type_, i_channel, name, label)

            sd.dump(save_dir, "session.zip")
        print(f"Data have been written to '{save_dir}'") #DEBUG

    def from_stackio(self, fn, status=None):
        """Load session content from StackdataIO instance.

        Arguments:
            fn -- str, filename of the saved session
            status -- Status object for displaying progress

        Returns a new SessionModel instance.
        """
        if status is None:
            status = DummyStatus()

        # Read session data and load content
        sd = StackdataIO(status=status)
        sd.load(fin=fn)
        self.set_microscope(name=sd.microscope_name, resolution=sd.microscope_resolution)
        self.rois = sd.rois
        for trace in sd.traces:
            name = trace['name']
            self.traces[name] = {
                    'name': name,
                    'roi': trace['rois'],
                    'select': trace['select'],
                    'highlight': False,
                    'val': {},
                    'plot': {},
                    }

        # Load stacks
        chan_info = []
        stack_paths = {}
        for ch in sd.channels:
            x = {}
            if ch['file_directory'] is None or ch['file_name'] is None:
                path = None
                x['stack_id'] = None
            else:
                path = os.path.join(ch['file_directory'], ch['file_name'])
                try:
                    x['stack_id'] = stack_paths[path]
                except KeyError:
                    stack_id = self.open_stack(path, status=status)
                    stack_paths[path] = stack_id
                    x['stack_id'] = stack_id
            x['name'] = ch['name']
            x['i_channel'] = ch['i_channel']
            x['label'] = ch['label']
            x['type'] = ch['type']
            chan_info.append(x)
        return chan_info


    def binarize_phc_stack(self, *, outfile=None, status=None, return_result=False):
        from ..tools.binarize import binarize_phasecontrast_stack as tool_bin_phc

        # Get index of first phase-contrast channel
        for i, spec in enumerate(self.stack.channels):
            if spec.type == const.CH_CAT_PHC:
                i_channel = i
                break
        else:
            print("SessionModel.binarize_phc_stack: no phase-contrast channel found.") #DEBUG
            return

        spec = self.stack.channels[i_channel]
        stack = self.stack.stack(spec.name)
        phc_channel = spec.channel
        result = tool_bin_phc(stack=stack,
                              i_channel=phc_channel,
                              outfile=outfile,
                              status=status,
                              return_result=return_result,
                             )
        return result


    def background_correction(self, outfile, status=None):
        from ..tools.bgcorr import perform_background_correction

        i_chan_fl = None
        i_chan_bin = None
        for i, spec in enumerate(self.stack.channels):
            if spec.type == const.CH_CAT_FL and i_chan_fl is None:
                i_chan_fl = i
            elif spec.type == const.CH_CAT_BIN and i_chan_bin is None:
                i_chan_bin = i
            if i_chan_fl is not None and i_chan_bin is not None:
                break

        # Get fluorescence channel
        if i_chan_fl is None:
            print("SessionModel.background_correction: no fluorescence channel found.") #DEBUG
            return
        c_fl0 = self.stack.get_image(channel=i_chan_fl, frame=0)
        chan_fl = np.empty((self.stack.n_frames, self.stack.height, self.stack.width), dtype=c_fl0.dtype)
        chan_fl[0, ...] = c_fl0
        for t in range(1, self.stack.n_frames):
            chan_fl[t, ...] = self.stack.get_image(channel=i_chan_fl, frame=t)

        # Get segmentation channel
        if i_chan_bin is None:
            outfile_bin = f"{os.path.splitext(outfile)[0]}_segmented.npz"
            chan_bin = self.binarize_phc_stack(outfile=outfile_bin, status=status, return_result=True)
        else:
            c_bin0 = self.stack.get_image(channel=i_chan_bin, frame=0)
            chan_bin = np.empty((self.stack.n_frames, self.stack.height, self.stack.width), dtype=c_bin0.dtype)
            chan_bin[0, ...] = c_bin0
            for t in range(1, self.stack.n_frames):
                chan_bin[t, ...] = self.stack.get_image(channel=i_chan_bin, frame=t)

        perform_background_correction(chan_fl=chan_fl, chan_bin=chan_bin, outfile=outfile, status=status)

