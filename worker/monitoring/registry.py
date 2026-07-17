"""
站点监控注册表：website_id → MonitorClass 映射，供 run_order_check() 分发。
"""
from monitoring.platforms.itemmania import ItemmaniaMonitor
from monitoring.platforms.barotem import BarotemMonitor
from monitoring.platforms.itembay import ItembayMonitor

MONITOR_REGISTRY = {
    1: ItemmaniaMonitor,
    2: BarotemMonitor,
    3: ItembayMonitor,
}
