package com.auto.service.impl;

import com.auto.entity.MachinePlatformAccount;
import com.auto.mapper.MachinePlatformAccountMapper;
import com.auto.service.MachinePlatformAccountService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class MachinePlatformAccountServiceImpl extends ServiceImpl<MachinePlatformAccountMapper, MachinePlatformAccount>
        implements MachinePlatformAccountService {

    @Override
    public List<MachinePlatformAccount> findAllActive() {
        return list(new LambdaQueryWrapper<MachinePlatformAccount>()
                .eq(MachinePlatformAccount::getIsActive, 1));
    }

    @Override
    public List<MachinePlatformAccount> findByMachineIdActive(Integer machineId) {
        return list(new LambdaQueryWrapper<MachinePlatformAccount>()
                .eq(MachinePlatformAccount::getMachineId, machineId)
                .eq(MachinePlatformAccount::getIsActive, 1));
    }

    @Override
    public List<MachinePlatformAccount> findByAccountIdActive(Integer accountId) {
        return list(new LambdaQueryWrapper<MachinePlatformAccount>()
                .eq(MachinePlatformAccount::getAccountId, accountId)
                .eq(MachinePlatformAccount::getIsActive, 1));
    }

    @Override
    public MachinePlatformAccount findByMachineIdAndAccountId(Integer machineId, Integer accountId) {
        return getOne(new LambdaQueryWrapper<MachinePlatformAccount>()
                .eq(MachinePlatformAccount::getMachineId, machineId)
                .eq(MachinePlatformAccount::getAccountId, accountId)
                .eq(MachinePlatformAccount::getIsActive, 1), false);
    }
}
