package com.auto.service.impl;

import com.auto.entity.VideoStreamDevice;
import com.auto.mapper.VideoStreamDeviceMapper;
import com.auto.service.VideoStreamDeviceService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class VideoStreamDeviceServiceImpl
        extends ServiceImpl<VideoStreamDeviceMapper, VideoStreamDevice>
        implements VideoStreamDeviceService {

    @Override
    public IPage<VideoStreamDevice> search(String keyword, Page<VideoStreamDevice> page) {
        LambdaQueryWrapper<VideoStreamDevice> w = new LambdaQueryWrapper<>();
        w.eq(VideoStreamDevice::getIsActive, 1)
                .like(keyword != null, VideoStreamDevice::getName, keyword)
                .orderByDesc(VideoStreamDevice::getId);
        return page(page, w);
    }

    @Override
    public List<VideoStreamDevice> findAllActive() {
        return list(new LambdaQueryWrapper<VideoStreamDevice>()
                .eq(VideoStreamDevice::getIsActive, 1)
                .orderByAsc(VideoStreamDevice::getId));
    }
}
