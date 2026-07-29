"""Collect chardet's nested mypyc extensions using fully qualified names."""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


datas = collect_data_files("chardet")
hiddenimports = collect_submodules("chardet.pipeline")
