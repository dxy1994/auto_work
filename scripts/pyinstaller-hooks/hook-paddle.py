"""Collect Paddle CPU inference without compiler and TensorRT tooling."""

from PyInstaller.utils.hooks import collect_all, is_module_or_submodule


def _is_required_submodule(name: str) -> bool:
    excluded_modules = (
        "paddle.tensorrt",
        "paddle.utils.cpp_extension",
    )
    return not any(
        is_module_or_submodule(name, excluded)
        for excluded in excluded_modules
    )


datas, binaries, hiddenimports = collect_all(
    "paddle",
    filter_submodules=_is_required_submodule,
)
