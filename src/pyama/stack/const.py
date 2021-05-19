ST_FMT_BASE = 'base'
ST_FMT_TIFF = 'tiff'
ST_FMT_NUMPY = 'numpy'
ST_FMT_ILASTIK = 'ilastik'
ST_FMT_VIRTUAL = 'virtual'

T = 'T'
Z = 'Z'
C = 'C'
Y = 'Y'
X = 'X'

STACK_DIM = (T, Z, C)
IMG_DIM = (Y, X)
ALL_DIM = (T, Z, C, Y, X)

EVT_RESHAPE = 'stack-reshape'
EVT_STACK_RENAME = 'stack-rename'
EVT_CLOSE = 'stack-close'
