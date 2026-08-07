"""跨平台订单聊天发送器。

后端负责把订单解析为明确的客户会话地址和平台选择器；本模块只在订单
所属账号的浏览器会话中，严格按照消息顺序发送文字和图片。
"""

import asyncio
import html
import os
import re
import tempfile
from typing import Optional
from urllib.parse import (
    parse_qsl,
    unquote,
    urlencode,
    urljoin,
    urlparse,
    urlunparse,
)

MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_CHAT_CLOSE_DELAY_MS = 10_000
DEFAULT_ITEMMANIA_TARGET = {
    "input_selector": "#write_chat",
    "send_selector": "#send_btn",
    "file_selector": "#attach_layer input[type=file]",
    "upload_auto_send": True,
    "upload_close_selector": "#attach_layer .close",
}
DEFAULT_KOREAN_AFFIRMATIVE_REPLIES = (
    "네",
    "예",
    "넵",
    "네네",
    "네 본인 맞습니다",
    "네 본인 맛습니다",
    "맛습니다",
    "맞습니다",
    "맞아요",
    "본인입니다",
    "ok",
    "네 저예요",
)


def send_chat(
    account_id: int,
    target: dict,
    messages: list,
    main_loop: Optional[asyncio.AbstractEventLoop] = None,
    keep_open: bool = False,
    post_action: Optional[dict] = None,
) -> dict:
    """同步入口：确认问句发送后保持聊天页，直到回答或等待超时。"""
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
    execution_timeout = _chat_execution_timeout_seconds(normalized_target)
    try:
        future = asyncio.run_coroutine_threadsafe(coroutine, owner_loop)
        return future.result(timeout=execution_timeout)
    except TimeoutError:
        future.cancel()
        return {
            "success": False,
            "message": f"聊天执行超时（{execution_timeout:g}s）",
            "reply_received": False,
            "affirmative_reply": False,
        }
    except Exception as exc:
        if not coroutine.cr_running:
            coroutine.close()
        return {"success": False, "message": f"聊天执行异常: {exc}"}


