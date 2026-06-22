class SessionView:
    """SessionView base class

    This class defines an API for session views.
    Session views should be created by subclassing this class
    and implementing the necessary methods.
    """

    @classmethod
    def create(cls, *args, **kwargs):
        """Create a new SessionView instance and return it.

        This method is the preferred way to instantiate a session view.
        It calls the (optional) 'prepare' method to perform all
        necessary preparation that must be run in the
        GUI thread before creating the SessionView.
        Then, the class is instantiated, and the new instance is returned.

        The arguments (args, kwargs) are provided to both the
        'prepare' and '__init__' method.
        """
        cls.prepare(*args, **kwargs)
        return cls(*args, **kwargs)

    @classmethod
    def prepare(cls, *args, **kwargs):
        """Run all preparation tasks.

        For details, see the 'create' method.
        """
        pass

    def __init__(self, title='SessionView'):
        raise NotImplementedError

    def mainloop(self):
        """Run the GUI mainloop.

        This method must be implemented by subclasses.
        """
        raise NotImplementedError

    def update_status(self, msg, current=None, total=None):
        """Callback for updating the status message.

        This method must be run from the GUI thread.
        This method must be implemented by subclasses.
        """
        raise NotImplementedError
