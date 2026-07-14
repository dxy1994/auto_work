package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.Account;
import com.auto.entity.LoginLog;
import com.auto.entity.Website;
import com.auto.service.AccountService;
import com.auto.service.CryptoService;
import com.auto.service.LoginLogService;
import com.auto.service.WebsiteService;
import com.auto.ws.AgentRegistry;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * 自动登录控制面：解密密码、选取在线 agent、经 WebSocket 下发任务并汇聚结果。
 *
 * <p>对应原 Python routers/automation.py。真正的浏览器自动化在 worker 上执行。
 */
@RestController
@RequestMapping("/api/automation")
public class AutomationController {

    /** 登录任务等待 agent 回报的超时（秒）。 */
    private static final int AUTO_LOGIN_TIMEOUT = 180;
    private static final int MANUAL_LOGIN_TIMEOUT = 330;

    private final WebsiteService websiteService;
    private final AccountService accountService;
    private final LoginLogService loginLogService;
    private final CryptoService crypto;
    private final AgentRegistry registry;

    public AutomationController(WebsiteService websiteService, AccountService accountService,
                                LoginLogService loginLogService, CryptoService crypto,
                                AgentRegistry registry) {
        this.websiteService = websiteService;
        this.accountService = accountService;
        this.loginLogService = loginLogService;
        this.crypto = crypto;
        this.registry = registry;
    }

    // ── 触发登录 ────────────────────────────────────────────────

    @PostMapping("/login")
    public Map<String, Object> triggerLogin(
            @RequestParam(name = "website_id") Integer websiteId,
            @RequestParam(name = "account_id") Integer accountId,
            @RequestParam(name = "task_id", required = false) String taskId,
            @RequestParam(name = "machine_id", required = false) Integer machineId) {
        Website website = websiteService.getById(websiteId);
        if (website == null) throw ApiException.notFound("网站不存在");
        Account account = accountService.getById(accountId);
        if (account == null) throw ApiException.notFound("账号不存在");
        validateLoginTarget(websiteId, website, account);

        Integer target = registry.pickAgent(machineId);
        if (target == null) {
            throw ApiException.unavailable("无在线 agent，请先启动至少一个 worker");
        }

        String plainPassword = crypto.decrypt(account.getPassword());
        if (taskId == null || taskId.isBlank()) {
            taskId = websiteId + "_" + accountId + "_" + (System.currentTimeMillis() / 1000L);
        }

        boolean isManual = "captcha".equals(website.getLoginType());
        CompletableFuture<Map<String, Object>> fut;
        try {
            fut = registry.dispatchLogin(
                    target, taskId, isManual, website.getUrl(), account.getUsername(), plainPassword,
                    website.getLoginType(), website.getLoginConfig(), websiteId, accountId);
        } catch (IllegalStateException e) {
            throw ApiException.conflict(e.getMessage());
        }

        int timeout = isManual ? MANUAL_LOGIN_TIMEOUT : AUTO_LOGIN_TIMEOUT;
        Map<String, Object> result;
        try {
            result = fut.get(timeout, TimeUnit.SECONDS);
        } catch (TimeoutException e) {
            registry.dispatchCancel(target, accountId);
            registry.cleanupLoginTask(taskId);
            result = new LinkedHashMap<>();
            result.put("status", "failed");
            result.put("message", "任务超时未返回，请检查 worker 状态");
            result.put("duration_ms", timeout * 1000);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            registry.dispatchCancel(target, accountId);
            registry.cleanupLoginTask(taskId);
            result = new LinkedHashMap<>();
            result.put("status", "failed");
            result.put("message", "请求已中断，任务终止信号已发送");
            result.put("duration_ms", 0);
        } catch (Exception e) {
            registry.cleanupLoginTask(taskId);
            result = new LinkedHashMap<>();
            result.put("status", "failed");
            result.put("message", "任务执行异常，请查看服务端与 worker 日志");
            result.put("duration_ms", 0);
        }

        LoginLog logEntry = new LoginLog();
        logEntry.setWebsiteId(websiteId);
        logEntry.setAccountId(accountId);
        logEntry.setStatus(String.valueOf(result.getOrDefault("status", "failed")));
        Object msg = result.get("message");
        logEntry.setMessage(msg == null ? "" : msg.toString());
        Object dur = result.get("duration_ms");
        if (dur instanceof Number n) {
            logEntry.setDurationMs(n.intValue());
        }
        loginLogService.save(logEntry);

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("task_id", taskId);
        resp.putAll(result);
        return resp;
    }

