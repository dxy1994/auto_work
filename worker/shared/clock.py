"""全局 print 拦截器：所有 print() 自动带时间戳。"""
import builtins
from datetime import datetime

_original_print = builtins.print


def _ts_print(*args, **kwargs):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _original_print(f"[{ts}]", *args, **kwargs)


def install():
    """安装时间戳 print 拦截器。"""
    builtins.print = _ts_print
