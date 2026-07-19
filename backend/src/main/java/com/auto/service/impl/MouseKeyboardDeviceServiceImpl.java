package com.auto.service.impl;

import com.auto.entity.MouseKeyboardDevice;
import com.auto.mapper.MouseKeyboardDeviceMapper;
import com.auto.service.MouseKeyboardDeviceService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class MouseKeyboardDeviceServiceImpl
        extends ServiceImpl<MouseKeyboardDeviceMapper, MouseKeyboardDevice>
        implements MouseKeyboardDeviceService {

    @Override
    public IPage<MouseKeyboardDevice> search(String keyword, Page<MouseKeyboardDevice> page) {
        LambdaQueryWrapper<MouseKeyboardDevice> w = new LambdaQueryWrapper<>();
        w.eq(MouseKeyboardDevice::getIsActive, 1)
                .like(keyword != null, MouseKeyboardDevice::getName, keyword)
                .orderByDesc(MouseKeyboardDevice::getId);
        return page(page, w);
    }

    @Override
    public List<MouseKeyboardDevice> findAllActive() {
        return list(new LambdaQueryWrapper<MouseKeyboardDevice>()
                .eq(MouseKeyboardDevice::getIsActive, 1)
                .orderByAsc(MouseKeyboardDevice::getId));
    }
}
