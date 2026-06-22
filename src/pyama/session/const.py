import os

PLOT_COLOR = 'k'
PLOT_COLOR_HIGHLIGHT = '#ff0000'
PLOT_ALPHA = .3
PLOT_ALPHA_HIGHLIGHT = 1
PLOT_WIDTH = 1.5
PLOT_WIDTH_HIGHLIGHT = 2

ROI_COLOR_SELECTED = '#00aa00'
ROI_COLOR_DESELECTED = '#0088ff'
ROI_COLOR_UNTRACKABLE = '#cc00cc'
ROI_COLOR_HIGHLIGHT = '#ff0000'
ROI_WIDTH = 1
ROI_WIDTH_HIGHLIGHT = 3

DESELECTED_DARKEN_FACTOR = .3

TYPE_AREA = 'Area'

CMD_INIT_SESSION = 'cmd_init_session'
CMD_READ_SESSION_FROM_DISK = 'cmd_read_session_from_disk'
CMD_SAVE_SESSION_TO_DISK = 'cmd_save_session_to_disk'
CMD_CONFIG_SESSION = 'cmd_config_session'
CMD_SET_MICROSCOPE = 'cmd_set_microscope'
CMD_SET_SESSION = 'cmd_set_session'
CMD_DISCARD_SESSION = 'cmd_discard_session'
CMD_NEW_STACK = 'cmd_new_stack'
CMD_UPDATE_STACK_LIST = 'cmd_update_stack_list'
CMD_CLOSE_STACK = 'cmd_close_stack'
CMD_UPDATE_TRACES = 'cmd_update_traces'
CMD_TOOL_BINARIZE = 'cmd_tool_binarize'
CMD_TOOL_BGCORR = 'cmd_tool_bgcorr'
CMD_RESTART_APP = 'cmd_restart_app'
CMD_QUIT_APP = 'cmd_quit_app'

RESP_NEW_SESSION_ID = 'resp_new_session_id'

CONST_INITIAL_DIR = '/project/ag-moonraedler/'