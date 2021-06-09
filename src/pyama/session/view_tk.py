import os
import queue
import re
import time
import tkinter as tk
import tkinter.filedialog as tkfd
import tkinter.simpledialog as tksd

import matplotlib as mpl
mpl.rcParams['pdf.fonttype'] = 42 # Edit plots with Illustrator
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backend_bases import MouseButton
import numpy as np

from . import const
from .sessionopener_tk import SessionOpener
from ..stack import metastack as ms
from ..stackviewer_tk import StackViewer
from ..util.events import Event
from ..util.status import DummyStatus
from .view import SessionView

KEYS_NEXT_CELL = {'Down', 'KP_Down'}
KEYS_PREV_CELL = {'Up', 'KP_Up'}
KEYS_HIGHLIGHT_CELL = {'Return', 'KP_Enter'}
KEYS_SHOW_CONTOURS = {'Insert', 'KP_Insert'}
KEYS_CHANNEL = {fmt.format(sym) for fmt in ('{}', 'KP_{}') for sym in range(1, 10)}
KEYS_NEXT_FRAME = {'Right', 'KP_Right'}
KEYS_PREV_FRAME = {'Left', 'KP_Left'}
KEYS_FIRST_FRAME = {'Home', 'KP_Home'}
KEYS_LAST_FRAME = {'End', 'KP_End'}

FRAME_SCROLL_RATE_MAX = 8e9

QUEUE_POLL_INTERVAL = 10

# tkinter event state constants for key presses
# see: https://web.archive.org/web/20181009085916/http://infohost.nmt.edu/tcc/help/pubs/tkinter/web/event-handlers.html
EVENT_STATE_SHIFT = 1
EVENT_STATE_CTRL = 4

MODE_SELECTION = 'selection'
MODE_HIGHLIGHT = 'highlight'

TOOL_LABEL_BINARIZE = "Binarize…"

DESELECTED_DARKEN_FACTOR = .3

MIC_RES = {
        # Resolutions are given in µm/px
        # See: https://collab.lmu.de/x/9QGFAw
        "Nikon (4x)":           1.61,
        "Nikon (10x PhC)":       .649,
        "Nikon (20x)":           .327,
        "Nikon TIRF (4x)":      1.621,
        "Nikon TIRF (10x PhC)":  .658,
        "Nikon TIRF (20x)":      .333,
        "Nikon TIRF (60x)":      .108,
        "Zeiss (10x PhC)":       .647,
        "Zeiss (20x)":           .312,
        "Zeiss (40x)":           .207,
        "UNikon (4x)":          1.618,
        "UNikon (10x PhC)":      .655,
        "UNikon (10x)":          .650,
        "UNikon (20x)":          .331,
        "UNikon (40x)":          .163,
        "UNikon (60x)":          .108,
        "UNikon (100x)":         .065,
        "Cell culture (5x)":     .81,
        "Cell culture (10x PhC)":.42,
        "Cell culture (20x)":    .21,
    }
MIC_RES_UNSPEC = "Unspecified (use [px])"
MIC_RES_CUSTOM = "Custom"
MIC_RES_UNSPEC_IDX = 1
MIC_RES_CUSTOM_IDX = 2

