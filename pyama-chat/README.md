# pyama-chat

`pyama-chat` provides a conversational command-line helper that collects the inputs
needed to run the PyAMA processing workflow. It walks the user through selecting an
ND2 file, choosing the phase-contrast channel and feature set, and configuring
fluorescence channel feature selections. The resulting context is printed so it can
be passed to the processing workers or other automation.
