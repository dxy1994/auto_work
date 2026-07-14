package com.auto.service;

import com.auto.entity.CookiesStore;
import com.baomidou.mybatisplus.extension.service.IService;

public interface CookiesStoreService extends IService<CookiesStore> {

    CookiesStore findByWebsiteIdAndAccountId(Integer websiteId, Integer accountId);
}
