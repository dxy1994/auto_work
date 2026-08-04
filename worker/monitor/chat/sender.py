"""跨平台订单聊天发送器。

后端负责把订单解析为明确的客户会话地址和平台选择器；本模块只在订单
所属账号的浏览器会话中，严格按照消息顺序发送文字和图片。
"""

import asyncio
import os
import tempfile
from typing import Optional
from urllib.parse import urlparse

MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_CHAT_CLOSE_DELAY_MS = 10_000
DEFAULT_ITEMMANIA_TARGET = {
    "input_selector": "#write_chat",
    "send_selector": "#send_btn",
    "file_selector": "#attach_layer input[type=file]",
    "upload_auto_send": True,
    "upload_close_selector": "#attach_layer .close",
}


def send_chat(
    account_id: int,
    target: dict,
    messages: list,
    main_loop: Optional[asyncio.AbstractEventLoop] = None,
    keep_open: bool = False,
    post_action: Optional[dict] = None,
) -> dict:
    """同步入口：发送一批有序聊天消息，结束后始终关闭临时聊天页。"""
    from monitor.browser.session import BrowserSession

    try:
        normalized_messages = _normalize_messages(messages)
        normalized_target = _normalize_target(target, normalized_messages)
    except ValueError as exc:
        return {"success": False, "message": str(exc)}

    session = BrowserSession.get_or_create(account_id=account_id)
    if session._context is None:
        return {"success": False, "message": "浏览器会话未初始化"}

    owner_loop = main_loop or session.owner_loop
    if owner_loop is None or owner_loop.is_closed() or not owner_loop.is_running():
        return {"success": False, "message": "浏览器事件循环不可用"}

    coroutine = _do_send_chat_with_post_action(
        session,
        normalized_target,
        normalized_messages,
        post_action,
        keep_open=False,
    )
    try:
        future = asyncio.run_coroutine_threadsafe(coroutine, owner_loop)
        return future.result(timeout=120)
    except TimeoutError:
        future.cancel()
        return {"success": False, "message": "聊天发送超时（120s）"}
    except Exception as exc:
        if not coroutine.cr_running:
            coroutine.close()
        return {"success": False, "message": f"聊天执行异常: {exc}"}


def send_web_chat(
    account_id: int,
    chat_url: str,
    scripts: list,
    main_loop: Optional[asyncio.AbstractEventLoop] = None,
    keep_open: bool = False,
) -> dict:
    """兼容旧版招呼调用，按 ItemMania 默认配置转换为聊天指令。"""
    target = {**DEFAULT_ITEMMANIA_TARGET, "url": chat_url}
    messages = [
        {
            "content": item.get("content", ""),
            "image_urls": [item["image_url"]] if item.get("image_url") else [],
        }
        for item in (scripts or [])
    ]
    return send_chat(account_id, target, messages, main_loop, keep_open)


async def _do_send_web_chat(
    session,
    chat_url: str,
    scripts: list,
    keep_open: bool = False,
) -> dict:
    """兼容旧版异步入口；keep_open 参数不再保留聊天页。"""
    target = {**DEFAULT_ITEMMANIA_TARGET, "url": chat_url}
    messages = [
        {
            "content": item.get("content", ""),
            "image_urls": [item["image_url"]] if item.get("image_url") else [],
        }
        for item in (scripts or [])
    ]
    return await _do_send_chat(session, target, messages, keep_open=False)


async def _do_send_chat(
    session,
    target: dict,
    messages: list,
    keep_open: bool = False,
) -> dict:
    """串行执行聊天命令；keep_open 仅为兼容旧调用，页面始终关闭。"""
    chat_lock = getattr(session, "_chat_send_lock", None)
    if chat_lock is None:
        chat_lock = asyncio.Lock()
        setattr(session, "_chat_send_lock", chat_lock)
    async with chat_lock:
        return await _do_send_chat_locked(session, target, messages)


