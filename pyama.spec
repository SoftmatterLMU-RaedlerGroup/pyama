# -*- mode: python ; coding: utf-8 -*-

# PyInstaller spec for PyAMA (Qt GUI)
# Entry point discovered from pyproject: pyama_qt.main:main
# Source file: pyama-qt/src/pyama_qt/main.py

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Ensure Qt plugins and submodules are collected for onefile build
_pyside6_datas = collect_data_files('PySide6', include_py_files=True)
_hidden = collect_submodules('PySide6') + collect_submodules('shiboken6')


a = Analysis(
    ['pyama-qt/src/pyama_qt/main.py'],
    pathex=['.'],
    binaries=[],
    datas=_pyside6_datas,
    hiddenimports=_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Build as a single-file executable (onefile)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='pyama',
    console=True,  # keep True to see errors in terminal; flip to False later if desired
    disable_windowed_traceback=False,
    target_arch=None,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    bootloader_ignore_signals=False,
    strip=False,
    onefile=True,
    # debug=True,  # uncomment to get verbose console from the bootloader
)
