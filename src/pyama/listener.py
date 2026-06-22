import random
import string
import threading


class Listeners:
    def __init__(self, kinds=None, debug=False):
        self.__kinds = kinds
        self.debug = debug
        self.__listeners = {}
        self.__lock = threading.RLock()

    @property
    def kinds(self):
        return self.__kinds

    def register(self, fun, kind=None):
        """
        Register a listener that will be notified on changes.

        Listeners can be registered to listen to all kinds of events or only to certain kinds.
        The kinds should be strings.
        When kind is None, fun will be called by all of these events.

        A listener ID is returned that can be used to delete the listener.
        If the registration was not successful, None is returned.

        Note that if ``fun`` raises an exception, the corresponding listener will not be called anymore.

        :param fun: The function to be called on change, will be called without parameters
        :type fun: function handle
        :param kind: The kind of events when the function will be called
        :type kind: None, str or iterable containing strings

        :return: a listener ID or None
        :rtype: str or None
        """
        if self.__kinds is not None:
            # Convert kind to valid format
            if kind is None:
                kind = self.__kinds
            else:
                s_kind = set()

                if type(kind) == str and kind in self.__kinds:
                    s_kind.add(kind)
                else:
                    for k in kind:
                        if type(kind) == str and kind in self.__kinds:
                            s_kind.add(kind)
                kind = s_kind

            if not kind:
                if self.debug:
                    print(f"Cannot register listener: bad kind \"{kind}\"")
                return None

        with self.__lock:
            # Register listener and return its listener ID
            lid = self._generate_unique_id()
            self.__listeners[lid] = {"fun": fun, "kind": kind}
            return lid

    def _generate_unique_id(self):
        # Get a unique listener ID
        # Not thread-safe!
        k = 0
        isInvalid = True
        while isInvalid:
            k += 1
            lid = "".join(random.choices(
                string.ascii_letters + string.digits, k=k))
            isInvalid = lid in self.__listeners
        return lid

    def notify(self, kind=None):
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
                    listener["fun"]()
                except Exception:
                    if self.debug:
                        raise
                    self.delete(lid)

    def delete(self, lid):
        """Delete the listener with ID ``lid``, if existing."""
        with self.__lock:
            if lid in self.__listeners:
                del self.__listeners[lid]
            elif self.debug:
                print(f"Cannot delete listener: ID \"{lid}\" not found.")

    def clear(self):
        """Delete all listeners"""
        with self.__lock:
            self.__listeners = {}