async def _do_send_chat_locked(
    session,
    target: dict,
    messages: list,
) -> dict:
    """打开客户会话并按消息顺序发送；含图片时保留页面 10 秒再关闭。"""
    try:
        messages = _normalize_messages(messages)
        target = _normalize_target(target, messages)
    except ValueError as exc:
        return {"success": False, "message": str(exc)}

    if not session.begin_transient_operation():
        return {"success": False, "message": "浏览器会话正在关闭"}

    page = None
    chat_url = target["url"]
    has_images = any(message["image_urls"] for message in messages)
    try:
        page = await session.new_page()
        session.track_transient_page(page)
        await page.goto(chat_url, wait_until="commit", timeout=10000)
        await page.wait_for_timeout(500)
        await _dismiss_blocking_popup(page, target)

        input_box = page.locator(target["input_selector"]).first
        send_button = page.locator(target["send_selector"]).first
        ready = False
        for _ in range(2):
            try:
                await input_box.wait_for(timeout=5000)
                await send_button.wait_for(timeout=2000)
                ready = True
                break
            except Exception:
                await page.wait_for_timeout(1000)
        if not ready:
            return {
                "success": False,
                "message": "客户聊天页面加载超时，未找到输入框或发送按钮",
            }
        if not await _locator_is_enabled(input_box):
            return {
                "success": False,
                "message": "客户聊天输入框当前不可用，可能已结束或被限制",
            }
        if not await _locator_is_enabled(send_button):
            return {
                "success": False,
                "message": "客户聊天发送按钮当前不可用，可能已结束或被限制",
            }

        image_base = _image_base_url()
        for index, message in enumerate(messages):
            for image_url in message["image_urls"]:
                resolved_url = (
                    image_base + image_url if image_url.startswith("/") else image_url
                )
                try:
                    await _send_image_via_chat(page, resolved_url, target)
                except Exception as exc:
                    return {
                        "success": False,
                        "message": f"第 {index + 1} 条消息的图片发送失败: {exc}",
                    }

            content = message["content"]
            if content:
                sent_before = await _sent_message_count(page, target)
                await input_box.click()
                await page.keyboard.type(content, delay=50)
                await send_button.click(force=True, timeout=5000)
                if sent_before is None:
                    await page.wait_for_timeout(
                        _positive_int(target.get("text_settle_ms"), 600)
                    )
                elif not await _wait_for_sent_message(
                        page, target, sent_before):
                    return {
                        "success": False,
                        "message": (
                            f"第 {index + 1} 条文字点击发送后"
                            "未在会话中显示"
                        ),
                    }

        return {
            "success": True,
            "message": f"聊天发送成功（{len(messages)} 条消息）",
        }
    except Exception as exc:
        return {"success": False, "message": f"聊天执行异常: {exc}"}
    finally:
        try:
            if page:
                try:
                    if has_images:
                        try:
                            await page.wait_for_timeout(
                                IMAGE_CHAT_CLOSE_DELAY_MS
                            )
                        except Exception:
                            # 页面可能被平台提前关闭，不能让等待失败覆盖发送结果。
                            pass
                    await page.close()
                finally:
                    session.untrack_transient_page(page)
        finally:
            session.end_transient_operation()


async def _do_send_chat_with_post_action(
    session,
    target: dict,
    messages: list,
    post_action: Optional[dict] = None,
    keep_open: bool = False,
) -> dict:
    """先完成聊天；有后置动作时关闭聊天页，再串行执行后置动作。"""
    action = dict(post_action or {})
    chat_result = await _do_send_chat(
        session,
        target,
        messages,
        keep_open=False,
    )
    if not action:
        return chat_result
    if not chat_result.get("success"):
        return {
            **chat_result,
            "chat_sent": False,
            "chat_closed": True,
            "delivery_confirmed": False,
        }
    if action.get("type") != "confirm_delivery":
        return {
            "success": False,
            "message": "不支持的聊天后置动作",
            "chat_sent": True,
            "chat_closed": True,
            "delivery_confirmed": False,
        }
    delivery_result = await _do_confirm_delivery(session, action)
    return {
        **delivery_result,
        "chat_sent": True,
        "chat_closed": True,
        "delivery_confirmed": bool(delivery_result.get("success")),
    }


