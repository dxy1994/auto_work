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
