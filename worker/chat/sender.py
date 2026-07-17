"""
聊天发送器 — 统一的网站聊天消息发送实现。

合并自原有两份重复实现：
  - automation/chat_sender.py（通用版）
  - automation/monitors/itemmania.py（ItemMania 专用版）

现在所有平台统一调用本模块的 send_web_chat()。
"""
import asyncio
import os
import tempfile
from typing import Optional


def send_web_chat(account_id: int, chat_url: str, scripts: list,
                  main_loop: Optional[asyncio.AbstractEventLoop] = None,
                  keep_open: bool = False) -> dict:
    """同步入口：向网站聊天页面发送招呼消息，阻塞直到完成。

    Args:
        account_id: 账号 ID（定位浏览器会话）
        chat_url:  聊天页面完整 URL
        scripts:   话术列表 [{"content": "...", "image_url": "..."}, ...]
        main_loop: 主事件循环引用（可选，优先用于跨线程调度）
        keep_open: True 时保留聊天页面不关闭，供后续使用

    Returns:
        {"success": bool, "message": str}
    """
    from browser.session import BrowserSession

    print(f"[ChatSender] 开始发送招呼 account_id={account_id}, "
          f"chat_url={chat_url}, 话术条数={len(scripts)}")

    # ── URL 校验 ──
    if not chat_url:
        return {"success": False, "message": "无效的聊天URL"}

    session = BrowserSession.get_or_create(account_id=account_id)
    if session._context is None:
        return {"success": False, "message": "浏览器会话未初始化"}

    # ── 确定目标事件循环 ──
    owner_loop = main_loop or session.owner_loop
    if owner_loop is None or owner_loop.is_closed() or not owner_loop.is_running():
        return {"success": False, "message": "浏览器事件循环不可用"}

    coroutine = _do_send_web_chat(session, chat_url, scripts, keep_open=keep_open)
    try:
        future = asyncio.run_coroutine_threadsafe(coroutine, owner_loop)
        return future.result(timeout=120)
    except TimeoutError:
        future.cancel()
        return {"success": False, "message": "招呼发送超时（120s）"}
    except Exception as e:
        if not coroutine.cr_running:
            coroutine.close()
        return {"success": False, "message": f"招呼执行异常: {e}"}


