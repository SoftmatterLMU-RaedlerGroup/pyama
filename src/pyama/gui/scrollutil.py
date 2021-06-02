import tkinter as tk


class ScrolledWidget(tk.Frame):
    """Wrapper class for adding scrollbars.

Scrollbars are automatically added to a scrollable widget.
This widget can be embedded like a Frame.

Note that this class requires `widget` to be scrollable,
i.e. `widget` must provide the methods '{x,y}view' and the
widget options '{x,y}scrollcommand'.
For non-scrollable widgets, use ScrolledFrame instead.

This class is inspired by:
http://effbot.org/zone/tkinter-autoscrollbar.htm

Options:
widget -- the scrollable widget that shall be scrolled
parent -- the parent widget
horizontal_scroll -- add a horizontal scrollbar
vertical_scroll -- add a vertical scrollbar
horizontal_dynamic -- show/hide horizontal scrollbar automatically
vertical_dynamic -- show/hide horizontal scrollbar automatically
**kwargs -- further arguments passed to the tk.Frame constructor
    """
    def __init__(self, parent=None, horizontal_scroll=True, vertical_scroll=True,
            horizontal_dynamic=True, vertical_dynamic=True, **kwargs):
        super().__init__(parent, **kwargs)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.horizontal_dynamic = bool(horizontal_dynamic)
        self.vertical_dynamic = bool(vertical_dynamic)
        self.widget = None

        if horizontal_scroll:
            self.horizontal_scrollbar = tk.Scrollbar(
                    self, orient=tk.HORIZONTAL)
        else:
            self.horizontal_scrollbar = None

        if vertical_scroll:
            self.vertical_scrollbar = tk.Scrollbar(
                    self, orient=tk.VERTICAL)
        else:
            self.vertical_scrollbar = None


    def set_widget(self, widget=None):
        """Set the scrolled widget"""
        if self.widget is not None:
            self.widget.grid_forget()
            self.widget.config(xscrollcommand=None, yscrollcommand=None)
        self.widget = widget
        if self.widget is None:
            if self.horizontal_scrollbar:
                self.horizontal_scrollbar.config(command=None)
                self._set_horiz(0., 1.)
            if self.vertical_scrollbar:
                self.vertical_scrollbar.config(command=None)
                self._set_vert(0., 1.)
        else:
            self.widget.grid(in_=self, row=0, column=0, sticky='NESW')
            if self.horizontal_scrollbar:
                self.widget.config(xscrollcommand=self._set_horiz)
                self.horizontal_scrollbar.config(command=self.widget.xview)
            if self.vertical_scrollbar:
                self.widget.config(yscrollcommand=self._set_vert)
                self.vertical_scrollbar.config(command=self.widget.yview)


    def _set_horiz(self, lo, hi):
        if float(lo) > 0. or float(hi) < 1. or not self.horizontal_dynamic:
            self.horizontal_scrollbar.grid(row=1, column=0, sticky='ESW')
            self.horizontal_scrollbar.set(lo, hi)
        else:
            self.horizontal_scrollbar.grid_forget()


    def _set_vert(self, lo, hi):
        if float(lo) > 0. or float(hi) < 1. or not self.vertical_dynamic:
            self.vertical_scrollbar.grid(row=0, column=1, sticky='NES')
            self.vertical_scrollbar.set(lo, hi)
        else:
            self.vertical_scrollbar.grid_forget()



class ScrolledFrame(ScrolledWidget):
    """Frame with automatic scrollbars.

This class provides a frame with automatic scrollbars.
Add items to the 'viewport' attribute, which is a frame
that can be scrolled.

This class is based on:
https://gist.github.com/mp035/9f2027c3ef9172264532fcd6262f3b01

For possible constructor arguments, see 'ScrolledWidget'.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.canvas = tk.Canvas(self,
                width=0,
                height=0,
                borderwidth=0,
                highlightthickness=0,
                takefocus=False,
                )
        self.viewport = tk.Frame(self.canvas)
        self.vp_win = self.canvas.create_window(
                (0, 0), window=self.viewport, anchor=tk.N+tk.W)
        self.viewport.bind('<Configure>', self._cb_config_viewport)
        self.canvas.bind('<Configure>', self._cb_config_canvas)
        self.bind('<Configure>', self._cb_config_self)
        super().set_widget(self.canvas)


    def _cb_config_self(self, evt):
        bd = 2 * self.config('borderwidth')[-1]
        height = evt.height - bd
        width = evt.width - bd
        self.canvas.configure(height=height, width=width)


    def _cb_config_canvas(self, evt):
        rw = self.viewport.winfo_reqwidth()
        rh = self.viewport.winfo_reqheight()
        if evt.width > rw:
            rw = evt.width
        if evt.height > rh:
            rh = evt.height
        self.canvas.itemconfig(self.vp_win, width=rw, height=rh)


    def _cb_config_viewport(self, evt):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))


    def set_widget(self, widget=None):
        """Do not use this method."""
        raise AttributeError