def _chat_execution_timeout_seconds(target: dict) -> float:
    """外层调用必须晚于页面内回复等待结束，不能提前取消聊天页。"""
    execution_timeout = 120.0
    if target.get("wait_for_reply"):
        reply_timeout_ms = _positive_int(
            target.get("reply_timeout_ms"), 300_000)
        execution_timeout = max(
            execution_timeout,
            reply_timeout_ms / 1000 + 30,
        )
    return execution_timeout


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
    """串行执行聊天命令；回复等待期间保留页面，结束后再关闭。"""
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
    """打开客户会话并发送；确认问句发送后持续等待买家第一条回答。"""
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
        if target.get("conversation_resolver") == "barotem_order_list":
            chat_url = await _resolve_barotem_conversation(
                page, target, session=session)
        else:
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

        reply_anchor_index = None
        reply_anchor_start = None
        reply_anchor_text = ""
        if target.get("wait_for_reply"):
            text_indexes = [
                index for index, message in enumerate(messages)
                if message["content"]
            ]
            if not text_indexes:
                return {
                    "success": False,
                    "message": "确认分类缺少用于询问买家的文字话术",
                    "reply_received": False,
                    "affirmative_reply": False,
                }
            choice_indexes = [
                index for index in text_indexes
                if "네" in messages[index]["content"]
                and "아니요" in messages[index]["content"]
            ]
            # 优先选择同时包含“네 / 아니요”选项的当前问句；只匹配选项，
            # 不硬编码整段话术。若以后去掉选项字样，则回退到最后一条确认文字。
            reply_anchor_index = (
                choice_indexes[-1] if choice_indexes else text_indexes[-1]
            )

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
                if index == reply_anchor_index:
                    reply_anchor_start = await _conversation_message_count(
                        page, target)
                    reply_anchor_text = content
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

        if target.get("wait_for_reply"):
            reply, anchor_seen = await _wait_for_customer_reply_after_anchor(
                page,
                target,
                reply_anchor_start or 0,
                reply_anchor_text,
            )
            if reply is None:
                return {
                    "success": False,
                    "message": (
                        "未在会话中定位到本次确认问句话术"
                        if not anchor_seen
                        else "等待买家按要求回答超时"
                    ),
                    "reply_received": False,
                    "affirmative_reply": False,
                    "reply_text": "",
                }
            affirmative = _is_korean_affirmative_reply(
                reply, target.get("affirmative_replies") or ())
            return {
                "success": affirmative,
                "message": (
                    "买家已作出肯定回答"
                    if affirmative
                    else "买家未按要求肯定回答，拒绝本次交易"
                ),
                "reply_received": True,
                "affirmative_reply": affirmative,
                "reply_text": reply,
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
                    if has_images and not target.get("wait_for_reply"):
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


async def _resolve_barotem_conversation(
        page, target: dict, session=None) -> str:
    """Resolve Barotem's jangNum from the seller order card, then open chat."""
    order_no = str(target.get("order_no") or "").strip()
    if not re.fullmatch(r"\d+-\d+", order_no):
        raise RuntimeError("Barotem 订单号无效，无法定位聊天")

    cache_get = getattr(session, "cached_conversation_url", None)
    cache_forget = getattr(session, "forget_conversation_url", None)
    cached_url = cache_get("barotem", order_no) if callable(cache_get) else ""
    if cached_url:
        try:
            _validate_barotem_chat_url(cached_url)
            await page.goto(
                cached_url, wait_until="domcontentloaded", timeout=15000)
            return cached_url
        except Exception:
            if callable(cache_forget):
                cache_forget("barotem", order_no)

    list_target = str(
        target.get("url") or target.get("detail_url") or ""
    ).strip()
    if not list_target:
        raise RuntimeError("Barotem 订单列表地址未配置")

    for list_url in _barotem_order_list_candidates(list_target):
        await page.goto(
            list_url,
            wait_until="domcontentloaded",
            timeout=15000,
        )
        content = page.locator(".product_contents").first
        try:
            await content.wait_for(state="attached", timeout=10000)
        except Exception:
            continue

        cards = page.locator(".product_contents .product_wrap")
        for index in range(await cards.count()):
            card = cards.nth(index)
            checkbox = card.locator("input.product_checkbox").first
            if await checkbox.count() == 0:
                continue
            card_order_no = str(
                await checkbox.get_attribute("value") or ""
            ).strip()
            if card_order_no != order_no:
                continue

            chat_button = card.locator(
                '[onclick*="/chat/view?jangNum="]'
            ).first
            if await chat_button.count() == 0:
                raise RuntimeError(
                    f"Barotem 订单 {order_no} 没有可用的聊天入口"
                )
            onclick = html.unescape(str(
                await chat_button.get_attribute("onclick") or ""
            ))
            match = re.search(
                r"(?P<path>/chat/view\?jangNum=(?P<id>\d+))",
                onclick,
            )
            if not match:
                raise RuntimeError(
                    f"Barotem 订单 {order_no} 的聊天地址无效"
                )

            chat_url = urljoin(list_url, match.group("path"))
            _validate_barotem_chat_url(chat_url)
            await page.goto(
                chat_url, wait_until="domcontentloaded", timeout=15000)
            cache_set = getattr(session, "remember_conversation_url", None)
            if callable(cache_set):
                cache_set("barotem", order_no, chat_url)
            return chat_url

    raise RuntimeError(
        f"Barotem 当前和已完成订单列表中未找到订单 {order_no} 的聊天入口"
    )


def _validate_barotem_chat_url(url: str) -> None:
    parsed = urlparse(str(url or ""))
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if (
        parsed.scheme not in {"http", "https"}
        or (parsed.hostname or "").lower()
        not in {"barotem.com", "www.barotem.com"}
        or parsed.path.rstrip("/") != "/chat/view"
        or not re.fullmatch(r"\d+", query.get("jangNum", ""))
    ):
        raise RuntimeError("Barotem 聊天地址域名、路径或会话编号无效")


def _barotem_order_list_candidates(url: str) -> list[str]:
    """Search the live order first and the completed order as a fallback."""
    parsed = urlparse(str(url or ""))
    candidates = []
    for mode in ("4", "5"):
        path = re.sub(
            r"/mypage/sellview/\d+/?$",
            f"/mypage/sellview/{mode}",
            parsed.path,
        )
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key != "mode"
        ]
        query.append(("mode", mode))
        candidate = urlunparse(parsed._replace(
            path=path,
            query=urlencode(query),
        ))
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


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
    """打开平台交付页，执行单步或两步确认，并复核服务器状态。"""
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

        await _open_delivery_page(page, normalized, session)
        await page.wait_for_timeout(1000)
        if await _delivery_url_is_complete(
                page, normalized, timeout=0):
            return {
                "success": True,
                "message": "截图已发送，网站商品交付此前已确认",
                "already_completed": True,
            }
        await _wait_for_delivery_ready(page, normalized, timeout=10000)
        await _dismiss_blocking_popup(page, normalized)

        if await _delivery_absence_is_complete(
                page, normalized, timeout=0):
            return {
                "success": True,
                "message": "截图已发送，网站商品交付此前已确认",
                "already_completed": True,
            }

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

        if not normalized["single_click"]:
            confirm = page.locator(normalized["confirm_selector"]).first
            await confirm.wait_for(state="visible", timeout=5000)
            await confirm.click(force=True, timeout=10000)
        await page.wait_for_timeout(1500)

        immediate_status = (
            await _wait_for_delivery_success_text(
                page, normalized, timeout=10000
            )
            if normalized["success_before_reload"]
            else ""
        )
        if immediate_status:
            return {
                "success": True,
                "message": "截图已发送，平台商品交付确认已提交",
                "website_status": immediate_status,
                "already_completed": False,
            }

        if await _delivery_url_is_complete(
                page, normalized, timeout=5000):
            return {
                "success": True,
                "message": (
                    "截图已发送，聊天页已关闭，"
                    "ItemBay 商品交付已确认"
                ),
                "already_completed": False,
            }

        # 重新进入交付页，以服务器最终状态作为成功依据，避免只凭点击判断。
        await _open_delivery_page(page, normalized, session)
        if await _delivery_url_is_complete(
                page, normalized, timeout=2000):
            return {
                "success": True,
                "message": (
                    "截图已发送，聊天页已关闭，"
                    "ItemBay 商品交付已确认"
                ),
                "already_completed": False,
            }
        await _wait_for_delivery_ready(page, normalized, timeout=10000)
        await _dismiss_blocking_popup(page, normalized)

        if normalized["success_absent_selector"]:
            if await _delivery_absence_is_complete(
                    page, normalized, timeout=10000):
                return {
                    "success": True,
                    "message": (
                        "截图已发送，聊天页已关闭，"
                        "ItemBay 商品交付已确认"
                    ),
                    "already_completed": False,
                }
            return {
                "success": False,
                "message": (
                    "网站商品交付状态未更新，"
                    "聊天页仍显示商品交付按钮"
                ),
            }

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


