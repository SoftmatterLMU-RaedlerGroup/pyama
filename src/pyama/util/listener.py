import random
import string
import threading

from .events import Event
from . import make_uid


class Listeners:
    """Listener notification class

    @param kinds different event categories offered by this Listeners instance
    <!-- :type kinds: --> None, str or iterable of str
    @param require_queue Force listeners to pass a queue at registering
    <!-- :type require_queue: --> bool
    @param debug
    <!-- :type debug: --> bool
    """
    def __init__(self, kinds=None, require_queue=False, debug=False):
        if kinds is None:
            self.__kinds = ()
        elif isinstance(kinds, str):
            self.__kinds = (str,)
        else:
            try:
                assert all(isinstance(k, str) for k in kinds)
            except Exception:
                raise ValueError("`kinds` must be None, str or iterable of str")
            self.__kinds = tuple(k for k in kinds)
        self.__require_queue = require_queue
        self.debug = debug
        self.__listeners = {}
        self.__lock = threading.RLock()


    @property
    def kinds(self):
        return self.__kinds


    def register(self, fun, kind=None, queue=None):
        """
        Register a listener that will be notified on changes.

        Listeners can be registered to listen to all kinds of events or only to certain kinds.
        The kinds should be strings.
        When kind is None, fun will be called by all of these events.

        If a queue is passed, an Event will be fed into the queue, including
        ``fun`` and any arguments passed at notifying.
        If no queue is passed, ``fun`` will be called directly by the notifying thread.

        A listener ID is returned that can be used to delete the listener.
        If the registration was not successful, None is returned.

        Note that if ``fun`` raises an exception, the corresponding listener will not be called anymore.

        @param fun The function to be called on change, will be called without parameters
        <!-- :type fun: --> function handle
        @param kind The kind of events when the function will be called
        <!-- :type kind: --> None, str or iterable containing strings
        @param queue Queue object to feed an event as notification
        <!-- :type queue: --> None or Queue

        @return  a listener ID or None
        <!-- :rtype: --> str or None
        """
        if self.__kinds is not None:
            # Convert kind to valid format
            if kind is None:
                kind = self.__kinds
            else:
                s_kind = set()

                if isinstance(kind, str):
                    assert kind in self.__kinds
                    s_kind.add(kind)
                else:
                    for k in kind:
                        assert isinstance(kind, str) and kind in self.__kinds
                        s_kind.add(kind)
                kind = s_kind

            if not kind:
                if self.debug:
                    print(f"Cannot register listener: bad kind \"{kind}\"")
                return None

        if self.__require_queue and not queue:
            raise ValueError("This Listeners instance requires a queue.")

        with self.__lock:
            # Register listener and return its listener ID
            lid = make_uid(fun)
            self.__listeners[lid] = {'fun': fun, 'kind': kind, 'queue': queue}
            return lid


    def notify(self, kind=None, *args, **kwargs):
        """
        Notify the listeners.

        If ``kind is None``, all listeners are notified.
        Else, only the listeners registered for event kind ``kind`` are notified.
        """
        with self.__lock:
            for lid, listener in self.__listeners.items():
                if kind is not None and kind not in listener["kind"]:
                    continue
                try:
                    if listener['queue']:
                        Event.fire(listener['queue'], listener['fun'], *args, **kwargs)
                    else:
                        listener['fun'](*args, **kwargs)
                except Exception:
                    if self.debug:
                        raise
                    self.delete(lid)


    def delete(self, lid):
        """Delete the listener with ID ``lid``, if existing."""
        try:
            with self.__lock:
                del self.__listeners[lid]
        except KeyError:
            if self.debug:
                print(f"Cannot delete listener: ID \"{lid}\" not found.")


    def clear(self):
        """Delete all listeners"""
        with self.__lock:
            self.__listeners = {}
