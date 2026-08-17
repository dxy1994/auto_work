package com.auto.trade;

import com.auto.entity.MachinePlatformAccount;
import com.auto.entity.Platform;
import com.auto.entity.PlatformAccount;
import com.auto.service.CryptoService;
import com.auto.service.MachinePlatformAccountService;
import com.auto.service.PlatformAccountService;
import com.auto.service.PlatformService;
import com.auto.ws.AgentRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/** 在 Monitor 注册后，为本机绑定且尚未运行的平台账号补发订单监控任务。 */
@Service
public class OrderMonitorAutoStartService {

    private static final Logger log = LoggerFactory.getLogger(OrderMonitorAutoStartService.class);

    private final MachinePlatformAccountService bindingService;
    private final PlatformAccountService accountService;
    private final PlatformService platformService;
    private final CryptoService cryptoService;
    private final AgentRegistry agentRegistry;

    public OrderMonitorAutoStartService(
            MachinePlatformAccountService bindingService,
            PlatformAccountService accountService,
            PlatformService platformService,
            CryptoService cryptoService,
            AgentRegistry agentRegistry) {
        this.bindingService = bindingService;
        this.accountService = accountService;
        this.platformService = platformService;
        this.cryptoService = cryptoService;
        this.agentRegistry = agentRegistry;
    }

    public StartSummary startBoundAccounts(int machineId) {
        return startBoundAccounts(machineId, null);
    }

    public StartSummary startBoundAccounts(int machineId, Object reportedTasksObject) {
        int started = 0;
        int alreadyRunning = 0;
        int stoppedUnbound = 0;
        int skipped = 0;
        List<MachinePlatformAccount> bindings = bindingService.findByMachineIdActive(machineId);
        Set<Integer> boundAccountIds = bindings.stream()
                .map(MachinePlatformAccount::getAccountId)
                .filter(java.util.Objects::nonNull)
                .collect(Collectors.toSet());

        Map<Integer, ReportedTask> actualTasks = new java.util.LinkedHashMap<>();
        agentRegistry.getMachineOrderTasks(machineId).forEach((accountId, info) ->
                actualTasks.put(accountId, new ReportedTask(
                        info == null ? null : info.taskId,
                        info == null ? null : info.status)));
        appendReportedTasks(actualTasks, reportedTasksObject);

        for (Map.Entry<Integer, ReportedTask> running : actualTasks.entrySet()) {
            Integer accountId = running.getKey();
            if (boundAccountIds.contains(accountId)) {
                continue;
            }
            ReportedTask info = running.getValue();
            boolean stopped = "stopping".equals(info.status())
                    || agentRegistry.requestOrderCheckStop(
                            machineId, accountId, "账号已从该机器解绑，正在停止监控...");
            if (stopped) {
                stoppedUnbound++;
                log.info("[OrderMonitor] 已停止解绑账号的残留监控 machine_id={} account_id={} task_id={}",
                        machineId, accountId, info.taskId());
            } else {
                skipped++;
                log.warn("[OrderMonitor] 无法停止解绑账号的残留监控 machine_id={} account_id={}",
                        machineId, accountId);
            }
        }

        for (MachinePlatformAccount binding : bindings) {
            Integer accountId = binding.getAccountId();
            if (accountId == null) {
                skipped++;
                continue;
            }
            AgentRegistry.TaskInfo current = agentRegistry.getAccountTask(accountId);
            if (current != null) {
                if (current.machineId == machineId) {
                    alreadyRunning++;
                } else if ("running".equals(current.status)
                        && agentRegistry.requestOrderCheckStop(
                                current.machineId,
                                accountId,
                                "账号已改绑其他机器，正在停止旧机器监控...")) {
                    stoppedUnbound++;
                    log.info("[OrderMonitor] 已停止账号在旧机器上的残留监控 account_id={} old_machine_id={} new_machine_id={}",
                            accountId, current.machineId, machineId);
                } else {
                    skipped++;
                    log.info("[OrderMonitor] 等待账号在旧机器上的监控退出 account_id={} old_machine_id={} new_machine_id={} status={}",
                            accountId, current.machineId, machineId, current.status);
                }
                continue;
            }

            PlatformAccount account = accountService.getById(accountId);
            if (account == null || !Integer.valueOf(1).equals(account.getIsActive())) {
                skipped++;
                log.warn("[OrderMonitor] 跳过不存在或已停用的绑定账号 machine_id={} account_id={}",
                        machineId, accountId);
                continue;
            }
            Platform platform = platformService.getById(account.getWebsiteId());
            if (platform == null || !Integer.valueOf(1).equals(platform.getIsActive())) {
                skipped++;
                log.warn("[OrderMonitor] 跳过不存在或已停用的平台 machine_id={} account_id={} website_id={}",
                        machineId, accountId, account.getWebsiteId());
                continue;
            }

            String taskId = "order_auto_" + account.getWebsiteId() + "_" + accountId
                    + "_" + UUID.randomUUID();
            String plainPassword;
            try {
                plainPassword = cryptoService.decrypt(account.getPassword());
            } catch (Exception e) {
                skipped++;
                log.error("[OrderMonitor] 账号密码解密失败，跳过自动启动 machine_id={} account_id={}: {}",
                        machineId, accountId, e.getMessage());
                continue;
            }
            try {
                agentRegistry.dispatchOrderCheck(
                        machineId,
                        taskId,
                        platform.getUrl(),
                        account.getUsername(),
                        plainPassword,
                        platform.getLoginType(),
                        platform.getLoginConfig(),
                        account.getWebsiteId(),
                        accountId);
                started++;
            } catch (IllegalStateException race) {
                alreadyRunning++;
                log.info("[OrderMonitor] 账号监控已由其他请求启动 machine_id={} account_id={}: {}",
                        machineId, accountId, race.getMessage());
            } catch (Exception e) {
                skipped++;
                log.error("[OrderMonitor] 自动启动失败 machine_id={} account_id={}: {}",
                        machineId, accountId, e.getMessage(), e);
            }
        }

        StartSummary summary = new StartSummary(
                bindings.size(), started, alreadyRunning, stoppedUnbound, skipped);
//        log.info("[OrderMonitor] 机器账号监控对账完成 machine_id={} bound={} started={} running={} stopped_unbound={} skipped={}",
//                machineId, summary.total(), summary.started(), summary.alreadyRunning(),
//                summary.stoppedUnbound(), summary.skipped());
        return summary;
    }

    private void appendReportedTasks(
            Map<Integer, ReportedTask> target, Object reportedTasksObject) {
        if (!(reportedTasksObject instanceof List<?> reportedTasks)) {
            return;
        }
        for (Object itemObject : reportedTasks) {
            if (!(itemObject instanceof Map<?, ?> item)) {
                continue;
            }
            Integer accountId = toInteger(item.get("account_id"));
            if (accountId == null) {
                continue;
            }
            target.put(accountId, new ReportedTask(
                    item.get("task_id") == null ? null : item.get("task_id").toString(),
                    item.get("status") == null ? null : item.get("status").toString()));
        }
    }

    private Integer toInteger(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return value == null ? null : Integer.valueOf(value.toString());
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    private record ReportedTask(String taskId, String status) {
    }

    public record StartSummary(
            int total, int started, int alreadyRunning, int stoppedUnbound, int skipped) {
    }
}
