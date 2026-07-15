package com.auto.service.impl;

import com.auto.entity.CookiesStore;
import com.auto.mapper.CookiesStoreMapper;
import com.auto.service.CookiesStoreService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

@Service
public class CookiesStoreServiceImpl extends ServiceImpl<CookiesStoreMapper, CookiesStore>
        implements CookiesStoreService {

    @Override
    public CookiesStore findByWebsiteIdAndAccountId(Integer websiteId, Integer accountId) {
        return getOne(new LambdaQueryWrapper<CookiesStore>()
                .eq(CookiesStore::getWebsiteId, websiteId)
                .eq(CookiesStore::getAccountId, accountId), false);
    }
}
