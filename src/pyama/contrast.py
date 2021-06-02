from .gui_tk import get_root
import numpy as np
import tkinter as tk

class ContrastAdjuster:
    def __init__(self, sv):
        """Constructor of ContrastAdjuster frame.

@param sv StackViewer to which the ContrastAdjuster belongs
<!-- <!-- :type sv: --> <!-- :py:class: --> -->`StackViewer`
        """
        # Initialize attributes
        self.img = None
        self.hist_max = 255
        self.i_frame = None
        self.i_channel = None
        self.img_min = None
        self.img_max = None
        self.limit_line = None

        self.pmin = True
        self.pmax = True

        self.mouse_state = None
        self.mouse_moved = False
        self.former_mouse_x = None

        # Build GUI
        root = get_root(sv.mainframe)

        self.stackviewer = sv
        self.trace_frame = sv.i_frame_var.trace_add("write",
            self.select_new_image)
        self.trace_channel = sv.i_channel_var.trace_add("write",
            self.select_new_image)

        self.mainframe = tk.Toplevel(root)
        self.mainframe.resizable(False, False)
        self.mainframe.title("Adjust contrast")
        self.mainframe.bind("<Destroy>", self.close)

        self.histcan = tk.Canvas(self.mainframe, width=256, height=100,
            background="white", highlightthickness=0, borderwidth=0)
        root.update_idletasks()
        self.histcan.pack()

        frame = tk.Frame(self.mainframe, relief=tk.FLAT)
        frame.pack(fill=tk.X, expand=False)
        self.min_label = tk.Label(frame, text="min")
        self.min_label.pack(side=tk.LEFT, anchor=tk.W)
        self.max_label = tk.Label(frame, text="max")
        self.max_label.pack(side=tk.RIGHT, anchor=tk.E)

        self.scale_var = tk.StringVar(self.mainframe, value='NONE')
        b = tk.Radiobutton(self.mainframe, text="No scaling",
            command=self._update_scaling,
            variable=self.scale_var, value='NONE')
        b.pack(anchor=tk.W)
        b = tk.Radiobutton(self.mainframe, text="Linear scaling",
            command=self._update_scaling,
            variable=self.scale_var, value='LINEAR')
        b.pack(anchor=tk.W)
        b = tk.Radiobutton(self.mainframe, text="Logarithmic scaling",
            command=self._update_scaling,
            variable=self.scale_var, value='LOG')
        b.pack(anchor=tk.W)
        b = tk.Radiobutton(self.mainframe, text="Cumulative sum",
            command=self._update_scaling,
            variable=self.scale_var, value='EQUALIZE')
        b.pack(anchor=tk.W)

        self.auto_limit_var = tk.BooleanVar(self.mainframe, value=True)
        b = tk.Checkbutton(self.mainframe, text="Auto limit",
            command=self._update_limit_mode,
            variable=self.auto_limit_var, anchor=tk.W)
        b.pack(fill=tk.X, anchor=tk.W, expand=True)


        # Setup
        self.select_new_image()
        self.draw_limit_line()

        self.histcan.bind("<Button-1>", self._limit_selection_action)
        self.histcan.bind("<B1-Motion>", self._limit_selection_action)
        self.histcan.bind("<ButtonRelease-1>", self._limit_selection_finished)
        self.histcan.bind("<Motion>", self._draw_handle)
        self.histcan.bind("<Leave>", lambda _: self.histcan.delete("c"))


    def close(self, *_, isDisplayUpdate=True):
        """Close the ContrastAdjuster frame.

After closing, the contrast settings will be discarded.
        """
        self.stackviewer.contrast_adjuster = None

        if self.trace_frame is not None:
            self.stackviewer.i_frame_var.trace_remove("write", self.trace_frame)
            self.trace_frame = None
        if self.trace_channel is not None:
            self.stackviewer.i_channel_var.trace_remove("write", self.trace_channel)
            self.trace_channel = None

        # Inhibit multiple calls to this callback
        self.mainframe.unbind("<Destroy>")
        self.mainframe.destroy()

        if isDisplayUpdate:
            self._update_display()


    def select_new_image(self, *_):
        """Update contrast adjuster to new image"""
        i_frame = self.stackviewer.i_frame_var.get() - 1
        i_channel = self.stackviewer.i_channel_var.get() - 1

        try:
            self.img = self.stackviewer.stack.get_image(
                channel=i_channel, frame=i_frame)
            self.img_min = self.img.min()
            self.img_max = self.img.max()
        except Exception:
            self.img = None
            self.img_min = None
            self.img_max = None

        self.draw_hist()
        if self.scale_var.get() == 'EQUALIZE':
            self.limit_line = None
            self.draw_limit_line()


    def _update_scaling(self, *_):
        """Update information of the image (like color extrema)"""
        if self.scale_var.get() != 'NONE' and self.auto_limit_var.get():
            self._set_limits()
        else:
            self.update_limit_line()
        self._update_display()


    def _update_limit_mode(self):
        """Change between automatic and manual limit selection"""
        if self.auto_limit_var.get():
            self._set_limits()
            self._update_display()
        else:
            if self.scale_var.get() == 'NONE':
                self.scale_var.set('LINEAR')
            pmin, pmax = self._get_limits()
            self._set_limits(pmin, pmax)


    def _get_movement_action(self, y, height=None):
        """
Assess which limit movement action to perform

The movement action is determined by the y-position of the
mouse pointer on the canvas.
The following positions are possible:

* If the mouse is in the upper quarter of the canvas, move the maximum (returns ``MAX``).
* If the mouse is in the middle two quarters of the canvas, move both minimum and maximum (returns ``BOTH``).
* If the mouse is in the lower quarter of the canvas, move the minimum (returns ``MIN``).

If the height of the histogram canvas has already been retrieved,
if can be given as additional argument to reduce computational load.

@param y Mouse position on canvas
<!-- :type y: --> scalar numerical
@param height Height of histogram canvas (optional)
<!-- :type height: --> int
@return  The determined movement action
<!-- :rtype: --> str
        """
        # Get histogram height
        if height is None:
            self.histcan.update_idletasks()
            height = self.histcan.winfo_height()

        # Decide which action to perform
        if y < .25 * height:
            action = "MAX"
        elif y <= .75 * height:
            action = "BOTH"
        else:
            action = "MIN"
        return action


    def _limit_selection_action(self, evt):
        """Callback for manual limit selection"""
        # Set to manual limit mode
        if self.auto_limit_var.get():
            self.auto_limit_var.set(False)
            self._update_limit_mode()
        elif self.scale_var.get() == 'NONE':
            self.scale_var.set('LINEAR')

        # Get action (hysteresis for better usability)
        if self.mouse_state is None:
            action = self._get_movement_action(evt.y)
            self.mouse_state = action
        else:
            action = self.mouse_state

        # Get histogram properties
        self.histcan.update_idletasks()
        height = self.histcan.winfo_height()
        width = self.histcan.winfo_width()

        # Get current limits
        old_pmin, old_pmax = self._get_limits()

        # Get requested limits based on action
        if action == "MAX":
            new_max = evt.x
            new_min = None
        elif action == "MIN":
            new_max = None
            new_min = evt.x
        elif action == "BOTH":
            a = (old_pmax - old_pmin) * width / height / self.hist_max
            new_y = height - evt.y
            new_min = -a * new_y + evt.x
            new_max = a * (height - new_y) + evt.x

        # Transform new limits to canvas coordinates
        if new_min is not None:
            new_min *= self.hist_max / width
        if new_max is not None:
            new_max *= self.hist_max / width

        # Prevent limits from unphysical values
        if action == "BOTH":
            if new_min < 0:
                diff = new_min
            elif new_max > self.hist_max:
                diff = new_max - self.hist_max
            else:
                diff = 0
            new_min -= diff
            new_max -= diff

        elif new_min is not None:
            if new_min < 0:
                new_min = 0
            elif new_min >= self.hist_max:
                new_min = self.hist_max - 1
                new_max = self.hist_max
            elif new_min >= old_pmax:
                new_max = new_min + 1

        elif new_max is not None:
            if new_max < 1:
                new_max = 1
                new_min = 0
            elif new_max > self.hist_max:
                new_max = self.hist_max
            elif new_max <= old_pmin:
                new_min = new_max - 1

        # Update limits
        self._set_limits(new_min, new_max)
        self._draw_handle(evt)
        self._update_display()


    def _limit_selection_finished(self, evt):
        """Callback for limit selection (mouse release)"""
        # Reset limit movement control variables
        self.mouse_state = None


    def _set_limits(self, new_min=None, new_max=None):
        """Set limits of the colormap

Limits can be given as parameters.
Otherwise, they will be determined automatically.

@param new_min requested minimum (optional)
<!-- :type new_min: --> integer >=0
@param new_max requested maximum (optional)
<!-- :type new_max: --> integer >=1
        """
        if new_min is not None or new_max is not None:
            # Limits are given as parameters
            if new_min is not None:
                self.pmin = new_min
            if new_max is not None:
                self.pmax = new_max
        else:
            # Automatic limits
            self.pmax = True
            self.pmin = True
        self.update_limit_line()

    def _get_limits(self, img=None):
        if self.scale_var.get() == 'NONE':
            if img is not None:
                iinfo = np.iinfo(img.flat[0])
                pmin = iinfo.min
                pmax = iinfo.max
            elif self.img is not None:
                iinfo = np.iinfo(self.img.flat[0])
                pmin = iinfo.min
                pmax = iinfo.max
            else:
                pmin = 0
                pmax = 255
        else:
            if self.pmin is True:
                if img is not None:
                    pmin = img.min()
                elif self.img is not None:
                    pmin = self.img_min
                else:
                    pmin = 0
            else:
                pmin = self.pmin

            if self.pmax is True:
                if img is not None:
                    pmax = img.max()
                elif self.img is not None:
                    pmax = self.img_max
                else:
                    pmax = 255
            else:
                pmax = self.pmax
        return pmin, pmax


    def image_in_limits(self, img):
        # Get scaling limits for this image
        pmin, pmax = self._get_limits(img)

        # Find pixels inside and outside of limits
        mask_min = img <= pmin
        mask_max = img >= pmax
        mask_between = ~(mask_min | mask_max)
        img_between = img[mask_between]

        return pmin, pmax, img_between, (mask_min, mask_max, mask_between)


    def update_limit_line(self):
        self.limit_line = None
        if self.img is None:
            pass
        else:
            pmin, pmax, img_between, _ = self.image_in_limits(self.img)
            scale_cmd = self.scale_var.get()
            if scale_cmd == 'EQUALIZE':
                uvals, inverse_idx, counts = np.unique(img_between, return_inverse=True, return_counts=True)
                cumsum = np.cumsum(counts) / counts.sum()
                self.limit_line = np.stack([uvals, cumsum], axis=-1)
            elif scale_cmd == 'LOG':
                a = 1 / np.log(pmax - pmin + 1)
                supp = np.linspace(pmin, pmax)
                self.limit_line = np.stack((supp, a * np.log(supp - pmin + 1)), axis=-1)
        self.draw_limit_line()


    def convert(self, img):
        """Convert an image to uint8

The image is scaled depending on the settings of control variables
of this ContrastAdjuster instance.

@param img The image to be scaled
<!-- :type img: --> 2-dim numpy array

@return  The converted image
<!-- :rtype: --> 2-dim numpy array with dtype uint8
        """
        pmin, pmax, img_between, (mask_min, mask_max, mask_between) = self.image_in_limits(img)

        # Create and populate scaled display image
        img8 = np.empty_like(img, dtype=np.uint8)
        img8[mask_min] = 0
        img8[mask_max] = 255

        scale_cmd = self.scale_var.get()
        if scale_cmd == 'EQUALIZE':
            uvals, inverse_idx, counts = np.unique(img_between, return_inverse=True, return_counts=True)
            cumsum = np.rint(np.cumsum(counts) * (255 / counts.sum())).astype(np.uint8)
            img8[mask_between] = cumsum[inverse_idx]
        elif scale_cmd == 'LOG':
            a = 1 / np.log(pmax - pmin + 1)
            img8[mask_between] = np.rint(255 * a * np.log(img[mask_between] - pmin + 1)).astype(np.uint8)
        else:
            img8[mask_between] = np.round((img[mask_between] - pmin) / (pmax / 255))

        return img8


    def draw_hist(self):
        """Calculate the image histogram."""
        # Check for existing image
        if self.img is None:
            self.histcan.delete("h")
            self.hist_max = 255
            return

        # Get the maximum of the histogram
        if self.img_max <= 0xff:
            self.hist_max = 0xff        # 8-bit
        elif self.img_max <= 0x0fff:
            self.hist_max = 0x0fff      # 12-bit
        elif self.img_max <= 0x3fff:
            self.hist_max = 0x3fff      # 14-bit
        else:
            self.hist_max = 0xffff      # 16-bit

        # Calculate histogram
        self.histcan.update_idletasks()
        n_bins = self.histcan.winfo_width()
        hist_height = self.histcan.winfo_height()

        histogram = np.histogram(self.img, bins=n_bins, range=(0, self.hist_max), density=True)[0]
        histogram = histogram * (hist_height / histogram.max())

        # Draw histogram
        self.histcan.delete("h")
        for i, x in enumerate(histogram):
            self.histcan.create_line(i, hist_height, i, hist_height - x, tags="h")
        self.histcan.tag_lower("h")

    def check_limit_line(self):
        """Bring cached points of limit line in correct format"""
        pmin, pmax = self._get_limits()
        if self.limit_line is None or self.limit_line.size == 0:
            self.limit_line = np.array([[pmin, 0], [pmax, 1]])
        if self.limit_line[0, 0] != 0:
            np.concatenate(([[0, 0]], self.limit_line))
        if self.limit_line[-1, 0] < self.hist_max:
            np.concatenate((self.limit_line, [[self.hist_max, 1]]))
        elif self.limit_line[-1, 0] > self.hist_max:
            self.limit_line = None
            self.check_limit_line()
        self.min_label["text"] = "{:.0f}".format(pmin)
        self.max_label["text"] = "{:.0f}".format(pmax)

    def draw_limit_line(self):
        """Draw line indicating limits in histogram"""
        self.histcan.update_idletasks()
        width = self.histcan.winfo_width()
        height = self.histcan.winfo_height()

        self.check_limit_line()
        limit_line = self.limit_line.copy()
        limit_line[:, 1] = 1 - limit_line[:, 1]
        limit_line = limit_line * np.array([[width/self.hist_max, height]])

        self.histcan.delete("l")
        self.histcan.create_line(*limit_line.flatten(), fill="red", tags="l")


    def _draw_handle(self, evt):
        """
Draw handle (point on line) in histogram.

The handle is a help to intuitively grasp the action that will be,
or in case of mouse button pressed, is being performed.
The action is one of "move the maximum", "move the minimum" and
"move both maximum and minimum/move limits".

@param evt The mouse event causing this call
        """
        pmin, pmax = self._get_limits()

        # Get canvas properties
        self.histcan.update_idletasks()
        width = self.histcan.winfo_width()
        height = self.histcan.winfo_height()

        # Get action
        if self.mouse_state is None:
            action = self._get_movement_action(evt.y, height)
        else:
            action = self.mouse_state

        # Get handle position
        if action == "MIN":
            x_handle = width * pmin / self.hist_max
            y_handle = height
        elif action == "MAX":
            x_handle = width * pmax / self.hist_max
            y_handle = 0
        else:
            self.check_limit_line()
            y_evt = 1 - evt.y / height
            yi_above = np.searchsorted(self.limit_line[:, 1], y_evt, side='right')
            x_above, y_above = self.limit_line[yi_above, :]
            x_below, y_below = self.limit_line[yi_above-1, :]

            if y_above == y_below:
                x_handle = (x_above + x_below) / 2
            else:
                x_handle = (x_above - x_below) / (y_above - y_below) * (y_evt - y_below) + x_below

            x_handle *= width / self.hist_max
            y_handle = evt.y

        # Draw new handle
        r = 4
        self.histcan.delete("c")
        self.histcan.create_oval(x_handle-r, y_handle-r, x_handle+r, y_handle+r, fill="red", outline="", tags="c")


    def get_focus(self):
        """Give focus to this ContrastAdjuster frame"""
        self.mainframe.focus_set()
        self.mainframe.lift()

    def _update_display(self):
        """Cause the StackViewer to update the displayed image"""
        self.stackviewer._show_img()
