package com.auto.service;

import com.auto.entity.PlatformCookie;
import com.baomidou.mybatisplus.spring.service.IService;

public interface PlatformCookieService extends IService<PlatformCookie> {

    PlatformCookie findByWebsiteIdAndAccountId(Integer websiteId, Integer accountId);
}
