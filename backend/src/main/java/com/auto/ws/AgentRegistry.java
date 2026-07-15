package com.auto.ws;

import com.auto.entity.Machine;
import com.auto.service.MachineService;
import com.auto.trade.TradeOffer;
import com.auto.trade.WorkerRuntimeStatus;
import tools.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Agent 运行时注册表（进程内内存态）。
 *
 * <p>对应原 Python routers/agent.py 的模块级映射与派发函数：维护 machine ↔ ws、
 * task ↔ machine、account ↔ 任务镜像、以及 /login 等待的 Future，并向 worker 派发
 * login / manual_login / order_check / cancel / captcha_input。
 */
@Component
public class AgentRegistry {

    private static final Logger log = LoggerFactory.getLogger(AgentRegistry.class);

    /** machine_id -> WebSocket 会话。 */
    private final Map<Integer, WebSocketSession> agentConnections = new ConcurrentHashMap<>();
    /** 前端验证码 WebSocket：task_id -> 会话。 */
    private final Map<String, WebSocketSession> captchaConnections = new ConcurrentHashMap<>();
    /** task_id -> machine_id。 */
    private final Map<String, Integer> taskToMachine = new ConcurrentHashMap<>();
    /** task_id -> 派发时的具体 Agent 会话，用于拒绝旧连接迟到结果。 */
    private final Map<String, WebSocketSession> taskToAgentSession = new ConcurrentHashMap<>();
    /** account_id -> 任务镜像。 */
    private final Map<Integer, TaskInfo> accountTasks = new ConcurrentHashMap<>();
    /** account_id -> task_id，用于登录和订单任务统一防重。 */
    private final Map<Integer, String> accountTaskIds = new ConcurrentHashMap<>();
    /** task_id -> Future（/login 等待 agent 回 task_result）。 */
    private final Map<String, CompletableFuture<Map<String, Object>>> loginFutures = new ConcurrentHashMap<>();
    /** 已结束任务号隔离期，防止客户端立即复用后被迟到结果污染。 */
    private final Map<String, Long> retiredTaskIds = new ConcurrentHashMap<>();
    /** machine_id -> Worker 最近一次游戏运行态。 */
    private final Map<Integer, WorkerRuntimeStatus> runtimeStatuses = new ConcurrentHashMap<>();
    private static final long TASK_ID_QUARANTINE_MS = 30 * 60 * 1000L;
    private final Object taskLock = new Object();

