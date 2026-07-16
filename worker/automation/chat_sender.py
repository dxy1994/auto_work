"""
chat_sender.py — Web 聊天发送器（ItemMania）。

在浏览器中打开聊天页面，逐条发送文字和图片消息。
从同步线程调用，通过 asyncio.run_coroutine_threadsafe() 桥接到主事件循环。
"""

import asyncio
import tempfile
import os
from concurrent.futures import Future
from typing import Optional

# 主事件循环引用（由 main.py 设置）
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_loop(loop: asyncio.AbstractEventLoop):
    """存储主事件循环引用，供跨线程调度。"""
    global _main_loop
    _main_loop = loop


def send_web_chat(account_id: int, chat_url: str, scripts: list) -> dict:
    """同步入口：向 ItemMania 聊天页面发送招呼消息，阻塞直到完成。

    Args:
        account_id: 账号 ID（定位浏览器会话）
        chat_url:  聊天页面完整 URL
        scripts:   话术列表 [{"content": "...", "image_url": "..."}, ...]

    Returns:
        {"success": bool, "message": str}
    """
    if _main_loop is None:
        return {"success": False, "message": "event loop 未初始化"}

    future = asyncio.run_coroutine_threadsafe(
        _do_send_web_chat(account_id, chat_url, scripts),
        _main_loop,
    )
    try:
        return future.result(timeout=120)
    except TimeoutError:
        future.cancel()
        return {"success": False, "message": "招呼发送超时（120s）"}
    except Exception as e:
        return {"success": False, "message": f"招呼执行异常: {e}"}


async def _do_send_web_chat(account_id: int, chat_url: str, scripts: list) -> dict:
    """Async 实现：打开聊天页面 → 逐条发送 → 关闭页面。"""
    from automation.browser_session import BrowserSession

    # 获取已有浏览器会话（不上传配置，不执行登录）
    session = BrowserSession.get_or_create(account_id=account_id)
    if session._context is None:
        return {"success": False, "message": "浏览器会话未初始化"}

    page = None
    try:
        page = await session.new_page()

        # 打开聊天页面
        print(f"[ChatSender] 打开聊天页面: {chat_url}")
        await page.goto(chat_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        # 等待页面就绪
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # 等待输入框可用
        try:
            await page.wait_for_selector("#write_chat", timeout=10000)
            await page.wait_for_selector("#send_btn", timeout=5000)
        except Exception:
            return {"success": False, "message": "聊天页面加载超时，输入框或发送按钮未找到"}

        # 逐条发送
        for i, item in enumerate(scripts):
            image_url = item.get("image_url", "")
            content = item.get("content", "")

            # 先发图片
            if image_url:
                try:
                    await _send_image_via_chat(page, image_url)
                except Exception as e:
                    print(f"[ChatSender] 图片发送失败 (第{i+1}条): {e}")

            # 再发文字
            if content:
                await page.fill("#write_chat", content)
                await page.click("#send_btn")
                await page.wait_for_timeout(600)
                print(f"[ChatSender] 第{i+1}条文字已发送")

        print(f"[ChatSender] 所有招呼已发送 (共{len(scripts)}条)")
        return {"success": True, "message": "招呼发送成功"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"招呼执行异常: {e}"}
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


async def _send_image_via_chat(page, image_url: str):
    """下载图片并通过聊天页面的文件上传发送。

    1. 下载图片到临时文件（用 requests + asyncio.to_thread 避免阻塞）
    2. set_input_files 上传到 #attach_layer
    3. 点击发送按钮
    """
    import requests
    from io import BytesIO
    from PIL import Image

    # 下载图片（在线程池中执行，不阻塞事件循环）
    def _download():
        resp = requests.get(image_url, timeout=15)
        resp.raise_for_status()
        return resp.content

    img_data = await asyncio.to_thread(_download)

    # 写入临时文件
    ext = _guess_ext(image_url)
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    try:
        tmp.write(img_data)
        tmp.close()

        # 用 Playwright 上传文件
        file_input = page.locator("#attach_layer input[type=file]")
        await file_input.set_input_files(tmp.name)

        # 等待预览加载
        await page.wait_for_timeout(1000)

        # 点击发送
        send_btn = page.locator("#attach_layer .btn_send")
        await send_btn.click()
        await page.wait_for_timeout(800)

        # 关闭 attach_layer
        close_btn = page.locator("#attach_layer .close")
        if await close_btn.is_visible():
            await close_btn.click()
            await page.wait_for_timeout(300)

        print(f"[ChatSender] 图片已发送: {image_url}")
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def _guess_ext(url: str) -> str:
    """从 URL 推测文件扩展名。"""
    url_lower = url.lower()
    if ".png" in url_lower:
        return ".png"
    if ".jpg" in url_lower or ".jpeg" in url_lower:
        return ".jpg"
    if ".webp" in url_lower:
        return ".webp"
    if ".gif" in url_lower:
        return ".gif"
    return ".png"
