from listener import Listeners
import math
import numpy as np
import tkinter as tk
import tkinter.ttk as ttk

UNIT_px = 'px'
UNIT_µm = 'µm'
TYPE_RECT = 'rect'
TYPE_SQUARE = 'sqare'

PAD_COLUMN_SEP = 20
RED_FLASH_MS = 300

ROI_TAG = "roi"
ROI_DRAFT_TAG = "roi_draft"
X = 0
Y = 1


def new_roi_selector(sv):
    return RoiSelector(sv)


def float2str(f, var=None):
    """
    Convert float to nicely formatted string
    
    :param f: float to convert to string
    :type f: float
    :param var: (optional) tkinter.StringVar to write value to
    :type var: None or tkinter.StringVar
    :return: string with nicely formatted float, or None
    :rtype: str or None
    """
    s = "{:f}".format(f)
    idx_point = s.find(".")
    if idx_point > -1:
        s = s.rstrip("0")
        if len(s) == idx_point + 1:
            s = s[:-1]
    if not s:
        s = "0"
    if var is not None:
        var.set(s)
    return s


def str2float(s, mustPositive=True, mustNonNegative=False):
    """
    Convert string to float

    :param s: The string or tkinter StringVar to convert
    :type s: str or tkinter.StringVar
    :param mustPositive: flag if value must be larger than 0
    :type mustPositive: bool
    :param mustNonNegative: flag if value must not be smaller than 0
    :type mustNonNegative: bool
    :return: the float value or None for invalid string
    :rtype: float or None
    """
    if type(s) != str:
        s = s.get()
    s = s.replace(',', '.')
    try:
        f = float(s)
    except Exception:
        return None
    if not np.isfinite(f):
        return None
    elif mustPositive and f <= 0:
        return None
    elif mustNonNegative and f < 0:
        return None
    else:
        return f


def flash_red(widget):
    """Make widget background flash red"""
    widget.config(background="red")
    widget.after(RED_FLASH_MS, lambda:widget.config(background="white"))