async def _open_delivery_page(page, normalized: dict, session) -> str:
    """打开交付页面；Barotem 复用订单列表解析器进入对应聊天会话。"""
    if normalized.get("conversation_resolver") == "barotem_order_list":
        return await _resolve_barotem_conversation(
            page,
            {
                **normalized,
                "url": normalized["detail_url"],
            },
            session=session,
        )
    await page.goto(
        normalized["detail_url"],
        wait_until="domcontentloaded",
        timeout=15000,
    )
    return normalized["detail_url"]


async def _wait_for_delivery_ready(
        page, normalized: dict, timeout: int) -> None:
    selector = normalized.get("ready_selector")
    if not selector:
        return
    ready = page.locator(selector).first
    await ready.wait_for(state="visible", timeout=timeout)


async def _delivery_absence_is_complete(
        page, normalized: dict, timeout: int) -> bool:
    selector = normalized.get("success_absent_selector")
    if not selector:
        return False

    locator = page.locator(selector).first
    deadline = asyncio.get_running_loop().time() + max(0, timeout) / 1000
    while True:
        try:
            if await locator.count() == 0 or not await locator.is_visible():
                return True
        except Exception:
            return False
        if asyncio.get_running_loop().time() >= deadline:
            return False
        await page.wait_for_timeout(250)


