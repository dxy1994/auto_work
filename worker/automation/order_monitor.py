"""
订单查询与提醒服务（worker 端）- 基类

定义 BaseOrderMonitor，封装通用监控流程：
浏览器启动 → 登录 → 导航 → 轮询检测 → 异常重试。

各站点子类（在 monitors/ 目录下）覆写以下方法：
  - get_order_cfg() → dict       站点配置（URL、超时等）
  - detect_order(page) → Tuple   订单检测逻辑
  - refresh_goods(...)           上架刷新逻辑（可选）
  - post_login_check(page)       登录后检查（可选）

公共入口 run_order_check() 根据 website_id 分发到对应子类。
"""

import datetime
import threading
import time
from typing import Optional, Tuple, List

from patchright.sync_api import Page

import config
from automation.audio_alert import play_alert_audio
from automation.browser_session import BrowserSession
from automation.page_worker import PageWorker
from automation.cookie_reader import save_from_context
from automation.browser import sync_upload_profile
from orders.model import NormalizedOrder
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
    """订单监控基类。子类需覆写 tag、get_order_cfg、detect_order。"""

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
        # ── 浏览器会话 ──
        self._session: Optional[BrowserSession] = None

    # ── 子类必须覆写 ──

    def get_order_cfg(self) -> dict:
        """返回站点监控配置（my_page_url, wait_timeout, refresh_interval 等）。"""
        raise NotImplementedError

    def detect_order(self, page) -> Tuple[bool, int, str]:
        """检测订单，返回 (detected, count, alert_text)。"""
        raise NotImplementedError

    def _get_workers(self) -> List[PageWorker]:
        """
        子类必须覆写：返回要启动的 PageWorker 列表。
        基类默认返回空列表（向后兼容：运行传统单页面循环）。
        """
        return []

    # ── 子类可选覆写 ──

    def refresh_goods(self, page, last_time: datetime.datetime,
                      timeout: int) -> datetime.datetime:
        """上架刷新回调，返回更新后的 last_up_goods_time。"""
        return last_time

    # ── 订单采集模板方法（供子类复用） ──

    def _collect_and_report_orders(self, page) -> int:
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

        orders = self._extract_orders_from_table(page)
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

        new_orders = [
            o for o in orders
            if o.get('trade_id')
            and o['trade_id'] not in self._reported_order_ids
        ]
        if not new_orders:
            print(f"[{self._log_tag}] 所有 {len(orders)} 个订单均已上报过")
            return 0

        # ── 向总控批量查重，跳过已入库的订单 ──
        reporter = get_reporter()
        candidate_ids = [o['trade_id'] for o in new_orders]
        try:
            existing_ids = reporter.check_existing_orders(
                self.website_id, candidate_ids)
            if existing_ids:
                self._reported_order_ids.update(existing_ids)
                print(f"[{self._log_tag}] 总控已有 {len(existing_ids)} 个订单，跳过")
        except Exception as e:
            print(f"[{self._log_tag}] 总控查重失败，按全部新订单处理: {e}")
            existing_ids = set()

        new_orders = [
            o for o in new_orders
            if o['trade_id'] not in existing_ids
        ]
        if not new_orders:
            print(f"[{self._log_tag}] 所有订单均已存在于总控")
            return 0

        print(f"[{self._log_tag}] 真正新订单 {len(new_orders)} 个"
              f" (共提取 {len(orders)} 个)")

        reported = 0
        for order_data in new_orders:
            trade_id = order_data.get('trade_id', '?')
            try:
                normalized = self._build_normalized_order(page, order_data)
                if normalized is None:
                    continue
                reporter.report_order_detected(
                    self.account_id, normalized)
                self._reported_order_ids.add(order_data['trade_id'])
                reported += 1
                print(f"[{self._log_tag}] 订单已上报: "
                      f"trade_id={order_data.get('trade_id')}")
            except Exception as e:
                print(f"[{self._log_tag}] 订单上报失败 "
                      f"(trade_id={trade_id}): {e}")

        return reported

    def _extract_orders_from_table(self, page) -> list:
        """子类覆写：从页面提取订单原始数据列表。默认返回空。"""
        return []

    def _build_normalized_order(self, page, order_data: dict):
        """
        子类覆写：将提取的原始数据转为 NormalizedOrder。
        返回 None 表示该订单应跳过。
        """
        raise NotImplementedError

    def _is_on_collect_page(self, page) -> bool:
        """子类可选覆写：判断当前页是否为采集目标页。默认总是 True。"""
        return True

    def post_login_check(self, page) -> bool:
        """登录后检测，返回 True 表示需要重新登录。"""
        return False

    def pre_detect_check(self, page) -> bool:
        """
        每轮检测前校验页面地址，分三种情况处理：
          1. 目标页面（子类覆写 _is_target_page）→ True，正常继续
          2. 登录页  → False，基类自动重新导航回 my_page
          3. 未知页面 → False + 播报异常语音，提示人工处理
        """
        url = page.url

        # 情况1: 目标页面
        if self._is_target_page(url):
            return True

        # 情况2: 登录页
        if self._is_login_url(url):
            print(f"[{self._log_tag}] 检测到登录页: {url}，触发重新导航")
            return False

        # 情况3: 未知页面 → 播报异常
        print(f"[{self._log_tag}] 页面异常: {url}")
        play_alert_audio(text=f"{self.tag}账号{self.account_id} 页面异常，请人工处理")
        return False

    def _is_target_page(self, url: str) -> bool:
        """子类覆写：判断 URL 是否属于目标监控页面。默认不校验。"""
        return True

    def _is_login_url(self, url: str) -> bool:
        """
        判断当前页面是否为登录页。
        用站点配置的 login_url 做前缀匹配，精准识别各站点的登录地址。
        """
        if not self.login_url:
            return False
        return url.startswith(self.login_url)

    # ── 内部辅助 ──

    @property
    def _log_tag(self) -> str:
        """日志前缀，包含站点标签和账号ID。"""
        return f"{self.tag}:{self.account_id}"

    def _stopped(self):
        return self.stop_event is not None and self.stop_event.is_set()

    def _make_result(self, status, message, order_count=0):
        return _make_result(status, message, self.start, order_count)

    # ── 浏览器 / 导航辅助 ──

    def _navigate_to_my_page(self, page, my_page_url, my_page_selector,
                             wait_timeout):
        """导航到"我的页面"，成功返回 True，失败抛出异常。"""
        if my_page_url:
            print(f"[{self._log_tag}] 导航到: {my_page_url}")
            try:
                page.goto(my_page_url, wait_until="domcontentloaded",
                          timeout=wait_timeout)
            except Exception as e:
                print(f"[{self._log_tag}] 进入我的页面超时: {e}，重试...")
                try:
                    page.goto(my_page_url, wait_until="commit",
                              timeout=wait_timeout)
                except Exception as e2:
                    print(f"[{self._log_tag}] 二次尝试也失败: {e2}")
                    raise
        elif my_page_selector:
            page.wait_for_selector(my_page_selector, timeout=10000)
            page.click(my_page_selector)
            page.wait_for_load_state("networkidle", timeout=wait_timeout)
        else:
            raise Exception(f"[{self._log_tag}] 未配置 my_page_url 或 my_page_selector")

    def _resolve_my_page(self, context, page, my_page_url, my_page_selector,
                         wait_timeout):
        """优先复用恢复的标签页，避免不必要的导航。返回正确的 page。"""
        if my_page_url:
            if page.url == my_page_url:
                print(f"[{self._log_tag}] 当前页面已是目标页，无需导航")
                return page
            for p in context.pages:
                if p != page and p.url == my_page_url:
                    print(f"[{self._log_tag}] 从恢复标签页中找到目标页: {p.url}")
                    return p
            self._navigate_to_my_page(page, my_page_url, "", wait_timeout)
            return page

        self._navigate_to_my_page(page, "", my_page_selector, wait_timeout)
        return page

    def _wait_page_stable(self, page, timeout=15000):
        """等待页面稳定（networkidle + 短暂缓冲）。"""
        page.wait_for_timeout(1000)
        try:
            page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass

    def _save_and_upload(self, context):
        """保存 Cookie 并上传浏览器配置到 RustFS（兼容旧代码）。"""
        try:
            save_from_context(context, self.account_id)
        except Exception:
            pass
        try:
            context.close()
        except Exception:
            pass
        sync_upload_profile(self.account_id)

    def _safe_reload_or_navigate(self, page, my_page_url,
                                    wait_timeout):
        """尝试刷新页面，失败则重新导航到我的页面。"""
        try:
            page.reload(wait_until="domcontentloaded", timeout=wait_timeout)
        except Exception as e:
            print(f"[{self._log_tag}] 刷新超时: {e}，重新导航")
            page.goto(my_page_url, wait_until="domcontentloaded",
                      timeout=wait_timeout)
            page.wait_for_timeout(2000)

    def _ensure_page(self, page, url: str, reason: str, timeout: int = 15000):
        """确保当前在指定页面，不在则导航过去。"""
        if url not in page.url:
            print(f"[{self._log_tag}] {reason}，导航到: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            page.wait_for_timeout(1000)
            try:
                page.wait_for_load_state("networkidle", timeout=timeout)
            except Exception:
                pass

    # ── 核心监控循环（多页面并行）──

    def run(self) -> dict:
        """
        多页面并行监控协调器。

        流程：
          1. 获取或创建 BrowserSession（同一账户共享浏览器上下文）
          2. 登录（首次）、登录后检查
          3. 导航主页面到 my_page
          4. 获取子类定义的 PageWorker 列表
          5. 启动所有 Worker 线程并行运行
          6. 等待所有线程完成
          7. 异常时重试
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

        print(f"[{self._log_tag}] ═══ 开始监控订单（多页面并行） ═══")
        print(f"[{self._log_tag}] 我的页面: {my_page_url}, "
              f"跳过登录: {self.skip_login}")

        while retry_count < max_retries:
            if self._stopped():
                return self._make_result("cancelled", "用户手动终止")

            try:
                print(f"[{self._log_tag}] ─── 创建浏览器会话 "
                      f"(重试={retry_count}) ───")

                # 1. 获取或创建 BrowserSession
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
                    # 2. 登录
                    login_result = self._session.ensure_login()
                    if (login_result["status"] != "success"
                            and not self.skip_login):
                        raise Exception(
                            f"登录失败: {login_result['message']}")

                    # 3. 登录后站点特有检查（如 barotem 登录弹窗）
                    main_page = self._session.get_main_page()
                    if not self.skip_login and has_credentials:
                        need_relogin = self.post_login_check(main_page)
                        if need_relogin:
                            print(f"[{self._log_tag}] ── 强制重新登录 ──")
                            from automation.login_handler import do_login
                            lr = do_login(
                                main_page, self.login_url, self.username,
                                self.password, self.login_config,
                                self.website_id, self.account_id,
                                self.login_type,
                                my_page_url=my_page_url, force_login=True,
                                stop_event=self.stop_event,
                            )
                            if lr["status"] != "success":
                                raise Exception(
                                    f"重新登录失败: {lr['message']}")
                            main_page.goto(my_page_url,
                                           wait_until="commit",
                                           timeout=wait_timeout)
                            self._wait_page_stable(main_page)

                    # 4. 导航主页面到 my_page
                    print(f"[{self._log_tag}] ─── 导航到我的页面 ───")
                    self._resolve_my_page(
                        self._session.get_context(), main_page,
                        my_page_url, my_page_selector, wait_timeout)
                    self._wait_page_stable(main_page)

                    retry_count = 0
                    print(f"[{self._log_tag}] ✅ 会话就绪 "
                          f"(main_page={main_page.url})，启动 Worker 线程")

                    # 5. 获取 Workers
                    workers = self._get_workers()
                    if not workers:
                        raise Exception("未配置任何 PageWorker")

                    # 6. 启动 Worker 线程
                    threads = []
                    for w in workers:
                        t = threading.Thread(
                            target=self._worker_runner, args=(w,),
                            daemon=True)
                        threads.append(t)
                        t.start()

                    print(f"[{self._log_tag}] {len(threads)} 个 Worker 已启动")

                    # 7. 等待所有 Worker 完成
                    for t in threads:
                        t.join()

                    # 正常退出
                    status = "cancelled" if self._stopped() else "completed"
                    msg = "用户手动终止" if self._stopped() else "监控正常结束"
                    return self._make_result(status, msg)

                finally:
                    # 释放 BrowserSession（引用计数）
                    try:
                        self._session.release()
                    except Exception:
                        pass
                    self._session = None

            except Exception as e:
                retry_count += 1
                print(f"[{self._log_tag}] 第{retry_count}次崩溃，5s后重试: {e}")
                # 强制释放 session
                if self._session:
                    try:
                        self._session.close()
                    except Exception:
                        pass
                    self._session = None
                time.sleep(5)

        return self._make_result("failed",
                                 f"重试{max_retries}次后仍然失败")

    def _worker_runner(self, worker: PageWorker):
        """在独立线程中运行单个 Worker。异常时通知所有 Worker 停止。"""
        try:
            worker.run()
        except Exception as e:
            print(f"[{worker._log_tag}] Worker 异常退出: {e}")
            import traceback
            traceback.print_exc()
            # 通知所有 Worker 停止
            if self.stop_event:
                self.stop_event.set()
        finally:
            worker.stop()


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
    """根据 website_id 分发到不同站点的监控逻辑。"""
    start = time.time()
    login_config = login_config or {}

    cred_status = "有" if url and username and password else "无"
    print(f"[OrderCheck] ═══ 开始订单检查 ═══")
    print(f"[OrderCheck] 账号ID={account_id}, 网站ID={website_id}, "
          f"登录类型={login_type}, 凭证={cred_status}, 强制登录={force_login}")

    # 延迟导入避免循环依赖
    from automation.monitors import MONITOR_REGISTRY

    monitor_cls = MONITOR_REGISTRY.get(website_id)
    if monitor_cls is None:
        result = _make_result(
            "skipped", f"网站 ID {website_id} 未配置订单查询逻辑", start)
        print(f"[OrderCheck] ═══ 订单检查结束 ═══ "
              f"账号ID={account_id}, 状态=skipped, 耗时=0ms")
        return result

    result = None
    try:
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
        result = monitor.run()
    except Exception as e:
        result = _make_result("failed", f"订单查询异常：{e}", start)
    finally:
        status = result.get("status", "unknown") if result else "no_result"
        msg = result.get("message", "") if result else ""
        elapsed = int((time.time() - start) * 1000)
        print(f"[OrderCheck] ═══ 订单检查结束 ═══ "
              f"账号ID={account_id}, 状态={status}, 耗时={elapsed}ms, {msg}")
    return result
