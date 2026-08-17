package com.auto.service.impl;

import com.auto.entity.Machine;
import com.auto.mapper.MachineMapper;
import com.auto.service.MachineService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class MachineServiceImpl extends ServiceImpl<MachineMapper, Machine> implements MachineService {

    @Override
    public IPage<Machine> search(String keyword, String status, Page<Machine> page) {
        LambdaQueryWrapper<Machine> w = new LambdaQueryWrapper<>();
        w.eq(Machine::getIsActive, 1)
                .and(keyword != null, q -> q.like(Machine::getName, keyword)
                        .or().like(Machine::getMacAddress, keyword)
                        .or().like(Machine::getIpAddress, keyword))
                .eq(status != null, Machine::getStatus, status)
                .orderByDesc(Machine::getId);
        return page(page, w);
    }

    @Override
    public List<Machine> findAllActive() {
        return list(new LambdaQueryWrapper<Machine>().eq(Machine::getIsActive, 1));
    }

    @Override
    public Machine findByMacAddress(String macAddress) {
        return getOne(new LambdaQueryWrapper<Machine>()
                .eq(Machine::getMacAddress, macAddress), false);
    }

    @Override
    public Machine findByMkDeviceId(Integer mkDeviceId) {
        return getOne(new LambdaQueryWrapper<Machine>()
                .eq(Machine::getMkDeviceId, mkDeviceId)
                .eq(Machine::getIsActive, 1), false);
    }

    @Override
    public Machine findByVsDeviceId(Integer vsDeviceId) {
        return getOne(new LambdaQueryWrapper<Machine>()
                .eq(Machine::getVsDeviceId, vsDeviceId)
                .eq(Machine::getIsActive, 1), false);
    }
}
