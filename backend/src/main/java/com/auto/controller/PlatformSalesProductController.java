package com.auto.controller;

import com.auto.common.PageRequests;
import com.auto.entity.PlatformSalesProduct;
import com.auto.service.PlatformSalesProductService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/** 平台当前在售商品镜像查询。写入仅由 Worker 完整快照同步触发。 */
@RestController
@RequestMapping("/api/platform-sales-products")
public class PlatformSalesProductController {

    private final PlatformSalesProductService productService;

    public PlatformSalesProductController(
            PlatformSalesProductService productService) {
        this.productService = productService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "website_id", required = false)
            Integer websiteId,
            @RequestParam(name = "platform_account_id", required = false)
            Integer platformAccountId,
            @RequestParam(name = "game_id", required = false)
            Integer gameId,
            @RequestParam(name = "parse_status", required = false)
            String parseStatus,
            @RequestParam(name = "keyword", required = false)
            String keyword,
            @RequestParam(name = "page", defaultValue = "1")
            int page,
            @RequestParam(name = "page_size", defaultValue = "50")
            int pageSize) {
        IPage<PlatformSalesProduct> result = productService.search(
                websiteId,
                platformAccountId,
                gameId,
                parseStatus,
                keyword,
                PageRequests.of(page, pageSize));
        return Map.of(
                "total", result.getTotal(),
                "items", result.getRecords());
    }

    @GetMapping("/account/{platformAccountId}")
    public List<PlatformSalesProduct> listByAccount(
            @org.springframework.web.bind.annotation.PathVariable
            Integer platformAccountId) {
        return productService.findByAccountId(platformAccountId);
    }
}
