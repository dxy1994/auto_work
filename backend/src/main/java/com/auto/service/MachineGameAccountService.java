package com.auto.service;

import com.auto.entity.MachineGameAccount;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface MachineGameAccountService extends IService<MachineGameAccount> {

    List<MachineGameAccount> findByMachineIdActiveOrderByPriorityDesc(Integer machineId);

    MachineGameAccount findByMachineIdAndGameAccountId(Integer machineId, Integer gameAccountId);

    /** 按账号+大区查找机器关联（用于精准选机）。 */
    MachineGameAccount findByMachineIdAndGameAccountIdAndRegionId(Integer machineId, Integer gameAccountId, Integer regionId);

    MachineGameAccount findByGameAccountIdActive(Integer gameAccountId);

    List<MachineGameAccount> findByGameAccountIdsActive(List<Integer> gameAccountIds);

    /** 按账号ID+大区ID查找活跃机器关联列表。 */
    List<MachineGameAccount> findByGameAccountIdsAndRegionIdActive(List<Integer> gameAccountIds, Integer regionId);
}
