package com.auto.ws;

import com.auto.entity.Machine;
import com.auto.service.MachineService;
import com.auto.service.WirelessHidDeviceManager;
import com.auto.service.WirelessHidDeviceManager.WorkerBinding;
import com.auto.trade.TradeOffer;
import com.auto.trade.WorkerRuntimeStatus;
import com.auto.trade.MachineSessionLost;
import com.auto.trade.MachineSessionRestored;
import com.auto.trade.OrderMonitorStopped;
import tools.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Agent 运行时注册表（进程内内存态）。
 *
 * <p>对应原 Python routers/agent.py 的模块级映射与派发函数：维护 machine ↔ ws、
 * task ↔ machine、account ↔ 任务镜像。
 */
@Component
public class AgentRegistry {

    private static final Logger log = LoggerFactory.getLogger(AgentRegistry.class);

    /** machine_id -> WebSocket 会话。 */
    private final Map<Integer, WebSocketSession> agentConnections = new ConcurrentHashMap<>();
    /** machine_id -> 当前 WebSocket 会话建立时间。 */
    private final Map<Integer, LocalDateTime> agentConnectedAt = new ConcurrentHashMap<>();
    /** task_id -> machine_id。 */
    private final Map<String, Integer> taskToMachine = new ConcurrentHashMap<>();
    /** task_id -> 派发时的具体 Agent 会话，用于拒绝旧连接迟到结果。 */
    private final Map<String, WebSocketSession> taskToAgentSession = new ConcurrentHashMap<>();
    /** account_id -> 任务镜像。 */
    private final Map<Integer, TaskInfo> accountTasks = new ConcurrentHashMap<>();
    /** account_id -> task_id，用于订单任务统一防重。 */
    private final Map<Integer, String> accountTaskIds = new ConcurrentHashMap<>();
    /** 已结束任务号隔离期，防止客户端立即复用后被迟到结果污染。 */
    private final Map<String, Long> retiredTaskIds = new ConcurrentHashMap<>();
    /** machine_id -> Worker 最近一次游戏运行态。 */
    private final Map<Integer, WorkerRuntimeStatus> runtimeStatuses = new ConcurrentHashMap<>();
    /** machine_id -> Worker 角色（monitor / game_executor）。 */
    private final Map<Integer, String> machineRoles = new ConcurrentHashMap<>();
    private static final long TASK_ID_QUARANTINE_MS = 30 * 60 * 1000L;
    private final Object taskLock = new Object();

    private final ObjectMapper objectMapper;
    private final MachineService machineService;
    private final ApplicationEventPublisher eventPublisher;
    private final WirelessHidDeviceManager wirelessHidDeviceManager;
    public AgentRegistry(ObjectMapper objectMapper, MachineService machineService,
                         ApplicationEventPublisher eventPublisher,
                         WirelessHidDeviceManager wirelessHidDeviceManager) {
        this.objectMapper = objectMapper;
        this.machineService = machineService;
        this.eventPublisher = eventPublisher;
        this.wirelessHidDeviceManager = wirelessHidDeviceManager;
    }

    /** 任务镜像。 */
    public static class TaskInfo {
        public int machineId;
        public String taskId;
        public String status;
        public String message;
        public double startTime;
    }

    // ═══════════════════════════════════════════════════════════
    // 会话生命周期
    // ═══════════════════════════════════════════════════════════

    /** 处理 register：按 mac upsert machines，置在线并刷新心跳，返回 machine_id。 */
    public Integer handleRegister(Map<String, Object> msg) {
        String mac = str(msg.get("mac"));
        Machine m = machineService.findByMacAddress(mac);
        if (m == null) {
            m = new Machine();
            m.setMacAddress(mac);
        }
        m.setHostname(str(msg.get("hostname")));
        m.setIpAddress(str(msg.get("ip")));
        m.setOsInfo(str(msg.get("os")));
        m.setStatus("online");
        m.setLastHeartbeat(LocalDateTime.now());
        if (m.getIsActive() == null) {
            m.setIsActive(1);
        }
        machineService.saveOrUpdate(m);
        // 成功注册本身就是恢复证据；即使后端重启前数据库仍为 online，也要清理遗留掉线提醒。
        if (m.getId() != null) {
            eventPublisher.publishEvent(new MachineSessionRestored(m.getId()));
        }

        String role = str(msg.get("role"));
        if (role != null) {
            machineRoles.put(m.getId(), role);
        }
        return m.getId();
    }

