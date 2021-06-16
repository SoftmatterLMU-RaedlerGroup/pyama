import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tkfd

from . import const
from ..util.status import DummyStatus
from ..util.events import Event
from ..stack import Stack
from ..stack import metastack as ms

class SessionOpener:
    """Ask the user for stacks.

    Arguments:
        root - the parent tkinter.Tk object
        callback - call this function after finishing
    """
    # To test this class, run e.g.:
    # $ cd pyama
    # $ ipython
    # In [1]: %load_ext autoreload
    # In [2]: %autoreload 2
    # In [3]: from src.session.sessionopener_tk import SessionOpener
    # In [4]: import tkinter as tk
    # In [5]: root = tk.Tk(); SessionOpener(root); root.mainloop()
    # Repeat In [5] for each test run

    def __init__(self, root, control_queue, status=None):
        self.root = root
        self.frame = tk.Toplevel(self.root)
        self.frame.title("Select stacks and channels")
        self.frame.geometry('600x300')
        self.frame.protocol('WM_DELETE_WINDOW', self.cancel)
        self.stack_ids = None
        self.stack_getter = None
        self.channels = []
        if status is None:
            self.status = DummyStatus()
        else:
            self.status = status
        self.control_queue = control_queue
        self.active = True
        self.session_id = None
        self.cmd_map = {
            const.RESP_NEW_SESSION_ID: self.set_session_id,
            const.CMD_UPDATE_STACK_LIST: self.refresh_stacklist,
            }

        # PanedWindow
        paned = tk.PanedWindow(self.frame)
        paned = tk.PanedWindow(self.frame, orient=tk.HORIZONTAL, sashwidth=2, sashrelief=tk.RAISED)
        paned.pack(expand=True, fill=tk.BOTH)

        # Stack selection
        stack_frame = tk.Frame(paned)
        paned.add(stack_frame, sticky='NESW', width=200)
        stack_frame.grid_columnconfigure(1, weight=1)
        stack_frame.grid_rowconfigure(0, weight=1)

        ## Listbox
        list_frame = tk.Frame(stack_frame)
        list_frame.grid(row=0, column=0, columnspan=2, sticky='NESW')
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.var_stack_list = tk.StringVar()
        self.stack_list = tk.Listbox(list_frame, selectmode=tk.SINGLE,
                listvariable=self.var_stack_list, highlightthickness=0, exportselection=False)
        self.stack_list.grid(row=0, column=0, sticky='NESW')
        self.stack_list.bind("<<ListboxSelect>>", self.stacklist_selection)
        list_y_scroll = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.stack_list.yview)
        list_x_scroll = tk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.stack_list.xview)
        self.stack_list.config(yscrollcommand=list_y_scroll.set)
        self.stack_list.config(xscrollcommand=list_x_scroll.set)
        list_y_scroll.grid(row=0, column=1, sticky='NESW')
        list_x_scroll.grid(row=1, column=0, sticky='NESW')

        ## Buttons
        btn_frame = tk.Frame(stack_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky='NESW')
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        self.btn_open = tk.Button(btn_frame, text="Open...", state=tk.DISABLED, command=self.open_stack)
        self.btn_open.grid(row=0, column=0, sticky='WE', padx=5)
        self.btn_remove = tk.Button(btn_frame, text="Remove", state=tk.DISABLED, command=self.remove_stack)
        self.btn_remove.grid(row=0, column=1, sticky='WE', padx=5)

        ## Display
        self.var_stack = tk.StringVar(self.frame)
        self.var_n_chan = tk.StringVar(self.frame)
        tk.Label(stack_frame, text="Stack:", anchor=tk.W).grid(row=2, column=0, sticky='NESW', padx=5)
        tk.Label(stack_frame, text="Channels:", anchor=tk.W).grid(row=3, column=0, sticky='NESW', padx=5)
        tk.Label(stack_frame, textvariable=self.var_stack, anchor=tk.W).grid(row=2, column=1, sticky='NESW')
        tk.Label(stack_frame, textvariable=self.var_n_chan, anchor=tk.W).grid(row=3, column=1, sticky='NESW')

        # Channel selection
        chan_frame = tk.Frame(paned)
        paned.add(chan_frame, sticky='NESW', width=400)
        chan_frame.grid_rowconfigure(0, weight=1)
        chan_frame.grid_columnconfigure(0, weight=1)

        ## Channel display
        self.chan_disp_frame = tk.Frame(chan_frame)
        self.chan_disp_frame.grid(row=0, column=0, sticky='NESW')
        self.chan_disp_frame.grid_columnconfigure(1, weight=1, pad=5, minsize=30)
        self.chan_disp_frame.grid_columnconfigure(2, weight=0, pad=5)
        self.chan_disp_frame.grid_columnconfigure(3, weight=1, pad=5)

        tk.Label(self.chan_disp_frame, text="Channel", anchor=tk.W).grid(row=0, column=0, sticky='W')
        tk.Label(self.chan_disp_frame, text="Label", anchor=tk.W).grid(row=0, column=1, sticky='W')
        tk.Label(self.chan_disp_frame, text="Type", anchor=tk.W).grid(row=0, column=2, sticky='W')
        tk.Label(self.chan_disp_frame, text="Stack [Channel]", anchor=tk.W).grid(row=0, column=3, sticky='W')

        ## Separator
        ttk.Separator(chan_frame, orient=tk.HORIZONTAL).grid(row=1, column=0, sticky='ESW')

        ## Channel configuration
        chan_add_frame = tk.Frame(chan_frame)
        chan_add_frame.grid(row=2, column=0, sticky='ESW')
        chan_add_frame.grid_columnconfigure(0, weight=1, pad=5)
        chan_add_frame.grid_columnconfigure(1, weight=1, pad=5)
        chan_add_frame.grid_columnconfigure(2, weight=1, pad=5)

        tk.Label(chan_add_frame, text="Add new channel", anchor=tk.W).grid(row=0, column=0, columnspan=4, sticky='EW')
        tk.Label(chan_add_frame, text="Channel", anchor=tk.W).grid(row=1, column=0, sticky='EW')
        tk.Label(chan_add_frame, text="Type", anchor=tk.W).grid(row=1, column=1, sticky='EW')
        tk.Label(chan_add_frame, text="Label", anchor=tk.W).grid(row=1, column=2, sticky='EW')

        self.var_chan = tk.IntVar(self.frame)
        self.var_label = tk.StringVar(self.frame)
        self.var_type = tk.StringVar(self.frame)

        self.chan_opt = tk.OptionMenu(chan_add_frame, self.var_chan, 0)
        self.chan_opt.grid(row=2, column=0, sticky='NESW')
        self.type_opt = tk.OptionMenu(chan_add_frame, self.var_type,
            *const.CH_CAT_LIST)
        self.type_opt.grid(row=2, column=1, sticky='NESW')
        self.label_entry = tk.Entry(chan_add_frame, textvariable=self.var_label)
        self.label_entry.grid(row=2, column=2, sticky='NESW')
        self.add_chan_btn = tk.Button(chan_add_frame, text="Add", command=self.add_chan)
        self.add_chan_btn.grid(row=2, column=3, sticky='EW')
        self.disable_channel_selection()

        # OK and Cancel buttons
        btn_frame = tk.Frame(self.frame)
        btn_frame.pack(expand=True, fill=tk.X)
        btn_frame.grid_columnconfigure(0, weight=1, pad=20)
        btn_frame.grid_columnconfigure(1, weight=1, pad=20)
        tk.Button(btn_frame, text="Cancel", width=10, command=self.cancel).grid(row=0, column=0)
        tk.Button(btn_frame, text="OK", width=10, command=self.finish).grid(row=0, column=1)

        # Request new session
        Event.fire(self.control_queue, const.CMD_INIT_SESSION)

    def to_front(self):
        """Show this window above all other windows"""
        self.frame.lift()

    def open_stack(self):
        """Open a new stack"""
        fn = tkfd.askopenfilename(title="Open stack",
                                  parent=self.frame,
                                  initialdir='res',
                                  filetypes=(
                                        ("Stack", '*.tif *.tiff *.npy *.npz *.h5'),
                                        ("TIFF", '*.tif *.tiff'),
                                        ("Numpy", '*.npy *.npz'),
                                        ("HDF5", '*.h5'),
                                        ("All files", '*')
                                  )
                                 )
        if fn:
            Event.fire(self.control_queue, const.CMD_NEW_STACK, fn, self.session_id)

    def set_session_id(self, session_id):
        print(f"New session ID: {session_id}") #DEBUG
        self.session_id = session_id
        self.btn_open.config(state=tk.NORMAL)

    def remove_stack(self):
        """Remove a stack from the list"""
        sel = self.stack_list.curselection()
        if not sel:
            return
        try:
            sel = int(sel[-1])
        except Exception:
            return
        Event.fire(self.control_queue, const.CMD_CLOSE_STACK,
                session_id=self.session_id, stack_id=self.stack_ids[sel])

        self.del_chan(sel)

    def refresh_stacklist(self, stack_getter, select=None):
        """Refresh ListBox with loaded stacks.

        The new stacklist must be given as `stacks`.
        If `select` is a valid index, this item is selected.
        """
        self.stack_getter = stack_getter
        stack_list = []
        stack_ids = []
        for s in self.stack_getter().values():
            stack_list.append("{name} ({dir})".format(**s))
            stack_ids.append(s['id'])
        self.stack_ids = tuple(stack_ids)
        self.var_stack_list.set(stack_list)
        self.stack_list.selection_clear(0, tk.END)
        if select is not None:
            if select is True:
                select = tk.END
            self.stack_list.selection_set(select)
        self.stacklist_selection()
        self.btn_remove.config(state=(tk.NORMAL if stack_list else tk.DISABLED))

    def stacklist_selection(self, event=None):
        stack_id = self.selected_stack_id
        try:
            stack = self.stack_getter(stack_id)
            if stack is None:
                raise KeyError
            stack_name = stack['name']
            stack_n_chan = stack['n_channels']
            self.activate_channel_selection(stack)
        except Exception:
            stack_name = ""
            stack_n_chan = ""
            self.disable_channel_selection()
        self.var_stack.set(stack_name)
        self.var_n_chan.set(stack_n_chan)

    @property
    def selected_stack_id(self):
        sel = self.stack_list.curselection()
        try:
            sel = int(sel[-1])
            return self.stack_ids[sel]
        except Exception:
            return None

    def activate_channel_selection(self, stack):
        self.chan_opt.config(state=tk.NORMAL)
        self.label_entry.config(state=tk.NORMAL)
        self.type_opt.config(state=tk.NORMAL)
        self.add_chan_btn.config(state=tk.NORMAL)

        self.chan_opt['menu'].delete(0, tk.END)
        for i in range(stack['n_channels']):
            self.chan_opt['menu'].add_command(label=i, command=tk._setit(self.var_chan, i))
        self.var_chan.set(0)
        self.var_label.set('')
        self.var_type.set(const.CH_CAT_PHC)

    def disable_channel_selection(self):
        self.var_chan.set(())
        self.var_label.set('')
        self.var_type.set("None")
        self.chan_opt.config(state=tk.DISABLED)
        self.label_entry.config(state=tk.DISABLED)
        self.type_opt.config(state=tk.DISABLED)
        self.add_chan_btn.config(state=tk.DISABLED)

    def add_chan(self):
        stack_id = self.selected_stack_id
        try:
            self.channels.append({'stack_id': stack_id,
                                  'i_channel': self.var_chan.get(),
                                  'label': self.var_label.get(),
                                  'type': self.var_type.get(),
                                 })
        except KeyError:
            return
        self.refresh_channels()

    def del_chan(self, i_chan):
        """Remove a channel from the selection"""
        try:
            self.channels[i_chan]['stack_id'] = None
        except KeyError:
            return
        self.refresh_channels()

    def refresh_channels(self):
        """Redraw the channel selection"""
        i = 0
        idx_del = []
        for j, ch in enumerate(self.channels):
            # Remove widgets of channels marked for deletion
            if ch['stack_id'] is None:
                if 'widgets' in ch:
                    for w in ch['widgets'].values():
                        w.destroy()
                idx_del.append(j)
                continue

            # Check if channel is new
            wdg = None
            if 'widgets' not in ch:
                stack = self.stack_getter(ch['stack_id'])
                if stack is None:
                    stack_name = "<ERROR>"
                else:
                    stack_name = stack['name']
                wdg = {}
                wdg['idx'] = tk.Label(self.chan_disp_frame, text=i,
                        anchor=tk.E, relief=tk.SUNKEN, bd=1)
                wdg['label'] = tk.Label(self.chan_disp_frame, text=ch['label'],
                        anchor=tk.W, relief=tk.SUNKEN, bd=1)
                wdg['type'] = tk.Label(self.chan_disp_frame, text=ch['type'],
                        anchor=tk.W, relief=tk.SUNKEN, bd=1)
                wdg['stack'] = tk.Label(self.chan_disp_frame,
                        text="{} [{}]".format(stack_name, ch['i_channel']),
                        anchor=tk.W, relief=tk.SUNKEN, bd=1)
                wdg['button'] = tk.Button(self.chan_disp_frame, text="X")
                wdg['button'].config(command=lambda b=wdg['button']: self.del_chan(b.grid_info()['row']-1)) #TODO
                ch['widgets'] = wdg

            # Check if previous widget has been deleted
            elif i != j:
                wdg = ch['widgets']
                wdg['idx'].grid_forget()
                wdg['label'].grid_forget()
                wdg['type'].grid_forget()
                wdg['stack'].grid_forget()
                wdg['button'].grid_forget()

            # Redraw widgets if necessary
            i += 1
            if wdg is not None:
                wdg['idx'].config(text=i)
                wdg['idx'].grid(row=i, column=0, sticky='NESW')
                wdg['label'].grid(row=i, column=1, sticky='NESW')
                wdg['type'].grid(row=i, column=2, sticky='NESW')
                wdg['stack'].grid(row=i, column=3, sticky='NESW')
                wdg['button'].grid(row=i, column=4, sticky='NESW')

        # Delete channels marked for deletion
        for i in sorted(idx_del, reverse=True):
            self.channels.pop(i)

    def cancel(self):
        """Close the window and call callback with `None`"""
        self.active = False
        self.frame.destroy()
        if self.session_id is not None:
            Event.fire(self.control_queue, const.CMD_DISCARD_SESSION, self.session_id)

    def finish(self):
        """Close the window and call callback with channels"""
        if not self.channels:
            self.cancel()
            return
        self.active = False
        chan_info = []
        self.frame.destroy()
        for ch in self.channels:
            x = {}
            stack = self.stack_getter(ch['stack_id'])
            if stack is None:
                continue
            x['stack_id'] = ch['stack_id'] #DEBUG: Attention, changed behaviour
            x['name'] = stack['name']
            x['dir'] = stack['dir']
            x['i_channel'] = ch['i_channel']
            x['label'] = ch['label']
            x['type'] = ch['type']
            chan_info.append(x)
        Event.fire(self.control_queue, const.CMD_CONFIG_SESSION,
                session_id=self.session_id, stacks=chan_info)
