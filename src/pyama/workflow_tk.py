#! /usr/bin/env python3
import queue
import sys
import tkinter as tk
import tkinter.font as tkfont
import tkinter.ttk as ttk
from . import gui_tk as gui
from .recursive_tree_comparer import RecursiveComparer

# Unicode status symbols:
# dependencies OK: u+2713 or u+2714
# dependencies not OK: u+2717 or u+2718
# input needed: u+26a0 or u+270f


class WorkflowGUI:
    def __init__(self, module_manager):
        # Module management setup
        self.modman = module_manager
        self.mod_list = self.modman.list_display()

        # Basic GUI setup
        self.frame = gui.new_toplevel()
        self.frame.title("PyAMA Workflow")

        self.root = gui.get_root()
        self.mod_list_frame = None
        self.dependencies_fulfilled = False
        self._update_queue = queue.Queue()

        # Menu bar
        menubar = tk.Menu(self.frame)
        self.frame.config(menu=menubar)

        filemenu = tk.Menu(menubar)
        menubar.add_cascade(label="File", menu=filemenu)
        filemenu.add_command(label="Quit", command=self.frame.quit)

        helpmenu = tk.Menu(menubar)
        menubar.add_cascade(label="Help", menu=helpmenu)

        # Module control buttons
        frame = tk.Frame(self.frame)
        frame.pack(side=tk.TOP, fill=tk.X)

        self.load_button = tk.Button(frame, text="Add…",
                command=self.prompt_new_module)
        self.load_button.pack(side=tk.LEFT)

        self.remove_button = tk.Button(frame, text="Remove",
                command=self.remove_mod,
                state=tk.DISABLED)
        self.remove_button.pack(side=tk.LEFT)

        self.down_button = tk.Button(frame, text="Down",
                command=lambda: self.move_mod("down"),
                state=tk.DISABLED)
        self.down_button.pack(side=tk.LEFT)

        self.up_button = tk.Button(frame, text="Up",
                command=lambda: self.move_mod("up"),
                state=tk.DISABLED)
        self.up_button.pack(side=tk.LEFT)

        self.refresh_button = tk.Button(frame, text="Refresh",
                command=self.refresh_mod_tree)
        self.refresh_button.pack(side=tk.LEFT)

        self.run_button = tk.Button(frame, text="Run all",
                command=self.modman.invoke_workflow, state=tk.DISABLED)
        self.run_button.pack(side=tk.LEFT)

        # Treeview with scrollbar
        frame = tk.Frame(self.frame)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        tree_scroll = ttk.Scrollbar(frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.mod_tree = ttk.Treeview(frame,
                columns=("id", "status"),
                displaycolumns=(),
                selectmode="browse",
                yscrollcommand=tree_scroll.set)
        self.mod_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.mod_tree.yview)
        self.mod_tree.heading("#0", text="Workflow")
        #self.mod_tree.heading("id", text="ID")
        self.mod_tree.bind("<<TreeviewSelect>>", self.selection_changed)
        self.mod_tree.bind("<Button-1>", self.deselect_on_click)

        # Info frame
        self.info_frame = tk.Frame(self.frame)
        self.info_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Populate module tree
        self.refresh_mod_tree()
        self.update_info()

        self.mod_tree.tag_configure("dep_conf", background="yellow")
        self.mod_tree.tag_configure("dep_other", background="red")

        # Prepare listeners
        self.modman.register_listener(lambda: self.schedule(self.refresh_mod_tree), kind="order")
        self.modman.register_listener(lambda: self.schedule(self.refresh_run_button), kind="workflow")
        self.modman.register_listener(lambda: self.schedule(self.refresh_dependencies), kind="dependency")
        self.root.after(40, self._update)


    def _update(self):
        """
        Execute jobs in queue.
        
        Call this method only from whithin the Tkinter main thread.
        """
        while True:
            try:
                func, args, kwargs = self._update_queue.get(block=False)
            except queue.Empty:
                break
            self.root.after_idle(func, *args, **kwargs)
        self.root.after(40, self._update)


    def schedule(self, func, *args, **kwargs):
        """
        Feed new job into queue.
        
        Use this function to change the GUI from another thread.
        """
        self._update_queue.put((func, args, kwargs))


    def mainloop(self):
        """Start the Tk mainloop"""
        gui.mainloop()

    @property
    def root_tk(self):
        """Get Tk root for use in other modules"""
        return self.root

    def get_id(self, iid):
        """Return module ID of module at Treeview position ``iid``"""
        return self.mod_tree.set(iid, column="id")

    def _insert_item(self, mod_id, parent='', index='end'):
        name = self.modman.modules[mod_id].name
        iid = self.mod_tree.insert(parent, index, text=name, values=(mod_id,))
        return iid


    def refresh_mod_tree(self):
        """Step through module list and synchronize it"""
        RecursiveComparer.go(self.mod_tree, self.modman.module_order)
        self.selection_changed()


    def refresh_dependencies(self, parent=""):
        """Update the dependencies of all modules"""
        # If we start the test new, clear global dependency flag
        if not parent:
            self.dependencies_fulfilled = True

        # Iterate over all children
        for iid in self.mod_tree.get_children(parent):
            index = self.get_item_index(iid)

            # Acquire dependencies of children
            try:
                isConfRequired, deps = self.modman.check_module_dependencies(index)
            except IndexError:
                continue

            # Set global dependency flag
            if deps or isConfRequired:
                self.dependencies_fulfilled = False

            # Set tags of item according to dependency
            dep_tags = set()
            dep_tags_remove = {"dep_conf", "dep_other"}
            if deps:
                dep_tags.add("dep_other")
                dep_tags_remove.discard("dep_other")
            elif isConfRequired:
                dep_tags.add("dep_conf")
                dep_tags_remove.discard("dep_conf")
            tags = set(self.mod_tree.item(iid, "tags"))
            tags -= dep_tags_remove
            tags |= dep_tags
            self.mod_tree.item(iid, tags=tuple(tags))

            # Recursively check dependencies of children
            if self.mod_tree.get_children(iid):
                self.refresh_dependencies(iid)

        if not parent:
            if self.dependencies_fulfilled:
                self.run_button.config(state=tk.NORMAL)
            else:
                self.run_button.config(state=tk.DISABLED)


    def prompt_new_module(self, *_):
        """Open dialog for selecting modules to insert"""
        if self.mod_list_frame is None:
            self.mod_list_frame = ModuleListFrame(self)
        else:
            self.mod_list_frame.to_front()

    def get_item_index(self, iid=None):
        """Return the index of the selected module"""
        if iid is None:
            iid = self.mod_tree.focus()
        index = []
        while iid:
            index.append(self.mod_tree.index(iid))
            if self.mod_tree.parent(iid):
                index[-1] += 1
            iid = self.mod_tree.parent(iid)
        if not index:
            return None
        index.reverse()
        return index

    def insert_mod(self, mod_name, mod_id):
        """Insert a module into the list after the current selection"""
        iid = self.mod_tree.focus()
        if iid:
            index = self.get_item_index()
            if not self.mod_tree.parent(iid) or self.mod_tree.set(iid, column="id"):
                index[-1] += 1
        else:
            index = -1
        self.modman.module_order_insert(mod_id, index)

    def move_mod(self, direction):
        """Move a module in the list up or down"""
        iid = self.mod_tree.focus()
        index_old = self.get_item_index(iid)
        if not index_old:
            return
        index_new = index_old.copy()
        if direction == "up":
            if not self.mod_tree.prev(iid):
                return
            index_new[-1] -= 1
        elif direction == "down":
            if not self.mod_tree.next(iid):
                return
            index_new[-1] += 1
        else:
            print("bad direction: '{}'".format(direction))
            return
        self.modman.module_order_move(index_old, index_new)
        self.mod_tree.see(iid)
        self.selection_changed()

    def remove_mod(self, *_, iid=None):
        """Remove a module from the list"""
        if not iid:
            iid = self.mod_tree.focus()
        if iid:
            index = self.get_item_index(iid)
            self.modman.module_order_remove(index)
        self.selection_changed()

    def refresh_run_button(self):
        """Refresh state of run button"""
        if self.modman.is_workflow_running():
            self.run_button.config(state=tk.DISABLED)
        else:
            self.run_button.config(state=tk.NORMAL)

    def get_module(self, iid=None, mod_id=None):
        """
        Get a reference to the module instance.
        
        Specify either iid (module ID of ``self.mod_tree``)
        or module ID.
        When specifying both, iid overrides module ID.
        Returns module instance or, on error, None.
        """
        if iid is None and mod_id is None:
            return None
        elif iid is not None:
            mod_id = self.mod_tree.set(iid, column='id')
        if mod_id:
            return self.modman.modules.get(mod_id)
        return None

    def deselect_on_click(self, evt):
        """Deselect all items if an empty part is clicked"""
        iid = self.mod_tree.identify_row(evt.y)
        if not iid:
            self.mod_tree.focus('')
            self.mod_tree.selection_set('')

    def selection_changed(self, *_):
        """Update control button states upon selection change"""
        remove_button_state = tk.DISABLED
        up_button_state = tk.DISABLED
        down_button_state = tk.DISABLED

        iid = self.mod_tree.focus()
        if iid and self.mod_tree.set(iid, column="id"):
            remove_button_state = tk.NORMAL
            if self.mod_tree.prev(iid):
                up_button_state = tk.NORMAL
            if self.mod_tree.next(iid):
                down_button_state = tk.NORMAL

        self.remove_button.config(state=remove_button_state)
        self.up_button.config(state=up_button_state)
        self.down_button.config(state=down_button_state)
        self.update_info()

    def update_info(self):
        iid = self.mod_tree.focus()
        if not iid:
            self.clear_info(True)
        else:
            self.show_module_info(iid)

    def clear_info(self, showNote=False):
        for c in self.info_frame.winfo_children():
            c.destroy()
        if showNote:
            tk.Label(self.info_frame, text="No module selected").pack(side=tk.TOP)

    def show_module_info(self, iid):
        mod = self.get_module(iid)
        if not mod:
            self.clear_info(True)
            return

        # Prepare info frame
        self.clear_info()
        self.info_frame.columnconfigure(1, weight=1)
        self.info_frame.rowconfigure(2, weight=1)

        # Define descriptor labels
        fmt = {"font": tkfont.Font(family="TkDefaultFont", weight="bold")}
        tk.Label(self.info_frame,
                anchor=tk.E,
                **fmt,
                text="Name:"
                ).grid(row=0, column=0, sticky=tk.E)
        tk.Label(self.info_frame,
                anchor=tk.E,
                **fmt,
                text="ID:"
                ).grid(row=1, column=0, sticky=tk.E)
        tk.Label(self.info_frame,
                anchor=tk.E,
                **fmt,
                text="Requires:"
                ).grid(row=2, column=0, sticky=tk.E+tk.N)

        # Define content labels (and list)
        tk.Label(self.info_frame,
                anchor=tk.W,
                text=mod.name
                ).grid(row=0, column=1, sticky=tk.W)
        tk.Label(self.info_frame,
                anchor=tk.W,
                text=mod.id
                ).grid(row=1, column=1, sticky=tk.W)
        dep_frame = ttk.Frame(self.info_frame)
        dep_frame.grid(row=2, column=1, sticky="NESW")
        dep_tree = ttk.Treeview(dep_frame,
                height=3,
                show="tree",
                selectmode="none",
                takefocus=False)
        dep_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dep_tree_scroll = ttk.Scrollbar(dep_frame,
                command=dep_tree.yview)
        dep_tree_scroll.pack(side=tk.LEFT, fill=tk.Y)
        dep_tree.config(xscrollcommand=dep_tree_scroll.set)
        dep_tree.column("#0", minwidth=5, width=15)

        # Display dependencies
        _, deps = self.modman.check_module_dependencies(self.get_item_index(iid))
        if deps:
            for dep_id, dep_data in deps.items():
                diid = dep_tree.insert("", "end", text=dep_id)
                for d in dep_data:
                    dep_tree.insert(diid, "end", text=d)

        # Define buttons
        btn_conf = tk.Button(self.info_frame, text="Configure")
        btn_conf.grid(row=0, column=2, sticky=tk.N+tk.E+tk.S+tk.W)
        if mod.has_fun('conf'):
            btn_conf.config(command=lambda: self.modman.module_perform(mod.id, "conf"))
        else:
            btn_conf.config(state=tk.DISABLED)

        btn_run = tk.Button(self.info_frame, text="Run")
        btn_run.grid(row=1, column=2, sticky=tk.N+tk.E+tk.S+tk.W)
        if mod.has_fun('run'):
            btn_run.config(command=lambda: self.modman.module_perform(mod.id, "run"))
        else:
            btn_run.config(state=tk.DISABLED)


