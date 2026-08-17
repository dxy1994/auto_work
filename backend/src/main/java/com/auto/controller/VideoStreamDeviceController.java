package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.Machine;
import com.auto.entity.VideoStreamDevice;
import com.auto.service.MachineService;
import com.auto.service.VideoStreamDeviceService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 视频流设备管理。 */
@RestController
@RequestMapping("/api/vs-devices")
public class VideoStreamDeviceController {

    private final VideoStreamDeviceService vsDeviceService;
    private final MachineService machineService;

    public VideoStreamDeviceController(VideoStreamDeviceService vsDeviceService,
                                       MachineService machineService) {
        this.vsDeviceService = vsDeviceService;
        this.machineService = machineService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize,
            @RequestParam(name = "keyword", required = false) String keyword) {
        IPage<VideoStreamDevice> result = vsDeviceService.search(keyword, PageRequests.of(page, pageSize));
        List<Map<String, Object>> items = new ArrayList<>();
        for (VideoStreamDevice d : result.getRecords()) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", d.getId());
            item.put("name", d.getName());
            item.put("device_type", d.getDeviceType());
            item.put("device_info", d.getDeviceInfo());
            item.put("remark", d.getRemark());
            item.put("is_active", d.getIsActive());
            item.put("created_at", d.getCreatedAt());
            item.put("updated_at", d.getUpdatedAt());
            Machine m = machineService.findByVsDeviceId(d.getId());
            item.put("machine_name", m != null ? (m.getName() != null ? m.getName() : m.getMacAddress()) : null);
            items.add(item);
        }
        return Map.of("total", result.getTotal(), "items", items);
    }

    @GetMapping("/all")
    public List<VideoStreamDevice> listAll() {
        return vsDeviceService.findAllActive();
    }

    @GetMapping("/{id}")
    public VideoStreamDevice get(@PathVariable Integer id) {
        VideoStreamDevice d = vsDeviceService.getById(id);
        if (d == null) throw ApiException.notFound("设备不存在");
        return d;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public VideoStreamDevice create(@RequestBody VideoStreamDevice payload) {
        payload.setId(null);
        payload.setIsActive(1);
        vsDeviceService.save(payload);
        return payload;
    }

    @PutMapping("/{id}")
    public VideoStreamDevice update(@PathVariable Integer id, @RequestBody VideoStreamDevice payload) {
        VideoStreamDevice d = vsDeviceService.getById(id);
        if (d == null) throw ApiException.notFound("设备不存在");
        if (payload.getName() != null) d.setName(payload.getName());
        if (payload.getDeviceType() != null) d.setDeviceType(payload.getDeviceType());
        if (payload.getDeviceInfo() != null) d.setDeviceInfo(payload.getDeviceInfo());
        if (payload.getRemark() != null) d.setRemark(payload.getRemark());
        if (payload.getIsActive() != null) d.setIsActive(payload.getIsActive());
        vsDeviceService.updateById(d);
        return d;
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Integer id) {
        VideoStreamDevice d = vsDeviceService.getById(id);
        if (d == null) throw ApiException.notFound("设备不存在");
        vsDeviceService.removeById(id);
    }
}
