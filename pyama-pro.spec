# -*- mode: python ; coding: utf-8 -*-

# Minimal PyInstaller spec for PyAMA-Qt (Qt GUI)
# Relies on built-in hooks (e.g., PySide6) without manual data/hiddenimports.

from PyInstaller.utils.hooks import collect_submodules, copy_metadata
hiddenimports = collect_submodules('xsdata_pydantic_basemodel.hooks')
# Include bioio plugin modules with underscores, not hyphens
hiddenimports += collect_submodules('bioio_nd2')
# If CZI plugin is desired, include it as well
hiddenimports += collect_submodules('bioio_czi')

block_cipher = None

# Collect plugin distribution metadata so entry-point discovery works in bundle
plugin_metadata = []
plugin_metadata += copy_metadata('bioio')
plugin_metadata += copy_metadata('bioio-nd2')
plugin_metadata += copy_metadata('bioio-czi')

a = Analysis(
    ['pyama-pro/src/pyama_pro/main.py'],
    # Include project roots so imports resolve without extra config
    pathex=['.', 'pyama-pro/src', 'pyama-core/src'],
    binaries=[],
    datas=plugin_metadata,
    hiddenimports=hiddenimports,
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
    name='pyama-pro',
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
