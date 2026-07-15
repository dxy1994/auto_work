package com.auto.service;

import com.auto.entity.CookiesStore;
import com.baomidou.mybatisplus.spring.service.IService;

public interface CookiesStoreService extends IService<CookiesStore> {

    CookiesStore findByWebsiteIdAndAccountId(Integer websiteId, Integer accountId);
}
