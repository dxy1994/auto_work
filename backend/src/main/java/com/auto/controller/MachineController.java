package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.Machine;
import com.auto.entity.MachineAccount;
import com.auto.entity.MachineGame;
import com.auto.service.MachineAccountService;
import com.auto.service.MachineGameService;
import com.auto.service.MachineService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 机器管理。 */
@RestController
@RequestMapping("/api/machines")
public class MachineController {

    private final MachineService machineService;
    private final MachineGameService machineGameService;
    private final MachineAccountService machineAccountService;

    public MachineController(MachineService machineService, MachineGameService machineGameService,
                            MachineAccountService machineAccountService) {
        this.machineService = machineService;
        this.machineGameService = machineGameService;
        this.machineAccountService = machineAccountService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize,
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "status", required = false) String status) {
        IPage<Machine> result = machineService.search(keyword, status, PageRequests.of(page, pageSize));
        List<Map<String, Object>> items = new ArrayList<>();
        for (Machine m : result.getRecords()) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", m.getId());
            item.put("mac_address", m.getMacAddress());
            item.put("ip_address", m.getIpAddress());
            item.put("hostname", m.getHostname());
            item.put("name", m.getName());
            item.put("os_info", m.getOsInfo());
            item.put("status", m.getStatus());
            item.put("last_heartbeat", m.getLastHeartbeat());
            item.put("remark", m.getRemark());
            item.put("is_active", m.getIsActive());
            item.put("created_at", m.getCreatedAt());
            item.put("updated_at", m.getUpdatedAt());
            // 标识机器类型
            boolean hasGames = !machineGameService.findByMachineIdActiveOrderByPriorityDesc(m.getId()).isEmpty();
            boolean hasAccounts = !machineAccountService.findByMachineIdActive(m.getId()).isEmpty();
            item.put("type", hasGames ? "game" : hasAccounts ? "account" : "none");
            items.add(item);
        }
        return Map.of("total", result.getTotal(), "items", items);
    }

    @GetMapping("/all")
    public List<Machine> listAll() {
        return machineService.findAllActive();
    }

    @GetMapping("/{machineId}")
    public Machine get(@PathVariable Integer machineId) {
        Machine m = machineService.getById(machineId);
        if (m == null) throw ApiException.notFound("机器不存在");
        return m;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Machine create(@RequestBody Machine payload) {
        if (machineService.findByMacAddress(payload.getMacAddress()) != null) {
            throw ApiException.badRequest("MAC地址 " + payload.getMacAddress() + " 已存在");
        }
        payload.setId(null);
        payload.setIsActive(1);
        machineService.save(payload);
        return payload;
    }

    @PutMapping("/{machineId}")
    public Machine update(@PathVariable Integer machineId, @RequestBody Machine payload) {
        Machine m = machineService.getById(machineId);
        if (m == null) throw ApiException.notFound("机器不存在");
        if (payload.getHostname() != null) m.setHostname(payload.getHostname());
        if (payload.getIpAddress() != null) m.setIpAddress(payload.getIpAddress());
        if (payload.getName() != null) m.setName(payload.getName());
        if (payload.getOsInfo() != null) m.setOsInfo(payload.getOsInfo());
        if (payload.getStatus() != null) m.setStatus(payload.getStatus());
        if (payload.getRemark() != null) m.setRemark(payload.getRemark());
        if (payload.getIsActive() != null) m.setIsActive(payload.getIsActive());
        machineService.updateById(m);
        return m;
    }

    @DeleteMapping("/{machineId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Integer machineId) {
        Machine m = machineService.getById(machineId);
        if (m == null) throw ApiException.notFound("机器不存在");
        machineService.removeById(machineId);
    }

    // ── 机器关联游戏 ────────────────────────────────────────────

    @GetMapping("/{machineId}/games")
    public List<MachineGame> listGames(@PathVariable Integer machineId) {
        return machineGameService.findByMachineIdActiveOrderByPriorityDesc(machineId);
    }

    @PostMapping("/{machineId}/games")
    @ResponseStatus(HttpStatus.CREATED)
    public MachineGame addGame(@PathVariable Integer machineId, @RequestBody MachineGame payload) {
        if (!machineAccountService.findByMachineIdActive(machineId).isEmpty()) {
            throw ApiException.badRequest("该机器已关联网站账户，不能同时关联游戏");
        }
        if (machineGameService.findByMachineIdAndGameId(machineId, payload.getGameId()) != null) {
            throw ApiException.badRequest("该游戏已关联此机器");
        }
        payload.setId(null);
        payload.setMachineId(machineId);
        payload.setIsActive(1);
        machineGameService.save(payload);
        return payload;
    }

    @PutMapping("/games/{mgId}")
    public MachineGame updateGame(@PathVariable Integer mgId, @RequestBody MachineGame payload) {
        MachineGame mg = machineGameService.getById(mgId);
        if (mg == null) throw ApiException.notFound("关联记录不存在");
        if (payload.getPriority() != null) mg.setPriority(payload.getPriority());
        if (payload.getMaxConcurrent() != null) mg.setMaxConcurrent(payload.getMaxConcurrent());
        if (payload.getIsActive() != null) mg.setIsActive(payload.getIsActive());
        machineGameService.updateById(mg);
        return mg;
    }

    @DeleteMapping("/games/{mgId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void removeGame(@PathVariable Integer mgId) {
        MachineGame mg = machineGameService.getById(mgId);
        if (mg == null) throw ApiException.notFound("关联记录不存在");
        machineGameService.removeById(mgId);
    }

    // ── 机器关联账户 ────────────────────────────────────────────

    @GetMapping("/{machineId}/accounts")
    public List<MachineAccount> listAccounts(@PathVariable Integer machineId) {
        return machineAccountService.findByMachineIdActive(machineId);
    }

    @PostMapping("/{machineId}/accounts")
    @ResponseStatus(HttpStatus.CREATED)
    public MachineAccount addAccount(@PathVariable Integer machineId, @RequestBody MachineAccount payload) {
        if (!machineGameService.findByMachineIdActiveOrderByPriorityDesc(machineId).isEmpty()) {
            throw ApiException.badRequest("该机器已关联游戏，不能同时关联网站账户");
        }
        if (machineAccountService.findByMachineIdAndAccountId(machineId, payload.getAccountId()) != null) {
            throw ApiException.badRequest("该账户已关联此机器");
        }
        payload.setId(null);
        payload.setMachineId(machineId);
        payload.setIsActive(1);
        machineAccountService.save(payload);
        return payload;
    }

    @DeleteMapping("/accounts/{maId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void removeAccount(@PathVariable Integer maId) {
        MachineAccount ma = machineAccountService.getById(maId);
        if (ma == null) throw ApiException.notFound("关联记录不存在");
        machineAccountService.removeById(maId);
    }
}