    // ── 登录日志 ────────────────────────────────────────────────

    @GetMapping("/logs")
    public List<LoginLog> getLoginLogs(
            @RequestParam(name = "website_id", required = false) Integer websiteId,
            @RequestParam(name = "account_id", required = false) Integer accountId,
            @RequestParam(name = "limit", defaultValue = "50") int limit) {
        return loginLogService.search(websiteId, accountId, PageRequests.limit(limit));
    }

    // ── 订单查询与提醒 ──────────────────────────────────────────

    @PostMapping("/order-check")
    public Map<String, Object> orderCheck(
            @RequestParam(name = "account_id") Integer accountId,
            @RequestParam(name = "machine_id", required = false) Integer machineId) {
        Account account = accountService.getById(accountId);
        if (account == null) throw ApiException.notFound("账号不存在");
        Website website = websiteService.getById(account.getWebsiteId());
        if (website == null) throw ApiException.notFound("网站不存在");
        validateActiveTarget(website, account);

        Integer target = registry.pickAgent(machineId);
        if (target == null) {
            throw ApiException.unavailable("无在线 agent，请先启动至少一个 worker");
        }

        String plainPassword = crypto.decrypt(account.getPassword());
        String taskId = "order_" + account.getWebsiteId() + "_" + accountId + "_" + (System.currentTimeMillis() / 1000L);

        try {
            registry.dispatchOrderCheck(target, taskId, website.getUrl(), account.getUsername(),
                    plainPassword, website.getLoginType(), website.getLoginConfig(),
                    account.getWebsiteId(), accountId);
        } catch (IllegalStateException e) {
            throw ApiException.conflict(e.getMessage());
        }

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("status", "started");
        resp.put("message", "订单监控已启动，将持续循环检测订单数量");
        return resp;
    }

    @GetMapping("/order-check/status")
    public Object orderCheckStatus(@RequestParam(name = "account_id", required = false) Integer accountId) {
        return registry.getOrderCheckStatus(accountId);
    }

    @PostMapping("/order-check/{accountId}/cancel")
    public Map<String, Object> orderCheckCancel(@PathVariable Integer accountId) {
        Map<String, Object> resp = new LinkedHashMap<>();
        AgentRegistry.TaskInfo info = registry.getAccountTask(accountId);
        if (info == null) {
            resp.put("status", "idle");
            resp.put("message", "没有正在运行的订单检查");
            return resp;
        }
        if (!"running".equals(info.status)) {
            resp.put("status", info.status);
            resp.put("message", "任务不在运行中");
            return resp;
        }
        boolean ok = registry.dispatchCancel(info.machineId, accountId);
        if (!ok) {
            resp.put("status", info.status);
            resp.put("message", "下发终止失败，agent 可能已离线");
            return resp;
        }
        info.status = "stopping";
        info.message = "正在终止...";
        resp.put("status", "stopping");
        resp.put("message", "已发送终止信号，浏览器将自动关闭");
        return resp;
    }

    private void validateLoginTarget(Integer websiteId, Website website, Account account) {
        if (!websiteId.equals(account.getWebsiteId())) {
            throw ApiException.badRequest("账号不属于指定网站");
        }
        validateActiveTarget(website, account);
    }

    private void validateActiveTarget(Website website, Account account) {
        if (!Integer.valueOf(1).equals(website.getIsActive())) {
            throw ApiException.conflict("网站已停用，不能执行登录");
        }
        if (!Integer.valueOf(1).equals(account.getIsActive())) {
            throw ApiException.conflict("账号已停用，不能执行登录");
        }
    }
}
