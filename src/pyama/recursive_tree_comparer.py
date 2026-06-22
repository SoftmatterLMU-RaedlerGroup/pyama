class RecursiveComparer:
    """
    ``RecursiveComparer`` synchronizes the ``Treeview`` of the workflow GUI
    with the ``ModuleOrder``.

    The recommended way of using it is the ``RecursiveComparer.go`` method.
    """
    def __init__(self, tree, mo):
        """
        Set up the RecursiveComparer.

        :param tree: the ``Treeview`` instance to be synchronized
        :type tree: ttk.Treeview
        :param mo: the ``ModuleOrder`` with which to synchronize ``tree``
        :type mo: ``ModuleOrder``
        """
        self.tree = tree
        self.mo = mo
        self.moi = ModuleOrderIterator(mo.order)

        self.i_tree = []
        self.i_mo = []

        #self.moi.print_order() #DEBUG

    @classmethod
    def go(cls, tree, mo, checkDependency=False):
        """
        Synchronize a ``Treeview`` with a ``ModuleOrder``.

        :param tree: the ``Treeview`` instance to be synchronized
        :type tree: ttk.Treeview
        :param mo: the ``ModuleOrder`` with which to synchronize ``tree``
        :type mo: ``ModuleOrder``
        :param checkDependency: Flag whether to check the dependencies of the modules
        :type checkDependency: bool
        """
        comparer = cls(tree, mo)
        comparer.compare(checkDependency=checkDependency)


    def id_of(self, iid):
        """Return module ID of item at ``iid``"""
        return self.tree.set(iid, column="id")


    def insert(self, mod_id, prev=None, parent=None):
        """
        Insert a new item into the ``Treeview``.

        :param mod_id: the ID of the module to be inserted ("" for dummy)
        :type mod_id: str
        :param prev: the ``iid`` of the before which to insert the new item
        :type prev: str
        :param parent: the ``iid`` of the parent of the new item
        :type parent: str

        Either ``prev`` or ``parent`` must be given.
        If ``prev`` is not given, the new item is inserted as last child.
        """
        # Get name and ID of module to be inserted
        if not mod_id:
            # Dummy item for empty loops
            mod_name = ""
            mod_id = ""
        else:
            mod_name = self.mo.modules[mod_id].name

        # Get index where to insert the item
        if prev is None:
            index = "end"
        else:
            index = self.tree.index(prev)
        
        # Get parent of the item to be inserted
        if parent is None:
            if prev is None:
                raise ValueError("Either parent or prev must be given.")
            parent = self.tree.parent(prev)

        # Insert the item into the tree
        iid = self.tree.insert(parent, index, text=mod_name, values=(mod_id,))

        # Return the iid of the newly inserted item
        return iid


    def compare(self, parent="", checkDependency=False):
        """Compare tree view and module order content.
        
        :param parent: The ``iid`` of the item whose children to synchronize
        :type parent: str
        :param checkDependency: Flag whether to check the dependencies of the modules
        :type checkDependency: bool
        
        By default, compare the top-level items."""
        # Get first child of current parent
        children = self.tree.get_children(parent)
        if children:
            iid = children[0]
        else:
            iid = ""

        # Iterate over items of ModuleOrder in current level
        while self.moi.has_next():
            self.moi.goto_next()

            # Compare module IDs
            m_id = self.moi.get_id()
            t_id = self.id_of(iid)

            # DEBUG
            #print("index={}, m_id={:20s}, t_id={:20s}".format(self.moi.index, m_id, t_id))

            if m_id != t_id:
                next_iid = self.tree.next(iid)
                next_t_id = self.id_of(next_iid)
                if m_id == next_t_id:
                    # Module ID is found one step further, swap items
                    old_iid = iid
                    self.tree.move(next_iid, parent, self.tree.index(old_iid))
                    iid = next_iid

                    # When `old_iid` seems to be deleted, keep focus
                    if t_id != self.moi.get_next_id():
                        sel = self.tree.selection()
                        if old_iid in sel:
                            self.tree.focus(iid)
                            self.tree.selection_set(iid)
                else:
                    # Module ID is not found in tree, insert it
                    if iid:
                        iid = self.insert(m_id, prev=iid)
                    else:
                        iid = self.insert(m_id, parent=parent)

            # Compare children of current parent
            children = self.tree.get_children(iid)
            if self.moi.is_loop():
                if self.moi.has_children():
                    self.moi.step_into_children()
                    self.compare(parent=iid)
                else:
                    if not (len(children) == 1 and self.id_of(children[0]) == ""):
                        self.tree.delete(*children)
                        self.insert("", parent=iid)
            elif children:
                self.tree.delete(*children)

            # Proceed to next item in tree view
            iid = self.tree.next(iid)

        # Delete all additional items in tree view
        while iid:
            if self.tree.focus() == iid:
                prev = self.tree.prev(iid)
                if prev:
                    self.tree.selection_set(prev)
                    self.tree.focus(prev)
            old = iid
            iid = self.tree.next(iid)
            self.tree.delete(old)

        # Return iterator to parent
        if self.moi.has_parent():
            self.moi.goto_parent()


