package com.auto.service.impl;

import com.auto.entity.MachineGame;
import com.auto.mapper.MachineGameMapper;
import com.auto.service.MachineGameService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class MachineGameServiceImpl extends ServiceImpl<MachineGameMapper, MachineGame>
        implements MachineGameService {

    @Override
    public List<MachineGame> findByMachineIdActiveOrderByPriorityDesc(Integer machineId) {
        return list(new LambdaQueryWrapper<MachineGame>()
                .eq(MachineGame::getMachineId, machineId)
                .eq(MachineGame::getIsActive, 1)
                .orderByDesc(MachineGame::getPriority));
    }

    @Override
    public List<MachineGame> findByGameIdActiveOrderByPriorityDesc(Integer gameId) {
        return list(new LambdaQueryWrapper<MachineGame>()
                .eq(MachineGame::getGameId, gameId)
                .eq(MachineGame::getIsActive, 1)
                .orderByDesc(MachineGame::getPriority)
                .orderByAsc(MachineGame::getMachineId));
    }

    @Override
    public MachineGame findByMachineIdAndGameId(Integer machineId, Integer gameId) {
        return getOne(new LambdaQueryWrapper<MachineGame>()
                .eq(MachineGame::getMachineId, machineId)
                .eq(MachineGame::getGameId, gameId), false);
    }
}
