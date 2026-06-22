#! /bin/env python3
import os
import sys

# Define meta information
__version__ = "0.1.8"
__author__ = "Daniel Woschée"
__contact__ = "daniel.woschee@physik.lmu.de"
PACKAGE_NAME = "PyAMA"

if __name__ == "__main__":
    # Check for Python 3.8
    ver_major, ver_minor = sys.version_info[:2]
    if ver_major != 3 or ver_minor < 8:
        raise RuntimeError("At least Python 3.8 required, found %d.%d." % (ver_major, ver_minor))

    # Start workflow
    #from src import workflow_starter
    #workflow_starter.start_workflow(version=__version__, name=PACKAGE_NAME)

    # Check for arguments
    try:
        open_path = sys.argv[1]
    except IndexError:
        open_path = None
    else:
        if not os.path.isfile(open_path):
            open_path = None

    from .session import SessionController
    while True:
        controller = SessionController(name=PACKAGE_NAME, version=__version__, read_session_path=open_path)
        restart_flag = controller.start()
        for session_id in list(controller.sessions.keys()):
            controller.discard_session(session_id)
        if restart_flag:
            continue
        else:
            break


