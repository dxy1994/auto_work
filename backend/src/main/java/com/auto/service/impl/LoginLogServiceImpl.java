package com.auto.service.impl;

import com.auto.entity.LoginLog;
import com.auto.mapper.LoginLogMapper;
import com.auto.service.LoginLogService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class LoginLogServiceImpl extends ServiceImpl<LoginLogMapper, LoginLog> implements LoginLogService {

    @Override
    public List<LoginLog> search(Integer websiteId, Integer accountId, int limit) {
        LambdaQueryWrapper<LoginLog> w = new LambdaQueryWrapper<>();
        w.eq(websiteId != null, LoginLog::getWebsiteId, websiteId)
                .eq(accountId != null, LoginLog::getAccountId, accountId)
                .orderByDesc(LoginLog::getId);
        return page(new Page<>(1, limit), w).getRecords();
    }
}