    private final ObjectMapper objectMapper;
    private final MachineService machineService;
    public AgentRegistry(ObjectMapper objectMapper, MachineService machineService) {
        this.objectMapper = objectMapper;
        this.machineService = machineService;
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

    public boolean registerCaptcha(String taskId, WebSocketSession session) {
        return captchaConnections.putIfAbsent(taskId, session) == null;
    }

    public void removeCaptcha(String taskId, WebSocketSession session) {
        captchaConnections.remove(taskId, session);
    }

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
        }
        if (previous != null && previous != session) {
            try {
                previous.close();
            } catch (Exception e) {
                log.warn("[Agent] 关闭被替换会话失败 machine_id={}: {}", machineId, e.getMessage());
            }
        }
    }

    public void updateHeartbeat(int machineId) {
        updateHeartbeat(machineId, Map.of());
    }

    @SuppressWarnings("unchecked")
    public void updateHeartbeat(int machineId, Map<String, Object> msg) {
        Machine m = machineService.getById(machineId);
        if (m != null) {
            m.setLastHeartbeat(LocalDateTime.now());
            if (!"online".equals(m.getStatus())) {
                m.setStatus("online");
            }
            machineService.updateById(m);
        }
        Object runtimeObj = msg.get("runtime");
        if (runtimeObj instanceof Map<?, ?> rawRuntime) {
            Map<String, Object> runtime = (Map<String, Object>) rawRuntime;
            runtimeStatuses.put(machineId, new WorkerRuntimeStatus(
                    asInt(runtime.get("game_id")),
                    asInt(runtime.get("game_account_id")),
                    asInt(runtime.get("region_id")),
                    str(runtime.get("client_status")),
                    str(runtime.get("character_name")),
                    str(runtime.get("executor_status")),
                    str(runtime.get("current_assignment_id")),
                    str(runtime.get("ui_health"))));
        }
    }

    public WorkerRuntimeStatus getRuntimeStatus(int machineId) {
        return runtimeStatuses.get(machineId);
    }

    public boolean isAgentOnline(int machineId) {
        WebSocketSession session = agentConnections.get(machineId);
        return session != null && session.isOpen();
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
        if (!agentConnections.remove(machineId, session)) {
            log.info("[Agent] 忽略已被新连接替换的旧会话断开 machine_id={}", machineId);
            return;
        }
        setMachineOffline(machineId);
        runtimeStatuses.remove(machineId);
        failTasksForMachine(machineId, "worker 断线，任务中断");
    }

    private void failTasksForMachine(int machineId, String message) {
        taskToMachine.forEach((taskId, boundMachineId) -> {
            if (boundMachineId != null && boundMachineId == machineId
                    && taskToMachine.remove(taskId, boundMachineId)) {
                CompletableFuture<Map<String, Object>> fut = loginFutures.remove(taskId);
                if (fut != null && !fut.isDone()) {
                    Map<String, Object> r = new LinkedHashMap<>();
                    r.put("status", "failed");
                    r.put("message", message);
                    r.put("duration_ms", 0);
                    fut.complete(r);
                }
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
        Object resultObj = msg.get("result");
        Map<String, Object> result = resultObj instanceof Map ? (Map<String, Object>) resultObj
                : new LinkedHashMap<>();

        CompletableFuture<Map<String, Object>> fut = loginFutures.remove(taskId);
        if (fut != null && !fut.isDone()) {
            fut.complete(result);
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

    /** 把 worker 通用事件转成前端验证码 WS 约定格式并转发。 */
    public void forwardEventToFrontend(Map<String, Object> msg) {
        String taskId = str(msg.get("task_id"));
        WebSocketSession ws = captchaConnections.get(taskId);
        if (ws == null) {
            return;
        }
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", msg.get("event"));
        payload.put("task_id", taskId);
        payload.put("message", msg.getOrDefault("message", ""));
        sendJson(ws, payload);
    }

    public void forwardCaptchaRequired(Map<String, Object> msg) {
        String taskId = str(msg.get("task_id"));
        WebSocketSession ws = captchaConnections.get(taskId);
        if (ws == null) {
            return;
        }
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", "captcha_required");
        payload.put("task_id", taskId);
        sendJson(ws, payload);
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
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", "trade_offer");
        payload.put("assignment_id", offer.assignmentId());
        payload.put("execution_token", offer.executionToken());
        payload.put("lease_expires_at", offer.leaseExpiresAt().toString());
        payload.put("order", offer.orderPayload());
        return sendToAgent(machineId, payload);
    }

    /** Worker 接受 offer 后，使用同一不可持久化明文令牌授权开始。 */
    public boolean sendTradeStart(int machineId, String assignmentId, String executionToken) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", "trade_start");
        payload.put("assignment_id", assignmentId);
        payload.put("execution_token", executionToken);
        return sendToAgent(machineId, payload);
    }

    /** 下发登录任务，返回可等待的 Future（agent 回 task_result 时被唤醒）。 */
    public CompletableFuture<Map<String, Object>> dispatchLogin(
            int machineId, String taskId, boolean manual, String url, String username,
            String password, String loginType, Map<String, Object> loginConfig,
            Integer websiteId, Integer accountId) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", manual ? "manual_login" : "login");
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
            CompletableFuture<Map<String, Object>> fut = new CompletableFuture<>();
            if (loginFutures.putIfAbsent(taskId, fut) != null) {
                releaseTask(taskId, accountId);
                throw new IllegalStateException("任务编号已存在");
            }
            if (!sendToAgent(machineId, payload)) {
                loginFutures.remove(taskId, fut);
                releaseTask(taskId, accountId);
                throw new IllegalStateException("发送任务到 agent 失败");
            }
            return fut;
        }
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

    /** 登录等待超时或调用方中断时释放内存态，避免后续任务被永久占用。 */
    public void cleanupLoginTask(String taskId) {
        synchronized (taskLock) {
            CompletableFuture<Map<String, Object>> future = loginFutures.remove(taskId);
            if (future != null) {
                future.cancel(false);
            }
            taskToMachine.remove(taskId);
            taskToAgentSession.remove(taskId);
            retireTaskId(taskId);
            releaseAccountTask(taskId);
        }
    }

    public boolean dispatchCancel(int machineId, int accountId) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", "cancel");
        payload.put("account_id", accountId);
        return sendToAgent(machineId, payload);
    }

    public boolean sendCaptchaInput(String taskId, String value) {
        Integer machineId = taskToMachine.get(taskId);
        if (machineId == null) {
            return false;
        }
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", "captcha_input");
        payload.put("task_id", taskId);
        payload.put("value", value);
        return sendToAgent(machineId, payload);
    }

    // ═══════════════════════════════════════════════════════════
    // 订单任务状态查询
    // ═══════════════════════════════════════════════════════════

    public TaskInfo getAccountTask(int accountId) {
        return accountTasks.get(accountId);
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
