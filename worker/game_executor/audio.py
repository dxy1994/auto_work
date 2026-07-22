"""游戏执行端的 Windows 语音播报。"""

import subprocess


_POWERSHELL_SPEECH_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$synth = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $voice = $synth.GetInstalledVoices() |
        Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'zh-*' } |
        Select-Object -First 1
    if ($null -ne $voice) {
        $synth.SelectVoice($voice.VoiceInfo.Name)
    }
    $synth.Speak([Console]::In.ReadToEnd())
}
finally {
    $synth.Dispose()
}
"""


def _speak_with_powershell(message: str) -> None:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            _POWERSHELL_SPEECH_SCRIPT,
        ],
        input=message.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
        creationflags=creation_flags,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or f"PowerShell exit code {result.returncode}")


def _speak_with_sapi(message: str) -> None:
    import pythoncom
    from win32com.client import Dispatch

    pythoncom.CoInitialize()
    try:
        Dispatch("SAPI.SpVoice").Speak(message)
    finally:
        pythoncom.CoUninitialize()


def _system_beep() -> None:
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass


def speak_text(text: str) -> bool:
    """优先使用 System.Speech，失败后依次回退到 SAPI 和系统蜂鸣。"""
    message = str(text or "").strip()
    if not message:
        return False

    print(f"[GameExecutorAudio] 开始播报: {message}")
    try:
        _speak_with_powershell(message)
        print("[GameExecutorAudio] 播报完成（System.Speech）")
        return True
    except Exception as powershell_error:
        print(
            "[GameExecutorAudio] System.Speech 播报失败，尝试 SAPI: "
            f"{powershell_error}"
        )

    try:
        _speak_with_sapi(message)
        print("[GameExecutorAudio] 播报完成（SAPI）")
        return True
    except Exception as sapi_error:
        print(f"[GameExecutorAudio] SAPI 播报失败: {sapi_error}")
        try:
            _system_beep()
        finally:
            print("[GameExecutorAudio] 未找到可用的文字语音引擎，已回退为系统提示音")
        return False
