"""
站点监控模块包。

每个站点子模块定义继承自 BaseOrderMonitor 的监控类，覆写站点特有逻辑。

MONITOR_REGISTRY 维护 website_id → MonitorClass 的映射，供 run_order_check() 分发。
"""

from automation.monitors.itemmania import ItemmaniaMonitor
from automation.monitors.barotem import BarotemMonitor
from automation.monitors.itembay import ItembayMonitor

MONITOR_REGISTRY = {
    1: ItemmaniaMonitor,
    2: BarotemMonitor,
    3: ItembayMonitor,
}
"""
站点监控模块包。

每个站点子模块导出一个 get_config() 函数，返回该站点的监控配置：
  - order_cfg: 通用监控循环所需的页面 URL、超时等配置
  - detect_order: 订单检测回调
  - refresh_goods: 上架刷新回调（可选）
  - post_login_check: 登录后检查回调（可选）
  - skip_login: 是否跳过登录流程（默认 False）
"""
