#! /usr/bin/env python3

import numpy as np
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tkfdlg

class PolygonDrawer:
    """Shows a Tk window on which a rectangle can be drawn."""

    def __init__(self):
        """Builds and shows the window."""
        # Set up root window
        self.root = tk.Tk()
        self.root.title("Polygon in canvas")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        #fn = tkfdlg.askopenfilename(title="Wähle Datei aus")
        #print(type(fn))
        #print(fn)

        # Set up frame in root window
        self.mainframe = ttk.Frame(self.root, height="20c", width="20c")
        self.mainframe.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))

        # Show a label
        ttk.Label(self.mainframe, text="Klicken, um ein Polygon zu zeichnen"
            ).grid(column=0, row=0, sticky=(tk.W))

        # Set up canvas
        self.canvas = tk.Canvas(self.mainframe, background="white")
        self.canvas.grid(column=0, row=1, sticky=(tk.N, tk.W, tk.E, tk.S))
        self.canvas.bind("<1>", self.canvas_clicked)
        self.canvas.bind("<Motion>", self.canvas_dragged)

        # Initialize rectangle drawing state variables
        self.rectState = False
        self.x_base = None
        self.y_base = None

        # Enter the event loop
        self.root.mainloop()


    def canvas_clicked(self, e):
        """Callback function for mouse clicks on the canvas.

If no rectangle is being drawn, a new rectangle is initialized.
If a rectangle is being drawn, it is finalized.
        """

        if not self.rectState:
            # No rectangle being drawn; draw a new one
            self.canvas.delete("r")
            self.x_base = e.x
            self.y_base = e.y
            self.canvas.create_rectangle(
                (self.x_base, self.y_base, self.x_base, self.y_base),
                outline="red", tag="r")
            self.rectState = True

        else:
            # Finalize currently drawn rectangle
            self.canvas.itemconfigure("r", outline="black")
            self.x_base = None
            self.y_base = None
            self.rectState = False

    def canvas_dragged(self, e):
        """Callback function for mouse movement on the canvas.

If no rectangle is being drawn, do nothing.
If a rectangle is being drawn, update its shape.
        """
        if not self.rectState:
            return

        x = e.x
        y = e.y

        x_nw, x_se = (self.x_base, x) if x > self.x_base else (x, self.x_base)
        y_nw, y_se = (self.y_base, y) if y > self.y_base else (y, self.y_base)
        self.canvas.coords("r", x_nw, y_nw, x_se, y_se)



if __name__ == "__main__":
    PolygonDrawer()