class RoiSelector:
    def __init__(self, sv):
        # Get StackViewer-related content
        self.sv = sv

        # Define control/logic variables
        self._listeners = Listeners(debug=True)
        self.unit_conv_fac = .6

        # Length unit is pixels, with 1px == `self.unit_conv_fac` µm
        # Angle unit is degree
        self._offset_x = 5
        self._offset_y = 0
        self._width = 50
        self._height = 50
        self._pad_x = 20
        self._pad_y = 20
        self._pivot_x = 0
        self._pivot_y = 0
        self._angle = 0
        self._max_x = self.sv.stack.width - 1
        self._max_y = self.sv.stack.height - 1

        # Set up window
        self.root = tk.Toplevel(sv.root)
        self.root.title("PyAMA ROI-Selector")
        self.root.event_add("<<Submit>>", "<Return>", "<KP_Enter>")

        # Define variables
        self.var_unit = tk.StringVar(self.root, value=UNIT_px)
        self.var_unit_px = tk.StringVar(self.root, value=1)
        self.var_unit_µm = tk.StringVar(self.root, value=1)
        self.var_type_roi = tk.StringVar(self.root, value=TYPE_SQUARE)
        self.var_offset_x = tk.StringVar(self.root, value=self._offset_x)
        self.var_offset_y = tk.StringVar(self.root, value=self._offset_y)
        self.var_width = tk.StringVar(self.root, value=self._width)
        self.var_height = tk.StringVar(self.root, value=self._height)
        self.var_pad_x = tk.StringVar(self.root, value=self._pad_x)
        self.var_pad_y = tk.StringVar(self.root, value=self._pad_y)
        self.var_pivot_x = tk.StringVar(self.root, value=self._pivot_x)
        self.var_pivot_y = tk.StringVar(self.root, value=self._pivot_y)
        self.var_angle = tk.StringVar(self.root, value=self._angle)

        # Build GUI

        ## Radio buttons
        self._new_label("Units:", 0, 0)
        tk.Radiobutton(self.root, text=UNIT_px, value=UNIT_px,
            variable=self.var_unit, anchor=tk.W).grid(row=0, column=1,
            columnspan=2, sticky=tk.W)
        tk.Radiobutton(self.root, text=UNIT_µm, value=UNIT_µm,
            variable=self.var_unit, anchor=tk.W).grid(row=0, column=4,
            columnspan=2, sticky=tk.W)

        self.entry_unit_px = tk.Entry(self.root, width=5,
            textvariable=self.var_unit_px, background="white")
        self.entry_unit_px.grid(row=1, column=1, sticky="WE")
        self.entry_unit_px.bind("<<Submit>>", self.update_unit_conversion)
        self._new_label(UNIT_px, 1, 2)
        self._new_label("=", 1, 3, pad=5)
        self.entry_unit_µm = tk.Entry(self.root, width=5,
            textvariable=self.var_unit_µm, background="white")
        self.entry_unit_µm.grid(row=1, column=4, sticky="WE")
        self.entry_unit_µm.bind("<<Submit>>", self.update_unit_conversion)
        self._new_label(UNIT_µm, 1, 5)

        self._new_label("Type:", 2, 0)
        tk.Radiobutton(self.root, text="Square", value=TYPE_SQUARE,
            variable=self.var_type_roi, anchor=tk.W).grid(row=2, column=1,
            columnspan=2, sticky=tk.W)
        tk.Radiobutton(self.root, text="Rectangle", value=TYPE_RECT,
            variable=self.var_type_roi, anchor=tk.W).grid(row=2, column=4,
            columnspan=2, sticky=tk.W)

        ## Build spinboxes
        self._new_label("x-Offset:", 3, 0)
        self.sp_offset_x = self._new_spinbox(self.var_offset_x, 3, 1)
        self._new_label(self.var_unit, 3, 2)
        self._new_label("y-Offset:", 3, 4)
        self.sp_offset_y = self._new_spinbox(self.var_offset_y, 3, 5)
        self._new_label(self.var_unit, 3, 6)

        self._new_label("Width:", 4, 0)
        self.sp_width = self._new_spinbox(self.var_width, 4, 1)
        self._new_label(self.var_unit, 4, 2)
        self._new_label("Height:", 4, 4)
        self.sp_height = self._new_spinbox(self.var_height, 4, 5)
        self._new_label(self.var_unit, 4, 6)

        self._new_label("x-Padding:", 5, 0)
        self.sp_pad_x = self._new_spinbox(self.var_pad_x, 5, 1)
        self._new_label(self.var_unit, 5, 2)
        self._new_label("y-Padding:", 5, 4)
        self.sp_pad_y = self._new_spinbox(self.var_pad_y, 5, 5)
        self._new_label(self.var_unit, 5, 6)

        self._new_label("x-Pivot:", 6, 0)
        self.sp_pivot_x = self._new_spinbox(self.var_pivot_x, 6, 1)
        self._new_label(self.var_unit, 6, 2)
        self._new_label("y-Pivot:", 6, 4)
        self.sp_pivot_y = self._new_spinbox(self.var_pivot_y, 6, 5)
        self._new_label(self.var_unit, 6, 6)

        self._new_label("Angle:", 7, 0)
        self.sp_angle = self._new_spinbox(self.var_angle, 7, 1)
        self._new_label("°", 7, 2)

        # Callbacks
        self.sp_offset_x.bind("<<Submit>>", self.submit_spinner)
        self.sp_offset_x.config(command=lambda: self.spinner_input(self.sp_offset_x))

        self.sp_offset_y.bind("<<Submit>>", self.submit_spinner)
        self.sp_offset_y.config(command=lambda: self.spinner_input(self.sp_offset_y))

        self.sp_width.bind("<<Submit>>", self.submit_spinner)
        self.sp_width.config(command=lambda: self.spinner_input(self.sp_width))

        self.sp_height.bind("<<Submit>>", self.submit_spinner)
        self.sp_height.config(command=lambda: self.spinner_input(self.sp_height))

        self.sp_pad_x.bind("<<Submit>>", self.submit_spinner)
        self.sp_pad_x.config(command=lambda: self.spinner_input(self.sp_pad_x))

        self.sp_pad_y.bind("<<Submit>>", self.submit_spinner)
        self.sp_pad_y.config(command=lambda: self.spinner_input(self.sp_pad_y))

        self.sp_pivot_x.bind("<<Submit>>", self.submit_spinner)
        self.sp_pivot_x.config(command=lambda:self.spinner_input(self.sp_pivot_x))

        self.sp_pivot_y.bind("<<Submit>>", self.submit_spinner)
        self.sp_pivot_y.config(command=lambda:self.spinner_input(self.sp_pivot_y))

        self.sp_angle.bind("<<Submit>>", self.submit_spinner)
        self.sp_angle.config(command=lambda: self.spinner_input(self.sp_angle))

        self.var_unit.trace_add("write", lambda *_:self.update_units())
        self.var_type_roi.trace_add("write", self.update_roi_type)

        # Initialize state
        self.update_units()
        self.update_roi_type()

        # Initialize RoiDrawer
        RoiDrawer(self, self.sv.canvas)


    def _new_label(self, text, row, column, parent=None, pad=0):
        """Label factory method"""
        if parent is None:
            parent = self.root
        content = {}
        if type(text) == str:
            content["text"] = text
        else:
            content["textvariable"] = text
            content["width"] = 3
        label = tk.Label(parent, **content, anchor=tk.W)
        label.grid(row=row, column=column, sticky="WE", padx=pad)
        return label


    def _new_spinbox(self, var, row, column, parent=None):
        """Spinbox factory method"""
        if parent is None:
            parent = self.root
        sb = tk.Spinbox(parent, from_=-np.inf, to=np.inf, width=5,
            textvariable=var, background="white")
        sb.grid(row=row, column=column, sticky="WE")
        return sb


    def update_units(self):
        """Callback for switching between px and µm"""
        if self.unit == UNIT_µm:
            float2str(1/self.unit_conv_fac, self.var_unit_px)
            self.var_unit_µm.set("1")
            self.entry_unit_px.config(state=tk.NORMAL)
            self.entry_unit_µm.config(state=tk.DISABLED)
        else:
            self.var_unit_px.set("1")
            float2str(self.unit_conv_fac, self.var_unit_µm)
            self.entry_unit_px.config(state=tk.DISABLED)
            self.entry_unit_µm.config(state=tk.NORMAL)

        self.update_values()


    def update_values(self):
        """Callback for converting values between px and µm"""
        if self.unit == UNIT_µm:
            float2str(self._offset_x * self.unit_conv_fac, self.var_offset_x)
            float2str(self._width * self.unit_conv_fac, self.var_width)
            float2str(self._pad_x * self.unit_conv_fac, self.var_pad_x)
            float2str(self._pivot_x * self.unit_conv_fac, self.var_pivot_x)

            float2str(self._offset_y * self.unit_conv_fac, self.var_offset_y)
            float2str(self._height * self.unit_conv_fac, self.var_height)
            float2str(self._pad_y * self.unit_conv_fac, self.var_pad_y)
            float2str(self._pivot_y * self.unit_conv_fac, self.var_pivot_y)
        else:
            float2str(self._offset_x, self.var_offset_x)
            float2str(self._width, self.var_width)
            float2str(self._pad_x, self.var_pad_x)
            float2str(self._pivot_x, self.var_pivot_x)

            float2str(self._offset_y, self.var_offset_y)
            float2str(self._height, self.var_height)
            float2str(self._pad_y, self.var_pad_y)
            float2str(self._pivot_y, self.var_pivot_y)
        

    def update_unit_conversion(self, evt=None):
        """Callback for updating px/µm conversion factor"""
        if hasattr(evt, "widget") and evt.widget == self.entry_unit_µm:
            new_µm = str2float(self.var_unit_µm, True)
            if new_µm is None:
                float2str(self.unit_conv_fac, self.var_unit_µm)
                flash_red(self.entry_unit_µm)
                return

            self.unit_conv_fac = new_µm
            self.root.focus_set()

        else:
            new_px = str2float(self.var_unit_px, True)
            if new_px is None:
                float2str(1/self.unit_conv_fac, self.var_unit_px)
                flash_red(self.entry_unit_px)
                return

            self.unit_conv_fac = 1 / new_px
            self.root.focus_set()


    def update_roi_type(self, *_):
        """Callback for switching between squared and rectangular ROIs"""
        if self.roi_type == TYPE_SQUARE:
            self.sp_height.config(state=tk.DISABLED)
            self.sp_pad_y.config(state=tk.DISABLED)

            self._height = self._width
            self._pad_y = self._pad_x

            self.var_height.set(self.var_width.get())
            self.var_pad_y.set(self.var_pad_x.get())

            self._notify_listeners()

        else:
            self.sp_height.config(state=tk.NORMAL)
            self.sp_pad_y.config(state=tk.NORMAL)


    def submit_spinner(self, evt):
        """Callback for pressing enter on spinner"""
        self.spinner_input(evt.widget)


    def spinner_input(self, widget):
        """Callback for processing changes of spinner values"""
        if widget == self.sp_offset_x:
            off_x = str2float(self.var_offset_x, False)
            if off_x is None:
                off_x = self._offset_x
                if self.unit == UNIT_µm:
                    off_x *= self.unit_conv_fac
                float2str(off_x, self.var_offset_x)
                flash_red(self.sp_offset_x)
            else:
                if self.unit == UNIT_µm:
                    self._offset_x = off_x / self.unit_conv_fac
                else:
                    self._offset_x = off_x

        elif widget == self.sp_offset_y:
            off_y = str2float(self.var_offset_y, False)
            if off_y is None:
                off_y = self._offset_y
                if self.unit == UNIT_µm:
                    off_y *= self.unit_conv_fac
                float2str(off_y, self.var_offset_y)
                flash_red(self.sp_offset_y)
            else:
                if self.unit == UNIT_µm:
                    self._offset_y = off_y / self.unit_conv_fac
                else:
                    self._offset_y = off_y

        elif widget == self.sp_width:
            width = str2float(self.var_width, True)
            if width is None:
                width = self._width
                if self.unit == UNIT_µm:
                    width *= self.unit_conv_fac
                float2str(width, self.var_width)
                flash_red(self.sp_width)
            else:
                if self.unit == UNIT_µm:
                    self._width = width / self.unit_conv_fac
                else:
                    self._width = width
                if self.var_type_roi.get() == TYPE_SQUARE:
                    self._height = self._width
                    self.var_height.set(self.var_width.get())

        elif widget == self.sp_height:
            height = str2float(self.var_height, True)
            if height is None:
                height = self._height
                if self.unit == UNIT_µm:
                    height *= self.unit_conv_fac
                float2str(height, self.var_height)
                flash_red(self.sp_height)
            else:
                if self.unit == UNIT_µm:
                    self._height = height / self.unit_conv_fac
                else:
                    self._height = height

        elif widget == self.sp_pad_x:
            pad_x = str2float(self.var_pad_x, False, True)
            if pad_x is None:
                pad_x = self._pad_x
                if self.unit == UNIT_µm:
                    pad_x *= self.unit_conv_fac
                float2str(pad_x, self.var_pad_x)
                flash_red(self.sp_pad_x)
            else:
                if self.unit == UNIT_µm:
                    self._pad_x = pad_x / self.unit_conv_fac
                else:
                    self._pad_x = pad_x
                if self.roi_type == TYPE_SQUARE:
                    self._pad_y = self._pad_x
                    self.var_pad_y.set(self.var_pad_x.get())

        elif widget == self.sp_pad_y:
            pad_y = str2float(self.var_pad_y, False, True)
            if pad_y is None:
                pad_y = self._pad_y
                if self.unit == UNIT_µm:
                    pad_y *= self.unit_conv_fac
                float2str(pad_y, self.var_pad_y)
                flash_red(self.sp_pad_y)
            else:
                if self.unit == UNIT_µm:
                    self._pad_y = pad_y / self.unit_conv_fac
                else:
                    self._pad_y = pad_y

        elif widget == self.sp_pivot_x:
            pivot_x = str2float(self.var_pivot_x, False)
            if pivot_x is None:
                pivot_x = self._pivot_x
                if self.unit == UNIT_µm:
                    pivot_x *= self.unit_conv_fac
                float2str(pivot_x, self.var_pivot_x)
                flash_red(self.sp_pivot_x)
            else:
                if self.unit == UNIT_µm:
                    self._pivot_x = pivot_x / self.unit_conv_fac
                else:
                    self._pivot_x = pivot_x

        elif widget == self.sp_pivot_y:
            pivot_y = str2float(self.var_pivot_y, False)
            if pivot_y is None:
                pivot_y = self._pivot_y
                if self.unit == UNIT_µm:
                    pivot_y *= self.unit_conv_fac
                float2str(pivot_y, self.var_pivot_y)
                flash_red(self.sp_pivot_y)
            else:
                if self.unit == UNIT_µm:
                    self._pivot_y = pivot_y / self.unit_conv_fac
                else:
                    self._pivot_y = pivot_y

        elif widget == self.sp_angle:
            angle = str2float(self.var_angle, False)
            if angle is None:
                float2str(self._angle, self.var_angle)
                flash_red(self.sp_angle)
            else:
                # Confine angle to interval [-180°, 180°]
                if angle >= 360:
                    angle -= (angle // 360) * 360
                if angle > 180:
                    angle -= 360
                if angle <= 360:
                    angle += (abs(angle) // 360) * 360
                if angle < -180:
                    angle += 360
                float2str(angle, self.var_angle)
                self._angle = angle

        self.root.focus_set()
        self._notify_listeners()


    def register_listener(self, fun):
        """Register a new function ``fun`` to be executed on change"""
        return self._listeners.register(fun)


    def delete_listener(self, lid):
        """Delete listener with ID ``lid``"""
        self._listeners.delete(lid)
    

    def _notify_listeners(self):
        """Execute listeners due to grid change"""
        self._listeners.notify()

    @property
    def unit(self):
        return self.var_unit.get()

    @property
    def roi_type(self):
        return self.var_type_roi.get()

    @property
    def offset_x(self):
        return self._offset_x

    @offset_x.setter
    def offset_x(self, off_x):
        self.offset_x = off_x
        if self.unit == UNIT_µm:
            off_x *= self.unit_conv_fac
        float2str(off_x, self.var_offset_x)
        self._notify_listeners()

    @property
    def offset_y(self):
        return self._offset_y

    @offset_y.setter
    def offset_y(self, off_y):
        self._offset_y = off_y
        if self.unit == UNIT_µm:
            off_y *= self.unit_conv_fac
        float2str(off_y, self.var_offset_y)
        self._notify_listeners()

    @property
    def pivot_x(self):
        return self._pivot_x

    @pivot_x.setter
    def pivot_x(self, pivot_x):
        self._pivot_x = pivot_x
        if self.unit == UNIT_µm:
            pivot_x *= self.unit_conv_fac
        float2str(pivot_x, self.var_pivot_x)
        self._notify_listeners()

    @property
    def pivot_y(self):
        return self._pivot_y

    @pivot_y.setter
    def pivot_y(self, pivot_y):
        self._pivot_y = pivot_y
        if self.unit == UNIT_µm:
            pivot_y *= self.unit_conv_fac
        float2str(pivot_y, self.var_pivot_y)
        self._notify_listeners()

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, wid):
        self._width = wid
        if self.unit == UNIT_µm:
            wid *= self.unit_conv_fac
        float2str(wid, self.var_width)

        if self.roi_type == TYPE_SQUARE:
            self._height = self._width
            self.var_height.set(self.var_width.get())

        self._notify_listeners()

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, heig):
        self._height = heig
        if self.unit == UNIT_µm:
            heig *= self.unit_conv_fac
        float2str(heig, self.var_height)

        if self.roi_type == TYPE_SQUARE:
            self._width = self._height
            self.var_width.set(self.var_height.get())

        self._notify_listeners()

    @property
    def pad_x(self):
        return self._pad_x

    @pad_x.setter
    def pad_x(self, px):
        self._pad_x = px
        if self.unit == UNIT_µm:
            px *= self.unit_conv_fac
        float2str(px, self.var_pad_x)

        if self.roi_type == TYPE_SQUARE:
            self._pad_y = self._pad_x
            self.var_pad_y.set(self.var_pad_x.get())

        self._notify_listeners()

    @property
    def pad_y(self):
        return self._pad_y

    @pad_y.setter
    def pad_y(self, py):
        self._pad_y = py
        if self.unit == UNIT_µm:
            py *= self.unit_conv_fac
        float2str(py, self.var_pad_y)

        if self.roi_type == TYPE_SQUARE:
            self._pad_x = self._pad_y
            self.var_pad_x.set(self.var_pad_y.get())

        self._notify_listeners()

    @property
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, ang):
        float2str(ang, self.var_angle)
        self._angle = ang
        self._notify_listeners()

    def span(self):
        """Return an array of ROI coordinates"""
        return span_rois(
            self._width, self._height,
            self._pad_x, self._pad_y,
            self._max_x, self._max_y,
            self._angle,
            self._pivot_x, self._pivot_y,
            self._offset_x, self._offset_y,
            self.sv.canvas)


