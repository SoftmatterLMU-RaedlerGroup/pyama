# -*- mode: python ; coding: utf-8 -*-

# Minimal PyInstaller spec for PyAMA-Qt (Qt GUI)
# Relies on built-in hooks (e.g., PySide6) without manual data/hiddenimports.

block_cipher = None

a = Analysis(
    ['pyama-qt/src/pyama_qt/main.py'],
    # Include project roots so imports resolve without extra config
    pathex=['.', 'pyama-qt/src', 'pyama-core/src'],
    binaries=[],
    datas=[],
    hiddenimports=['xsdata_pydantic_basemodel.hooks'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='pyama-qt',
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    bootloader_ignore_signals=False,
    strip=False,
    onefile=True,
)
