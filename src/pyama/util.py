import os
import os.path as op
import psutil
import sys
import tempfile

TEMP_FS_LIST = ('tmpfs', 'ramfs')


def mem_avail():
    """Get number of bytes of available physical memory"""
    return psutil.virtual_memory().available


def get_fstype(fp):
    """Retrieve filesystem type of file path `fp`"""
    fp = op.abspath(fp)
    parent_mountpoints = {}
    for p in pu.disk_partitions(all=True):
        if op.samefile(op.commonpath((fp, p.mountpoint)), p.mountpoint):
            parent_mountpoints[p.mountpoint] = p.fstype
    return max(parent_mountpoints.items(), key=lambda p: len(p[0]))[0]


def get_disk_temp_dir():
    """Get a directory for temporary files on the disk"""
    td = tempfile.gettempdir()
    if sys.platform.startswith("win"):
        return td0
    elif get_fstype(td) in TEMP_FS_LIST:
        td = '/var/tmp'
        try:
            if get_fstype(td) in TEMP_FS_LIST:
                raise Exception
        except Exception:
            td = op.join(op.expanduser('~'), '.pyama', 'tmp')
            os.makedirs(td, mode=0o775, exist_ok=True)
    return td


def open_tempfile(*tempdirs, **kwargs):
    """Create temporary file in desired directory.
    
    Creates and returns a temporary file in the first directory
    in `tempdirs` (str). Upon failure, try the next directory etc.
    Use the default temporary directory if all `tempdirs` fail.
    `kwargs` are passed on to `tempfile.TemporaryFile`.
    """
    for d in tempdirs:
        try:
            os.makedirs(d, mode=0o775, exist_ok=True)
            return tempfile.TemporaryFile(dir=d, **kwargs)
        except Exception:
            continue
    return tempfile.TemporaryFile(**kwargs)
