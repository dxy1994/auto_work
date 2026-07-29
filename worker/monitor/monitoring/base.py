"""
订单查询与提醒服务（Worker 端）- 基类（Async API）

定义 BaseOrderMonitor，封装通用监控流程：
浏览器启动 → 登录 → 导航 → 多 Worker 并发执行（asyncio.gather）。

各站点子类（在 platforms/ 目录下）覆写以下方法：
  - get_order_cfg() → dict              站点配置
  - _get_workers() → list[PageWorker]   返回 Worker 列表
  - _extract_orders_from_table(page)    表格数据提取
  - _build_normalized_order(page, raw)  订单标准化

可选覆写：
  - post_login_check(page)              登录后检查
  - _is_on_collect_page(page)           采集目标页判断
  - _is_target_page(url)                目标页面判断

公共入口 run_order_check() 根据 website_id 分发到对应子类。
"""

import asyncio
import threading
import time
from typing import Optional, List

from patchright.async_api import Page

from monitor import config
from monitor.browser.audio import play_alert_audio_async
from monitor.browser.session import BrowserSession
from monitor.monitoring.extraction import OrderExtractionResult
from monitor.monitoring.worker import PageWorker
from common.reporter import Reporter

PLAYWRIGHT_HEADLESS = config.PLAYWRIGHT_HEADLESS


def _make_result(status, message, start, order_count=0):
    return {
        "status": status,
        "message": message,
        "order_count": order_count,
        "duration_ms": int((time.time() - start) * 1000),
    }


# ── 活跃 Monitor 注册表（account_id → BaseOrderMonitor）──
_active_monitors: dict = {}
_active_monitors_lock = threading.Lock()


def _register_monitor(account_id: int, monitor: 'BaseOrderMonitor'):
    with _active_monitors_lock:
        _active_monitors[account_id] = monitor


def _unregister_monitor(account_id: int):
    with _active_monitors_lock:
        _active_monitors.pop(account_id, None)


def get_active_monitor(account_id: int) -> Optional['BaseOrderMonitor']:
    """获取指定账号的活跃 Monitor，用于向其提交招呼等子任务。"""
    with _active_monitors_lock:
        return _active_monitors.get(account_id)


