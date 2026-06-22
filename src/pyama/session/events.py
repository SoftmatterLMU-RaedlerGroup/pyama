import time

class Event:
    """Container for sharing callable events between threads.

    Constructor arguments:
        cmd -- str indicating a command for consumer, or function to be called by consumer
        args, kwargs -- arguments and keyword arguments with which command/function is called
    One of 'cmd' and 'fun' must be given. If 'fun' is given, 'cmd' is ignored.
    
    Properties:
        cmd -- the 'cmd' as received by constructor
        time -- monotonic time of instantiation
        called -- boolean flag; True iff this instance has been called already

    To execute the event, call the event like a function. If the constructor
    argument 'cmd' is not callable, the call requires a callable as 'fun' argument.

    The 'Event' class provides a mechanism to prevent unnecessary calls of
    events that have been deprecated by a more recent event.
    To use the mechanism, simply provide the latest allowed time as
    'not_after' argument to the call. The time must be compatible to the
    value returned by the 'now' method.
    The call returns False if it would have been unnecessary, else True.

    This class is not thread-safe. Once fed into a queue, it should not be
    modified by the producer anymore.
    """
    def __init__(self, cmd, *args, **kwargs):
        self.time = self.now()
        if callable(cmd):
            self.cmd = None
            self.fun = cmd
        elif isinstance(cmd, str):
            self.cmd = cmd
            self.fun = None
        else:
            raise ValueError("'cmd' must be a callable or a string")
        if args is None:
            self.args = ()
        else:
            self.args = args
        if kwargs is None:
            self.kwargs = {}
        else:
            self.kwargs = kwargs
        self.called = None

    def __call__(self, fun=None, not_after=None):
        if not_after is not None and not_after >= self.time:
            self.called = True
            return False
        if fun is None:
            fun = self.fun
        self.called = self.now
        fun(*self.args, **self.kwargs)
        return True

    @staticmethod
    def now():
        """Return the current time"""
        return time.perf_counter_ns()

    @classmethod
    def fire(cls, queue, cmd, *args, **kwargs):
        """Fire an event into a queue.

        Arguments:
            queue -- a queue into which to feed the event
            cmd -- command; will be passed to the constructor
            args -- arguments; will be passed to the constructor
            kwargs -- dict of keyword arguments; will be passed to the constructor
        """
        queue.put_nowait(cls(cmd, *args, **kwargs))