class RoiDrawer:
    """Draw updated ROI grid onto canvas.

    This class is the link between the ``RoiSelector`` and the canvas
    on which to draw the ROI grid.

    It registers itself as a listener to the ``RoiSelector`` and draws
    the updated ROI grid on the canvas.
    The ROI is marked with the tag defined by ``ROI_TAG``.

    :param selector: RoiSelector to which to listen
    :type selector: :class:RoiSelector
    :param canvas: Canvas on which to draw the ROI grid
    :type canvas: :class:tkinter.Canvas
    """
    def __init__(self, selector, canvas):
        self.selector = selector
        self.canvas = canvas

        self.selector.register_listener(self.draw)
        self.draw()


    def draw(self):
        """Draw the new ROI grid on the canvas."""
        self.canvas.delete(ROI_TAG)
        self.canvas.delete(ROI_DRAFT_TAG)

        for roi in self.selector.span():
            self.canvas.create_polygon(*roi.flat, fill="",
                outline="yellow", tags=ROI_TAG)


def span_rois(width, height, pad_x, pad_y, max_x, max_y, angle=0, pivot_x=0, pivot_y=0, off_x=0, off_y=0, canvas=None):
    """Calculate the coordinates of the ROI grid sites.

    :param width: width (in pixels) of a ROI
    :type width: float
    :param height: height (in pixels) of a ROI
    :type height: float
    :param pad_x: distance (in pixels) between adjacent ROIs in x-direction
    :type pad_x: float
    :param pad_y: distance (in pixels) between adjacent ROIs in y-direction
    :type pad_y: float
    :param max_x: maximum x-coordinate (in pixels) of viewport/image on which to draw ROIs
    :type max_x: float
    :param max_y: maximum y-coordinate (in pixels) of viewport/image on which to draw ROIs
    :type max_y: float
    :param angle: angle (in degrees) by which to rotate the ROI grid
    :type angle: float
    :pivot_x: x-coordinate (in pixels) of the rotation center and origin of the new coordinate system
    :type pivot_x: float
    :pivot_y: y-coordinate (in pixels) of the rotation center and origin of the new coordinate system
    :type pivot_y: float
    :param off_x: offset (in pixels) in x-direction of the ROI grid from the origin of the new coordinate system
    :type off_x: float
    :param off_y: offset (in pixels) in y-direction of the ROI grid from the origin of the new coordinate system
    :type off_y: float
    :param canvas: (only for debugging) canvas for drawing debug information
    :type canvas: tkinter.canvas
    """

    # Set up function for ROI rotation
    trans_fun = make_transformation(angle, x_new=pivot_x, y_new=pivot_y)

    # Calculate limits for ROIs
    limits = np.zeros([4,2])
    limits[(1,2),X] = max_x
    limits[(2,3),Y] = max_y
    limits = trans_fun(limits)
    limit_minX = limits[:,X].min()
    limit_maxX = limits[:,X].max()
    limit_minY = limits[:,Y].min()
    limit_maxY = limits[:,Y].max()

    # Get limits check function
    check_limit = make_limit_check(limits)

    # Get leftmost and uppermost ROI edge
    x_unit = pad_x + width
    y_unit = pad_y + height
    x00 = initial_value(x_unit, limit_minX, off_x)
    y0 = initial_value(y_unit, limit_minY, off_y)

    # Iterate over rows and columns
    rois = []
    while True:
        y1 = y0 + height
        if y1 > limit_maxY:
            break
        x0 = x00
        while True:
            x1 = x0 + width
            if x1 > limit_maxX:
                break
            if check_limit(x0, x1, y0, y1):
                # Add roi to list
                roi = np.array([[x0,y0],[x1,y0],[x1,y1],[x0,y1]])
                roi = trans_fun(roi, inverse=True)
                rois.append(roi)
            x0 += x_unit
        y0 += y_unit