    public void bindAgent(int machineId, WebSocketSession session) {
        WebSocketSession previous;
        synchronized (taskLock) {
            previous = agentConnections.get(machineId);
            if (previous != null && previous != session) {
                failTasksForMachine(machineId, "worker 连接已被新会话替换，原任务中断");
            }
            agentConnections.put(machineId, session);
            agentConnectedAt.put(machineId, LocalDateTime.now());
        }
        if (previous != null && previous != session) {
            try {
                previous.close();
            } catch (Exception e) {
                log.warn("[Agent] 关闭被替换会话失败 machine_id={}: {}", machineId, e.getMessage());
            }
            eventPublisher.publishEvent(new MachineSessionLost(
                    machineId, "worker 连接已被新会话替换"));
        }
    }

    public void updateHeartbeat(int machineId) {
        updateHeartbeat(machineId, Map.of());
    }

    @SuppressWarnings("unchecked")
    public void updateHeartbeat(int machineId, Map<String, Object> msg) {
        Machine m = machineService.getById(machineId);
        if (m != null) {
            boolean restored = !"online".equals(m.getStatus());
            String reportedIp = str(msg.get("ip"));
            if (reportedIp != null && !reportedIp.isBlank()) {
                m.setIpAddress(reportedIp);
            }
            m.setLastHeartbeat(LocalDateTime.now());
            if (!"online".equals(m.getStatus())) {
                m.setStatus("online");
            }
            machineService.updateById(m);
            if (restored) {
                eventPublisher.publishEvent(new MachineSessionRestored(machineId));
            }
        }
        Object runtimeObj = msg.get("runtime");
        if (runtimeObj instanceof Map<?, ?> rawRuntime) {
            Map<String, Object> runtime = (Map<String, Object>) rawRuntime;
            String role = str(runtime.get("role"));
            if (role != null) {
                machineRoles.put(machineId, role);
            }
            runtimeStatuses.put(machineId, new WorkerRuntimeStatus(
                    role,
                    asInt(runtime.get("game_id")),
                    asInt(runtime.get("game_account_id")),
                    asInt(runtime.get("region_id")),
                    str(runtime.get("client_status")),
                    str(runtime.get("character_name")),
                    str(runtime.get("executor_status")),
                    str(runtime.get("current_assignment_id")),
                    str(runtime.get("ui_health"))));
            if ("monitor".equals(role) && runtime.containsKey("active_tasks")) {
                syncMonitorTasks(machineId, runtime.get("active_tasks"));
            }
        }
    }

    /**
     * 使用 Monitor 心跳中的真实任务快照恢复后端镜像。
     *
     * <p>这样后端重启或 Worker 重连后，任意浏览器查询到的都是同一份服务器状态，
     * 而不是只有发起监控的浏览器依赖本地乐观状态。</p>
     */
    public void restoreMonitorTasks(int machineId, Object activeTasksObject) {
        syncMonitorTasks(machineId, activeTasksObject);
    }

