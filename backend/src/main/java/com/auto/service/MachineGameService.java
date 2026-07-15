package com.auto.service;

import com.auto.entity.MachineGame;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface MachineGameService extends IService<MachineGame> {

    List<MachineGame> findByMachineIdActiveOrderByPriorityDesc(Integer machineId);

    List<MachineGame> findByGameIdActiveOrderByPriorityDesc(Integer gameId);

    MachineGame findByMachineIdAndGameId(Integer machineId, Integer gameId);
}
