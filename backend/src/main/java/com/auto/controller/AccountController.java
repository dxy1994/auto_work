package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.Account;
import com.auto.service.AccountService;
import com.auto.service.CryptoService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/** 账号管理。 */
@RestController
@RequestMapping("/api/accounts")
public class AccountController {

    private final AccountService accountService;
    private final CryptoService crypto;

    public AccountController(AccountService accountService, CryptoService crypto) {
        this.accountService = accountService;
        this.crypto = crypto;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "website_id", required = false) Integer websiteId,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize) {
        IPage<Account> result = accountService.search(websiteId, PageRequests.of(page, pageSize));
        return Map.of("total", result.getTotal(), "items", result.getRecords());
    }

    @GetMapping("/all")
    public List<Account> listAll() {
        return accountService.findAllActive();
    }

    @GetMapping("/{id}")
    public Account get(@PathVariable Integer id) {
        Account a = accountService.getById(id);
        if (a == null) throw ApiException.notFound("账号不存在");
        return a;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Transactional
    public Account create(@RequestBody Account payload) {
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
        accountService.save(payload);
        return payload;
    }

    @PutMapping("/{id}")
    @Transactional
    public Account update(@PathVariable Integer id, @RequestBody Account payload) {
        if (payload == null) {
            throw ApiException.badRequest("请求参数不能为空");
        }
        Account a = accountService.getById(id);
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
        accountService.updateById(a);
        return a;
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Integer id) {
        Account a = accountService.getById(id);
        if (a == null) throw ApiException.notFound("账号不存在");
        accountService.removeById(id);
    }

    /** 取消同网站其他默认账号（excludeId 可为 null）。 */
    private void unsetDefaults(Integer websiteId, Integer excludeId) {
        List<Account> defaults = accountService.findByWebsiteIdAndIsDefault(websiteId, 1).stream()
                .filter(other -> excludeId == null || !other.getId().equals(excludeId))
                .toList();
        defaults.forEach(other -> other.setIsDefault(0));
        if (!defaults.isEmpty()) {
            accountService.updateBatchById(defaults);
        }
    }
}
