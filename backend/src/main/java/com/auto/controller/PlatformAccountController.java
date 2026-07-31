package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.PlatformAccount;
import com.auto.service.PlatformAccountService;
import com.auto.service.CryptoService;
import com.auto.service.GameRegionInventoryShopPriceService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/** 账号管理。 */
@RestController
@RequestMapping("/api/platform-accounts")
public class PlatformAccountController {

    private final PlatformAccountService platformAccountService;
    private final CryptoService crypto;
    private final GameRegionInventoryShopPriceService shopPriceService;

    public PlatformAccountController(PlatformAccountService platformAccountService, CryptoService crypto,
                                     GameRegionInventoryShopPriceService shopPriceService) {
        this.platformAccountService = platformAccountService;
        this.crypto = crypto;
        this.shopPriceService = shopPriceService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "website_id", required = false) Integer websiteId,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize) {
        IPage<PlatformAccount> result = platformAccountService.search(websiteId, PageRequests.of(page, pageSize));
        return Map.of("total", result.getTotal(), "items", result.getRecords());
    }

    @GetMapping("/all")
    public List<PlatformAccount> listAll() {
        return platformAccountService.findAllActive();
    }

    @GetMapping("/{id}")
    public PlatformAccount get(@PathVariable Integer id) {
        PlatformAccount a = platformAccountService.getById(id);
        if (a == null) throw ApiException.notFound("账号不存在");
        return a;
    }

    /** 按需解密单个账号密码；禁止浏览器和中间缓存保存明文响应。 */
    @GetMapping("/{id}/password")
    public ResponseEntity<Map<String, String>> revealPassword(@PathVariable Integer id) {
        PlatformAccount account = platformAccountService.getById(id);
        if (account == null) throw ApiException.notFound("账号不存在");
        String password = crypto.decrypt(account.getPassword());
        return ResponseEntity.ok()
                .cacheControl(CacheControl.noStore())
                .body(Map.of("password", password));
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Transactional
    public PlatformAccount create(@RequestBody PlatformAccount payload) {
        if (payload == null || payload.getWebsiteId() == null || payload.getLabel() == null
                || payload.getLabel().isBlank() || payload.getUsername() == null
                || payload.getUsername().isBlank() || payload.getPassword() == null
                || payload.getPassword().isBlank()) {
            throw ApiException.badRequest("网站、标签、用户名和密码不能为空");
        }
        boolean isDefault = payload.getIsDefault() != null && payload.getIsDefault() == 1;
        if (isDefault) {
            unsetDefaults(payload.getWebsiteId(), null);
        }
        payload.setId(null);
        payload.setPassword(crypto.encrypt(payload.getPassword()));
        payload.setIsDefault(isDefault ? 1 : 0);
        payload.setIsActive(1);
        platformAccountService.save(payload);
        shopPriceService.initForAccount(payload.getId());
        return payload;
    }

    @PutMapping("/{id}")
    @Transactional
    public PlatformAccount update(@PathVariable Integer id, @RequestBody PlatformAccount payload) {
        if (payload == null) {
            throw ApiException.badRequest("请求参数不能为空");
        }
        PlatformAccount a = platformAccountService.getById(id);
        if (a == null) throw ApiException.notFound("账号不存在");
        if (payload.getIsDefault() != null && payload.getIsDefault() == 1) {
            unsetDefaults(a.getWebsiteId(), id);
        }
        if (payload.getLabel() != null) a.setLabel(payload.getLabel());
        if (payload.getUsername() != null) a.setUsername(payload.getUsername());
        if (payload.getPassword() != null && !payload.getPassword().isEmpty()) {
            a.setPassword(crypto.encrypt(payload.getPassword()));
        }
        if (payload.getExtraFields() != null) a.setExtraFields(payload.getExtraFields());
        if (payload.getIsDefault() != null) a.setIsDefault(payload.getIsDefault());
        if (payload.getIsActive() != null) a.setIsActive(payload.getIsActive());
        platformAccountService.updateById(a);
        return a;
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Integer id) {
        PlatformAccount a = platformAccountService.getById(id);
        if (a == null) throw ApiException.notFound("账号不存在");
        platformAccountService.removeById(id);
    }

    /** 取消同网站其他默认账号（excludeId 可为 null）。 */
    private void unsetDefaults(Integer websiteId, Integer excludeId) {
        List<PlatformAccount> defaults = platformAccountService.findByWebsiteIdAndIsDefault(websiteId, 1).stream()
                .filter(other -> excludeId == null || !other.getId().equals(excludeId))
                .toList();
        defaults.forEach(other -> other.setIsDefault(0));
        if (!defaults.isEmpty()) {
            platformAccountService.updateBatchById(defaults);
        }
    }
}
