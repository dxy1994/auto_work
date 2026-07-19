package com.auto.service;

import com.auto.entity.MachinePlatformAccount;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface MachinePlatformAccountService extends IService<MachinePlatformAccount> {

    List<MachinePlatformAccount> findByMachineIdActive(Integer machineId);

    List<MachinePlatformAccount> findByAccountIdActive(Integer accountId);

    MachinePlatformAccount findByMachineIdAndAccountId(Integer machineId, Integer accountId);
}