class BaseOrderMonitor:
    """订单监控基类。子类需覆写 tag、get_order_cfg、_get_workers。"""

    tag: str = ""
    skip_login: bool = False

    def __init__(
        self,
        task_id: str,
        website_id: int,
        account_id: int,
        start: float,
        reporter: Reporter,
        login_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        login_type: str = "form",
        login_config: Optional[dict] = None,
        stop_event: Optional[threading.Event] = None,
        force_login: bool = False,
    ):
        self.task_id = task_id
        self.website_id = website_id
        self.account_id = account_id
        self.start = start
        self.reporter = reporter
        self.login_url = login_url
        self.username = username
        self.password = password
        self.login_type = login_type
        self.login_config = login_config or {}
        self.stop_event = stop_event
        self.force_login = force_login

        self._reported_order_ids: set = set()
        self._consecutive_extraction_fails = 0
        self._known_order_statuses: dict = {}
        self._active_temp_pages: set = set()
        self._session: Optional[BrowserSession] = None

    # ── 聊天子任务（复用 Monitor 已有 session，如同开详情页）──

    def do_chat(self, msg: dict) -> dict:
        """在 Monitor 事件循环中执行订单聊天，复用已有 session。

        与 Itemmania 详情页同理：直接在 session owner loop 上调度
        _do_send_chat，不需要 queue/processor/pause。
        """
        from monitor.chat.sender import _do_send_chat_with_post_action
        from monitor.monitoring.chat import normalize_chat_command, report_chat_result

        try:
            command = normalize_chat_command(msg)
        except Exception as exc:
            command = {
                "request_id": str(msg.get("request_id") or "invalid-chat"),
                "order_id": msg.get("order_id"),
                "purpose": str(msg.get("purpose") or "manual"),
            }
            result = {"success": False, "message": str(exc)}
            report_chat_result(self.reporter, command, result, log_tag=self._log_tag)
            return result

        session = self._session
        if session is None or session._context is None or session._owner_loop is None:
            result = {"success": False, "message": "浏览器会话未就绪"}
            report_chat_result(self.reporter, command, result)
            return result

        coro = _do_send_chat_with_post_action(
            session,
            command["target"],
            command["messages"],
            command.get("post_action"),
            keep_open=True)
        try:
            future = asyncio.run_coroutine_threadsafe(coro, session._owner_loop)
            result = future.result(timeout=120)
        except TimeoutError:
            future.cancel()
            result = {"success": False, "message": "聊天发送超时（120s）"}
        except Exception as e:
            result = {"success": False, "message": str(e)}

        report_chat_result(self.reporter, command, result, log_tag=self._log_tag)

        return result

    def do_greeting(self, msg: dict) -> dict:
        """Compatibility alias for an older controller during rolling upgrades."""
        return self.do_chat(msg)

    # ── 子类必须覆写 ──

    def get_order_cfg(self) -> dict:
        raise NotImplementedError

    def _get_workers(self) -> List[PageWorker]:
        return []

    # ── 订单采集模板方法（供子类复用）──

    async def _collect_and_report_orders(self, page) -> int:
        if not self._is_on_collect_page(page):
            print(f"[{self._log_tag}] 不在采集目标页，跳过订单采集")
            return 0

        extraction = await self._extract_orders_from_table(page)
        if extraction.failed:
            self._consecutive_extraction_fails += 1
            print(f"[{self._log_tag}] 订单提取失败 "
                  f"(连续失败{self._consecutive_extraction_fails}次)。"
                  f"原因：{extraction.error}；解决方案：检查登录状态和订单表格页面结构。")
            if self._consecutive_extraction_fails >= 3:
                await play_alert_audio_async(
                    text=f"{self.tag}账号{self.account_id} "
                         f"信息提取连续失败{self._consecutive_extraction_fails}次，请检查")
                self._consecutive_extraction_fails = 0
            return 0

        orders = extraction.orders
        if not orders:
            self._consecutive_extraction_fails = 0
            print(f"[{self._log_tag}] 订单表格正常，当前无订单")
            return 0

        self._consecutive_extraction_fails = 0
        await play_alert_audio_async(
            text=f"{self.tag}账号{self.account_id} "
                 f"检测到{len(orders)}个订单")

        for o in orders:
            order_no = o.get('order_no', '')
            if not order_no:
                continue
            new_state = o.get('state', '')
            old_state = self._known_order_statuses.get(order_no)
            if old_state and old_state != new_state:
                print(f"[{self._log_tag}] 订单状态变更: {order_no} "
                      f"{old_state} -> {new_state}")
                await play_alert_audio_async(
                    text=f"{self.tag}账号{self.account_id}: "
                         f"订单{order_no}状态变更为{new_state}")
            self._known_order_statuses[order_no] = new_state

        new_orders = [
            o for o in orders
            if o.get('order_no')
            and o['order_no'] not in self._reported_order_ids
        ]
        if not new_orders:
            print(f"[{self._log_tag}] 所有 {len(orders)} 个订单均已上报过")
            return 0

        candidate_ids = [o['order_no'] for o in new_orders]
        try:
            existing_ids = await asyncio.to_thread(
                self.reporter.check_existing_orders,
                self.website_id, candidate_ids)
            if existing_ids:
                self._reported_order_ids.update(existing_ids)
                print(f"[{self._log_tag}] 总控已有 {len(existing_ids)} 个订单，跳过")
        except Exception as e:
            print(f"[{self._log_tag}] 总控查重失败，按全部新订单处理: {e}")
            existing_ids = set()

        new_orders = [
            o for o in new_orders
            if o['order_no'] not in existing_ids
        ]
        if not new_orders:
            print(f"[{self._log_tag}] 所有订单均已存在于总控")
            return 0

        print(f"[{self._log_tag}] 真正新订单 {len(new_orders)} 个"
              f" (共提取 {len(orders)} 个)")

        reported = 0
        for order_data in new_orders:
            trade_id = order_data.get('order_no', '?')
            try:
                normalized = await self._build_normalized_order(page, order_data)
                if normalized is None:
                    continue
                self.reporter.report_order_detected(
                    self.account_id, normalized)
                self._reported_order_ids.add(order_data['order_no'])
                reported += 1
                print(f"[{self._log_tag}] 订单已上报: "
                      f"trade_id={order_data.get('order_no')}")
            except Exception as e:
                print(f"[{self._log_tag}] 订单上报失败 "
                      f"(trade_id={trade_id}): {e}")

        return reported

    async def _extract_orders_from_table(self, page) -> OrderExtractionResult:
        return OrderExtractionResult.failure("当前平台未实现订单表格提取器")

    def _build_normalized_order(self, page, order_data: dict):
        raise NotImplementedError

    def _is_on_collect_page(self, page) -> bool:
        return True

    async def post_login_check(self, page) -> bool:
        return False

    def _is_target_page(self, url: str) -> bool:
        return True

    # ── 内部辅助 ──

    @property
    def _log_tag(self) -> str:
        return f"{self.tag}:{self.account_id}"

    def _stopped(self):
        return self.stop_event is not None and self.stop_event.is_set()

    def _make_result(self, status, message, order_count=0):
        return _make_result(status, message, self.start, order_count)

    # ── 导航辅助 ──

    async def _wait_page_stable_async(self, page, timeout=15000):
        await page.wait_for_timeout(1000)
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass

    async def _resolve_my_page_async(self, page, my_page_url,
                                      my_page_selector, wait_timeout):
        if my_page_url:
            if page.url == my_page_url:
                print(f"[{self._log_tag}] 当前页面已是目标页，无需导航")
                return
            await self._navigate_to_my_page_async(
                page, my_page_url, "", wait_timeout)
        elif my_page_selector:
            await self._navigate_to_my_page_async(
                page, "", my_page_selector, wait_timeout)

    async def _navigate_to_my_page_async(self, page, my_page_url,
                                          my_page_selector, wait_timeout):
        if my_page_url:
            print(f"[{self._log_tag}] 导航到: {my_page_url}")
            try:
                await page.goto(my_page_url, wait_until="domcontentloaded",
                                timeout=wait_timeout)
            except Exception as e:
                print(f"[{self._log_tag}] 进入我的页面超时: {e}，重试...")
                try:
                    await page.goto(my_page_url, wait_until="commit",
                                    timeout=wait_timeout)
                except Exception as e2:
                    print(f"[{self._log_tag}] 二次尝试也失败: {e2}")
                    raise
        elif my_page_selector:
            await page.wait_for_selector(my_page_selector, timeout=10000)
            await page.click(my_page_selector)
            await page.wait_for_load_state("networkidle",
                                           timeout=wait_timeout)
        else:
            raise Exception(
                f"[{self._log_tag}] 未配置 my_page_url 或 my_page_selector")

    # ── 核心监控循环 ──

    async def run(self) -> dict:
        cfg = self.get_order_cfg()
        my_page_url = cfg.get("my_page_url", "")
        my_page_selector = cfg.get("my_page_selector", "")
        wait_timeout = cfg.get("wait_timeout", 30000)

        has_credentials = bool(
            self.login_url and self.username and self.password
            and self.login_config
        )
        retry_count = 0
        is_captcha = (self.login_type == "captcha")

        print(f"[{self._log_tag}] 开始监控订单（Async 多页面并行）")
        print(f"[{self._log_tag}] 我的页面: {my_page_url}, "
              f"跳过登录: {self.skip_login}")

        while True:
            if self._stopped():
                await self._shutdown_for_user_stop()
                return self._make_result("cancelled", "用户手动终止")

            try:
                if self._session is None:
                    print(f"[{self._log_tag}] 创建浏览器会话 (重试={retry_count})")
                    self._session = BrowserSession.get_or_create(
                        account_id=self.account_id,
                        login_url=self.login_url,
                        username=self.username,
                        password=self.password,
                        login_type=self.login_type,
                        login_config=self.login_config,
                        skip_login=self.skip_login,
                        force_login=self.force_login,
                        website_id=self.website_id,
                        my_page_url=my_page_url,
                        stop_event=self.stop_event,
                        headless=False if is_captcha else PLAYWRIGHT_HEADLESS,
                    )

                print(f"[{self._log_tag}] [1/6] session.init()...")
                await self._session.init()

                print(f"[{self._log_tag}] [2/6] ensure_login()...")
                login_result = await self._session.ensure_login()
                if (login_result["status"] != "success"
                        and not self.skip_login):
                    raise Exception(f"登录失败: {login_result['message']}")

                print(f"[{self._log_tag}] [3/6] post_login_check...")
                main_page = await self._session.get_main_page()
                if not self.skip_login and has_credentials:
                    need_relogin = await self.post_login_check(main_page)
                    if need_relogin:
                        print(f"[{self._log_tag}] 强制重新登录")
                        lr = await self._session._do_login()
                        if lr["status"] != "success":
                            raise Exception(f"重新登录失败: {lr['message']}")
                        await main_page.goto(my_page_url,
                                             wait_until="commit",
                                             timeout=wait_timeout)
                        await self._wait_page_stable_async(main_page)

                print(f"[{self._log_tag}] [4/6] 导航到 my_page...")
                await self._resolve_my_page_async(
                    main_page, my_page_url, my_page_selector, wait_timeout)
                await self._wait_page_stable_async(main_page)

                retry_count = 0
                print(f"[{self._log_tag}] 会话就绪 "
                      f"(main_page={main_page.url})，启动 Worker 协程")

                print(f"[{self._log_tag}] [5/6] _get_workers()...")
                workers = self._get_workers()
                if not workers:
                    raise Exception("未配置任何 PageWorker")

                for w in workers:
                    await w.init_page()
                await self._close_non_worker_pages(workers)

                main_page = workers[0]._page
                self._session._main_page = main_page

                print(f"[{self._log_tag}] {len(workers)} 个 Worker 页面已就绪")
                print(f"[{self._log_tag}] [6/6] 启动 {len(workers)} 个 Worker...")
                tasks = [asyncio.create_task(self._worker_runner(w))
                         for w in workers]
                tasks.append(asyncio.create_task(self._health_monitor(workers)))

                _register_monitor(self.account_id, self)
                print(f"[{self._log_tag}] {len(tasks)-1} 个 Worker + 健康监控已启动")

                try:
                    await asyncio.gather(*tasks)
                except Exception:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    raise
                if self._stopped():
                    await self._shutdown_for_user_stop()
                    return self._make_result("cancelled", "用户手动终止")
                raise RuntimeError("监控协程意外结束")

            except Exception as e:
                if self._stopped():
                    await self._shutdown_for_user_stop()
                    return self._make_result("cancelled", "用户手动终止")
                retry_count += 1
                print(f"[{self._log_tag}] 监控异常（第{retry_count}次）。"
                      f"原因：{e}；解决方案：浏览器保持打开，5 秒后自动重试；"
                      "若持续失败，请检查网络、登录状态和页面配置。")
                _unregister_monitor(self.account_id)
                if self._session is not None and not self._session.is_alive():
                    await self._session.reset_after_crash()
                    print(f"[{self._log_tag}] 检测到浏览器异常退出，5 秒后自动重启")
                await asyncio.sleep(5)

    async def _worker_runner(self, worker: PageWorker):
        while not self._stopped():
            try:
                await worker.run()
                if not self._stopped():
                    print(f"[{worker._log_tag}] Worker 意外结束。原因：监控循环提前返回；"
                          "解决方案：浏览器保持打开，5 秒后自动重启该 Worker。")
            except Exception as e:
                if not self._stopped():
                    if not worker.session.is_alive():
                        raise RuntimeError("浏览器进程或持久化上下文已退出") from e
                    print(f"[{worker._log_tag}] Worker 异常。原因：{e}；"
                          "解决方案：浏览器保持打开，5 秒后自动重启该 Worker；"
                          "若持续失败，请检查当前页面是否仍处于登录状态。")
                    import traceback
                    traceback.print_exc()
                    if worker.page_failure_requires_rebuild(e):
                        await worker.recover_page_after_failure(e)
                    else:
                        print(
                            f"[{worker._log_tag}] 页面仍可用，"
                            "保留当前标签并重启 Worker"
                        )
            if not self._stopped():
                await asyncio.sleep(5)
        await worker.stop()

    async def _shutdown_for_user_stop(self):
        """仅处理总控主动 cancel；普通异常和连接断开不得关闭浏览器。"""
        _unregister_monitor(self.account_id)
        try:
            self.reporter.report_status(
                self.task_id, "cancelled", "用户手动终止", self.account_id)
        except Exception as e:
            print(f"[{self._log_tag}] 终止状态上报失败。原因：{e}；"
                  "解决方案：总控将在最终任务结果返回后清理状态。")
        if self._session is None:
            return
        try:
            await self._session.shutdown(reason="user_cancel")
        except Exception as e:
            print(f"[{self._log_tag}] 主动终止时关闭浏览器失败。原因：{e}；"
                  "解决方案：请在监控机器上手动关闭残留浏览器进程。")
        finally:
            self._session.release()
            self._session = None

    async def _close_non_worker_pages(self, workers: List[PageWorker]):
        if not self._session or not self._session._context:
            return
        worker_page_ids = {id(w._page) for w in workers if w._page}
        protected_page_ids = (
            worker_page_ids | self._session.transient_page_ids())
        for p in list(self._session._context.pages):
            if id(p) in protected_page_ids:
                continue
            try:
                url = p.url
            except Exception:
                url = "unknown"
            print(f"[{self._log_tag}] 关闭非 Worker 页面: {url}")
            try:
                await p.close()
            except Exception:
                pass

    async def _health_monitor(self, workers: List[PageWorker],
                              health_interval: int = 30):
        timeout = health_interval * 2
        while not self._stopped():
            # 分段等待，让用户终止不必被完整的健康检查周期阻塞。
            for _ in range(health_interval):
                if self._stopped():
                    return
                await asyncio.sleep(1)
            now = time.time()
            for w in workers:
                idle = now - w.last_active
                if idle > timeout:
                    print(f"[{self._log_tag}] {w._name} "
                          f"超时无响应 ({int(idle)}s)")
