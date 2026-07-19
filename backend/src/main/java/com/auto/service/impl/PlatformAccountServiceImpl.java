package com.auto.service.impl;

import com.auto.entity.PlatformAccount;
import com.auto.mapper.PlatformAccountMapper;
import com.auto.service.PlatformAccountService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class PlatformAccountServiceImpl extends ServiceImpl<PlatformAccountMapper, PlatformAccount> implements PlatformAccountService {

    @Override
    public IPage<PlatformAccount> search(Integer websiteId, Page<PlatformAccount> page) {
        LambdaQueryWrapper<PlatformAccount> w = new LambdaQueryWrapper<>();
        w.eq(PlatformAccount::getIsActive, 1)
                .eq(websiteId != null, PlatformAccount::getWebsiteId, websiteId)
                .orderByDesc(PlatformAccount::getId);
        return page(page, w);
    }

    @Override
    public List<PlatformAccount> findByWebsiteIdAndIsDefault(Integer websiteId, Integer isDefault) {
        return list(new LambdaQueryWrapper<PlatformAccount>()
                .eq(PlatformAccount::getWebsiteId, websiteId)
                .eq(PlatformAccount::getIsDefault, isDefault));
    }

    @Override
    public List<PlatformAccount> findAllActive() {
        return list(new LambdaQueryWrapper<PlatformAccount>().eq(PlatformAccount::getIsActive, 1));
    }
}
