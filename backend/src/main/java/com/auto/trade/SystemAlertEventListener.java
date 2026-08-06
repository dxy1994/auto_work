package com.auto.trade;

import com.auto.entity.Machine;
import com.auto.entity.PlatformAccount;
import com.auto.service.MachinePlatformAccountService;
import com.auto.service.MachineService;
import com.auto.service.PlatformAccountService;
import com.auto.service.SystemAlertService;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

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
        String title = monitorMachine
                ? "订单监控机器「" + name + "」已掉线"
                : "机器「" + name + "」已掉线";
        String message = "掉线机器：" + machineIdentity(machine, event.machineId())
                + "。原因：" + safe(event.reason(), "Worker 连接已断开")
                + "。解决方案：检查该机器的进程和网络，重新连接总控；重连成功后本提醒会自动移除。";
        alertService.openOrRefresh(
                "machine_offline", "machine:" + event.machineId() + ":offline",
                event.machineId(), null, "critical", title, message);
    }

    @EventListener
    public void onMachineSessionRestored(MachineSessionRestored event) {
        alertService.dismissBySourceKey("machine:" + event.machineId() + ":offline");
    }

    @EventListener
    public void onGameClientDisconnected(GameClientDisconnected event) {
        Machine machine = machineService.getById(event.machineId());
        String gameName = safe(event.gameName(), safe(event.gameCode(), "未知游戏"));
        String account = safe(event.account(), "未识别");
        String process = event.processId() == null
                ? "未识别" : "PID " + event.processId();
        String confidence = String.format("%.1f%%", event.confidence() * 100.0);
        String gameAccount = event.gameAccountId() == null
                ? "" : "；中控游戏账号 ID #" + event.gameAccountId();
        String message = "检测机器：" + machineIdentity(machine, event.machineId())
                + "。游戏：" + gameName
                + "；登录账号：" + account + gameAccount
                + "；进程：" + process
                + "；断线弹窗匹配度：" + confidence
                + "。原因：检测到服务器连接已断开弹窗。"
                + "执行器已通知中控并将关闭该窗口对应的游戏进程。"
                + "解决方案：检查网络和服务器状态后，重新启动游戏客户端并登录。";
        alertService.openOrRefresh(
                "game_client_disconnected",
                "machine:" + event.machineId() + ":game:"
                        + safe(event.gameCode(), "unknown") + ":disconnected",
                event.machineId(), null, "critical",
                gameName + "服务器连接已断开",
                message);
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
                + "然后为平台账号 " + accountName + " 重新启动订单监控；监控恢复后本提醒会自动移除。";
        alertService.openOrRefresh(
                "order_monitor_stopped", "monitor:" + event.accountId() + ":stopped",
                event.machineId(), event.accountId(), "danger", "订单监控已掉线", message);
    }

    @EventListener
    public void onOrderMonitorRestored(OrderMonitorRestored event) {
        alertService.dismissBySourceKey(
                "monitor:" + event.accountId() + ":stopped");
    }

    private String machineDisplayName(Machine machine, int machineId) {
        if (machine == null) return "#" + machineId;
        if (machine.getName() != null && !machine.getName().isBlank()) return machine.getName();
        if (machine.getHostname() != null && !machine.getHostname().isBlank()) return machine.getHostname();
        if (machine.getMacAddress() != null && !machine.getMacAddress().isBlank()) return machine.getMacAddress();
        return "#" + machineId;
    }

    private String machineIdentity(Machine machine, int machineId) {
        List<String> parts = new ArrayList<>();
        if (machine != null) {
            addIdentityPart(parts, "名称", machine.getName());
            addIdentityPart(parts, "主机名", machine.getHostname());
            addIdentityPart(parts, "MAC", machine.getMacAddress());
            addIdentityPart(parts, "IP", machine.getIpAddress());
        }
        parts.add("ID #" + machineId);
        return String.join("；", parts);
    }

    private void addIdentityPart(List<String> parts, String label, String value) {
        if (value != null && !value.isBlank()) {
            parts.add(label + " " + value.trim());
        }
    }

    private String safe(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
