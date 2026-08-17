package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.Machine;
import com.auto.entity.MouseKeyboardDevice;
import com.auto.service.MachineService;
import com.auto.service.MouseKeyboardDeviceService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 鼠标键盘设备管理。 */
@RestController
@RequestMapping("/api/mk-devices")
public class MouseKeyboardDeviceController {

    private final MouseKeyboardDeviceService mkDeviceService;
    private final MachineService machineService;

    public MouseKeyboardDeviceController(MouseKeyboardDeviceService mkDeviceService,
                                         MachineService machineService) {
        this.mkDeviceService = mkDeviceService;
        this.machineService = machineService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize,
            @RequestParam(name = "keyword", required = false) String keyword) {
        IPage<MouseKeyboardDevice> result = mkDeviceService.search(keyword, PageRequests.of(page, pageSize));
        List<Map<String, Object>> items = new ArrayList<>();
        for (MouseKeyboardDevice d : result.getRecords()) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", d.getId());
            item.put("name", d.getName());
            item.put("device_type", d.getDeviceType());
            item.put("device_info", d.getDeviceInfo());
            item.put("remark", d.getRemark());
            item.put("is_active", d.getIsActive());
            item.put("created_at", d.getCreatedAt());
            item.put("updated_at", d.getUpdatedAt());
            Machine m = machineService.findByMkDeviceId(d.getId());
            item.put("machine_name", m != null ? (m.getName() != null ? m.getName() : m.getMacAddress()) : null);
            items.add(item);
        }
        return Map.of("total", result.getTotal(), "items", items);
    }

    @GetMapping("/all")
    public List<MouseKeyboardDevice> listAll() {
        return mkDeviceService.findAllActive();
    }

    @GetMapping("/{id}")
    public MouseKeyboardDevice get(@PathVariable Integer id) {
        MouseKeyboardDevice d = mkDeviceService.getById(id);
        if (d == null) throw ApiException.notFound("设备不存在");
        return d;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public MouseKeyboardDevice create(@RequestBody MouseKeyboardDevice payload) {
        payload.setId(null);
        payload.setIsActive(1);
        mkDeviceService.save(payload);
        return payload;
    }

    @PutMapping("/{id}")
    public MouseKeyboardDevice update(@PathVariable Integer id, @RequestBody MouseKeyboardDevice payload) {
        MouseKeyboardDevice d = mkDeviceService.getById(id);
        if (d == null) throw ApiException.notFound("设备不存在");
        if (payload.getName() != null) d.setName(payload.getName());
        if (payload.getDeviceType() != null) d.setDeviceType(payload.getDeviceType());
        if (payload.getDeviceInfo() != null) d.setDeviceInfo(payload.getDeviceInfo());
        if (payload.getRemark() != null) d.setRemark(payload.getRemark());
        if (payload.getIsActive() != null) d.setIsActive(payload.getIsActive());
        mkDeviceService.updateById(d);
        return d;
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Integer id) {
        MouseKeyboardDevice d = mkDeviceService.getById(id);
        if (d == null) throw ApiException.notFound("设备不存在");
        mkDeviceService.removeById(id);
    }
}
