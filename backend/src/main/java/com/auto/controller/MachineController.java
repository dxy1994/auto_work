package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.Machine;
import com.auto.entity.MachinePlatformAccount;
import com.auto.entity.MachineGameAccount;
import com.auto.service.MachinePlatformAccountService;
import com.auto.service.MachineGameAccountService;
import com.auto.service.MachineService;
import com.auto.service.MouseKeyboardDeviceService;
import com.auto.service.VideoStreamDeviceService;
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
    private final MachineGameAccountService machineGameService;
    private final MachinePlatformAccountService machineAccountService;
    private final MouseKeyboardDeviceService mkDeviceService;
    private final VideoStreamDeviceService vsDeviceService;

    public MachineController(MachineService machineService, MachineGameAccountService machineGameService,
                            MachinePlatformAccountService machineAccountService,
                            MouseKeyboardDeviceService mkDeviceService,
                            VideoStreamDeviceService vsDeviceService) {
        this.machineService = machineService;
        this.machineGameService = machineGameService;
        this.machineAccountService = machineAccountService;
        this.mkDeviceService = mkDeviceService;
        this.vsDeviceService = vsDeviceService;
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
            item.put("mk_device_id", m.getMkDeviceId());
            item.put("vs_device_id", m.getVsDeviceId());
            item.put("created_at", m.getCreatedAt());
            item.put("updated_at", m.getUpdatedAt());
            // 标识机器类型（可同时关联游戏账号和网站账户）
            boolean hasGames = !machineGameService.findByMachineIdActiveOrderByPriorityDesc(m.getId()).isEmpty();
            boolean hasAccounts = !machineAccountService.findByMachineIdActive(m.getId()).isEmpty();
            item.put("type", hasGames && hasAccounts ? "both" : hasGames ? "game" : hasAccounts ? "account" : "none");
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
        if (payload.getMkDeviceId() != null) {
            if (payload.getMkDeviceId() == -1) {
                m.setMkDeviceId(null);
            } else {
                Machine existingMk = machineService.findByMkDeviceId(payload.getMkDeviceId());
                if (existingMk != null && !existingMk.getId().equals(machineId)) {
                    throw ApiException.badRequest("该鼠标键盘设备已被机器 [" + existingMk.getName() + "] 关联");
                }
                m.setMkDeviceId(payload.getMkDeviceId());
            }
        }
        if (payload.getVsDeviceId() != null) {
            if (payload.getVsDeviceId() == -1) {
                m.setVsDeviceId(null);
            } else {
                Machine existingVs = machineService.findByVsDeviceId(payload.getVsDeviceId());
                if (existingVs != null && !existingVs.getId().equals(machineId)) {
                    throw ApiException.badRequest("该视频流设备已被机器 [" + existingVs.getName() + "] 关联");
                }
                m.setVsDeviceId(payload.getVsDeviceId());
            }
        }
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

    // ── 机器关联游戏账号 ────────────────────────────────────────

    @GetMapping("/{machineId}/game-accounts")
    public List<MachineGameAccount> listGames(@PathVariable Integer machineId) {
        return machineGameService.findByMachineIdActiveOrderByPriorityDesc(machineId);
    }

    @PostMapping("/{machineId}/game-accounts")
    @ResponseStatus(HttpStatus.CREATED)
    public MachineGameAccount addGame(@PathVariable Integer machineId, @RequestBody MachineGameAccount payload) {
        // 检查是否已存在相同账号+大区的关联
        MachineGameAccount existing = machineGameService.findByMachineIdAndGameAccountIdAndRegionId(
                machineId, payload.getGameAccountId(), payload.getRegionId());
        if (existing != null) {
            throw ApiException.badRequest("该游戏账号（大区）已关联此机器");
        }
        payload.setId(null);
        payload.setMachineId(machineId);
        payload.setIsActive(1);
        machineGameService.save(payload);
        return payload;
    }

    @PutMapping("/game-accounts/{mgId}")
    public MachineGameAccount updateGame(@PathVariable Integer mgId, @RequestBody MachineGameAccount payload) {
        MachineGameAccount mg = machineGameService.getById(mgId);
        if (mg == null) throw ApiException.notFound("关联记录不存在");
        if (payload.getPriority() != null) mg.setPriority(payload.getPriority());
        if (payload.getMaxConcurrent() != null) mg.setMaxConcurrent(payload.getMaxConcurrent());
        if (payload.getIsActive() != null) mg.setIsActive(payload.getIsActive());
        machineGameService.updateById(mg);
        return mg;
    }

    @DeleteMapping("/game-accounts/{mgId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void removeGame(@PathVariable Integer mgId) {
        MachineGameAccount mg = machineGameService.getById(mgId);
        if (mg == null) throw ApiException.notFound("关联记录不存在");
        machineGameService.removeById(mgId);
    }

    // ── 机器关联账户 ────────────────────────────────────────────

    @GetMapping("/{machineId}/platform-accounts")
    public List<MachinePlatformAccount> listAccounts(@PathVariable Integer machineId) {
        return machineAccountService.findByMachineIdActive(machineId);
    }

    @PostMapping("/{machineId}/platform-accounts")
    @ResponseStatus(HttpStatus.CREATED)
    public MachinePlatformAccount addAccount(@PathVariable Integer machineId, @RequestBody MachinePlatformAccount payload) {
        if (machineAccountService.findByMachineIdAndAccountId(machineId, payload.getAccountId()) != null) {
            throw ApiException.badRequest("该账户已关联此机器");
        }
        payload.setId(null);
        payload.setMachineId(machineId);
        payload.setIsActive(1);
        machineAccountService.save(payload);
        return payload;
    }

    @DeleteMapping("/platform-accounts/{maId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void removeAccount(@PathVariable Integer maId) {
        MachinePlatformAccount ma = machineAccountService.getById(maId);
        if (ma == null) throw ApiException.notFound("关联记录不存在");
        machineAccountService.removeById(maId);
    }
}