async def _delivery_url_is_complete(
        page, normalized: dict, timeout: int) -> bool:
    expected = normalized.get("success_url_contains")
    if not expected:
        return False

    deadline = asyncio.get_running_loop().time() + max(0, timeout) / 1000
    while True:
        current_url = unquote(str(getattr(page, "url", "") or ""))
        if expected in current_url:
            return True
        if asyncio.get_running_loop().time() >= deadline:
            return False
        await page.wait_for_timeout(250)


async def _try_read_delivery_stage(
        page, normalized: dict, timeout: int) -> tuple[Optional[int], str]:
    """读取当前激活的交付阶段；页面无阶段状态条时交给文本规则继续判断。"""
    selector = normalized.get("stage_selector")
    if not selector:
        return None, ""
    try:
        stages = page.locator(selector)
        await stages.first.wait_for(state="visible", timeout=timeout)
        active_class = str(
            normalized.get("stage_active_class") or "active"
        ).strip()
        for index in range(await stages.count()):
            stage = stages.nth(index)
            class_names = str(
                await stage.get_attribute("class") or ""
            ).split()
            if active_class in class_names:
                return index + 1, (await stage.inner_text()).strip()
    except Exception:
        return None, ""
    return None, ""


async def _try_read_delivery_status_text(
        page, normalized: dict, timeout: int) -> str:
    selector = normalized.get("success_selector")
    if not selector:
        return ""
    try:
        status = page.locator(selector).first
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


async def _wait_for_delivery_success_text(
        page, normalized: dict, timeout: int) -> str:
    """等待二次确认后的成功文案，避免刷新页面丢失瞬时结果弹窗。"""
    selector = normalized.get("success_selector")
    expected_texts = normalized.get("success_texts", [])
    if not selector or not expected_texts:
        return ""

    status = page.locator(selector).first
    deadline = asyncio.get_running_loop().time() + max(0, timeout) / 1000
    while True:
        try:
            if await status.count() > 0 and await status.is_visible():
                status_text = (await status.inner_text()).strip()
                if any(expected in status_text for expected in expected_texts):
                    return status_text
        except Exception:
            return ""
        if asyncio.get_running_loop().time() >= deadline:
            return ""
        await page.wait_for_timeout(250)


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
        if target.get("barotem_image_submit"):
            try:
                await _submit_barotem_image_via_paste(
                    page, temp_file.name)
            except _BarotemImageSubmitUnavailable as exc:
                raise RuntimeError(
                    f"Barotem 聊天页图片发送不可用: {exc}") from exc
            if sent_before is None:
                await page.wait_for_timeout(
                    _positive_int(target.get("image_settle_ms"), 2000)
                )
            elif not await _wait_for_sent_message(
                    page, target, sent_before):
                raise RuntimeError("图片确认发送后未在会话中显示")
            return

        file_input = page.locator(target["file_selector"]).first
        if await file_input.count() == 0:
            raise RuntimeError("未找到聊天图片上传控件")
        await file_input.set_input_files(temp_file.name)

        if not target.get("upload_auto_send", True):
            if not _page_is_closed(page):
                sent_after_selection = await _sent_message_count(page, target)
                already_sent = (
                    sent_before is not None
                    and sent_after_selection is not None
                    and sent_after_selection > sent_before
                )
                if not already_sent:
                    await _submit_image_upload(page, file_input, target)

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


class _BarotemImageSubmitUnavailable(RuntimeError):
    """当前聊天页不能完成 Barotem 图片粘贴与确认发送流程。"""


