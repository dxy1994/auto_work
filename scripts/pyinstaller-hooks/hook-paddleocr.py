"""Collect the OCR runtime without the optional document-to-Markdown stack."""

from PyInstaller.utils.hooks import collect_all, is_module_or_submodule


def _is_required_submodule(name: str) -> bool:
    return not is_module_or_submodule(name, "paddleocr._doc2md")


datas, binaries, hiddenimports = collect_all(
    "paddleocr",
    filter_submodules=_is_required_submodule,
)
