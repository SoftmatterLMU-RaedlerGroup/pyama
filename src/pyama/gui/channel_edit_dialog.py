#! /usr/bin/env python3
import tkinter as tk

from ..session import const as sess_const


class ChannelEditDialog(tk.Toplevel):
    """Dialog to change channel properties.

This class is intended to be used only through the
classmethod 'run'.

Currently, editing the channel description is not supported.
    """
    def __init__(self, parent, name, category):
        self.init_name = name
        self.init_cat = category
        self.chan_name = None
        self.chan_cat = None

        super().__init__(parent)
        self.title("PyAMA – Edit channel properties")
        self.config(padx=10, pady=10)
        self.resizable(width=True, height=False)
        self.grid_columnconfigure(1, weight=1)

        self.var_name = tk.StringVar(self, value=self.init_name)
        self.var_cat = tk.StringVar(self, value=self.init_cat)

        tk.Label(self, text=f"Edit properties of channel '{self.init_name}':").grid(row=0, column=0, columnspan=2, pady=(0, 10))
        tk.Label(self, text="Name:", anchor=tk.E).grid(row=1, column=0, sticky=tk.E, padx=(0, 5))
        tk.Label(self, text="Category:", anchor=tk.E).grid(row=2, column=0, sticky=tk.E, padx=(0, 5))

        tk.Entry(self, justify=tk.LEFT, exportselection=False, textvariable=self.var_name).grid(row=1, column=1, sticky=tk.E+tk.W)

        menu = tk.OptionMenu(self, self.var_cat, sess_const.CH_CAT_PHC, sess_const.CH_CAT_FL, sess_const.CH_CAT_BIN)
        menu.config(takefocus=True, bd=1, indicatoron=False, direction='flush')
        menu.grid(row=2, column=1, sticky=tk.E+tk.W)

        fr_buttons = tk.Frame(self)
        fr_buttons.grid(row=3, column=0, columnspan=2, sticky=tk.E+tk.W)
        fr_buttons.grid_rowconfigure(0)
        fr_buttons.grid_columnconfigure(0, weight=1, uniform='uniform_buttons', pad=20)
        fr_buttons.grid_columnconfigure(1, weight=1, uniform='uniform_buttons', pad=20)

        tk.Button(fr_buttons, text="OK", command=self.click_ok).grid(row=0, column=0, sticky=tk.E+tk.W, pady=(20, 0))
        tk.Button(fr_buttons, text="Cancel", command=self.destroy).grid(row=0, column=1, sticky=tk.E+tk.W, pady=(20, 0))

        self.bind('<Return>', self.click_ok)
        self.bind('<KP_Enter>', self.click_ok)
        self.bind('<Escape>', lambda *_: self.destroy())


    def click_ok(self, *_):
        new_name = self.var_name.get()
        if new_name and new_name != self.init_name:
            self.chan_name = new_name
        new_cat = self.var_cat.get()
        if new_cat and new_cat != self.init_cat:
            self.chan_cat = new_cat
        self.destroy()


    @classmethod
    def run(cls, parent, name, category):
        """Display channel editing dialog and return editions.

Arguments:
parent -- parent tkinter widget
name -- current name of the channel
category -- current category of the channel

A tuple (name, category) is returned.

If the user changed the name or category to a
non-empty value different from the initial value
and clicked OK, the new value is returned, else None.
        """
        d = cls(parent, name, category)
        d.transient(parent)
        d.grab_set()
        d.wait_window(d)
        return d.chan_name, d.chan_cat


if __name__ == '__main__':
    root = tk.Tk()
    res = ChannelEditDialog.run(root, "Some Name", "<Category>")
    print(res)