async def _do_confirm_delivery(session, action: dict) -> dict:
    """打开订单详情页，点击两级商品交付确认，并复核页面状态。"""
    try:
        normalized = _normalize_delivery_action(action)
    except ValueError as exc:
        return {"success": False, "message": str(exc)}

    if not session.begin_transient_operation():
        return {"success": False, "message": "浏览器会话正在关闭"}

    page = None
    try:
        page = await session.new_page()
        session.track_transient_page(page)

        on_event = getattr(page, "on", None)
        if callable(on_event):
            def accept_dialog(dialog):
                asyncio.create_task(dialog.accept())

            on_event("dialog", accept_dialog)

        await page.goto(
            normalized["detail_url"],
            wait_until="domcontentloaded",
            timeout=15000,
        )
        await page.wait_for_timeout(1000)

        # Itemmania 在订单进入第 4/5 阶段后会移除交付按钮。先检查阶段，
        # 避免网站其实已经完成，却因为找不到 #trade_btn 被判为失败。
        current_stage, current_status = await _try_read_delivery_stage(
            page, normalized, timeout=3000
        )
        if current_stage is None:
            current_status = await _try_read_delivery_status_text(
                page, normalized, timeout=3000
            )
        if (
            _delivery_stage_is_complete(current_stage, normalized)
            or _delivery_status_text_is_complete(current_status, normalized)
        ):
            if current_stage is None:
                status_description = f"当前状态：{current_status}"
            else:
                status_description = (
                    f"当前第 {current_stage} 阶段：{current_status or '未知'}"
                )
            return {
                "success": True,
                "message": (
                    "截图已发送，网站订单已离开第 "
                    f"{normalized['pending_stage']} 阶段"
                    f"（{status_description}），"
                    "按已完成处理"
                ),
                "website_stage": current_stage,
                "website_status": current_status,
                "already_completed": True,
            }

        open_confirm = page.locator(
            normalized["open_confirm_selector"]
        ).first
        await open_confirm.wait_for(state="visible", timeout=10000)
        await open_confirm.click(force=True, timeout=5000)

        confirm = page.locator(normalized["confirm_selector"]).first
        await confirm.wait_for(state="visible", timeout=5000)
        await confirm.click(force=True, timeout=10000)
        await page.wait_for_timeout(1500)

        # 重新进入详情页，以服务器最终状态作为成功依据，避免只凭点击判断。
        await page.goto(
            normalized["detail_url"],
            wait_until="domcontentloaded",
            timeout=15000,
        )
        current_stage, current_status = await _try_read_delivery_stage(
            page, normalized, timeout=10000
        )
        if current_stage is not None:
            if not _delivery_stage_is_complete(current_stage, normalized):
                return {
                    "success": False,
                    "message": (
                        "网站商品交付状态未更新，仍在第 "
                        f"{current_stage} 阶段：{current_status or '未知'}"
                    ),
                    "website_stage": current_stage,
                    "website_status": current_status,
                }
            return {
                "success": True,
                "message": (
                    "截图已发送，聊天页已关闭，网站订单已进入第 "
                    f"{current_stage} 阶段：{current_status or '未知'}"
                ),
                "website_stage": current_stage,
                "website_status": current_status,
                "already_completed": False,
            }

        status = page.locator(normalized["success_selector"]).first
        await status.wait_for(state="visible", timeout=10000)
        status_text = (await status.inner_text()).strip()
        if not any(
            expected in status_text
            for expected in normalized["success_texts"]
        ):
            return {
                "success": False,
                "message": f"网站商品交付状态未更新，当前状态: {status_text or '未知'}",
            }
        return {
            "success": True,
            "message": "截图已发送，聊天页已关闭，网站商品交付已确认",
        }
    except Exception as exc:
        return {"success": False, "message": f"网站商品交付确认失败: {exc}"}
    finally:
        try:
            if page:
                try:
                    await page.close()
                finally:
                    session.untrack_transient_page(page)
        finally:
            session.end_transient_operation()


