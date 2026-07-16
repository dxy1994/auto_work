package com.auto.service;

import com.auto.entity.MachineAccount;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface MachineAccountService extends IService<MachineAccount> {

    List<MachineAccount> findByMachineIdActive(Integer machineId);

    List<MachineAccount> findByAccountIdActive(Integer accountId);

    MachineAccount findByMachineIdAndAccountId(Integer machineId, Integer accountId);
}
