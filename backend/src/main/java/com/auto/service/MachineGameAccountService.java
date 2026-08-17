package com.auto.service;

import com.auto.entity.MachineGameAccount;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface MachineGameAccountService extends IService<MachineGameAccount> {

    List<MachineGameAccount> findByMachineIdActiveOrderByPriorityDesc(Integer machineId);

    MachineGameAccount findByMachineIdAndGameAccountId(Integer machineId, Integer gameAccountId);

    List<MachineGameAccount> findByGameAccountIdsActive(List<Integer> gameAccountIds);
}
