package com.auto.service;

import com.auto.entity.Account;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;

import java.util.List;

public interface AccountService extends com.baomidou.mybatisplus.spring.service.IService<Account> {

    IPage<Account> search(Integer websiteId, Page<Account> page);

    List<Account> findByWebsiteIdAndIsDefault(Integer websiteId, Integer isDefault);
}
