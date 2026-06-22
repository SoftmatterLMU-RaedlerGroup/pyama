def start_workflow(version=None, name=None, mainloop=True):
    # Import modules at custom locations
    from .modules import ModuleManager
    from .workflow_tk import WorkflowGUI

    # Load modules
    modman = ModuleManager()
    if version is not None:
        modman.register_builtin_data("__version__", version)
    if name is not None:
        modman.register_builtin_data("__name__", "PyAMA")

    # Display GUI
    gui = WorkflowGUI(modman)
    modman.register_builtin_data("__tk-root__", gui.root_tk)
    gui.mainloop()
