"""
提醒音频播放模块。

提供统一的音频提醒接口，支持三种播放方式（按优先级回退）：
  1. win32com SAPI.SpVoice 文字转语音（同步模式，阻塞调用线程）
  2. RustFS 对象存储或本地音频文件（守护线程播放）
  3. 系统蜂鸣（守护线程播放）

公共方法：
  - play_alert_audio(audio_path=None, text=None): 播放提醒音频
  - stop_speech(): 停止当前正在播放的语音（供 shutdown 调用）

设计决策（同步 Speak）：
  - Speak() 在调用线程上同步阻塞，确保播报期间调用方循环不会继续迭代入队新消息
  - 浏览器关闭 → 循环退出 → 没有新 Speak 调用 → 语音自然停止
  - 避免了 AudioThread 与 captcha 循环生命周期脱节导致关闭后仍播报的问题
"""

import asyncio
import functools
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import storage_sync

# 项目根目录（worker 的上一级），用于解析可选的自定义音频文件
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ── 全局 SAPI.SpVoice（懒初始化，仅在调用线程上使用）──
_voice = None
_voice_lock = threading.Lock()
_audio_executor = ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="audio-alert")


def _init_voice():
    """懒初始化 SAPI.SpVoice + COM。调用方必须持有 _voice_lock。"""
    global _voice
    if _voice is not None:
        return _voice

    import pythoncom
    pythoncom.CoInitialize()

    from win32com.client import Dispatch
    _voice = Dispatch("SAPI.SpVoice")
    print("[Audio] SAPI.SpVoice 初始化成功")
    return _voice


def _play_tts(text: str) -> bool:
    """
    同步播放 TTS 文字转语音。
    在调用线程上阻塞直到播报完成，确保播报期间调用方不会入队新消息。
    """
    try:
        from win32com.client import Dispatch  # noqa: F401  确认库可用
    except Exception as e:
        print(f"[Audio] win32com 不可用: {e}")
        return False

    with _voice_lock:
        voice = _init_voice()

    try:
        print(f"[Audio] 开始播报: {text[:30]}{'...' if len(text) > 30 else ''}")
        voice.Speak(text)  # 同步阻塞，播放完毕才返回
        print(f"[Audio] 播报完成: {text[:30]}{'...' if len(text) > 30 else ''}")
        return True
    except Exception as e:
        print(f"[Audio] 播报异常: {e}")
        # 尝试重新初始化语音引擎
        with _voice_lock:
            global _voice
            try:
                from win32com.client import Dispatch
                _voice = Dispatch("SAPI.SpVoice")
                print("[Audio] SpVoice 重新初始化成功")
            except Exception as re:
                print(f"[Audio] SpVoice 重新初始化失败: {re}")
                _voice = None
        return False


def stop_speech():
    """
    尝试停止当前正在播放的语音（供 shutdown 调用）。
    注意：同步 Speak() 阻塞期间无法从同一线程中断，
    本方法仅尝试让下一次 Speak 调用被略过。
    """
    # 同步模式下，Speak 阻塞时无法中断。
    # 但 shutdown 调用 stop_speech 后，captcha 循环已退出，
    # 不会再触发新的 Speak，语音自然停止。
    print("[Audio] stop_speech 调用（同步模式下无需额外操作）")


