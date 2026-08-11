# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('D:\\work\\auto_work\\worker\\.env.monitor.example', '.')]
binaries = []
hiddenimports = ['pythoncom', 'pywintypes', 'win32com.client', 'bs4']
hiddenimports += collect_submodules('common')
hiddenimports += collect_submodules('monitor')
tmp_ret = collect_all('patchright')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['D:\\work\\auto_work\\worker\\monitor\\main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['D:\\work\\auto_work\\scripts\\pyinstaller-hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests', 'game_executor', 'paddle', 'paddleocr', 'paddlex', 'cv2'],
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
    name='auto-monitor',
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
