package com.auto.trade;

import com.auto.entity.Machine;
import com.auto.entity.PlatformAccount;
import com.auto.service.MachinePlatformAccountService;
import com.auto.service.MachineService;
import com.auto.service.PlatformAccountService;
import com.auto.service.SystemAlertService;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

/** 将掉线事件持久化为提醒，并在机器恢复连接后自动关闭机器掉线提醒。 */
@Component
public class SystemAlertEventListener {

    private final SystemAlertService alertService;
    private final MachineService machineService;
    private final PlatformAccountService accountService;
    private final MachinePlatformAccountService machinePlatformAccountService;

    public SystemAlertEventListener(SystemAlertService alertService,
                                    MachineService machineService,
                                    PlatformAccountService accountService,
                                    MachinePlatformAccountService machinePlatformAccountService) {
        this.alertService = alertService;
        this.machineService = machineService;
        this.accountService = accountService;
        this.machinePlatformAccountService = machinePlatformAccountService;
    }

    @EventListener
    public void onMachineSessionLost(MachineSessionLost event) {
        Machine machine = machineService.getById(event.machineId());
        // 新连接替换旧会话时机器已经重新在线，不产生误报。
        if (machine != null && "online".equals(machine.getStatus())) {
            return;
        }
        String name = machineDisplayName(machine, event.machineId());
        boolean monitorMachine = !machinePlatformAccountService
                .findByMachineIdActive(event.machineId()).isEmpty();
        String title = monitorMachine ? "订单监控机器已掉线" : "机器已掉线";
        String message = "原因：" + safe(event.reason(), "Worker 连接已断开")
                + "。解决方案：检查机器 " + name + " 的进程和网络，重新连接总控；重连成功后本提醒会自动移除。";
        alertService.openOrRefresh(
                "machine_offline", "machine:" + event.machineId() + ":offline",
                event.machineId(), null, "critical", title, message);
    }

    @EventListener
    public void onMachineSessionRestored(MachineSessionRestored event) {
        alertService.dismissBySourceKey("machine:" + event.machineId() + ":offline");
    }

    @EventListener
    public void onOrderMonitorStopped(OrderMonitorStopped event) {
        Machine machine = machineService.getById(event.machineId());
        PlatformAccount account = accountService.getById(event.accountId());
        String machineName = machineDisplayName(machine, event.machineId());
        String accountName = account == null || account.getUsername() == null
                ? "账号 #" + event.accountId() : account.getUsername();
        String message = "原因：订单监控已停止，状态=" + safe(event.status(), "unknown")
                + "，" + safe(event.message(), "未返回具体信息")
                + "。解决方案：检查机器 " + machineName + " 的浏览器和登录状态，"
                + "然后为平台账号 " + accountName + " 重新启动订单监控；确认恢复后可手动关闭本提醒。";
        alertService.openOrRefresh(
                "order_monitor_stopped", "monitor:" + event.accountId() + ":stopped",
                event.machineId(), event.accountId(), "danger", "订单监控已掉线", message);
    }

    private String machineDisplayName(Machine machine, int machineId) {
        if (machine == null) return "#" + machineId;
        if (machine.getName() != null && !machine.getName().isBlank()) return machine.getName();
        if (machine.getHostname() != null && !machine.getHostname().isBlank()) return machine.getHostname();
        return "#" + machineId;
    }

    private String safe(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