    private void syncMonitorTasks(int machineId, Object activeTasksObject) {
        if (!(activeTasksObject instanceof List<?> activeTasks)) {
            return;
        }
        Set<Integer> reportedAccounts = new HashSet<>();
        WebSocketSession session = agentConnections.get(machineId);
        synchronized (taskLock) {
            for (Object itemObject : activeTasks) {
                if (!(itemObject instanceof Map<?, ?> item)) {
                    continue;
                }
                Integer accountId = asInt(item.get("account_id"));
                String taskId = str(item.get("task_id"));
                String status = str(item.get("status"));
                if (accountId == null
                        || taskId == null
                        || taskId.isBlank()
                        || (!"running".equals(status) && !"stopping".equals(status))) {
                    continue;
                }

                TaskInfo current = accountTasks.get(accountId);
                if (current != null && current.machineId != machineId) {
                    log.warn(
                            "[Agent] 忽略与其他机器冲突的监控任务快照 "
                                    + "account_id={} reported_machine={} owner_machine={}",
                            accountId, machineId, current.machineId);
                    continue;
                }
                reportedAccounts.add(accountId);
                if (current != null
                        && current.taskId != null
                        && !current.taskId.equals(taskId)) {
                    taskToMachine.remove(current.taskId, machineId);
                    taskToAgentSession.remove(current.taskId);
                    accountTaskIds.remove(accountId, current.taskId);
                    retireTaskId(current.taskId);
                }

                TaskInfo reported = current != null ? current : new TaskInfo();
                reported.machineId = machineId;
                reported.taskId = taskId;
                reported.status = status;
                reported.message = "stopping".equals(status)
                        ? "正在终止..."
                        : "订单监控运行中...";
                Object startTime = item.get("start_time");
                reported.startTime = startTime instanceof Number number
                        ? number.doubleValue()
                        : System.currentTimeMillis() / 1000.0;
                accountTasks.put(accountId, reported);
                accountTaskIds.put(accountId, taskId);
                taskToMachine.put(taskId, machineId);
                if (session != null && session.isOpen()) {
                    taskToAgentSession.put(taskId, session);
                }
            }

            accountTasks.forEach((accountId, info) -> {
                if (info != null
                        && info.machineId == machineId
                        && !reportedAccounts.contains(accountId)
                        && accountTasks.remove(accountId, info)) {
                    accountTaskIds.remove(accountId, info.taskId);
                    taskToMachine.remove(info.taskId, machineId);
                    taskToAgentSession.remove(info.taskId);
                    retireTaskId(info.taskId);
                }
            });
        }
    }

    public WorkerRuntimeStatus getRuntimeStatus(int machineId) {
        return runtimeStatuses.get(machineId);
    }

    public String getMachineRole(int machineId) {
        return machineRoles.get(machineId);
    }

    public boolean isAgentGameExecutor(int machineId) {
        return WorkerRuntimeStatus.isGameExecutorRole(machineRoles.get(machineId));
    }

    public boolean isAgentOnline(int machineId) {
        WebSocketSession session = agentConnections.get(machineId);
        return session != null && session.isOpen();
    }

    /**
     * 返回指定机器当前的实时会话快照。
     *
     * <p>只暴露总控诊断所需字段，不返回 WebSocket 请求头、属性或 URI。</p>
     */
    public Map<String, Object> getSessionSnapshot(int machineId) {
        WebSocketSession session;
        LocalDateTime connectedAt;
        synchronized (taskLock) {
            session = agentConnections.get(machineId);
            connectedAt = agentConnectedAt.get(machineId);
        }

        boolean connected = session != null && session.isOpen();
        WorkerRuntimeStatus runtime = runtimeStatuses.get(machineId);
        String role = machineRoles.get(machineId);

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("machine_id", machineId);
        out.put("connected", connected);
        out.put("session_id", connected ? session.getId() : null);
        out.put("remote_address", connected && session.getRemoteAddress() != null
                ? session.getRemoteAddress().toString() : null);
        out.put("connected_at", connected ? connectedAt : null);
        out.put("role", role);

        List<Map<String, Object>> activeTasks = new ArrayList<>();
        accountTasks.forEach((accountId, task) -> {
            if (task != null && task.machineId == machineId) {
                Map<String, Object> taskInfo = new LinkedHashMap<>();
                taskInfo.put("account_id", accountId);
                taskInfo.put("task_id", task.taskId);
                taskInfo.put("status", task.status);
                taskInfo.put("message", task.message);
                taskInfo.put("start_time", task.startTime);
                activeTasks.add(taskInfo);
            }
        });
        out.put("active_tasks", activeTasks);

        if (runtime == null) {
            out.put("runtime", null);
            return out;
        }

        Map<String, Object> runtimeInfo = new LinkedHashMap<>();
        runtimeInfo.put("role", runtime.role());
        runtimeInfo.put("game_id", runtime.gameId());
        runtimeInfo.put("game_account_id", runtime.gameAccountId());
        runtimeInfo.put("region_id", runtime.regionId());
        runtimeInfo.put("client_status", runtime.clientStatus());
        runtimeInfo.put("character_name", runtime.characterName());
        runtimeInfo.put("executor_status", runtime.executorStatus());
        runtimeInfo.put("current_assignment_id", runtime.currentAssignmentId());
        runtimeInfo.put("ui_health", runtime.uiHealth());
        out.put("runtime", runtimeInfo);
        return out;
    }

