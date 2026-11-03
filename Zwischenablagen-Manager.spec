# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [('icon.ico', '.')]
datas += collect_data_files('customtkinter')

# Speicherdienst: uvicorn und anyio laden Teile erst zur Laufzeit,
# unser Paket service wird nur bei "--service" importiert
hiddenimports = []
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('anyio')
hiddenimports += collect_submodules('service')


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Zwischenablagen-Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Zwischenablagen-Manager',
)