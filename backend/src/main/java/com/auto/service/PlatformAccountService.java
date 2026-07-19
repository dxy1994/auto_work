package com.auto.service;

import com.auto.entity.PlatformAccount;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;

import java.util.List;

public interface PlatformAccountService extends com.baomidou.mybatisplus.spring.service.IService<PlatformAccount> {

    IPage<PlatformAccount> search(Integer websiteId, Page<PlatformAccount> page);

    List<PlatformAccount> findByWebsiteIdAndIsDefault(Integer websiteId, Integer isDefault);

    List<PlatformAccount> findAllActive();
}