    public boolean isCurrentSession(int machineId, WebSocketSession session) {
        return session != null && agentConnections.get(machineId) == session;
    }

    public void setMachineOffline(int machineId) {
        Machine m = machineService.getById(machineId);
        if (m != null) {
            m.setStatus("offline");
            machineService.updateById(m);
        }
    }

    /** 机器断线：移除连接、置离线、清理任务镜像并唤醒等待中的 login Future。 */
    public void onAgentDisconnect(int machineId, WebSocketSession session) {
        boolean removed;
        synchronized (taskLock) {
            removed = agentConnections.remove(machineId, session);
            if (removed) {
                agentConnectedAt.remove(machineId);
            }
        }
        if (!removed) {
            log.info("[Agent] 忽略已被新连接替换的旧会话断开 machine_id={}", machineId);
            return;
        }
        setMachineOffline(machineId);
        runtimeStatuses.remove(machineId);
        machineRoles.remove(machineId);
        failTasksForMachine(machineId, "worker 断线，任务中断");
        eventPublisher.publishEvent(new MachineSessionLost(machineId, "worker 断线"));
    }

    private void failTasksForMachine(int machineId, String message) {
        taskToMachine.forEach((taskId, boundMachineId) -> {
            if (boundMachineId != null && boundMachineId == machineId
                    && taskToMachine.remove(taskId, boundMachineId)) {
                taskToAgentSession.remove(taskId);
                retireTaskId(taskId);
                releaseAccountTask(taskId);
            }
        });
    }

    // ═══════════════════════════════════════════════════════════
    // 上行消息处理
    // ═══════════════════════════════════════════════════════════

    public void handleTaskStatus(Map<String, Object> msg, WebSocketSession session) {
        Integer accountId = asInt(msg.get("account_id"));
        String taskId = str(msg.get("task_id"));
        if (accountId == null || taskToAgentSession.get(taskId) != session) {
            return;
        }
        TaskInfo info = accountTasks.get(accountId);
        if (info != null && info.taskId != null && info.taskId.equals(taskId)) {
            if (msg.get("status") != null) {
                info.status = str(msg.get("status"));
            }
            if (msg.get("message") != null) {
                info.message = str(msg.get("message"));
            }
        }
    }