#    # DEBUG
#    # Draw grid, viewport and pivot in grid coordinate system
#    if canvas is not None:
#        canvas.create_polygon(*limits.flat,
#            fill="", outline="red", tags=ROI_DRAFT_TAG)
#        canvas.create_line(*trans_fun(np.array([[-9, -9], [9, 9,]]), inverse=True).flat, fill="green", width=3, tags=ROI_DRAFT_TAG)
#        canvas.create_line(*trans_fun(np.array([[-9, 9], [9, -9,]]), inverse=True).flat, fill="green", width=3, tags=ROI_DRAFT_TAG)
#        trans_fun_debug = make_transformation(-angle, x_new=pivot_x, y_new=pivot_y)
#        for roi in rois:
#            canvas.create_polygon(*trans_fun_debug(roi, inverse=False).flat,
#                fill="", outline="red", tags=ROI_DRAFT_TAG)

    return rois


def initial_value(unit, limit=0., offset=0.):
    """Calculate an initial value for grid construction.

    :param unit: a unit length of the grid
    :type unit: float
    :param limit: the minimum value for grid sites
    :type limit: float
    :param offset: grid offset w.r.t. origin
    :type offset: float
    :return: Minimum allowed grid site
    :rtype: float

    The returned value is the smallest grid site larger or equal to
    ``limit``. The grid is shifted by ``offset``. Only the modulus
    ``offset % unit`` is considered; larger values of ``offset``
    are ignored.
    """
    # Get offset (with absolute value less than `unit`)
    if abs(offset) >= unit:
        offset = offset % unit
    offset_left = offset - unit
    offset_right = offset

    # Get multiple of `unit` next larger to `limit`
    m_limit = limit // unit
    if m_limit < 0:
        m_limit += 1
    init = m_limit * unit

    # Apply offset
    if limit - init <= offset_left:
        init += offset_left
    else:
        init += offset_right

    return init