async def _try_read_delivery_stage(
        page, normalized: dict, timeout: int) -> tuple[Optional[int], str]:
    """读取当前激活的交付阶段；页面无阶段状态条时交给文本规则继续判断。"""
    selector = normalized.get("stage_selector")
    if not selector:
        return None, ""
    try:
        stages = page.locator(selector)
        await stages.first.wait_for(state="visible", timeout=timeout)
        for index in range(await stages.count()):
            stage = stages.nth(index)
            class_names = str(
                await stage.get_attribute("class") or ""
            ).split()
            if "active" in class_names:
                return index + 1, (await stage.inner_text()).strip()
    except Exception:
        return None, ""
    return None, ""


async def _try_read_delivery_status_text(
        page, normalized: dict, timeout: int) -> str:
    try:
        status = page.locator(normalized["success_selector"]).first
        await status.wait_for(state="visible", timeout=timeout)
        return (await status.inner_text()).strip()
    except Exception:
        return ""


def _delivery_stage_is_complete(
        current_stage: Optional[int], normalized: dict) -> bool:
    pending_stage = normalized.get("pending_stage")
    return (
        current_stage is not None
        and pending_stage is not None
        and current_stage > pending_stage
    )


def _delivery_status_text_is_complete(
        status_text: str, normalized: dict) -> bool:
    return bool(status_text) and any(
        expected in status_text
        for expected in normalized.get("success_texts", [])
    )


