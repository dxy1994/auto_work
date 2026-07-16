package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.entity.Account;
import com.auto.entity.MachineAccount;
import com.auto.entity.Website;
import com.auto.service.AccountService;
import com.auto.service.CryptoService;
import com.auto.service.MachineAccountService;
import com.auto.service.WebsiteService;
import com.auto.ws.AgentRegistry;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 自动化控制面：订单查询、交易等任务的分发与状态查询。
 */
@RestController
@RequestMapping("/api/automation")
public class AutomationController {

    private final WebsiteService websiteService;
    private final AccountService accountService;
    private final MachineAccountService machineAccountService;
    private final CryptoService crypto;
    private final AgentRegistry registry;

    public AutomationController(WebsiteService websiteService, AccountService accountService,
                                MachineAccountService machineAccountService,
                                CryptoService crypto,
                                AgentRegistry registry) {
        this.websiteService = websiteService;
        this.accountService = accountService;
        this.machineAccountService = machineAccountService;
        this.crypto = crypto;
        this.registry = registry;
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

        // 查询该账户关联的所有机器
        List<MachineAccount> associations = machineAccountService.findByAccountIdActive(accountId);
        if (associations.isEmpty()) {
            throw ApiException.badRequest("该账号未关联任何机器，请先在机器管理中绑定");
        }

        // 确定目标机器
        Integer target;
        if (machineId != null) {
            // 指定了机器：验证该机器是否已在关联列表中
            boolean matched = associations.stream()
                    .anyMatch(ma -> ma.getMachineId().equals(machineId));
            if (!matched) {
                throw ApiException.badRequest("该账号未关联指定机器（machine_id=" + machineId + "）");
            }
            target = registry.pickAgent(machineId);
            if (target == null) {
                throw ApiException.unavailable("指定的机器不在线");
            }
        } else {
            // 未指定：从关联的机器中选第一个在线的
            target = null;
            for (MachineAccount ma : associations) {
                Integer mid = registry.pickAgent(ma.getMachineId());
                if (mid != null) {
                    target = mid;
                    break;
                }
            }
            if (target == null) {
                throw ApiException.unavailable("该账号关联的机器均不在线，请先启动至少一个 worker");
            }
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

    private void validateActiveTarget(Website website, Account account) {
        if (!Integer.valueOf(1).equals(website.getIsActive())) {
            throw ApiException.conflict("网站已停用");
        }
        if (!Integer.valueOf(1).equals(account.getIsActive())) {
            throw ApiException.conflict("账号已停用");
        }
    }
}
