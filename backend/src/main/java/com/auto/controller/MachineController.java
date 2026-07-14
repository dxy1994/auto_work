package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.Machine;
import com.auto.entity.MachineGame;
import com.auto.service.MachineGameService;
import com.auto.service.MachineService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/** 机器管理。 */
@RestController
@RequestMapping("/api/machines")
public class MachineController {

    private final MachineService machineService;
    private final MachineGameService machineGameService;

    public MachineController(MachineService machineService, MachineGameService machineGameService) {
        this.machineService = machineService;
        this.machineGameService = machineGameService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize,
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "status", required = false) String status) {
        IPage<Machine> result = machineService.search(keyword, status, PageRequests.of(page, pageSize));
        return Map.of("total", result.getTotal(), "items", result.getRecords());
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
        m.setIsActive(0);
        machineService.updateById(m);
    }

    // ── 机器关联游戏 ────────────────────────────────────────────

    @GetMapping("/{machineId}/games")
    public List<MachineGame> listGames(@PathVariable Integer machineId) {
        return machineGameService.findByMachineIdActiveOrderByPriorityDesc(machineId);
    }

    @PostMapping("/{machineId}/games")
    @ResponseStatus(HttpStatus.CREATED)
    public MachineGame addGame(@PathVariable Integer machineId, @RequestBody MachineGame payload) {
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
        mg.setIsActive(0);
        machineGameService.updateById(mg);
    }
}