class SessionView_Tk(SessionView):

    def __init__(self, title, control_queue, status):
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry('1300x600')
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Initialize variables
        self.queue = queue.Queue()
        self.control_queue = control_queue
        self.var_statusmsg = tk.StringVar(value="Initializing")
        self.status = status
        self.status_id = self.status.register_viewer(self.update_status, self.queue)
        self.session = None
        self._session_opener = None

        self.cmd_map = {
                const.CMD_SET_SESSION: self.set_session,
                const.CMD_UPDATE_TRACES: self.update_traces,
            }

        self.display_stack = None
        self.channel_selection = {}
        self.channel_order = []
        self.frame_indicators = []
        #self.traces = None #replace by self.session.traces
        #self.trace_info = None # replace by self.session.trace_info
        #self.rois = None # replace by self.session.rois
        self.fig = None
        self.fig_widget = None
        self.save_dir = None
        self.last_frame_scroll = Event.now()

        self.var_show_frame_indicator = tk.BooleanVar(value=True)
        self.var_mode = tk.StringVar(value=MODE_HIGHLIGHT)
        self.var_darken_deselected = tk.BooleanVar(value=False)
        self.var_show_roi_contours = tk.BooleanVar(value=True)
        self.var_show_roi_names = tk.BooleanVar(value=True)
        self.var_show_untrackable = tk.BooleanVar(value=False)
        self.var_microscope_res = tk.StringVar(value=MIC_RES_UNSPEC)

        # Build menu
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        filemenu = tk.Menu(menubar)
        menubar.add_cascade(label="File", menu=filemenu)
        filemenu.add_command(label="Open stack…", command=self.open_stack)
        filemenu.add_command(label="Open session", command=self.open_session)
        filemenu.add_command(label="Save", command=self.save)
        filemenu.add_command(label="Set output directory…", command=self._get_savedir)
        filemenu.add_command(label="Quit", command=self.root.quit)

        modemenu = tk.Menu(menubar)
        menubar.add_cascade(label="Mode", menu=modemenu)
        modemenu.add_radiobutton(label="Highlight", value=MODE_HIGHLIGHT, variable=self.var_mode)
        modemenu.add_radiobutton(label="Selection", value=MODE_SELECTION, variable=self.var_mode)

        self.toolmenu = tk.Menu(menubar)
        menubar.add_cascade(label="Tools", menu=self.toolmenu)
        self.toolmenu.add_command(label=TOOL_LABEL_BINARIZE, command=self.binarize, state=tk.DISABLED)
        self.toolmenu.add_command(label="Pickle maximum bounding box", command=self._pickle_max_bbox)
        self.toolmenu.add_command(label="Background correction…", command=self._background_correction)
        settmenu = tk.Menu(menubar)
        menubar.add_cascade(label="Settings", menu=settmenu)
        settmenu.add_checkbutton(label="Display frame indicator", variable=self.var_show_frame_indicator)
        settmenu.add_checkbutton(label="Display cell contours", variable=self.var_show_roi_contours)
        settmenu.add_checkbutton(label="Display cell labels", variable=self.var_show_roi_names)
        settmenu.add_checkbutton(label="Display untracked cells", variable=self.var_show_untrackable)
        settmenu.add_checkbutton(label="Darken deselected cells", variable=self.var_darken_deselected)

        self.micresmenu = tk.Menu(settmenu)
        settmenu.add_cascade(label="Microscope resolution", menu=self.micresmenu)
        for mic_opt in MIC_RES.keys():
            self._add_to_microscope_menu(mic_opt)
        MIC_RES[MIC_RES_UNSPEC] = None
        MIC_RES[MIC_RES_CUSTOM] = None
        self.micresmenu.insert(MIC_RES_UNSPEC_IDX,
                          'radiobutton',
                          label=MIC_RES_UNSPEC,
                          value=MIC_RES_UNSPEC,
                          variable=self.var_microscope_res,
                          command=lambda mo=MIC_RES_UNSPEC: self._change_microscope_resolution(mo)
                         )
        self.micresmenu.insert(MIC_RES_CUSTOM_IDX,
                          'radiobutton',
                          label=MIC_RES_CUSTOM,
                          value=MIC_RES_CUSTOM,
                          variable=self.var_microscope_res,
                          command=lambda mo=MIC_RES_CUSTOM: self._change_microscope_resolution(mo)
                         )

        helpmenu = tk.Menu(menubar)
        menubar.add_cascade(label="Help", menu=helpmenu)
        helpmenu.add_command(label="Breakpoint", command=self._breakpoint)
        helpmenu.add_command(label="Sleep 10s", command=self.sleep10)


        # Window structure
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=4, sashrelief=tk.RAISED)
        self.paned.grid(row=0, column=0, sticky='NESW')

        ## Channels frame
        self.chanframe = tk.Frame(self.paned)
        self.paned.add(self.chanframe, sticky='NESW')
        self.chanframe.grid_columnconfigure(0, weight=1)

        self.open_btn = tk.Button(self.chanframe, text="Open stack...", command=self.open_stack)
        self.open_btn.grid(row=0, column=0, sticky='NEW', padx=10, pady=5)
        self.chansellbl = tk.Label(self.chanframe, text="Display channels", anchor=tk.W, state=tk.DISABLED)
        self.chansellbl.grid(row=1, column=0, sticky='NESW', padx=10, pady=(20, 5))
        self.chanselframe = tk.Frame(self.chanframe)
        self.chanselframe.grid(row=2, column=0, sticky='ESW')
        self.plotsellbl = tk.Label(self.chanframe, text="Plot traces", anchor=tk.W, state=tk.DISABLED)
        self.plotsellbl.grid(row=3, column=0, sticky='ESW', padx=10, pady=(20, 5))
        self.plotselframe = tk.Frame(self.chanframe)
        self.plotselframe.grid(row=4, column=0, sticky='ESW')

        ## Stack frame
        self.stackframe = tk.Frame(self.paned)
        self.paned.add(self.stackframe, sticky='NESW')
        # self.stackframe.grid_columnconfigure(0, weight = 2, minsize=650)
        self.stackviewer = StackViewer(parent=self.stackframe, root=self.root, show_buttons='contrast')

        ## Figure frame
        self.figframe = tk.Frame(self.paned)
        self.paned.add(self.figframe, sticky='NESW')
        # self.figframe.grid_columnconfigure(0, weight = 1, minsize=500)
        self.create_figure()

        ## Statusbar
        self.statusbar = tk.Frame(self.root, padx=2, pady=2, bd=1, relief=tk.SUNKEN)
        self.statusbar.grid(row=1, column=0, sticky='NESW')
        tk.Label(self.statusbar, anchor=tk.W, textvariable=self.var_statusmsg).pack(side=tk.LEFT, anchor=tk.W)

        # Callbacks
        self.var_show_frame_indicator.trace_add('write', self._update_frame_indicator)
        self.var_darken_deselected.trace_add('write', lambda *_: self.display_stack._listeners.notify('image'))
        self.var_show_roi_contours.trace_add('write', self._update_show_roi_contours)
        self.var_show_roi_names.trace_add('write', self._update_show_roi_names)
        self.var_show_untrackable.trace_add('write', self._update_show_untrackable)

        self.stackframe.bind('<Configure>', self._stacksize_changed)
        self.stackviewer.register_roi_click(self._roi_clicked)

        ## Set global key bindings for display and cell selection
        # Some key symbols for the keypad (KP_*) may not be available in all systems.
        bindings = ((KEYS_NEXT_CELL | KEYS_PREV_CELL | KEYS_HIGHLIGHT_CELL, self._key_highlight_cell),
                    (KEYS_SHOW_CONTOURS, lambda _:
                        self.var_show_roi_contours.set(not self.var_show_roi_contours.get())),
                    (KEYS_NEXT_FRAME | KEYS_PREV_FRAME, self._key_scroll_frames),
                    (KEYS_CHANNEL, self._key_change_channel),
                    (KEYS_FIRST_FRAME | KEYS_LAST_FRAME, self._key_jump_frames),
                   )
        for keysyms, callback in bindings:
            for keysym in keysyms:
                if len(keysym) > 1:
                    keysym = f"<{keysym}>"
                try:
                    self.root.bind(keysym, callback)
                except Exception:
                    if not (os.name == 'nt' and re.fullmatch(r'<KP_\D.*>', keysym)):
                        # Cleaner start-up on Windows
                        # (the <KP_\D.*> keysyms are not available in Windows)
                        print(f"Failed to register keysym '{keysym}'")

    def mainloop(self):
        self.root.after(QUEUE_POLL_INTERVAL, self.poll_event_queue)
        self.root.mainloop()
        self.root.quit()

    def _breakpoint(self):
        """Enter a breakpoint for DEBUGging"""
        breakpoint()

    def sleep10(self):
        """Sleep 10 seconds for DEBUGging"""
        import threading
        def sleep(self=self, t_max=10):
            t = 0
            while t < t_max:
                with self.status("Sleeping", current=t, total=t_max):
                    time.sleep(1)
                    t += 1
        threading.Thread(target=sleep).start()

    def update_status(self, msg="", current=None, total=None):
        """Update the status shown in the status bar"""
        if current is None:
            status = msg
        elif total is None:
            status = f"{msg} {current}"
        else:
            status = f"{msg} {current}/{total}"
        self.var_statusmsg.set(status)
        self.root.update_idletasks()

    def create_figure(self):
        """Show an empty figure"""
        self.fig = Figure()
        mpl_canvas = FigureCanvasTkAgg(self.fig, master=self.figframe)
        self.fig.canvas.mpl_connect('pick_event', self._line_picker)
        mpl_canvas.draw()
        self.fig_widget = mpl_canvas.get_tk_widget()
        self.fig_widget.pack(fill=tk.BOTH, expand=True)

    def poll_event_queue(self):
        """Poll event queue"""
        while True:
            try:
                evt = self.queue.get_nowait()
            except queue.Empty:
                break
            if evt.fun is not None:
                evt()
                continue
            try:
                cmd = self.cmd_map[evt.cmd]
            except KeyError:
                pass
            else:
                evt(cmd)
                continue
            try:
                cmd = self.session_opener.cmd_map[evt.cmd]
            except (KeyError, AttributeError):
                pass
            else:
                evt(cmd)
                continue
            raise ValueError(f"Unknown command: '{evt.cmd}'")
        self.root.after(QUEUE_POLL_INTERVAL, self.poll_event_queue)

    @property
    def session_opener(self):
        """Return an active SessionOpener_Tk or None"""
        if self._session_opener is not None and not self._session_opener.active:
            self._session_opener = None
        return self._session_opener

    def open_stack(self):
        """Ask user to open new stack"""
        if self.session_opener is None:
            self._session_opener = SessionOpener(self.root, control_queue=self.control_queue, status=self.status)
        else:
            self.session_opener.to_front()

    def set_session(self, session=None):
        """Set a SessionModel instance for display"""
        #TODO: Allow multiple types of PhC and Segmentation
        self.session = session
        if self.session is None:
            self.display_stack = None
            pass
        else:
            with self.status("Loading stack …"):
                self.display_stack = self.session.display_stack

                # Create channel display buttons
                self.channel_order.clear()
                for k, x in tuple(self.channel_selection.items()):
                    x['button'].destroy()
                    del self.channel_selection[k]
                idx_phasecontrast = None
                idx_fluorescence = []
                idx_segmentation = None
                for i, spec in enumerate(self.session.stack.channels):
                    if spec.type == const.CH_CAT_PHC and not idx_phasecontrast:
                        idx_phasecontrast = i
                    elif spec.type == const.CH_CAT_FL:
                        idx_fluorescence.append(i)
                    elif spec.type == const.CH_CAT_BIN and not idx_segmentation:
                        idx_segmentation = i
                    else:
                        continue
                    x = {}
                    self.channel_selection[i] = x
                    x['type'] = spec.type
                    x['val'] = False
                    btntxt = []
                    if spec.label:
                        btntxt.append(spec.label)
                    if spec.type == const.CH_CAT_FL:
                        btntxt.append("{} {}".format(spec.type, len(idx_fluorescence)))
                    else:
                        btntxt.append(spec.type)
                    btntxt = "\n".join(btntxt)
                    x['button'] = tk.Button(self.chanselframe, justify=tk.LEFT, text=btntxt)
                    x['button'].bind('<ButtonPress-1><ButtonRelease-1>', self._build_chanselbtn_callback(i))

            # Display channel display buttons
            self.chansellbl.config(state=tk.NORMAL)
            if idx_phasecontrast is not None:
                self.channel_order.append(idx_phasecontrast)
                self.channel_selection[idx_phasecontrast]['button'].pack(anchor=tk.N,
                        expand=True, fill=tk.X, padx=10, pady=5)
            for i in idx_fluorescence:
                self.channel_order.append(i)
                self.channel_selection[i]['button'].pack(anchor=tk.N,
                        expand=True, fill=tk.X, padx=10, pady=5)
            if idx_segmentation is not None:
                self.channel_order.append(idx_segmentation)
                self.channel_selection[idx_segmentation]['button'].pack(anchor=tk.N,
                        expand=True, fill=tk.X, padx=10, pady=5)

            # Update tools menu
            if idx_phasecontrast is None:
                new_state = tk.DISABLED
            else:
                new_state = tk.NORMAL
            self.toolmenu.entryconfig(TOOL_LABEL_BINARIZE, state=new_state)

            # Initial channel selection and display
            self._change_channel_selection()
            self.update_roi_display(notify_listeners=False)
        self.stackviewer.set_stack(self.display_stack, wait=False)

    def save(self):
        """Save data to files"""
        if not self.save_dir:
            self._get_savedir()

        #TODO: in new thread
        Event.fire(self.control_queue, const.CMD_SAVE_SESSION_TO_DISK, self.session, self.save_dir, status=self.status)

    def _get_savedir(self):
        """Ask user for output directory"""
        options = {'mustexist': False,
                   'parent': self.root,
                   'title': "Choose output directory",
                  }
        if self.save_dir:
            options['initialdir'] = self.save_dir
        new_savedir = tkfd.askdirectory(**options)
        if new_savedir:
            if not os.path.exists(new_savedir):
                os.makedirs(new_savedir)
            elif not os.path.isdir(new_savedir):
                #TODO: show GUI dialog
                raise NotADirectoryError("Not a directory: '{}'".format(new_savedir))
            self.save_dir = new_savedir
        elif not new_savedir:
            raise ValueError("No save directory given")
        elif not os.path.isdir(self.save_dir):
            raise NotADirectoryError("Not a directory: '{}'".format(self.save_dir))

    def _stacksize_changed(self, evt):
        """Update stackviewer after stack size change"""
        self.stackviewer._change_stack_position(force=True)

    def _key_highlight_cell(self, evt):
        """Callback for highlighting cells by arrow keys

        Up/down arrows highlight cells,
        Enter toggles cell selection.
        """
        if not self.session or not self.session.traces:
            return
        cells_sorted = self.session.traces_sorted(self.stackviewer.i_frame)
        cells_highlight = list(cells_sorted.index(name) for name, tr in self.session.traces.items() if tr['highlight'])
        is_selection_updated = False

        if evt.keysym in KEYS_PREV_CELL:
            # Highlight previous cell
            for i in cells_highlight:
                self.highlight_trace(cells_sorted[i], val=False)
            if cells_highlight:
                new_highlight = cells_highlight[0] - 1
                if new_highlight < 0:
                    new_highlight = cells_sorted[-1]
                else:
                    new_highlight = cells_sorted[new_highlight]
            else:
                new_highlight = cells_sorted[-1]
            self.highlight_trace(new_highlight, val=True)
            self.update_highlight()

        elif evt.keysym in KEYS_NEXT_CELL:
            # Highlight next cell
            for i in cells_highlight:
                self.highlight_trace(cells_sorted[i], val=False)
            if cells_highlight:
                new_highlight = cells_highlight[-1] + 1
                if new_highlight >= len(cells_sorted):
                    new_highlight = cells_sorted[0]
                else:
                    new_highlight = cells_sorted[new_highlight]
            else:
                new_highlight = cells_sorted[0]
            self.highlight_trace(new_highlight, val=True)
            self.update_highlight()

        elif evt.keysym in KEYS_HIGHLIGHT_CELL:
            # Toggle cell selection
            for i in cells_highlight:
                self.select_trace(cells_sorted[i])
            self.update_selection()

    def _key_scroll_frames(self, evt):
        """Callback for scrolling through channels"""
        if evt.keysym in KEYS_NEXT_FRAME:
            if evt.state & EVENT_STATE_CTRL:
                cmd = 'up10'
            else:
                cmd = 'up'
        elif evt.keysym in KEYS_PREV_FRAME:
            if evt.state & EVENT_STATE_CTRL:
                cmd = 'down10'
            else:
                cmd = 'down'
        else:
            return
        clock = Event.now()
        if clock - self.last_frame_scroll < 1 / FRAME_SCROLL_RATE_MAX:
            return
        self.last_frame_scroll = clock
        self.stackviewer._i_frame_step(cmd)

    def _key_jump_frames(self, evt):
        """Callback for jumping to first or last frame"""
        if evt.keysym in KEYS_FIRST_FRAME:
            i_frame = 0
        elif evt.keysym in KEYS_LAST_FRAME:
            i_frame = -1
        else:
            return
        self.last_frame_scroll = Event.now()
        self.stackviewer.i_frame_jump(i_frame)

    def _key_change_channel(self, evt):
        """Callback for displaying channels"""
        if not self.channel_order:
            return
        try:
            new_chan = int(evt.keysym[-1]) - 1
            new_chan = self.channel_order[new_chan]
        except Exception:
            return
        self._change_channel_selection(new_chan)

    def _build_chanselbtn_callback(self, i):
        """Build callback for channel selection button.

        `i` is the key of the corresponding item in `self.channel_selection`.

        The returned callback will, by default, select the channel with key `i`
        and deselect all other buttons. However, if the control key is pressed
        simultaneously with the click, the selection of channel `i` is toggled.
        """
        def callback(event):
            nonlocal self, i
            self._change_channel_selection(i, toggle=bool(event.state & EVENT_STATE_CTRL), default=i)
        return callback

    def _change_channel_selection(self, *channels, toggle=False, default=None):
        """Select channels for display.

        `channels` holds the specified channels (indices to `self.channel_selection`).
        If `toggle`, the selections of the channels in `channels` are toggled.
        If not `toggle`, the channels in `channels` are selected and all others are deselected.
        If `default` is defined, it must be an index to `self.channel_selection`.
        The channel corresponding to `default` is selected if no other channel would
        be displayed after executing this function.
        """
        has_selected = False
        if not channels:
            pass
        elif toggle:
            for i in channels:
                ch = self.channel_selection[i]
                ch['val'] ^= True
                has_selected = ch['val']
        else:
            for i, ch in self.channel_selection.items():
                if i in channels:
                    ch['val'] = True
                    has_selected = True
                else:
                    ch['val'] = False
        if not has_selected and \
                not any(ch['val'] for ch in self.channel_selection.values()):
            if default is None:
                default = 0
            ch = self.channel_selection[self.channel_order[default]]
            ch['val'] = True
        self.display_stack._listeners.notify('image')
        self.root.after_idle(self._update_channel_selection_button_states)

    def _update_channel_selection_button_states(self):
        """Helper function

        Called by `_change_channel_selection` after all GUI updates
        are processed. Necessary because otherwise, changes would be
        overwritten by ButtonRelease event.
        """
        for ch in self.channel_selection.values():
            ch['button'].config(relief=(tk.SUNKEN if ch['val'] else tk.RAISED))

    def make_display_render_function(self, stack, render_segmentation):
        """Factory function for display rendering function.

        stack -- metastack of session instance
        render_segmentation -- function for rendering binary segmentation image
        """
        def render_display(meta, frame, scale=None):
            """Dynamically create display image.

            This method is to be called by `MetaStack.get_image`
            within the GUI thread.

            Arguments:
                meta -- the calling `MetaStack` instance; ignored
                frame -- the index of the selected frame
                scale -- scaling information; ignored
            """
            nonlocal self, stack, render_segmentation
            #TODO histogram-based contrast adjustment
            # Find channel to display
            channels = []
            for i in sorted(self.channel_selection.keys()):
                if self.channel_selection[i]['val']:
                    channels.append(i)
            if not channels:
                channels.append(0)

            # Update frame indicator
            self.root.after_idle(self._update_frame_indicator)

            # Get image scale
            self.root.update_idletasks()
            display_width = self.stackframe.winfo_width()
            if self.display_stack.width != display_width:
                scale = display_width / stack.width
            else:
                scale = self.display_stack.width / stack.width

            # Convert image to uint8
            imgs = []
            seg_img = None
            for i in channels:
                img = stack.get_image(channel=i, frame=frame)
                img = stack.scale_img(img, scale=scale)
                if stack.spec(i).type != const.CH_CAT_BIN:
                    if self.var_darken_deselected.get():
                        # Darken deselected and untracked cells
                        if seg_img is None:
                            seg_img = render_segmentation(stack, frame,
                                    rois=False, binary=True)
                            seg_img = ms.MetaStack.scale_img(seg_img, scale=scale)
                        bkgd = img[seg_img < .5].mean()
                        img = seg_img * (const.DESELECTED_DARKEN_FACTOR * img \
                                + (1 - const.DESELECTED_DARKEN_FACTOR) * bkgd) \
                              + (1 - seg_img) * img
                    img_min, img_max = img.min(), img.max()
                    img = ((img - img_min) * (255 / (img_max - img_min)))
                imgs.append(img)
            if len(imgs) > 1:
                img = np.mean(imgs, axis=0)
            else:
                img = imgs[0]
            img_min, img_max = img.min(), img.max()
            img = ((img - img_min) * (255 / (img_max - img_min))).astype(np.uint8)

            return img
        return render_display

    def update_traces(self):
        self._update_traces_display_buttons()
        self._update_microscope_resolution()
        self.plot_traces()

    def _update_traces_display_buttons(self):
        """Redraw buttons for selecting which quantities to plot"""
        self.plotsellbl.config(state=tk.NORMAL)
        for child in self.plotselframe.winfo_children():
            child.pack_forget()
        for name, info in sorted(self.session.trace_info.items(), key=lambda x: x[1]['order']):
            if info['button'] is None:
                if info['label']:
                    btn_txt = f"{name}\n{info['label']}"
                else:
                    btn_txt = name
                info['button'] = tk.Checkbutton(self.plotselframe, text=btn_txt,
                        justify=tk.LEFT, indicatoron=False,
                        command=lambda btn=name: self._update_traces_display(button=btn))
                info['var'] = tk.BooleanVar(info['button'], value=info['plot'])
                info['button'].config(variable=info['var'])
            info['button'].pack(anchor=tk.S, expand=True, fill=tk.X, padx=10, pady=5)

    def _update_traces_display(self, button=None):
        """Update plot after changing quantities to plot"""
        if button is not None:
            info = self.session.trace_info[button]
            info['plot'] = info['var'].get()
        else:
            for info in self.session.trace_info.values():
                info['var'].set(info['plot'])
        if not any(info['plot'] for info in self.session.trace_info.values()):
            if button is not None:
                info = self.session.trace_info[button]
                info['plot'] ^= True
                info['var'].set(info['plot'])
            else:
                for info in self.session.trace_info.values():
                    info['plot'] = True
                    info['var'].get(True)
        self.plot_traces()

    def plot_traces(self):
        """Plots the traces to the main window"""
        self.frame_indicators.clear()
        self.fig.clear()
        self.session.plot_traces(self.fig, is_interactive=True,
                frame_indicator_list=self.frame_indicators, status=self.status)
        self._update_frame_indicator(draw=False)
        self.fig.tight_layout(pad=.3)
        self.fig.canvas.draw()

    def _update_frame_indicator(self, *_, t=None, fr=None, draw=True):
        """Update display of vertical frame indicator in plot"""
        if self.var_show_frame_indicator.get():
            if t is None:
                if fr is None:
                    fr = self.stackviewer.i_frame
                t = self.session.to_hours(fr)
        else:
            t = np.NaN
        for indicator in self.frame_indicators:
            indicator.set_xdata([t, t])
        if draw:
            self.fig.canvas.draw()

    def _line_picker(self, event):
        """Callback for clicking on line in plot"""
        if not event.mouseevent.button == MouseButton.LEFT:
            return
        i = event.artist.get_label()
        self.highlight_trace(i)
        self.update_highlight()

    def highlight_trace(self, *trace, val=None, update_select=False):
        """Change highlight state of one or more traces.

        `trace` must be valid keys to `self.session.traces`.
        `val` specifies whether to highlight (True) the
        traces or not (False) or to toggle (None) highlighting.
        If `update_select` is True, a non-selected cell is
        selected before highlighting it; else, highlighting
        is ignored.

        This method does not update display.
        To update display, call `self.update_highlight`.

        If `update_select` is True, a return value of True
        indicates that a cell selection has changed. In this case,
        the user is responsible to call `self.update_selection`.
        """
        is_selection_updated = False
        if len(trace) > 1:
            for tr in trace:
                ret = self.highlight_trace(tr, val=val, update_select=update_select)
                if update_select and ret:
                    is_selection_updated = True
            return is_selection_updated
        else:
            trace = trace[0]
        tr = self.session.traces[trace]
        if val is None:
            val = not tr['highlight']
        elif val == tr['highlight']:
            return
        if not tr['select'] and val and update_select:
            self.select_trace(trace, val=True)
            is_selection_updated = True
        tr['highlight'] = val
        if val:
            if tr['select']:
                for plots in tr['plot'].values():
                    for plot in plots:
                        plot.set_color(const.PLOT_COLOR_HIGHLIGHT)
                        plot.set_lw(const.PLOT_WIDTH_HIGHLIGHT)
                        plot.set_alpha(const.PLOT_ALPHA_HIGHLIGHT)
                for fr, roi in enumerate(tr['roi']):
                    self.session.rois[fr][roi].stroke_width = const.ROI_WIDTH_HIGHLIGHT
                    self.session.rois[fr][roi].color = const.ROI_COLOR_HIGHLIGHT
            else:
                for fr, roi in enumerate(tr['roi']):
                    self.session.rois[fr][roi].stroke_width = const.ROI_WIDTH_HIGHLIGHT
                    self.session.rois[fr][roi].color = const.ROI_COLOR_DESELECTED
        else:
            if tr['select']:
                for plots in tr['plot'].values():
                    for plot in plots:
                        plot.set_color(const.PLOT_COLOR)
                        plot.set_lw(const.PLOT_WIDTH)
                        plot.set_alpha(const.PLOT_ALPHA)
            for fr, roi in enumerate(tr['roi']):
                self.session.rois[fr][roi].stroke_width = const.ROI_WIDTH
                if tr['select']:
                    self.session.rois[fr][roi].color = const.ROI_COLOR_SELECTED
                else:
                    self.session.rois[fr][roi].color = const.ROI_COLOR_DESELECTED
        return is_selection_updated

    def select_trace(self, *trace, val=None, update_highlight=False):
        """Change selection state of one or more traces.

        `trace` must be valid keys to `self.traces`.
        `val` specifies whether to select (True),
        deselect (False) or toggle (None) the selection.
        `update_highlight` specifies whether to remove
        highlighting (True) when a cell is deselected.

        This method does not update display.
        To update display, call `self.update_selection`.
        """
        if len(trace) > 1:
            for tr in trace:
                self.select_trace(tr, val=val)
            return
        else:
            trace = trace[0]
        tr = self.session.traces[trace]
        if val is None:
            val = not tr['select']
        elif val == tr['select']:
            return
        tr['select'] = val
        if val:
            roi_color = const.ROI_COLOR_HIGHLIGHT if tr['highlight'] else const.ROI_COLOR_SELECTED
            for fr, roi in enumerate(tr['roi']):
                self.session.rois[fr][roi].color = roi_color
        else:
            if update_highlight:
                self.highlight_trace(trace, val=False)
            for fr, roi in enumerate(tr['roi']):
                self.session.rois[fr][roi].color = const.ROI_COLOR_DESELECTED

    def update_highlight(self):
        """Redraw relevant display portions after highlight changes.

        Note: All tasks performed by `update_highlight` are also
        included in `update_selection`. Running both methods at
        the same time is not necessary.
        """
        self.fig.canvas.draw()
        self.display_stack._listeners.notify('roi')

    def update_selection(self):
        """Read traces after selection changes and update display"""
        self.plot_traces()
        self.display_stack._listeners.notify('roi')
        if self.var_darken_deselected.get():
            self.display_stack._listeners.notify('image')

    def update_roi_display(self, notify_listeners=True):
        """Update all ROIs.

        This method updates all display properties of all ROIs.
        """
        # Update untracked cells
        show_contour = self.var_show_untrackable.get() and self.var_show_roi_contours.get()
        for frame in self.session.rois:
            for roi in frame.values():
                if roi.name:
                    continue
                roi.color = const.ROI_COLOR_UNTRACKABLE
                roi.stroke_width = const.ROI_WIDTH
                roi.visible = show_contour

        # Update tracked cells
        show_contour = self.var_show_roi_contours.get()
        show_name = self.var_show_roi_names.get()
        for trace in self.session.traces.values():
            is_select = trace['select']
            is_highlight = trace['highlight']
            if not is_select:
                color = const.ROI_COLOR_DESELECTED
            elif is_highlight:
                color = const.ROI_COLOR_HIGHLIGHT
            else:
                color = const.ROI_COLOR_SELECTED
            if is_highlight:
                width = const.ROI_WIDTH_HIGHLIGHT
            else:
                width = const.ROI_WIDTH
            for ref, rois in zip(trace['roi'], self.session.rois):
                roi = rois[ref]
                roi.color = color
                roi.visible = show_contour
                roi.name_visible = show_name
                roi.stroke_width = width
        if notify_listeners:
            self.display_stack._listeners.notify('roi')

    def _roi_clicked(self, event, names):
        """Callback for click on ROI"""
        if not names:
            return
        is_selection_updated = False
        mode = self.var_mode.get()
        if event.state & EVENT_STATE_SHIFT:
            if mode == MODE_HIGHLIGHT:
                mode = MODE_SELECTION
            elif mode == MODE_SELECTION:
                mode = MODE_HIGHLIGHT
        if mode == MODE_HIGHLIGHT:
            for name in names:
                try:
                    is_selection_updated |= self.highlight_trace(name, update_select=True)
                except KeyError:
                    continue
            self.update_highlight()
        elif mode == MODE_SELECTION:
            for name in names:
                try:
                    self.select_trace(name, update_highlight=True)
                except KeyError:
                    continue
            is_selection_updated = True
        if is_selection_updated:
            self.update_selection()

    def _update_show_roi_contours(self, *_):
        """Update stackviewer after toggling ROI contour display"""
        show_contours = self.var_show_roi_contours.get()
        show_untrackable = show_contours and self.var_show_untrackable.get()
        for rois in self.session.rois:
            for roi in rois.values():
                if roi.name:
                    roi.visible = show_contours
                else:
                    roi.visible = show_untrackable
        self.display_stack._listeners.notify('roi')

    def _update_show_roi_names(self, *_):
        """Update stackviewer after toggling ROI name display"""
        show_names = self.var_show_roi_names.get()
        if show_names:
            show_untrackable = self.var_show_untrackable.get()
        else:
            show_untrackable = False
        for rois in self.session.rois:
            for roi in rois.values():
                if roi.name:
                    roi.name_visible = show_names
                else:
                    roi.name_visible = show_untrackable
        self.display_stack._listeners.notify('roi')

    def _update_show_untrackable(self, *_):
        """Update stackviewer after toggling display of untrackable cells"""
        show = self.var_show_untrackable.get() and self.var_show_roi_contours.get()
        for rois in self.session.rois:
            for roi in rois.values():
                if not roi.name:
                    roi.visible = show
        self.display_stack._listeners.notify('roi')

    def _add_to_microscope_menu(self, value, label=None):
        """Adds a radiobutton to the microscope menu.

        Arguments:
            value -- the key to the `MIC_RES` dict
            label -- display name; if missing, equals `value`

        The radiobutton is inserted at the end of the menu.
        """
        if label is None:
            label = value
        self.micresmenu.add_radiobutton(label=label,
                    value=value,
                    variable=self.var_microscope_res,
                    command=lambda v=value: self._change_microscope_resolution(v),
                    )

    def _change_microscope_resolution(self, mic_res):
        """Callback for changing microscope resolution

        `mic_res` is the key of `MIC_RES` that should be loaded.
        """
        if mic_res == MIC_RES_CUSTOM:
            initval = {}
            if MIC_RES[MIC_RES_CUSTOM] is not None:
                initval = MIC_RES[MIC_RES_CUSTOM]
            else:
                initval = 1
            res = tksd.askfloat(
                    "Microscope resolution",
                    "Enter custom microscope resolution [µm/px]:",
                    minvalue=0, parent=self.root, initialvalue=initval)
            res_dict = dict(resolution=res)
        elif mic_res == MIC_RES_UNSPEC:
            res_dict = {}
        else:
            res_dict = dict(name=mic_res, resolution=MIC_RES[mic_res])
        Event.fire(self.control_queue, const.CMD_SET_MICROSCOPE, self.session, **res_dict)

    def _update_microscope_resolution(self):
        """Display updates of microscope resolution.

        This method should not be called explicitly.
        It is called by `SessionView_Tk.update_traces`.
        """
        new_mic_name = self.session.mic_name
        new_mic_res = self.session.mic_res

        if not new_mic_res:
            # use pixel as length unit
            new_mic_name = MIC_RES_UNSPEC
            new_mic_res = None
        elif new_mic_name:
            if new_mic_name not in MIC_RES:
                # enter new_mic_name into MIC_RES
                self._add_to_microscope_menu(new_mic_name)
                MIC_RES[new_mic_name] = new_mic_res
            elif MIC_RES[new_mic_name] != new_mic_res:
                # name/value conflict with catalogue
                new_mic_name = MIC_RES_CUSTOM
        else:
            # custom (unnamed) resolution
            new_mic_name = MIC_RES_CUSTOM

        # Update display for custom resolution
        if new_mic_name == MIC_RES_CUSTOM:
            MIC_RES[MIC_RES_CUSTOM] = new_mic_res
            new_label = f"{MIC_RES_CUSTOM} ({new_mic_res} µm/px)"
        else:
            new_label = MIC_RES_CUSTOM

        # Apply changes
        self.micresmenu.entryconfig(MIC_RES_CUSTOM_IDX, label=new_label)
        if new_mic_name != self.var_microscope_res.get():
            self.var_microscope_res.set(new_mic_name)
        #if self.session.trace_info[const.DT_CAT_AREA]['plot']:
        #    self.plot_traces()

    def open_session(self):
        """Open a saved session"""
        fn = tkfd.askopenfilename(title="Open session data",
                                  initialdir='.',
                                  parent=self.root,
                                  filetypes=(("Session files", '*.zip *.json'), ("All files", '*')),
                                 )
        if fn is None:
            return

        # Forward filename to controller
        Event.fire(self.control_queue, const.CMD_READ_SESSION_FROM_DISK, fn)

    def binarize(self):
        # Get filename
        options = {'defaultextension': '.tif',
                   'filetypes': ( ("Numpy", '*.npy *.npz'), ("TIFF", '*.tif *.tiff'), ("All files", '*')),
                   'parent': self.root,
                   'title': "Choose output file for binarized phase-contrast stack",
                  }
        if self.save_dir:
            options['initialdir'] = self.save_dir
        outfile = tkfd.asksaveasfilename(**options)
        if not outfile:
            return

        # Start binarization
        Event.fire(self.control_queue,
                   const.CMD_TOOL_BINARIZE,
                   session=self.session,
                   outfile=outfile,
                   status=self.status,
                   )

    def _background_correction(self):
        """Write a background-corrected version of the fluorescence channel"""

        # Get filename
        options = {'defaultextension': '.tif',
                   'filetypes': ( ("TIFF", '*.tif *.tiff'), ("All files", '*') ),
                   'parent': self.root,
                   'title': "Choose output file for background-corrected fluorescence channel",
                  }
        if self.save_dir:
            options['initialdir'] = self.save_dir
        outfile = tkfd.asksaveasfilename(**options)
        if not outfile:
            return

        # Start background correction
        Event.fire(self.control_queue,
                   const.CMD_TOOL_BGCORR,
                   session=self.session,
                   outfile=outfile,
                   status=self.status,
                  )


    def _pickle_max_bbox(self):
        """Export bounding box of maximum extension of each selected cell"""
        if self.session is None or not self.session.traces:
            print("No ROIs to export")
            return

        options = dict(defaultextension='.pickle',
                       filetypes=(("Pickle", '*.pickle'), ("All", '*')),
                       parent=self.root,
                       title="Save bounding boxes as …",
                      )
        if self.save_dir:
            options['initialdir'] = self.save_dir
        save_name = tkfd.asksaveasfilename(**options)
        if not save_name:
            return

        from ..tools.roi_bboxer import get_selected_bboxes
        get_selected_bboxes(self.session, save_name)
