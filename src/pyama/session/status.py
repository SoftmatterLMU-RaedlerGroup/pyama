from collections import OrderedDict
from threading import RLock

from .events import Event

class Status:
    """Status message handler for propagating status messages beyond threads.

    Status message viewers are registered with the method 'register_viewer'.
    Call the object as a context manager to set a status.
    All registered viewers receive an Event for calling the registered function.
    """
    def __init__(self):
        self.msg_dict = OrderedDict()
        self.viewers = {}
        self.lock = RLock()

    def set(self, *_, **__):
        #TODO: delete self.set
        import traceback
        print("Called Status.set") #DEBUG
        traceback.print_stack(limit=2)
        return self(*_, **__)

    def register_viewer(self, cmd, queue):
        """Register a new status message viewer.

        The viewer must be a callable that takes the keyword arguments
        'msg', 'current' and 'total'.
        While 'msg' is a string that will always be set (but may be empty),
        'current' and 'total' may be None. If the message is a progress,
        'current' is a numeric value indicating the current progress,
        and 'total' is either a numeric value indicating the maximum value
        or None if no maximum value is known.

        This method returns a viewer ID that can be used to unregister
        the viewer with the 'unregister_viewer' method.
        """
        with self.lock:
            viewer_id = Event.now()
            self.viewers[viewer_id] = StatusViewer(cmd, queue)
        return viewer_id

    def unregister_viewer(self, viewer_id):
        """Unregister a status message viewer.

        The 'viewer_id' is the ID returned by 'register_viewer'.
        """
        with self.lock:
            try:
                del self.viewers[viewer_id]
            except KeyError:
                pass

    def __call__(self, msg, current=None, total=None):
        """Set a status message.

        Arguments:
            msg -- str with the message; may be an empty string
            current -- None or numeric value indicating current progress
            total -- None or numeric value indicating maximum progress

        'current' and 'total' are intended for calculating a position
        of a progress bar.

        Use the return value of this method as a context manager; e.g.:
        >>> status = Status()
        >>> # Share 'status' with other threads
        >>> for x in range(10):
        >>>     with status("Processing items", current=x+1, total=10):
        >>>         # do something with 'x'
        """
        return StatusMessage(msg, current=current, total=total,
                enter_cb=self._enter_status, exit_cb=self._exit_status)

    def _enter_status(self, message):
        """Set a status message.

        This method is called upon entering a status context.
        `message` is the `StatusMessage` instance to be entered.
        The message instance is brought to the top of the status
        stack and, if it is invoked initially, is assigned a message ID.
        Finally, the status display is updated.
        """
        with self.lock:
            if message._msg_id is None:
                msg_id = Event.now()
                message._msg_id = msg_id
                self.msg_dict[msg_id] = message
            else:
                try:
                    self.msg_dict.move_to_end(message._msg_id)
                except KeyError:
                    return
            self._update_status()

    def _exit_status(self, msg_id):
        with self.lock:
            try:
                del self.msg_dict[msg_id]
            except KeyError:
                return
            self._update_status()

    def _update_status(self):
        with self.lock:
            for msg in reversed(self.msg_dict.values()):
                break
            else:
                # No messages in queue left; create empty message
                msg = StatusMessage("")
            for k, v in self.viewers.items():
                try:
                    Event.fire(v.queue, v.cmd, **msg.asdict)
                except Exception:
                    del self.viewers[k]


class StatusViewer:
    def __init__(self, cmd, queue):
        self.cmd = cmd
        self.queue = queue


class StatusMessage:
    def __init__(self, msg, current=None, total=None, enter_cb=None, exit_cb=None):
        self._msg_id = None
        self.__msg = msg
        self.__current = current
        self.__total = total
        self.__enter_cb = enter_cb
        self.__exit_cb = exit_cb
        self.__lock = RLock()

    def __enter__(self):
        if self.__enter_cb is not None:
            self.__enter_cb(self)
        return self

    def __exit__(self, *_):
        if self.__exit_cb is None:
            return
        self.__exit_cb(self._msg_id)

    @property
    def asdict(self):
        """Return message as dictionary use for use as keyword arguments"""
        with self.__lock:
            return dict(msg=self.__msg, current=self.__current, total=self.__total)

    @property
    def msg(self):
        with self.__lock:
            return self.__msg

    @msg.setter
    def msg(self, new_msg):
        with self.__lock:
            self.__msg = new_msg
        self.__enter__()

    @property
    def current(self):
        with self.__lock:
            return self.__current

    @current.setter
    def current(self, new_current):
        with self.__lock:
            self.__current = new_current
        self.__enter__()

    @property
    def total(self):
        with self.__lock:
            return self.__total

    @total.setter
    def total(self, new_total):
        with self.__lock:
            self.__total = new_total
        self.__enter__()

    def reset(self, msg, current=None, total=None):
        with self.__lock:
            self.__msg = msg
            self.__current = current
            self.__total = total
        self.__enter__()


class DummyStatus:
    """Dummy status that does nothing.

    Use this class as a 'fallback Status' when no status needs to be displayed.
    """
    def __call__(self, msg, current=None, total=None):
        """Set a status message.

        Arguments:
            msg -- str with the message; may be an empty string
            current -- None or numeric value indicating current progress
            total -- None or numeric value indicating maximum progress

        See `Status.__call__` for more information.
        """
        return StatusMessage(msg, current=current, total=total)

    def set(self, *_, **__):
        #TODO: delete self.set
        import traceback
        print("Called DummyStatus.set") #DEBUG
        traceback.print_stack(limit=2)
        return self(*_, **__)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass
