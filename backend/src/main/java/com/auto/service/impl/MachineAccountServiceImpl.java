package com.auto.service.impl;

import com.auto.entity.MachineAccount;
import com.auto.mapper.MachineAccountMapper;
import com.auto.service.MachineAccountService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class MachineAccountServiceImpl extends ServiceImpl<MachineAccountMapper, MachineAccount>
        implements MachineAccountService {

    @Override
    public List<MachineAccount> findByMachineIdActive(Integer machineId) {
        return list(new LambdaQueryWrapper<MachineAccount>()
                .eq(MachineAccount::getMachineId, machineId)
                .eq(MachineAccount::getIsActive, 1));
    }

    @Override
    public List<MachineAccount> findByAccountIdActive(Integer accountId) {
        return list(new LambdaQueryWrapper<MachineAccount>()
                .eq(MachineAccount::getAccountId, accountId)
                .eq(MachineAccount::getIsActive, 1));
    }

    @Override
    public MachineAccount findByMachineIdAndAccountId(Integer machineId, Integer accountId) {
        return getOne(new LambdaQueryWrapper<MachineAccount>()
                .eq(MachineAccount::getMachineId, machineId)
                .eq(MachineAccount::getAccountId, accountId)
                .eq(MachineAccount::getIsActive, 1), false);
    }
}
