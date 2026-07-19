package com.auto.service;

import com.auto.entity.MouseKeyboardDevice;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface MouseKeyboardDeviceService extends IService<MouseKeyboardDevice> {

    IPage<MouseKeyboardDevice> search(String keyword, Page<MouseKeyboardDevice> page);

    List<MouseKeyboardDevice> findAllActive();
}