class ModuleListFrame:
    """
    An auxiliary class for selecting and inserting new modules.
    """
    def __init__(self, parent):
        """Create a new dialog.

        :param parent: the parent ``WorkflowGUI`` instance
        """
        # Basic setup of dialog window
        self.parent = parent
        self.root = tk.Toplevel(parent.frame)
        self.root.bind("<Destroy>", self._destroy)
        self.root.title("PyAMA Modules")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Create scrollbars
        scroll_y = ttk.Scrollbar(self.root, orient=tk.VERTICAL)
        scroll_y.grid(row=0, column=1, sticky=tk.N+tk.S)
        scroll_x = ttk.Scrollbar(self.root, orient=tk.HORIZONTAL)
        scroll_x.grid(row=1, column=0, sticky=tk.W+tk.E)

        # Set up list view
        self.list = ttk.Treeview(self.root,
                columns=("id", "version", "name"),
                displaycolumns=("id", "version"),
                selectmode="browse",
                yscrollcommand=scroll_y.set,
                xscrollcommand=scroll_x.set)
        self.list.grid(row=0, column=0, sticky=tk.N+tk.E+tk.S+tk.W)
        self.list.bind("<<TreeviewSelect>>", self.selection_changed)
        self.list.heading("#0", text="Name")
        self.list.heading("id", text="ID")
        self.list.heading("version", text="Version")

        scroll_y.config(command=self.list.yview)
        scroll_x.config(command=self.list.xview)

        # Set up addition button
        self.add_button = tk.Button(self.root, text="Add",
                state=tk.DISABLED, command=self.add_module)
        self.add_button.grid(row=2, column=0, columnspan=2,
                sticky=tk.N+tk.E+tk.S+tk.W)

        # Populate list with available modules
        self.populate()


    def populate(self):
        """Populate the list with sorted available modules"""
        categories = {}
        for m in self.parent.mod_list:
            cat = m["category"]

            # Insert category-less items at base level
            if not cat:
                self.list.insert("", 'end', text=m["name"],
                        values=(m["id"], m["version"], m["name"]))
            else:
                # Insert items in all categories to which they belong
                for p in cat:
                    if p not in categories:
                        p_iid = self.list.insert("", 'end', text=p)
                        categories[p] = p_iid
                    else:
                        p_iid = categories[p]
                    self.list.insert(p_iid, 'end', text=m["name"],
                            values=(m["id"], m["version"], m["name"]))

        # Sort entries
        self.sort_children_by_name()


    def to_front(self):
        """Bring the dialog window to front"""
        self.root.lift()

    def _destroy(self, *_):
        """Prevent dangling references upon destroying the dialog"""
        if self.parent is not None:
            self.parent.mod_list_frame = None
        self.parent = None

    def selection_changed(self, *_):
        """Toggle button state upon selection change"""
        iid = self.list.focus()
        if iid and not self.list.get_children(iid):
            self.add_button.config(state=tk.NORMAL)
        else:
            self.add_button.config(state=tk.DISABLED)

    def add_module(self,*_):
        """Insert selected module into parent list upon button click"""
        iid = self.list.focus()
        if not iid or self.list.get_children(iid):
            return
        values = self.list.set(iid)
        self.parent.insert_mod(values["name"], values["id"])

    def sort_children_by_name(self, parent="", isRecursive=True):
        """Sort the items displayed below `parent` by display name"""
        children = self.list.get_children(parent)
        children = sorted(children, key=lambda c: self.list.item(c, "text"))
        self.list.set_children(parent, *children)

        if isRecursive:
            for c in children:
                if self.list.get_children(c):
                    self.sort_children_by_name(c)