    @SuppressWarnings("unchecked")
    public void handleTaskResult(Map<String, Object> msg, WebSocketSession session) {
        String taskId = str(msg.get("task_id"));
        if (taskId == null || taskToAgentSession.get(taskId) != session) {
            log.info("[Agent] 忽略非任务所属会话的迟到结果 task_id={}", taskId);
            return;
        }
        Integer accountId = asInt(msg.get("account_id"));
        Integer machineId = taskToMachine.get(taskId);
        Object resultObject = msg.get("result");
        Map<String, Object> result = resultObject instanceof Map<?, ?> rawResult
                ? (Map<String, Object>) rawResult : Map.of();
        String resultStatus = str(result.get("status"));
        String resultMessage = str(result.get("message"));
        if (accountId != null && machineId != null && !"cancelled".equals(resultStatus)) {
            eventPublisher.publishEvent(new OrderMonitorStopped(
                    machineId, accountId, taskId, resultStatus, resultMessage));
        }
        if (accountId != null) {
            TaskInfo info = accountTasks.get(accountId);
            if (info != null && info.taskId != null && info.taskId.equals(taskId)) {
                accountTasks.remove(accountId, info);
            }
            accountTaskIds.remove(accountId, taskId);
        }
        taskToMachine.remove(taskId);
        taskToAgentSession.remove(taskId, session);
        retireTaskId(taskId);
        releaseAccountTask(taskId);
    }

    // ═══════════════════════════════════════════════════════════
    // 派发（供 automation 控制器调用）
    // ═══════════════════════════════════════════════════════════

    /** 选择目标 agent：指定则用之（需在线），否则选首个在线 agent；无则返回 null。 */
    public Integer pickAgent(Integer machineId) {
        if (machineId != null) {
            return agentConnections.containsKey(machineId) ? machineId : null;
        }
        for (Integer mid : agentConnections.keySet()) {
            return mid;
        }
        return null;
    }

    private boolean sendToAgent(int machineId, Map<String, Object> payload) {
        return sendJson(agentConnections.get(machineId), payload);
    }

    /** 向候选 Worker 发出有时效的交易指派，尚不授权执行。 */
    public boolean sendTradeOffer(int machineId, TradeOffer offer) {
        WorkerBinding binding;
        try {
            binding = wirelessHidDeviceManager.prepareWorkerBinding(machineId);
        } catch (Exception e) {
            log.warn("[Trade] 无法读取机器键鼠绑定 machine_id={}: {}", machineId, e.getMessage());
            return false;
        }
        if (binding == null) {
            log.warn("[Trade] 机器尚未绑定键鼠设备 machine_id={}", machineId);
            return false;
        }
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", "trade_offer");
        payload.put("assignment_id", offer.assignmentId());
        payload.put("execution_token", offer.executionToken());
        payload.put("lease_expires_at", offer.leaseExpiresAt().toString());
        payload.put("order", offer.orderPayload());
        payload.put("wireless_hid", workerBindingPayload(binding));
        return sendToAgent(machineId, payload);
    }