class ModuleOrderIterator:
    """
    ModuleOrderIterator provides an API for navigating through a
    ModuleOrder instance in a similar way to a ttk.Treeview.
    """
    def __init__(self, order):
        """
        Set up the ``ModuleOrderIterator``.

        :param order: the ``ModuleOrder.order``
        :type order: list
        """
        self.stack = [order]
        self.index = None
        self.next_into_children = False

    def has_next(self):
        """Check if a next item exists (on same level)."""
        if self.index is None and self.stack[0]:
            return True
        elif not self.index:
            return False
        elif self.next_into_children:
            return self.has_children()
        elif self.index[-1] < len(self.stack[-2]) - 1:
            return True
        else:
            return False

    def goto_next(self):
        """Proceed to next item (on same level)."""
        if self.next_into_children:
            self.goto_first_child()
        elif self.index is None and self.stack[-1]:
            self.index = [0]
            self.stack.append(self.stack[-1][0])
        elif self.index and (self.index[-1] < len(self.stack[-2]) - 1):
            self.index[-1] += 1
            self.stack[-1] = self.stack[-2][self.index[-1]]
        else:
            raise IndexError("Cannot go to next item.")

    def is_loop(self):
        """Check if current item is a loop."""
        return len(self.stack) > 1 and type(self.stack[-1]) != str

    def has_children(self):
        """Check if current item has child items (loop content)."""
        if not self.is_loop():
            return False
        return len(self.stack[-1]) > 1

    def step_into_children(self):
        """Mark down that next call to ``goto_next`` will to to first child"""
        if not self.has_children():
            raise IndexError("Cannot step into children when there are no children.")
        self.next_into_children = True

    def goto_first_child(self):
        """Make first child of current item the new current item."""
        self.next_into_children = False
        if not self.has_children():
            raise IndexError("Cannot index into children when there are no children.")
        self.index.append(1)
        self.stack.append(self.stack[-1][1])

    def has_parent(self):
        """Check if current item has a parent item (is not top-level)."""
        if self.index:
            return True
        return False

    def goto_parent(self):
        """Make parent of current item the new current item."""
        if not self.has_parent():
            raise IndexError("Cannot go to parent when there is no parent.")
        self.next_into_children = False
        self.stack.pop()
        self.index.pop()

    def get_id(self):
        """Return the module ID of the current item."""
        if self.is_loop():
            return self.stack[-1][0]
        return self.stack[-1]

    def get_next_id(self):
        """Return the module ID of the next item (in same level), or "" if there is no next item."""
        if not self.has_next():
            return ""
        elif self.index is None:
            s = self.stack[-1][0]
            if type(s) == list:
                s = s[0]
            return s
        else:
            try:
                return self.stack[-2][self.index[-1] + 1]
            except IndexError:
                return ""

    def print_index(self):
        """Print the index of the current item."""
        # DEBUG
        print("ModuleOrderIterator.index = {}".format(str(self.index)))

    def print_order(self):
        """Print ``ModuleOrder.order`` of the underlying ``ModuleOrder``."""
        # DEBUG
        print("ModuleOrder = {}".format(str(self.stack[0])))
