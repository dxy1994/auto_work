package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.Platform;
import com.auto.service.PlatformService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/** 网站管理。 */
@RestController
@RequestMapping("/api/platforms")
public class PlatformController {

    private final PlatformService platformService;

    public PlatformController(PlatformService platformService) {
        this.platformService = platformService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize,
            @RequestParam(name = "category", required = false) String category,
            @RequestParam(name = "keyword", required = false) String keyword) {
        IPage<Platform> result = platformService.search(category, keyword, PageRequests.of(page, pageSize));
        return Map.of("total", result.getTotal(), "items", result.getRecords());
    }

    @GetMapping("/all")
    public List<Platform> listAll() {
        return platformService.findAllActiveOrdered();
    }

    @GetMapping("/categories")
    public List<String> categories() {
        return platformService.findDistinctCategories();
    }

    @GetMapping("/{id}")
    public Platform get(@PathVariable Integer id) {
        Platform w = platformService.getById(id);
        if (w == null) throw ApiException.notFound("网站不存在");
        return w;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Platform create(@RequestBody Platform payload) {
        payload.setId(null);
        payload.setIsActive(1);
        platformService.save(payload);
        return payload;
    }

    @PutMapping("/{id}")
    public Platform update(@PathVariable Integer id, @RequestBody Platform payload) {
        Platform w = platformService.getById(id);
        if (w == null) throw ApiException.notFound("网站不存在");
        if (payload.getName() != null) w.setName(payload.getName());
        if (payload.getUrl() != null) w.setUrl(payload.getUrl());
        if (payload.getIcon() != null) w.setIcon(payload.getIcon());
        if (payload.getCategory() != null) w.setCategory(payload.getCategory());
        if (payload.getLoginType() != null) w.setLoginType(payload.getLoginType());
        if (payload.getLoginConfig() != null) w.setLoginConfig(payload.getLoginConfig());
        if (payload.getRemark() != null) w.setRemark(payload.getRemark());
        if (payload.getSortOrder() != null) w.setSortOrder(payload.getSortOrder());
        if (payload.getIsActive() != null) w.setIsActive(payload.getIsActive());
        platformService.updateById(w);
        return w;
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Integer id) {
        Platform w = platformService.getById(id);
        if (w == null) throw ApiException.notFound("网站不存在");
        platformService.removeById(id);
    }
}
