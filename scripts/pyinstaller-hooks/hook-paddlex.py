"""Collect local PaddleX inference without unused server and GenAI plugins."""

from PyInstaller.utils.hooks import collect_all, is_module_or_submodule


def _is_required_submodule(name: str) -> bool:
    excluded_modules = (
        "paddlex.inference.serving",
        "paddlex.inference.genai",
    )
    return not any(
        is_module_or_submodule(name, excluded)
        for excluded in excluded_modules
    )


datas, binaries, hiddenimports = collect_all(
    "paddlex",
    filter_submodules=_is_required_submodule,
)
