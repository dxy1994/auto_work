package com.auto.service.impl;

import com.auto.entity.Account;
import com.auto.mapper.AccountMapper;
import com.auto.service.AccountService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class AccountServiceImpl extends ServiceImpl<AccountMapper, Account> implements AccountService {

    @Override
    public IPage<Account> search(Integer websiteId, Page<Account> page) {
        LambdaQueryWrapper<Account> w = new LambdaQueryWrapper<>();
        w.eq(Account::getIsActive, 1)
                .eq(websiteId != null, Account::getWebsiteId, websiteId)
                .orderByDesc(Account::getId);
        return page(page, w);
    }

    @Override
    public List<Account> findByWebsiteIdAndIsDefault(Integer websiteId, Integer isDefault) {
        return list(new LambdaQueryWrapper<Account>()
                .eq(Account::getWebsiteId, websiteId)
                .eq(Account::getIsDefault, isDefault));
    }
}
