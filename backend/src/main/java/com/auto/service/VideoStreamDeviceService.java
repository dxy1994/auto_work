package com.auto.service;

import com.auto.entity.VideoStreamDevice;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface VideoStreamDeviceService extends IService<VideoStreamDevice> {

    IPage<VideoStreamDevice> search(String keyword, Page<VideoStreamDevice> page);

    List<VideoStreamDevice> findAllActive();
}