def make_transformation(angle, x_new=0, y_new=0):
    """Set up a coordinate transformation.

    :param angle: angle by which to rotate the coordinates
    :type angle: float
    :param x_new: x-coordinate of the new origin (=pivot)
    :type x_new: float
    :param y_new: y-coordinate of the new origin (=pivot)
    :type y_new: float
    :return: transformation function
    :rtype: function(coords0, inverse=False)

    A closure for coordinate transformation will be returned.
    The closure takes a n-by-2 numpy array ``coords0`` as argument,
    which are the coordinates to be transformed, where ``coords0[i,0]`` is
    the x-coordinate and ``coords0[i,1]`` the y-coordinate of point ``i``.
    The optional boolean flag ``inverse`` indicates whether to perform
    an inverse transformation, i.e. a back-transformation into the old
    system.
    """
    # Calculate (possibly translated) origin of new coordinate system
    new_origin = np.array([[x_new, y_new]])

    # Build rotation matrix
    angle = np.deg2rad(angle)
    cos_a = np.cos(angle)
    sin_a = np.sin(angle)
    R = np.matrix([[cos_a, -sin_a],[sin_a, cos_a]])

    # Make closure
    def transformation_function(coords0, inverse=False):
        """Rotates coordinates `coords` by a predetermined angle"""
        coords = coords0.copy()
        if inverse:
            coords = (R.T * coords.T).T
            if np.any(new_origin != 0):
                coords += new_origin
        else:
            if np.any(new_origin != 0):
                coords -= new_origin
            coords = (R * coords.T).T
        return coords

    # Return closure
    return transformation_function