def play_alert_audio(audio_path: Optional[str] = None, text: Optional[str] = None) -> bool:
    """
    播放提醒音频的公共方法，其他模块可直接调用。

    优先级：
      1. 如果 text 有值 → SAPI.SpVoice 同步文字转语音播放
      2. 如果 audio_path 有效 → 从 RustFS 下载（uploads/ 前缀）或播放本地文件
      3. 否则 → 系统蜂鸣（Windows winsound / 终端 \\a）

    参数:
        audio_path: 音频文件的相对路径，如 "uploads/audio/abc.mp3"
                   RustFS 路径（uploads/ 前缀）会先从对象存储下载再播放，
                   其他路径视为本地文件
        text:       要转语音的文本字符串，传 None 或不传则跳过 TTS

    返回:
        bool: True 表示成功播放（含回退），False 表示所有方式均失败
    """
    # ── 1. 尝试文字转语音（同步阻塞）──
    if text:
        if _play_tts(text):
            return True
        # TTS 失败，继续回退到音频文件

    # ── 2. 尝试播放自定义音频文件 ──
    if audio_path:
        # 2a. RustFS 路径（uploads/ 前缀）→ 下载到临时文件
        normalized = audio_path.replace("\\", "/")
        if normalized.startswith("uploads/"):
            object_key = normalized[len("uploads/"):]  # uploads/audio/xxx.mp3 → audio/xxx.mp3
            tmp_path = storage_sync.download_file(object_key, suffix=Path(normalized).suffix)
            if tmp_path:
                if _play_audio_file(tmp_path, is_temp=True):
                    return True
                # 播放失败，清理临时文件
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
            # 下载失败，继续回退到蜂鸣

        # 2b. 本地文件路径（向后兼容）
        else:
            full_path = PROJECT_ROOT / audio_path
            if full_path.exists():
                if _play_audio_file(str(full_path)):
                    return True
                # 文件存在但播放失败，继续回退到蜂鸣

    # ── 3. 回退：系统蜂鸣 ──
    return _play_system_beep()


async def play_alert_audio_async(
        audio_path: Optional[str] = None,
        text: Optional[str] = None) -> bool:
    """在专用单线程中播放提醒，避免阻塞事件循环并保持 COM 线程亲和性。"""
    loop = asyncio.get_running_loop()
    call = functools.partial(play_alert_audio, audio_path, text)
    return await loop.run_in_executor(_audio_executor, call)


def _play_audio_file(file_path: str, is_temp: bool = False) -> bool:
    """
    播放音频文件，尝试多种后端。
    所有方案均放入守护线程，确保阻塞式播放不会被 executor 回收 kill 掉。
    不再在调用线程上 sleep，避免阻塞 asyncio 事件循环。

    参数:
        file_path: 音频文件本地路径
        is_temp:   True 表示该文件是临时文件，播放完毕后会自动删除
    """
    # 方案A: pygame（守护线程轮询播放状态，pygame>=2.6 对 Python 3.12 兼容最佳）
    try:
        import pygame

        def _pygame_play():
            pygame.mixer.init()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            if is_temp:
                _cleanup_temp(file_path)

        t = threading.Thread(target=_pygame_play, daemon=True)
        t.start()
        print(f"[Audio] pygame 播放中: {file_path}")
        return True
    except Exception as e:
        print(f"[Audio] pygame 不可用: {e}")

    # 方案C: Windows Media Player (win32com)
    try:
        from win32com.client import Dispatch

        def _wmplayer_play():
            mp = Dispatch("WMPlayer.OCX")
            mp.URL = file_path
            mp.controls.play()
            import pythoncom
            while mp.playState != 1:  # 1 = Stopped
                pythoncom.PumpWaitingMessages()
                time.sleep(0.1)
            if is_temp:
                _cleanup_temp(file_path)

        t = threading.Thread(target=_wmplayer_play, daemon=True)
        t.start()
        print(f"[Audio] WMPlayer 播放中: {file_path}")
        return True
    except Exception as e:
        print(f"[Audio] WMPlayer 不可用: {e}")

    # 所有播放后端均失败，如果是临时文件则直接清理
    if is_temp:
        _cleanup_temp(file_path)
    print(f"[Audio] 所有播放后端均失败: {file_path}")
    return False


def _cleanup_temp(file_path: str):
    """安全删除临时音频文件。"""
    try:
        os.unlink(file_path)
        print(f"[Audio] 已删除临时文件: {file_path}")
    except Exception as e:
        print(f"[Audio] 删除临时文件失败: {e}")


def _play_system_beep() -> bool:
    """系统蜂鸣回退（在守护线程中执行，避免阻塞调用线程）。"""
    def _beep():
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            time.sleep(0.3)
            winsound.Beep(1000, 500)
            time.sleep(0.1)
            winsound.Beep(1200, 500)
            time.sleep(0.1)
            winsound.Beep(1000, 500)
        except ImportError:
            print("\a" * 3)
    t = threading.Thread(target=_beep, daemon=True)
    t.start()
    return True
