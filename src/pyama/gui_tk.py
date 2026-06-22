"""
This module is intended to provide general GUI-related functions.
"""
import tkinter as tk
from tkinter import filedialog
#import workflow_tk

global root
root = None

def get_root(w=None):
    """Obtain root of Tk widget."""
    if w is None:
        global root
        if root is None:
            root = tk.Tk()
    else:
        root = w.winfo_toplevel()
        if root.master:
            root = root.master
    return root

def new_toplevel(master=None, *arg, **kwarg):
    """Create a new toplevel window."""
    global root
    if master is not None:
        return tk.Toplevel(master, *arg, **kwarg)
    elif root is None:
        root = tk.Tk(*arg, **kwarg)
        return root
    else:
        return tk.Toplevel(master=root, *arg, **kwarg)

def mainloop():
    """Start the tkinter mainloop."""
    global root
    root.mainloop()


def askopenfilename(**args):
    """Provide file opening dialog for other plugins."""
    if not "master" in args:
        global root
        args["master"] = root
    return filedialog.askopenfilename(**args)


def asksaveasfilename(**args):
    """Provide file saving dialog for other plugins."""
    if not "master" in args:
        global root
        args["master"] = root
    return filedialog.asksaveasfilename(**args)


def askdirectory(**args):
    """Provide directory dialog for other plugins."""
    if not "master" in args:
        global root
        args["master"] = root
    return filedialog.askdirectory(**args)