def transform(coords, angle, x_new=0, y_new=0, inverse=False):
    """Convenience function for one-shot transformation

    :param coords: array of coordinates to be transformed
    :type coords: n-by-2 numpy array, with ``coords[i,0]`` the x-coordinate and ``coords[i,1]`` the y-coordinate of point ``i``
    :param angle: angle by which to rotate the coordinates
    :type angle: float
    :param x_new: x-coordinate of rotation center
    :type x_new: float
    :param y_new: y-coordinate of rotation center
    :type y_new: float
    :param inverse: flag whether to perform inverse transformation
    :type inverse: boolean
    :return: transformed coordinates
    :rtype: n-by-2 numpy array
    """
    return make_transformation(angle, x_new, y_new)(coords, inverse)


def make_limit_check(limits):
    """
    Return a function to check if a bounding box is inside limits.

    :param limits: The corners of a rectangle representing the limits.
        The rectangle may be rotated. The first column must be the x-values
        and the second column must be the y-values of the corners.
    :type limits: numpy array of shape (4,2)
    :return: function for checking if bounding box is inside limits
    :rtype: function(x0, x1, y0, y1)

    The signature of the returned function is ``function(x0, x1, y0, y1)``.
    ``x0`` and ``x1`` are the smallest and largest x-values of the bounding
    box, ``y0`` and ``y1`` are the smallest and largest y-values of the
    bounding box.
    The returned function assumes that ``x0 < x1`` and ``y0 < y1``.
    If this condition is not fulfilled, unexpected behaviour may occur.

    The returned function returns ``True`` if the bounding box is
    within the ``limits``, else ``False``.
    """
    # Check if `limits` are rotated or just
    isJust = (limits[:,Y] == limits[:,Y].max()).sum() == 2
    if isJust:
        # Make faster function for just `limits`
        maxX = limits[:,X].max()
        minX = limits[:,X].min()
        maxY = limits[:,Y].max()
        minY = limits[:,Y].min()
        def check(x0, x1, y0, y1):
            """
            Check if the given bounding box is inside the limits.
            
            Assumes that x0 < x1 and y0 < y1 are bounding box coordinates
            of a non-rotated rectangle.
            """
            return x0 < minX or x1 > maxX or y0 < minY or y1 < maxY

    else:
        # More expensive function for rotated `limits`
        # Get coordinates of limits corners
        # Meaning of the variable names [max|min][X|Y][x|y]:
        #   [max|min]: point of `limits` with a coordinate extremum
        #   [X|Y]: point of `limits` has an extremum x or y coordinate
        #   [x|y]: x or y coordinate of point of `limits`
        maxYx, maxYy = limits[limits[:,Y].argmax(),:].flat
        minYx, minYy = limits[limits[:,Y].argmin(),:].flat
        maxXx, maxXy = limits[limits[:,X].argmax(),:].flat
        minXx, minXy = limits[limits[:,X].argmin(),:].flat

        # Get limits edges
        edge_nw = lambda x: (maxYy - minXy) / (maxYx - minXx) * (x - minXx) + minXy
        edge_ne = lambda x: (maxXy - maxYy) / (maxXx - maxYx) * (x - maxYx) + maxYy
        edge_se = lambda x: (minYy - maxXy) / (minYx - maxXx) * (x - minYx) + minYy
        edge_sw = lambda x: (minXy - minYy) / (minXx - minYx) * (x - minXx) + minXy

        # Define check function
        def check(x0, x1, y0, y1):
            """
            Check if the given bounding box is inside the limits.

            Assumes that x0 < x1 and y0 < y1 are bounding box coordinates
            of a rotated rectangle.
            """
            # Get upper and lower limit for y0 and y1 at x0
            if x0 < minXx:
                return False
            if x0 > maxYx:
                x0y_upper = edge_ne(x0)
            else:
                x0y_upper = edge_nw(x0)
            if x0 > minYx:
                x0y_lower = edge_se(x0)
            else:
                x0y_lower = edge_sw(x0)

            # Check if y0 and y1 are inside limits at x0
            if y0 < x0y_lower or y1 < x0y_lower or y0 > x0y_upper or y1 > x0y_upper:
                return False

            # Get upper and lower limit for y0 and y1 at x1
            if x1 > maxXx:
                return False
            if x1 > maxYx:
                x1y_upper = edge_ne(x1)
            else:
                x1y_upper = edge_nw(x1)
            if x1 > minYx:
                x1y_lower = edge_se(x1)
            else:
                x1y_lower = edge_sw(x1)

            # Check if y0 and y1 are inside limits at x1
            if y0 < x1y_lower or y1 < x1y_lower or y0 > x1y_upper or y1 > x1y_upper:
                return False

            return True

    return check
