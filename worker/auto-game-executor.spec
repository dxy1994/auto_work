# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import copy_metadata

datas = [('D:\\work\\auto_work\\worker\\.env.game-executor.example', '.'), ('D:\\work\\auto_work\\worker\\game_executor\\executor\\lineage_classic\\images', 'game_executor\\executor\\lineage_classic\\images')]
hiddenimports = ['pythoncom', 'pywintypes', 'win32com.client']
datas += copy_metadata('python-bidi')
datas += copy_metadata('opencv-contrib-python')
datas += copy_metadata('pyclipper')
datas += copy_metadata('imagesize')
datas += copy_metadata('pypdfium2')
datas += copy_metadata('shapely')
hiddenimports += collect_submodules('common')
hiddenimports += collect_submodules('game_executor')


a = Analysis(
    ['D:\\work\\auto_work\\worker\\game_executor\\main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['D:\\work\\auto_work\\scripts\\pyinstaller-hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests', 'monitor', 'patchright', 'playwright', 'pygame'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='auto-game-executor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