async def _submit_barotem_image_via_paste(page, file_path: str) -> None:
    """派发页面 paste 事件生成预览，再点击 Barotem 的真实发送按钮。"""
    try:
        await page.locator("#happy_chating_form").first.wait_for(
            state="attached", timeout=15000)
        await page.locator("#imgpopup .imgview").first.wait_for(
            state="attached", timeout=5000)
    except Exception as exc:
        raise _BarotemImageSubmitUnavailable(
            "等待聊天表单或图片预览层就绪超时") from exc

    input_id = f"barotem_paste_file_{id(page)}"
    await page.evaluate(
        """
        inputId => {
            document.getElementById(inputId)?.remove();
            const input = document.createElement('input');
            input.type = 'file';
            input.id = inputId;
            input.accept = 'image/*';
            input.style.display = 'none';
            document.body.appendChild(input);
        }
        """,
        input_id,
    )

    try:
        image_input = page.locator(f"#{input_id}").first
        if await image_input.count() == 0:
            raise _BarotemImageSubmitUnavailable(
                "无法创建图片文件输入控件")
        await image_input.set_input_files(file_path)

        preview_items = page.locator("#imgpopup.inline .imgview li")
        preview_before = await preview_items.count()
        paste_result = await page.evaluate(
            """
            inputId => {
                try {
                    const input = document.getElementById(inputId);
                    const file = input?.files?.[0];
                    if (!file) throw new Error('file missing');
                    const transfer = new DataTransfer();
                    transfer.items.add(file);
                    const pasteEvent = new ClipboardEvent('paste', {
                        clipboardData: transfer,
                        bubbles: true,
                        cancelable: true
                    });
                    document.dispatchEvent(pasteEvent);
                    return {success: true, error: ''};
                } catch (error) {
                    return {
                        success: false,
                        error: String(
                            error && error.message ? error.message : error
                        )
                    };
                }
            }
            """,
            input_id,
        )
        if not isinstance(paste_result, dict) or not paste_result.get(
                "success"):
            paste_error = str(
                (paste_result or {}).get("error")
                if isinstance(paste_result, dict)
                else ""
            ).strip()
            raise _BarotemImageSubmitUnavailable(
                paste_error or "未能派发图片粘贴事件")

        deadline = asyncio.get_running_loop().time() + 10
        while await preview_items.count() <= preview_before:
            if asyncio.get_running_loop().time() >= deadline:
                raise _BarotemImageSubmitUnavailable(
                    "粘贴事件派发后未出现图片预览")
            await page.wait_for_timeout(100)

        confirm_button = page.locator(
            "#imgpopup.inline .chat_send_btn"
        ).first
        try:
            await confirm_button.wait_for(state="visible", timeout=5000)
            await confirm_button.click(force=True, timeout=5000)
        except Exception as exc:
            raise _BarotemImageSubmitUnavailable(
                "图片确认发送按钮不可用") from exc
    finally:
        try:
            await page.evaluate(
                """
                inputId => document.getElementById(inputId)?.remove()
                """,
                input_id,
            )
        except Exception:
            pass


async def _submit_image_upload(upload_page, file_input, target: dict) -> None:
    """优先执行平台上传按钮；未配置按钮时才提交文件所属表单。"""
    upload_send_selector = str(
        target.get("upload_send_selector") or ""
    ).strip()
    if upload_send_selector:
        upload_send = upload_page.locator(upload_send_selector).first
        await upload_send.wait_for(state="visible", timeout=5000)
        await upload_send.click(force=True, timeout=5000)
        return

    owner_form = file_input.locator("xpath=ancestor::form[1]").first
    if await owner_form.count() == 0:
        raise RuntimeError("未找到图片上传表单或发送按钮")
    await owner_form.evaluate("""
        form => {
            if (typeof form.requestSubmit === 'function') {
                form.requestSubmit();
            } else {
                form.submit();
            }
        }
    """)


