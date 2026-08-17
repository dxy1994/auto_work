package com.auto.service;

import com.auto.entity.Machine;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface MachineService extends IService<Machine> {

    IPage<Machine> search(String keyword, String status, Page<Machine> page);

    List<Machine> findAllActive();

    Machine findByMacAddress(String macAddress);

    Machine findByMkDeviceId(Integer mkDeviceId);

    Machine findByVsDeviceId(Integer vsDeviceId);
}
