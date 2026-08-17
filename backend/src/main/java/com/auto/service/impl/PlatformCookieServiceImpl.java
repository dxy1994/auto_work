package com.auto.service.impl;

import com.auto.entity.PlatformCookie;
import com.auto.mapper.PlatformCookieMapper;
import com.auto.service.PlatformCookieService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

@Service
public class PlatformCookieServiceImpl extends ServiceImpl<PlatformCookieMapper, PlatformCookie>
        implements PlatformCookieService {

    @Override
    public PlatformCookie findByWebsiteIdAndAccountId(Integer websiteId, Integer accountId) {
        return getOne(new LambdaQueryWrapper<PlatformCookie>()
                .eq(PlatformCookie::getWebsiteId, websiteId)
                .eq(PlatformCookie::getAccountId, accountId), false);
    }
}