async def _do_send_web_chat(session, chat_url: str, scripts: list,
                          keep_open: bool = False) -> dict:
    """Async 实现：打开聊天页面 → 逐条发送 → (可选)关闭页面。

    Args:
        keep_open: True 时保留聊天页面不关闭，供后续使用（如持续监控）
    """
    if not session.begin_transient_operation():
        return {"success": False, "message": "浏览器会话正在关闭"}

    page = None
    try:
        page = await session.new_page()
        session.track_transient_page(page)

        # 打开聊天页面
        print(f"[ChatSender] 打开聊天页面: {chat_url}")
        await page.goto(chat_url, wait_until="commit", timeout=10000)
        print(f"[ChatSender] 页面 commit 完成")
        await page.wait_for_timeout(500)

        # 等待输入框和发送按钮就绪（带重试）
        input_ready = False
        for attempt in range(2):
            try:
                await page.locator("#write_chat").first.wait_for(timeout=5000)
                await page.locator("#send_btn").first.wait_for(timeout=2000)
                input_ready = True
                print(f"[ChatSender] 输入框和发送按钮已就绪")
                break
            except Exception:
                print(f"[ChatSender] 第{attempt+1}次等待元素失败，尝试重试...")
                await page.wait_for_timeout(1000)

        if not input_ready:
            return {"success": False, "message": "聊天页面加载超时，输入框或发送按钮未找到"}

        # 图片相对路径补全：优先 STORAGE_PUBLIC_BASE_URL，为空则走后端代理
        from core.config import STORAGE_PUBLIC_BASE_URL, BACKEND_WS_URL
        from urllib.parse import urlparse
        if STORAGE_PUBLIC_BASE_URL:
            image_base = STORAGE_PUBLIC_BASE_URL.rstrip("/")
        else:
            _ws = urlparse(BACKEND_WS_URL)
            _scheme = "https" if _ws.scheme == "wss" else "http"
            image_base = f"{_scheme}://{_ws.netloc}"

        # 逐条发送
        failed_items = []
        print(f"[ChatSender] 开始逐条发送话术，共{len(scripts)}条")
        for i, item in enumerate(scripts):
            image_url = item.get("image_url", "")
            content = item.get("content", "")
            print(f"[ChatSender] 处理第{i+1}/{len(scripts)}条: "
                  f"content_len={len(content)}, has_image={bool(image_url)}")

            if image_url:
                # 相对路径补全域名
                if image_url.startswith("/"):
                    image_url = image_base + image_url
                try:
                    await _send_image_via_chat(page, image_url)
                except Exception as e:
                    print(f"[ChatSender] 图片发送失败 (第{i+1}条): {e}")
                    failed_items.append(f"第{i+1}条图片发送失败: {e}")

            if content:
                await page.locator("#write_chat").first.click()
                await page.keyboard.type(str(content), delay=50)
                await page.locator("#send_btn").click(force=True, timeout=5000)
                await page.wait_for_timeout(600)
                print(f"[ChatSender] 第{i+1}条文字已发送: "
                      f"{content[:30]}{'...' if len(content) > 30 else ''}")
            elif not image_url:
                print(f"[ChatSender] 第{i+1}条无内容，跳过")

        # 若最后一条包含图片消息，额外等待确保上传完成
        last_item = scripts[-1] if scripts else {}
        if last_item.get("image_url"):
            print(f"[ChatSender] 最后一条为图片消息，额外等待10秒确保上传完成")
            await page.wait_for_timeout(10000)

        if failed_items:
            msg = f"招呼部分失败: {'; '.join(failed_items)}"
            print(f"[ChatSender] {msg}")
            return {"success": False, "message": msg}

        print(f"[ChatSender] 所有招呼已发送 (共{len(scripts)}条)")
        return {"success": True, "message": "招呼发送成功"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"招呼执行异常: {e}"}
    finally:
        try:
            if page:
                if keep_open:
                    print(f"[ChatSender] 保留聊天页面供后续使用: {chat_url}")
                else:
                    try:
                        await page.close()
                    except Exception:
                        pass
                    finally:
                        session.untrack_transient_page(page)
        finally:
            session.end_transient_operation()


async def _send_image_via_chat(page, image_url: str):
    """下载图片并通过聊天页面的 input[type=file] 自动上传发送。

    页面机制：设置文件到 input[type=file] 后，页面 JS 会自动上传，
    无需点击发送按钮。
    """
    import requests

    print(f"[ChatSender] 开始下载图片: {image_url}")

    def _download():
        resp = requests.get(image_url, timeout=15)
        resp.raise_for_status()
        print(f"[ChatSender] 图片下载完成, size={len(resp.content)} bytes")
        return resp.content

    try:
        img_data = await asyncio.to_thread(_download)
    except Exception as e:
        print(f"[ChatSender] 图片下载失败: {e}")
        raise

    ext = _guess_ext(image_url)
    print(f"[ChatSender] 图片写入临时文件 ext={ext}")
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    try:
        tmp.write(img_data)
        tmp.close()

        # 对 attach_layer 中的 input[type=file] 设置文件
        # 页面 JS 会自动检测 change 事件并上传，无需点击发送按钮
        file_input = page.locator("#attach_layer input[type=file]")
        if await file_input.count() == 0:
            raise RuntimeError("上传控件 #attach_layer input[type=file] 未找到")
        await file_input.set_input_files(tmp.name)
        print(f"[ChatSender] 文件已设置到上传控件，等待自动上传")

        # 等待上传完成（attach_layer 自动关闭或 file_info 更新）
        await page.wait_for_timeout(2000)

        # 如果 attach_layer 仍然可见，尝试关闭
        close_btn = page.locator("#attach_layer .close")
        if await close_btn.count() > 0 and await close_btn.is_visible():
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
