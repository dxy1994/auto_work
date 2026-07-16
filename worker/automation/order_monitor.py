"""
订单查询与提醒服务（worker 端）- 基类（Async API）

定义 BaseOrderMonitor，封装通用监控流程：
浏览器启动 → 登录 → 导航 → 多 Worker 并发执行（asyncio.gather）。

各站点子类（在 monitors/ 目录下）覆写以下方法：
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

import config
from automation.audio_alert import play_alert_audio
from automation.browser_session import BrowserSession
from automation.page_worker import PageWorker
from reporter import get_reporter

PLAYWRIGHT_HEADLESS = config.PLAYWRIGHT_HEADLESS


# ═══════════════════════════════════════════════════════════
# 通用辅助函数
# ═══════════════════════════════════════════════════════════

def _make_result(status, message, start, order_count=0):
    return {
        "status": status,
        "message": message,
        "order_count": order_count,
        "duration_ms": int((time.time() - start) * 1000),
    }


# ═══════════════════════════════════════════════════════════
# BaseOrderMonitor - 订单监控基类
# ═══════════════════════════════════════════════════════════

class BaseOrderMonitor:
    """订单监控基类。子类需覆写 tag、get_order_cfg、_get_workers。"""

    # ── 子类覆写属性 ──
    tag: str = ""                        # 日志标签
    skip_login: bool = False             # 是否跳过登录流程（如 itemmania）

    def __init__(
        self,
        task_id: str,
        website_id: int,
        account_id: int,
        start: float,
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
        self.login_url = login_url
        self.username = username
        self.password = password
        self.login_type = login_type
        self.login_config = login_config or {}
        self.stop_event = stop_event
        self.force_login = force_login
        # ── 订单采集共用状态 ──
        self._reported_order_ids: set = set()
        self._consecutive_extraction_fails = 0
        self._known_order_statuses: dict = {}  # order_no → status
        self._active_temp_pages: set = set()  # 正在使用的临时页面 id
        # ── 浏览器会话 ──
        self._session: Optional[BrowserSession] = None

    # ── 子类必须覆写 ──

    def get_order_cfg(self) -> dict:
        """返回站点监控配置（my_page_url, wait_timeout, refresh_interval 等）。"""
        raise NotImplementedError

    def _get_workers(self) -> List[PageWorker]:
        """
        子类必须覆写：返回要启动的 PageWorker 列表。
        """
        return []

    # ── 订单采集模板方法（供子类复用） ──

    async def _collect_and_report_orders(self, page) -> int:
        """
        模板方法：提取 → 失败计数/播报 → 去重 → 委托子类构建 NormalizedOrder → 上报。

        子类需覆写：
          - _extract_orders_from_table(page) → list[dict]  提取原始数据
          - _build_normalized_order(page, order_data) → NormalizedOrder|None  平台特定处理
        可选覆写：
          - _is_on_collect_page(page) → bool  判断当前页是否为采集目标页

        返回本次上报的订单数。
        """
        if not self._is_on_collect_page(page):
            print(f"[{self._log_tag}] 不在采集目标页，跳过订单采集")
            return 0

        orders = await self._extract_orders_from_table(page)
        if not orders:
            self._consecutive_extraction_fails += 1
            print(f"[{self._log_tag}] 表格中无订单数据 "
                  f"(连续失败{self._consecutive_extraction_fails}次)")
            if self._consecutive_extraction_fails >= 3:
                play_alert_audio(
                    text=f"{self.tag}账号{self.account_id} "
                         f"信息提取连续失败{self._consecutive_extraction_fails}次，"
                         f"请检查")
                self._consecutive_extraction_fails = 0
            return 0

        self._consecutive_extraction_fails = 0

        # ── 检测到订单即播报（与是否已上报无关） ──
        play_alert_audio(
            text=f"{self.tag}账号{self.account_id} "
                 f"检测到{len(orders)}个订单")

        # ── 检测订单状态变更 ──
        for o in orders:
            order_no = o.get('order_no', '')
            if not order_no:
                continue
            new_state = o.get('state', '')
            old_state = self._known_order_statuses.get(order_no)
            if old_state and old_state != new_state:
                print(f"[{self._log_tag}] 📢 订单状态变更: {order_no} "
                      f"{old_state} → {new_state}")
                play_alert_audio(
                    text=f"{self.tag}账号{self.account_id}: "
                         f"订单{order_no}状态变更为{new_state}")
            self._known_order_statuses[order_no] = new_state

        new_orders = [
            o for o in orders
            if o.get('order_no')
            and o['order_no'] not in self._reported_order_ids
        ]
        if not new_orders:
            # print(f"[{self._log_tag}] 所有 {len(orders)} 个订单均已上报过")
            return 0

        # ── 向总控批量查重，跳过已入库的订单 ──
        reporter = get_reporter()
        candidate_ids = [o['order_no'] for o in new_orders]
        try:
            existing_ids = await asyncio.to_thread(
                reporter.check_existing_orders,
                self.website_id, candidate_ids)
            if existing_ids:
                self._reported_order_ids.update(existing_ids)
                # print(f"[{self._log_tag}] 总控已有 {len(existing_ids)} 个订单，跳过")
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
                reporter.report_order_detected(
                    self.account_id, normalized)
                self._reported_order_ids.add(order_data['order_no'])
                reported += 1
                print(f"[{self._log_tag}] 订单已上报: "
                      f"trade_id={order_data.get('order_no')}")
            except Exception as e:
                print(f"[{self._log_tag}] 订单上报失败 "
                      f"(trade_id={trade_id}): {e}")

        return reported

    async def _extract_orders_from_table(self, page) -> list:
        """子类覆写：从页面提取订单原始数据列表。默认返回空。"""
        return []

    def _build_normalized_order(self, page, order_data: dict):
        """
        子类覆写：将提取的原始数据转为 NormalizedOrder（async 或 sync）。
        返回 None 表示该订单应跳过。
        """
        raise NotImplementedError

    def _is_on_collect_page(self, page) -> bool:
        """子类可选覆写：判断当前页是否为采集目标页。默认总是 True。"""
        return True

    async def post_login_check(self, page) -> bool:
        """登录后检测，返回 True 表示需要重新登录。"""
        return False

    def _is_target_page(self, url: str) -> bool:
        """子类覆写：判断 URL 是否属于目标监控页面。默认不校验。"""
        return True

    # ── 内部辅助 ──

    @property
    def _log_tag(self) -> str:
        """日志前缀，包含站点标签和账号ID。"""
        return f"{self.tag}:{self.account_id}"

    def _stopped(self):
        return self.stop_event is not None and self.stop_event.is_set()

    def _make_result(self, status, message, order_count=0):
        return _make_result(status, message, self.start, order_count)

    # ── 导航辅助（Async）──

    async def _wait_page_stable_async(self, page, timeout=15000):
        """等待页面稳定（Async）。"""
        await page.wait_for_timeout(1000)
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass

    async def _resolve_my_page_async(self, page, my_page_url,
                                      my_page_selector, wait_timeout):
        """导航到我的页面（Async）。"""
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
        """导航辅助（Async）。"""
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

    # ── 核心监控循环（多页面并行 / Async）──

    async def run(self) -> dict:
        """
        多页面并行监控协调器（Async API）。

        流程：
          1. 获取或创建 BrowserSession，init() 启动浏览器
          2. 登录（首次）、登录后检查
          3. 导航主页面到 my_page
          4. 获取子类定义的 PageWorker 列表
          5. asyncio.gather() 并发运行所有 Worker
          6. 异常时重试
        """
        cfg = self.get_order_cfg()
        my_page_url = cfg.get("my_page_url", "")
        my_page_selector = cfg.get("my_page_selector", "")
        wait_timeout = cfg.get("wait_timeout", 30000)
        max_retries = cfg.get("max_retries", 999)

        has_credentials = bool(
            self.login_url and self.username and self.password
            and self.login_config
        )
        retry_count = 0
        is_captcha = (self.login_type == "captcha")

        print(f"[{self._log_tag}] ═══ 开始监控订单（Async 多页面并行） ═══")
        print(f"[{self._log_tag}] 我的页面: {my_page_url}, "
              f"跳过登录: {self.skip_login}")

        while retry_count < max_retries:
            if self._stopped():
                return self._make_result("cancelled", "用户手动终止")

            try:
                print(f"[{self._log_tag}] ─── 创建浏览器会话 "
                      f"(重试={retry_count}) ───")

                # 1. 获取或创建 BrowserSession
                print(f"[{self._log_tag}] [1/7] get_or_create BrowserSession...")
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

                try:
                    # 2. 初始化浏览器
                    print(f"[{self._log_tag}] [2/7] session.init()...")
                    await self._session.init()

                    # 3. 登录
                    print(f"[{self._log_tag}] [3/7] ensure_login()...")
                    login_result = await self._session.ensure_login()
                    if (login_result["status"] != "success"
                            and not self.skip_login):
                        raise Exception(
                            f"登录失败: {login_result['message']}")

                    # 4. 登录后站点特有检查（如 barotem 登录弹窗）
                    print(f"[{self._log_tag}] [4/7] get_main_page + post_login_check...")
                    main_page = await self._session.get_main_page()
                    if not self.skip_login and has_credentials:
                        need_relogin = await self.post_login_check(main_page)
                        if need_relogin:
                            print(f"[{self._log_tag}] ── 强制重新登录 ──")
                            lr = await self._session._do_login()
                            if lr["status"] != "success":
                                raise Exception(
                                    f"重新登录失败: {lr['message']}")
                            await main_page.goto(my_page_url,
                                                 wait_until="commit",
                                                 timeout=wait_timeout)
                            await self._wait_page_stable_async(main_page)

                    # 5. 导航主页面到 my_page
                    print(f"[{self._log_tag}] [5/7] 导航到 my_page...")
                    await self._resolve_my_page_async(
                        main_page, my_page_url, my_page_selector,
                        wait_timeout)
                    await self._wait_page_stable_async(main_page)

                    retry_count = 0
                    print(f"[{self._log_tag}] ✅ 会话就绪 "
                          f"(main_page={main_page.url})，启动 Worker 协程")

                    # 6. 获取 Workers
                    print(f"[{self._log_tag}] [6/7] _get_workers()...")
                    workers = self._get_workers()
                    if not workers:
                        raise Exception("未配置任何 PageWorker")

                    # 先按顺序初始化所有 Worker 页面，再清理多余页面
                    for w in workers:
                        await w.init_page()
                    await self._close_non_worker_pages(workers)

                    # 重新选取一个 worker 页面作为 main_page 引用
                    # （原 main_page 若未被 worker 使用则已关闭）
                    main_page = workers[0]._page
                    self._session._main_page = main_page

                    print(f"[{self._log_tag}] {len(workers)} 个 Worker 页面已就绪, "
                          f"context.pages={len(self._session._context.pages)}")

                    # 7. asyncio.gather 并发运行所有 Worker + 健康监控
                    print(f"[{self._log_tag}] [7/7] 启动 {len(workers)} 个 Worker...")
                    tasks = []
                    for w in workers:
                        task = asyncio.create_task(
                            self._worker_runner(w))
                        tasks.append(task)
                    tasks.append(asyncio.create_task(
                        self._health_monitor(workers)))

                    print(f"[{self._log_tag}] {len(tasks)-1} 个 Worker "
                          f"+ 健康监控已启动")

                    # 等待所有 Worker 完成（或任一异常）
                    results = await asyncio.gather(*tasks,
                                                   return_exceptions=True)
                    for r in results:
                        if isinstance(r, Exception):
                            print(f"[{self._log_tag}] Worker 异常: {r}")

                    status = "cancelled" if self._stopped() else "completed"
                    msg = ("用户手动终止" if self._stopped()
                           else "监控正常结束")
                    return self._make_result(status, msg)

                finally:
                    try:
                        await self._session.shutdown()
                        self._session.release()
                    except Exception:
                        pass
                    self._session = None

            except Exception as e:
                retry_count += 1
                print(f"[{self._log_tag}] 第{retry_count}次崩溃，5s后重试: {e}")
                if self._session:
                    try:
                        await self._session.shutdown()
                        self._session.close()
                    except Exception:
                        pass
                    self._session = None
                await asyncio.sleep(5)

        return self._make_result("failed",
                                 f"重试{max_retries}次后仍然失败")

    async def _worker_runner(self, worker: PageWorker):
        """运行单个 Worker 协程（页面已由外层初始化）。"""
        try:
            await worker.run()
        except Exception as e:
            print(f"[{worker._log_tag}] Worker 异常退出: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await worker.stop()

    async def _close_non_worker_pages(self, workers: List[PageWorker]):
        """初始化时关闭所有非 Worker 持有的多余页面。"""
        if not self._session or not self._session._context:
            return
        worker_page_ids = {id(w._page) for w in workers if w._page}
        for p in list(self._session._context.pages):
            if id(p) in worker_page_ids:
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
        """监控 Worker 心跳，检测卡死的 Worker。"""
        timeout = health_interval * 2
        while not self._stopped():
            await asyncio.sleep(health_interval)
            now = time.time()
            for w in workers:
                idle = now - w.last_active
                if idle > timeout:
                    print(f"[{self._log_tag}] ⚠️ {w._name} "
                          f"超时无响应 ({int(idle)}s)")


# ═══════════════════════════════════════════════════════════
# 业务逻辑分发
# ═══════════════════════════════════════════════════════════

def run_order_check(
    task_id: str,
    website_id: int,
    account_id: int,
    url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    login_type: str = "form",
    login_config: Optional[dict] = None,
    stop_event: Optional[threading.Event] = None,
    force_login: bool = False,
):
    """根据 website_id 分发到不同站点的监控逻辑（Async 桥接）。"""
    start = time.time()
    login_config = login_config or {}

    cred_status = "有" if url and username and password else "无"
    print(f"[OrderCheck] ═══ 开始订单检查 ═══", flush=True)
    print(f"[OrderCheck] 账号ID={account_id}, 网站ID={website_id}, "
          f"登录类型={login_type}, 凭证={cred_status}, 强制登录={force_login}", flush=True)

    print(f"[OrderCheck] 加载 MONITOR_REGISTRY...", flush=True)
    from automation.monitors import MONITOR_REGISTRY
    print(f"[OrderCheck] MONITOR_REGISTRY 已加载: {list(MONITOR_REGISTRY.keys())}", flush=True)

    monitor_cls = MONITOR_REGISTRY.get(website_id)
    if monitor_cls is None:
        result = _make_result(
            "skipped", f"网站 ID {website_id} 未配置订单查询逻辑", start)
        print(f"[OrderCheck] ═══ 订单检查结束 ═══ "
              f"账号ID={account_id}, 状态=skipped, 耗时=0ms")
        return result

    result = None
    try:
        print(f"[OrderCheck] 构造 monitor ({monitor_cls.__name__})...", flush=True)
        monitor = monitor_cls(
            task_id=task_id,
            website_id=website_id,
            account_id=account_id,
            start=start,
            login_url=url,
            username=username,
            password=password,
            login_type=login_type,
            login_config=login_config,
            stop_event=stop_event,
            force_login=force_login,
        )
        # 桥接：同步 → 异步
        print(f"[OrderCheck] 启动异步监控 loop...", flush=True)
        result = asyncio.run(monitor.run())
        print(f"[OrderCheck] 异步监控正常结束", flush=True)
    except Exception as e:
        import traceback
        print(f"[OrderCheck] ❌ 订单查询异常: {e}", flush=True)
        traceback.print_exc()
        result = _make_result("failed", f"订单查询异常：{e}", start)
    finally:
        status = result.get("status", "unknown") if result else "no_result"
        msg = result.get("message", "") if result else ""
        elapsed = int((time.time() - start) * 1000)
        print(f"[OrderCheck] ═══ 订单检查结束 ═══ "
              f"账号ID={account_id}, 状态={status}, 耗时={elapsed}ms, {msg}")
    return result