async def _send_image_via_chat(page, image_url: str, target: dict):
    """下载一张图片，并通过平台配置的文件控件完成上传/发送。"""
    import requests

    max_image_bytes = _positive_int(
        target.get("max_image_bytes"), MAX_IMAGE_BYTES)
    if max_image_bytes <= 0:
        max_image_bytes = MAX_IMAGE_BYTES

    def _download():
        with requests.get(image_url, timeout=15, stream=True) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").split(";")[0]
            if content_type and not content_type.lower().startswith("image/"):
                raise RuntimeError("下载地址返回的不是图片")
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_IMAGE_BYTES:
                raise RuntimeError("图片超过 10MB")
            chunks = []
            total = 0
            for chunk in response.iter_content(64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_image_bytes:
                    limit_mb = max_image_bytes / 1024 / 1024
                    raise RuntimeError(f"图片超过 {limit_mb:g}MB")
                chunks.append(chunk)
            if not chunks:
                raise RuntimeError("下载到的图片为空")
            return b"".join(chunks), content_type

    image_data, content_type = await asyncio.to_thread(_download)
    suffix = _guess_ext(image_url, content_type)
    temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        temp_file.write(image_data)
        temp_file.close()

        sent_before = await _sent_message_count(page, target)
        file_input = page.locator(target["file_selector"]).first
        if await file_input.count() == 0:
            raise RuntimeError("未找到聊天图片上传控件")
        await file_input.set_input_files(temp_file.name)

        if not target.get("upload_auto_send", True):
            upload_send = page.locator(target["upload_send_selector"]).first
            await upload_send.wait_for(timeout=5000)
            await upload_send.click(force=True, timeout=5000)

        if sent_before is None:
            await page.wait_for_timeout(
                _positive_int(target.get("image_settle_ms"), 2000)
            )
        elif not await _wait_for_sent_message(page, target, sent_before):
            raise RuntimeError("图片选择后未在会话中显示")
        close_selector = str(target.get("upload_close_selector") or "").strip()
        if close_selector:
            close_button = page.locator(close_selector).first
            if await close_button.count() > 0 and await close_button.is_visible():
                await close_button.click()
                await page.wait_for_timeout(300)
    finally:
        try:
            os.unlink(temp_file.name)
        except OSError:
            pass


def _normalize_target(target: dict, messages: list) -> dict:
    if not isinstance(target, dict):
        raise ValueError("聊天目标配置无效")
    result = dict(target)
    for key, label in (
        ("url", "客户聊天地址"),
        ("input_selector", "聊天输入框选择器"),
        ("send_selector", "聊天发送按钮选择器"),
    ):
        result[key] = str(result.get(key) or "").strip()
        if not result[key]:
            raise ValueError(f"{label}未配置")
    parsed = urlparse(result["url"])
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("客户聊天地址无效")

    has_images = any(
        isinstance(message, dict)
        and (message.get("image_url") or message.get("image_urls"))
        for message in (messages or [])
    )
    result["file_selector"] = str(result.get("file_selector") or "").strip()
    if has_images and not result["file_selector"]:
        raise ValueError("聊天图片上传控件选择器未配置")
    result["upload_auto_send"] = result.get("upload_auto_send", True) is not False
    result["upload_send_selector"] = str(
        result.get("upload_send_selector") or ""
    ).strip()
    result["blocking_popup_selector"] = str(
        result.get("blocking_popup_selector") or ""
    ).strip()
    result["blocking_popup_close_selector"] = str(
        result.get("blocking_popup_close_selector") or ""
    ).strip()
    is_itembay_chat = (
        (parsed.hostname or "").lower() in {"itembay.com", "www.itembay.com"}
        and parsed.path.rstrip("/").endswith(
            "/ibmessenger/bayTalkChatTran"
        )
    )
    if is_itembay_chat:
        if not result["blocking_popup_selector"]:
            result["blocking_popup_selector"] = "#sTalkPop"
        if not result["blocking_popup_close_selector"]:
            result["blocking_popup_close_selector"] = (
                "#sTalkPop .btn_pop_close"
            )
    if result["blocking_popup_close_selector"]:
        result["blocking_popup_wait_ms"] = max(
            100,
            _positive_int(result.get("blocking_popup_wait_ms"), 2000),
        )
    if (
        has_images
        and not result["upload_auto_send"]
        and not result["upload_send_selector"]
    ):
        raise ValueError("图片上传后发送按钮选择器未配置")
    result["sent_selector"] = str(
        result.get("sent_selector") or ""
    ).strip()
    if result["sent_selector"]:
        result["sent_timeout_ms"] = max(
            100,
            _positive_int(result.get("sent_timeout_ms"), 10000),
        )
    max_text_length = _positive_int(
        result.get("max_text_length"), 0)
    if max_text_length > 0:
        for index, message in enumerate(messages or []):
            content = str(
                message.get("content") or message.get("text") or ""
            )
            if len(content) > max_text_length:
                raise ValueError(
                    f"第 {index + 1} 条文字超过平台限制 "
                    f"{max_text_length} 个字符"
                )
        result["max_text_length"] = max_text_length
    max_image_bytes = _positive_int(
        result.get("max_image_bytes"), 0)
    if max_image_bytes > 0:
        result["max_image_bytes"] = max_image_bytes
    return result


async def _dismiss_blocking_popup(page, target: dict) -> bool:
    """关闭聊天页首次打开时可能遮挡输入区的非业务弹窗。"""
    close_selector = str(
        target.get("blocking_popup_close_selector") or ""
    ).strip()
    if not close_selector:
        return False

    wait_ms = max(
        100,
        _positive_int(target.get("blocking_popup_wait_ms"), 2000),
    )
    close_button = page.locator(close_selector).first
    try:
        await close_button.wait_for(state="visible", timeout=wait_ms)
    except Exception:
        # “今日不再显示”生效或平台未展示弹窗时属于正常路径。
        return False

    try:
        await close_button.click(timeout=2000)
        popup_selector = str(
            target.get("blocking_popup_selector") or ""
        ).strip()
        if popup_selector:
            popup = page.locator(popup_selector).first
            await popup.wait_for(state="hidden", timeout=2000)
        return True
    except Exception as exc:
        raise RuntimeError(f"聊天遮挡弹窗关闭失败: {exc}") from exc


async def _sent_message_count(page, target: dict) -> Optional[int]:
    selector = str(target.get("sent_selector") or "").strip()
    if not selector:
        return None
    return await page.locator(selector).count()


async def _wait_for_sent_message(
        page, target: dict, previous_count: int) -> bool:
    selector = str(target.get("sent_selector") or "").strip()
    if not selector:
        return True
    timeout_ms = max(
        100,
        _positive_int(target.get("sent_timeout_ms"), 10000),
    )
    deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
    sent_items = page.locator(selector)
    while asyncio.get_running_loop().time() < deadline:
        if await sent_items.count() > previous_count:
            return True
        await page.wait_for_timeout(100)
    return await sent_items.count() > previous_count


async def _locator_is_enabled(locator) -> bool:
    is_enabled = getattr(locator, "is_enabled", None)
    if not callable(is_enabled):
        return True
    return bool(await is_enabled())


def _normalize_delivery_action(action: dict) -> dict:
    if not isinstance(action, dict) or action.get("type") != "confirm_delivery":
        raise ValueError("商品交付确认动作无效")
    result = dict(action)
    for key, label in (
        ("detail_url", "订单详情地址"),
        ("open_confirm_selector", "商品交付按钮选择器"),
        ("confirm_selector", "最终交付确认按钮选择器"),
        ("success_selector", "交付结果选择器"),
    ):
        result[key] = str(result.get(key) or "").strip()
        if not result[key]:
            raise ValueError(f"{label}未配置")
    parsed = urlparse(result["detail_url"])
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("订单详情地址无效")
    values = result.get("success_texts")
    if not isinstance(values, list):
        raise ValueError("商品交付成功状态未配置")
    result["success_texts"] = [
        str(value).strip() for value in values if str(value).strip()
    ]
    if not result["success_texts"]:
        raise ValueError("商品交付成功状态未配置")
    result["stage_selector"] = str(
        result.get("stage_selector") or ""
    ).strip()
    pending_stage = result.get("pending_stage")
    if result["stage_selector"] or pending_stage is not None:
        if not result["stage_selector"]:
            raise ValueError("交付阶段选择器未配置")
        try:
            result["pending_stage"] = int(pending_stage)
        except (TypeError, ValueError):
            raise ValueError("待交付阶段编号无效") from None
        if result["pending_stage"] <= 0:
            raise ValueError("待交付阶段编号无效")
    else:
        result["pending_stage"] = None
    return result


def _normalize_messages(messages: list) -> list:
    if not isinstance(messages, list) or not messages:
        raise ValueError("聊天消息不能为空")
    normalized = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError(f"第 {index + 1} 条聊天消息无效")
        content = str(message.get("content") or message.get("text") or "").strip()
        image_urls = message.get("image_urls") or []
        if not isinstance(image_urls, list):
            raise ValueError(f"第 {index + 1} 条消息的图片列表无效")
        urls = [str(url).strip() for url in image_urls if str(url).strip()]
        single_url = str(message.get("image_url") or "").strip()
        if single_url and single_url not in urls:
            urls.append(single_url)
        if not content and not urls:
            raise ValueError(f"第 {index + 1} 条消息必须包含文字或图片")
        normalized.append({"content": content, "image_urls": urls})
    return normalized


def _image_base_url() -> str:
    from common.config import BACKEND_WS_URL
    from monitor.config import STORAGE_PUBLIC_BASE_URL

    if STORAGE_PUBLIC_BASE_URL:
        return STORAGE_PUBLIC_BASE_URL.rstrip("/")
    websocket_url = urlparse(BACKEND_WS_URL)
    scheme = "https" if websocket_url.scheme == "wss" else "http"
    return f"{scheme}://{websocket_url.netloc}"


def _guess_ext(url: str, content_type: str = "") -> str:
    media_type = (content_type or "").lower()
    if "jpeg" in media_type:
        return ".jpg"
    for name in ("png", "webp", "gif", "bmp"):
        if name in media_type:
            return f".{name}"
    path = urlparse(url).path.lower()
    for suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
        if path.endswith(suffix):
            return ".jpg" if suffix == ".jpeg" else suffix
    return ".png"


def _positive_int(value, fallback: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else fallback
    except (TypeError, ValueError):
        return fallback