    private Map<String, Object> workerBindingPayload(WorkerBinding binding) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("record_id", binding.recordId());
        payload.put("device_id", binding.deviceId());
        payload.put("name", binding.name());
        payload.put("ip", binding.ip());
        payload.put("control_port", binding.controlPort());
        return payload;
    }

    /** Worker 接受 offer 后，使用同一不可持久化明文令牌授权开始。 */
    public boolean sendTradeStart(int machineId, String assignmentId, String executionToken) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", "trade_start");
        payload.put("assignment_id", assignmentId);
        payload.put("execution_token", executionToken);
        return sendToAgent(machineId, payload);
    }

    /** 请求 Worker 立即取消当前交易，不需要再携带执行令牌。 */
    public boolean sendTradeCancel(int machineId, String assignmentId, String reason) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", "trade_cancel");
        payload.put("assignment_id", assignmentId);
        payload.put("reason", reason);
        return sendToAgent(machineId, payload);
    }

    /** 将人工客户审核结论下发给正在等待的交易执行器。 */
    public boolean sendTradeBuyerReviewDecision(
            int machineId, String assignmentId, String reviewId, boolean approved) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", "trade_buyer_review_decision");
        payload.put("assignment_id", assignmentId);
        payload.put("review_id", reviewId);
        payload.put("approved", approved);
        return sendToAgent(machineId, payload);
    }

    /** 下发通用聊天指令给持有订单来源账号会话的监控机器。 */
    public boolean sendChat(
            int machineId,
            String requestId,
            int orderId,
            int websiteId,
            int accountId,
            String platform,
            String sourceOrderNo,
            String purpose,
            List<Map<String, Object>> messages,
            Map<String, Object> target) {
        return sendChat(
                machineId, requestId, orderId, websiteId, accountId, platform,
                sourceOrderNo, purpose, messages, target, null);
    }

    /** 下发聊天指令，并可在聊天页关闭后串行执行一个平台动作。 */
    public boolean sendChat(
            int machineId,
            String requestId,
            int orderId,
            int websiteId,
            int accountId,
            String platform,
            String sourceOrderNo,
            String purpose,
            List<Map<String, Object>> messages,
            Map<String, Object> target,
            Map<String, Object> postAction) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", "chat");
        payload.put("request_id", requestId);
        payload.put("order_id", orderId);
        payload.put("website_id", websiteId);
        payload.put("account_id", accountId);
        payload.put("platform", platform);
        payload.put("source_order_no", sourceOrderNo);
        payload.put("purpose", purpose);
        payload.put("messages", messages);
        payload.put("target", target);
        if (postAction != null && !postAction.isEmpty()) {
            payload.put("post_action", postAction);
        }
        return sendToAgent(machineId, payload);
    }

    /** 下发订单监控任务（fire-and-forget），并在镜像表登记。 */
    public void dispatchOrderCheck(
            int machineId, String taskId, String url, String username, String password,
            String loginType, Map<String, Object> loginConfig, Integer websiteId, Integer accountId) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", "order_check");
        payload.put("task_id", taskId);
        payload.put("website_id", websiteId);
        payload.put("account_id", accountId);
        payload.put("url", url);
        payload.put("username", username);
        payload.put("password", password);
        payload.put("login_type", loginType);
        payload.put("login_config", loginConfig != null ? loginConfig : Map.of());

        synchronized (taskLock) {
            reserveTask(machineId, taskId, accountId);
            TaskInfo info = new TaskInfo();
            info.machineId = machineId;
            info.taskId = taskId;
            info.status = "running";
            info.message = "订单监控运行中...";
            info.startTime = System.currentTimeMillis() / 1000.0;
            if (accountTasks.putIfAbsent(accountId, info) != null) {
                releaseTask(taskId, accountId);
                throw new IllegalStateException("该账号已有任务在运行");
            }

            if (!sendToAgent(machineId, payload)) {
                accountTasks.remove(accountId, info);
                releaseTask(taskId, accountId);
                throw new IllegalStateException("发送任务到 agent 失败");
            }
        }
    }

    public boolean dispatchCancel(int machineId, int accountId) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", "cancel");
        payload.put("account_id", accountId);
        return sendToAgent(machineId, payload);
    }

    // ═══════════════════════════════════════════════════════════
    // 订单任务状态查询
    // ═══════════════════════════════════════════════════════════

    public TaskInfo getAccountTask(int accountId) {
        return accountTasks.get(accountId);
    }

    /** 返回某台 Monitor 当前上报的订单监控任务，用于启动时与数据库绑定做双向对账。 */
    public Map<Integer, TaskInfo> getMachineOrderTasks(int machineId) {
        Map<Integer, TaskInfo> result = new LinkedHashMap<>();
        synchronized (taskLock) {
            accountTasks.forEach((accountId, info) -> {
                if (info != null && info.machineId == machineId) {
                    result.put(accountId, info);
                }
            });
        }
        return result;
    }

    /** 停止指定机器上的订单监控，并同步更新后端任务镜像。 */
    public boolean requestOrderCheckStop(
            int machineId, int accountId, String stoppingMessage) {
        synchronized (taskLock) {
            TaskInfo info = accountTasks.get(accountId);
            if (info != null && info.machineId == machineId && "stopping".equals(info.status)) {
                return true;
            }
            if (!dispatchCancel(machineId, accountId)) {
                return false;
            }
            // 同一账号可能已经在新机器建立了合法镜像；此时只停止旧机器的残留任务，
            // 绝不能把新机器的任务误标记为 stopping。
            if (info != null && info.machineId == machineId) {
                info.status = "stopping";
                info.message = stoppingMessage;
            }
            return true;
        }
    }

    /** 读取镜像注册表：account_id 为 null 时返回全部运行中任务。 */
    public Object getOrderCheckStatus(Integer accountId) {
        if (accountId != null) {
            TaskInfo info = accountTasks.get(accountId);
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("account_id", accountId);
            if (info != null) {
                out.put("status", info.status);
                out.put("message", info.message != null ? info.message : "");
                out.put("start_time", info.startTime);
            } else {
                out.put("status", "idle");
                out.put("message", "");
                out.put("start_time", null);
            }
            return out;
        }
        Map<String, Object> all = new LinkedHashMap<>();
        accountTasks.forEach((aid, info) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("account_id", aid);
            item.put("status", info.status);
            item.put("message", info.message != null ? info.message : "");
            item.put("start_time", info.startTime);
            all.put(String.valueOf(aid), item);
        });
        return all;
    }

    // ═══════════════════════════════════════════════════════════
    // 辅助
    // ═══════════════════════════════════════════════════════════

    private boolean sendJson(WebSocketSession session, Map<String, Object> payload) {
        if (session == null || !session.isOpen()) {
            return false;
        }
        try {
            String text = objectMapper.writeValueAsString(payload);
            synchronized (session) {
                session.sendMessage(new TextMessage(text));
            }
            return true;
        } catch (Exception e) {
            log.warn("[Agent] 下发消息失败: {}", e.getMessage());
            return false;
        }
    }

    private void reserveTask(int machineId, String taskId, int accountId) {
        long now = System.currentTimeMillis();
        Long quarantineUntil = retiredTaskIds.get(taskId);
        if (quarantineUntil != null) {
            if (quarantineUntil > now) {
                throw new IllegalStateException("任务编号刚结束，请使用新的任务编号");
            }
            retiredTaskIds.remove(taskId, quarantineUntil);
        }
        WebSocketSession session = agentConnections.get(machineId);
        if (session == null || !session.isOpen()) {
            throw new IllegalStateException("agent 已离线");
        }
        if (taskToMachine.putIfAbsent(taskId, machineId) != null) {
            throw new IllegalStateException("任务编号已存在");
        }
        if (taskToAgentSession.putIfAbsent(taskId, session) != null) {
            taskToMachine.remove(taskId, machineId);
            throw new IllegalStateException("任务编号已存在");
        }
        if (accountTaskIds.putIfAbsent(accountId, taskId) != null) {
            taskToMachine.remove(taskId, machineId);
            taskToAgentSession.remove(taskId, session);
            throw new IllegalStateException("该账号已有任务在运行");
        }
    }

    private void releaseTask(String taskId, int accountId) {
        taskToMachine.remove(taskId);
        taskToAgentSession.remove(taskId);
        accountTaskIds.remove(accountId, taskId);
        retireTaskId(taskId);
    }

    private void releaseAccountTask(String taskId) {
        accountTaskIds.forEach((accountId, activeTaskId) -> {
            if (taskId.equals(activeTaskId)) {
                accountTaskIds.remove(accountId, activeTaskId);
                TaskInfo info = accountTasks.get(accountId);
                if (info != null && taskId.equals(info.taskId)) {
                    accountTasks.remove(accountId, info);
                }
            }
        });
    }

    private void retireTaskId(String taskId) {
        if (taskId != null) {
            retiredTaskIds.put(taskId, System.currentTimeMillis() + TASK_ID_QUARANTINE_MS);
        }
    }

    private static String str(Object o) {
        return o == null ? null : o.toString();
    }

    private static Integer asInt(Object o) {
        if (o == null) {
            return null;
        }
        if (o instanceof Number n) {
            return n.intValue();
        }
        try {
            return Integer.parseInt(o.toString());
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