def _page_is_closed(page) -> bool:
    is_closed = getattr(page, "is_closed", None)
    if not callable(is_closed):
        return False
    try:
        return bool(is_closed())
    except Exception:
        return False


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

    resolver = str(result.get("conversation_resolver") or "").strip()
    result["conversation_resolver"] = resolver
    if resolver:
        if resolver != "barotem_order_list":
            raise ValueError("unsupported conversation resolver")
        if (
            (parsed.hostname or "").lower()
            not in {"barotem.com", "www.barotem.com"}
            or not re.fullmatch(r"/mypage/sellview/\d+/?", parsed.path)
        ):
            raise ValueError("invalid Barotem order list URL")
        order_no = str(result.get("order_no") or "").strip()
        if not re.fullmatch(r"\d+-\d+", order_no):
            raise ValueError("invalid Barotem order number")
        result["order_no"] = order_no

    has_images = any(
        isinstance(message, dict)
        and (message.get("image_url") or message.get("image_urls"))
        for message in (messages or [])
    )
    result["barotem_image_submit"] = (
        result.get("barotem_image_submit") is True
    )
    result["file_selector"] = str(result.get("file_selector") or "").strip()
    if (
        has_images
        and not result["barotem_image_submit"]
        and not result["file_selector"]
    ):
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
        and not result["barotem_image_submit"]
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
    result["wait_for_reply"] = result.get("wait_for_reply") is True
    if result["wait_for_reply"]:
        for key, label in (
            ("conversation_selector", "聊天消息顺序选择器"),
            ("conversation_self_class", "己方聊天消息类名"),
            ("conversation_text_selector", "聊天文字选择器"),
        ):
            result[key] = str(result.get(key) or "").strip()
            if not result[key]:
                raise ValueError(f"{label}未配置")
        result["reply_timeout_ms"] = min(
            300_000,
            max(
                1_000,
                _positive_int(result.get("reply_timeout_ms"), 300_000),
            ),
        )
        raw_replies = result.get("affirmative_replies")
        replies = raw_replies if isinstance(raw_replies, (list, tuple)) else ()
        result["affirmative_replies"] = tuple(
            str(value).strip() for value in replies if str(value).strip()
        ) or DEFAULT_KOREAN_AFFIRMATIVE_REPLIES
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


async def _conversation_message_count(page, target: dict) -> int:
    selector = str(target.get("conversation_selector") or "").strip()
    if not selector:
        return 0
    return await page.locator(selector).count()


async def _read_conversation_message(item, target: dict):
    """读取一条真实聊天 DOM，并区分己方、买家和非消息行。"""
    text_selector = str(
        target.get("conversation_text_selector") or ""
    ).strip()
    text_item = item.locator(text_selector).first
    if await text_item.count() == 0:
        return None
    class_name = str(await item.get_attribute("class") or "")
    self_class = str(target.get("conversation_self_class") or "").strip()
    text = str(await text_item.inner_text()).strip()
    return self_class in class_name.split(), text, text_item


async def _wait_for_customer_reply_after_anchor(
        page, target: dict, start_index: int, anchor_text: str):
    """只读取本次动态确认问句之后的第一条买家消息。"""
    selector = str(target.get("conversation_selector") or "").strip()
    timeout_ms = min(
        300_000,
        max(
            1_000,
            _positive_int(target.get("reply_timeout_ms"), 300_000),
        ),
    )
    expected_anchor = _normalize_reply_candidate(anchor_text)
    deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
    conversation = page.locator(selector)
    next_index = max(0, int(start_index))
    anchor_seen = False
    while asyncio.get_running_loop().time() < deadline:
        count = await conversation.count()
        while next_index < count:
            item = conversation.nth(next_index)
            next_index += 1
            entry = await _read_conversation_message(item, target)
            if entry is None:
                # ItemBay 日期/系统通知行也位于同一列表，不属于对话。
                continue
            is_self, text, text_item = entry
            if not anchor_seen:
                if (
                    is_self
                    and expected_anchor
                    and _normalize_reply_candidate(text) == expected_anchor
                ):
                    anchor_seen = True
                continue
            if is_self:
                continue
            if not text:
                # 图片、贴图等非文字回答属于“其他回答”，直接拒绝。
                await page.wait_for_timeout(100)
                try:
                    text = str(await text_item.inner_text()).strip()
                except Exception:
                    text = ""
            return (text or "[非文字回复]")[:500], True
        await page.wait_for_timeout(250)
    return None, anchor_seen


def _normalize_reply_candidate(value: object) -> str:
    return "".join(
        character.casefold()
        for character in str(value or "")
        if character.isalnum()
    )


