package com.auto.service.impl;

import com.auto.entity.MachineGameAccount;
import com.auto.mapper.MachineGameAccountMapper;
import com.auto.service.MachineGameAccountService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class MachineGameAccountServiceImpl extends ServiceImpl<MachineGameAccountMapper, MachineGameAccount>
        implements MachineGameAccountService {

    @Override
    public List<MachineGameAccount> findByMachineIdActiveOrderByPriorityDesc(Integer machineId) {
        return list(new LambdaQueryWrapper<MachineGameAccount>()
                .eq(MachineGameAccount::getMachineId, machineId)
                .eq(MachineGameAccount::getIsActive, 1)
                .orderByDesc(MachineGameAccount::getPriority));
    }

    @Override
    public MachineGameAccount findByMachineIdAndGameAccountId(Integer machineId, Integer gameAccountId) {
        return getOne(new LambdaQueryWrapper<MachineGameAccount>()
                .eq(MachineGameAccount::getMachineId, machineId)
                .eq(MachineGameAccount::getGameAccountId, gameAccountId)
                .eq(MachineGameAccount::getIsActive, 1), false);
    }

    @Override
    public MachineGameAccount findByMachineIdAndGameAccountIdAndRegionId(Integer machineId, Integer gameAccountId, Integer regionId) {
        return getOne(new LambdaQueryWrapper<MachineGameAccount>()
                .eq(MachineGameAccount::getMachineId, machineId)
                .eq(MachineGameAccount::getGameAccountId, gameAccountId)
                .eq(regionId != null, MachineGameAccount::getRegionId, regionId)
                .eq(MachineGameAccount::getIsActive, 1), false);
    }

    @Override
    public MachineGameAccount findByGameAccountIdActive(Integer gameAccountId) {
        return getOne(new LambdaQueryWrapper<MachineGameAccount>()
                .eq(MachineGameAccount::getGameAccountId, gameAccountId)
                .eq(MachineGameAccount::getIsActive, 1), false);
    }

    @Override
    public List<MachineGameAccount> findByGameAccountIdsActive(List<Integer> gameAccountIds) {
        if (gameAccountIds == null || gameAccountIds.isEmpty()) return List.of();
        return list(new LambdaQueryWrapper<MachineGameAccount>()
                .in(MachineGameAccount::getGameAccountId, gameAccountIds)
                .eq(MachineGameAccount::getIsActive, 1)
                .orderByDesc(MachineGameAccount::getPriority));
    }

    @Override
    public List<MachineGameAccount> findByGameAccountIdsAndRegionIdActive(List<Integer> gameAccountIds, Integer regionId) {
        if (gameAccountIds == null || gameAccountIds.isEmpty()) return List.of();
        return list(new LambdaQueryWrapper<MachineGameAccount>()
                .in(MachineGameAccount::getGameAccountId, gameAccountIds)
                .eq(regionId != null, MachineGameAccount::getRegionId, regionId)
                .eq(MachineGameAccount::getIsActive, 1)
                .orderByDesc(MachineGameAccount::getPriority));
    }
}