def _is_korean_affirmative_reply(reply: str, allowed_replies) -> bool:
    allowed = {
        _normalize_reply_candidate(value)
        for value in allowed_replies
        if _normalize_reply_candidate(value)
    }
    if not allowed:
        allowed = {
            _normalize_reply_candidate(value)
            for value in DEFAULT_KOREAN_AFFIRMATIVE_REPLIES
        }
    # 真实 DOM 已将时间排除在气泡文字之外；只允许配置中的完整肯定回答。
    # 忽略空格、尖括号、标点和英文大小写，但不做子串匹配，避免“네 아니요”误确认。
    return _normalize_reply_candidate(reply) in allowed


async def _locator_is_enabled(locator) -> bool:
    is_enabled = getattr(locator, "is_enabled", None)
    if not callable(is_enabled):
        return True
    return bool(await is_enabled())


def _normalize_delivery_action(action: dict) -> dict:
    if not isinstance(action, dict) or action.get("type") != "confirm_delivery":
        raise ValueError("商品交付确认动作无效")
    result = dict(action)
    result["detail_url"] = str(result.get("detail_url") or "").strip()
    if not result["detail_url"]:
        raise ValueError("订单详情地址未配置")
    parsed = urlparse(result["detail_url"])
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("订单详情地址无效")

    is_itembay_delivery_detail = (
        (parsed.hostname or "").lower() in {"itembay.com", "www.itembay.com"}
        and parsed.path.rstrip("/").endswith(
            "/item/transaction/transactionGiveTakeDetail"
        )
    )
    result["single_click"] = result.get("single_click") is True
    result["success_before_reload"] = (
        result.get("success_before_reload") is True
    )
    result["open_confirm_selector"] = str(
        result.get("open_confirm_selector") or ""
    ).strip()
    result["confirm_selector"] = str(
        result.get("confirm_selector") or ""
    ).strip()
    result["ready_selector"] = str(
        result.get("ready_selector") or ""
    ).strip()
    result["success_selector"] = str(
        result.get("success_selector") or ""
    ).strip()
    result["success_absent_selector"] = str(
        result.get("success_absent_selector") or ""
    ).strip()
    result["success_url_contains"] = str(
        result.get("success_url_contains") or ""
    ).strip()
    result["blocking_popup_selector"] = str(
        result.get("blocking_popup_selector") or ""
    ).strip()
    result["blocking_popup_close_selector"] = str(
        result.get("blocking_popup_close_selector") or ""
    ).strip()

    if is_itembay_delivery_detail:
        result["single_click"] = action.get("single_click", True) is not False
        if not result["open_confirm_selector"]:
            result["open_confirm_selector"] = (
                ".bay-btn-confirm[onclick*='ItemGiveTake.setGiveItem']"
            )
        if not result["ready_selector"]:
            result["ready_selector"] = "#middle .list-page-detail"
        if not result["success_absent_selector"]:
            result["success_absent_selector"] = (
                ".bay-btn-confirm[onclick*='ItemGiveTake.setGiveItem']"
            )
        if not result["success_url_contains"]:
            result["success_url_contains"] = (
                "/mybay/status/mybayStatusGiveList"
            )

    if not result["open_confirm_selector"]:
        raise ValueError("商品交付按钮选择器未配置")
    if not result["single_click"] and not result["confirm_selector"]:
        raise ValueError("最终交付确认按钮选择器未配置")

    values = result.get("success_texts")
    if not isinstance(values, list):
        values = []
    result["success_texts"] = [
        str(value).strip() for value in values if str(value).strip()
    ]
    has_text_success_check = (
        bool(result["success_selector"])
        and bool(result["success_texts"])
    )
    if (
        not result["success_absent_selector"]
        and not result["success_url_contains"]
        and not has_text_success_check
    ):
        raise ValueError("商品交付成功状态未配置")
    result["stage_selector"] = str(
        result.get("stage_selector") or ""
    ).strip()
    result["stage_active_class"] = str(
        result.get("stage_active_class") or "active"
    ).strip()
    pending_stage = result.get("pending_stage")
    if result["stage_selector"] or pending_stage is not None:
        if not result["stage_selector"]:
            raise ValueError("交付阶段选择器未配置")
        if not result["stage_active_class"]:
            raise ValueError("交付阶段激活类名未配置")
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
